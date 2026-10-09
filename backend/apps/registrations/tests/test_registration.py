# Fungsi file: Pengujian app registrations: registrasi, kuota, pembatalan, tiket, dan ownership peserta.

from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, EventStatus
from apps.events.tests.support import event_data, published_event, setup_users
from apps.events.workflow import EventWorkflow
from apps.registrations.models import Registration, RegistrationStatus, Ticket
from apps.registrations.services import RegistrationService
from apps.registrations.views import RegistrationListView


class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.event = published_event(cls.owner, cls.admin, capacity=1)

    def register(self, user=None):
        return RegistrationService(user or self.participant).register(self.event.pk)

    def test_registration_issues_valid_unique_ticket(self):
        registration = self.register()
        self.assertEqual(registration.participant, self.participant)
        self.assertTrue(registration.ticket.is_valid)
        self.assertNotEqual(registration.ticket.token, registration.ticket.identifier)
        self.assertEqual(Registration.objects.count(), 1)

    def test_duplicate_and_full_event_are_rejected(self):
        self.register()
        for user in (self.participant, self.other):
            with self.subTest(user=user), self.assertRaises(ValidationError):
                self.register(user)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_cancellation_frees_capacity_and_reactivation_rotates_token(self):
        registration = self.register()
        ticket = registration.ticket
        RegistrationService(self.participant).cancel(registration.pk)
        ticket.refresh_from_db()
        self.assertFalse(ticket.is_valid)
        other_registration = self.register(self.other)
        with self.assertRaises(ValidationError):
            self.register()
        RegistrationService(self.other).cancel(other_registration.pk)
        restored = self.register()
        self.assertEqual(restored.pk, registration.pk)
        self.assertEqual(restored.ticket.identifier, ticket.identifier)
        self.assertNotEqual(restored.ticket.token, ticket.token)
        self.assertTrue(restored.ticket.is_valid)
        self.assertIsNone(restored.cancelled_at)

    def test_cancel_is_idempotent_and_only_owner_can_cancel(self):
        registration = self.register()
        with self.assertRaises(Http404):
            RegistrationService(self.other).cancel(registration.pk)
        first = RegistrationService(self.participant).cancel(registration.pk)
        second = RegistrationService(self.participant).cancel(registration.pk)
        self.assertEqual(first.cancelled_at, second.cancelled_at)

    def test_nonpublic_and_completed_events_cannot_be_registered(self):
        for status in EventStatus.values:
            if status == EventStatus.PUBLISHED:
                continue
            Event.objects.filter(pk=self.event.pk).update(status=status)
            with self.subTest(status=status), self.assertRaises((Http404, ValidationError)):
                self.register()

    def test_registration_window_boundaries(self):
        opening = self.event.registration_open
        closing = self.event.registration_close
        for now in (opening - timedelta(seconds=1), closing):
            with self.subTest(now=now), patch(
                "apps.registrations.services.timezone.now", return_value=now
            ), self.assertRaises(ValidationError):
                self.register()
        with patch("apps.registrations.services.timezone.now", return_value=opening):
            self.assertIsNotNone(self.register().pk)

    def test_paid_event_rejected_even_if_published_by_trusted_operator(self):
        Event.objects.filter(pk=self.event.pk).update(price=10)
        with self.assertRaises(ValidationError):
            self.register()

    def test_cancel_at_start_rejected_but_cancelled_event_can_be_cleaned_up(self):
        registration = self.register()
        with patch("apps.registrations.services.timezone.now", return_value=self.event.start_datetime):
            with self.assertRaises(ValidationError):
                RegistrationService(self.participant).cancel(registration.pk)
            Event.objects.filter(pk=self.event.pk).update(status=EventStatus.CANCELLED)
            cancelled = RegistrationService(self.participant).cancel(registration.pk)
            self.assertEqual(cancelled.status, RegistrationStatus.CANCELLED)

    def test_stale_actor_cannot_bypass_suspension(self):
        service = RegistrationService(self.participant)
        type(self.participant).objects.filter(pk=self.participant.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            service.register(self.event.pk)

    def test_ticket_failure_rolls_back_registration(self):
        with patch("apps.registrations.services.Ticket.objects.create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.register()
        self.assertFalse(Registration.objects.exists())

    def test_ticket_failure_rolls_back_reactivation(self):
        registration = self.register()
        RegistrationService(self.participant).cancel(registration.pk)
        with patch("apps.registrations.services.Ticket.objects.update_or_create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.register()
        registration.refresh_from_db()
        self.assertEqual(registration.status, RegistrationStatus.CANCELLED)
        self.assertFalse(registration.ticket.is_active)

    def test_ticket_failure_rolls_back_cancellation(self):
        registration = self.register()
        with patch("django.db.models.query.QuerySet.update", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                RegistrationService(self.participant).cancel(registration.pk)
        registration.refresh_from_db()
        self.assertEqual(registration.status, RegistrationStatus.REGISTERED)
        self.assertTrue(registration.ticket.is_active)

    def test_database_rejects_duplicate_registration_ticket_and_token(self):
        registration = self.register()
        original_token = registration.ticket.token
        operations = [
            lambda: Registration.objects.create(participant=self.participant, event=self.event),
            lambda: Ticket.objects.create(registration=registration),
            lambda: Registration.objects.filter(pk=registration.pk).update(status="BOGUS"),
            lambda: Registration.objects.filter(pk=registration.pk).update(status="CANCELLED"),
            lambda: Registration.objects.filter(pk=registration.pk).update(
                status="CANCELLED", cancelled_at=registration.registered_at - timedelta(seconds=1)
            ),
        ]
        for operation in operations:
            with self.assertRaises(IntegrityError), transaction.atomic():
                operation()
        other = Registration.objects.create(participant=self.other, event=self.event)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ticket.objects.create(registration=other, token=original_token)

    def test_event_state_and_expiry_control_ticket_validity(self):
        registration = self.register()
        for status in (EventStatus.APPROVED, EventStatus.CANCELLED, EventStatus.COMPLETED):
            Event.objects.filter(pk=self.event.pk).update(status=status)
            ticket = Ticket.objects.get(registration=registration)
            self.assertFalse(ticket.is_valid)
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.PUBLISHED)
        with patch("apps.registrations.models.timezone.now", return_value=self.event.end_datetime):
            self.assertFalse(Ticket.objects.get(registration=registration).is_valid)

    def test_capacity_cannot_shrink_below_existing_registrations(self):
        Event.objects.filter(pk=self.event.pk).update(capacity=2)
        self.register()
        self.register(self.other)
        workflow = EventWorkflow(self.admin)
        workflow.transition(self.event.pk, action="unpublish")
        workflow.transition(self.event.pk, action="request_revision", reason="Capacity review")
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).update(self.event.pk, data=event_data(capacity=1))
        self.event.refresh_from_db()
        self.assertEqual(self.event.capacity, 2)

    def test_confirm_and_csrf_required_and_privileged_fields_ignored(self):
        self.client.force_login(self.participant)
        url = reverse("registrations:create", args=[self.event.pk])
        self.assertEqual(self.client.post(url).status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.participant)
        self.assertEqual(csrf_client.post(url, {"confirm": "on"}).status_code, 403)
        response = self.client.post(url, {
            "confirm": "on", "participant": self.other.pk, "status": "CANCELLED",
            "event": 99999, "token": "forged",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Registration.objects.get().participant, self.participant)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_ticket_and_my_events_are_private_and_not_cacheable(self):
        registration = self.register()
        self.client.force_login(self.other)
        url = reverse("registrations:ticket", args=[registration.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("registrations:list")).json()["results"], [])
        self.client.force_login(self.participant)
        response = self.client.get(url)
        self.assertEqual(response.json()["token"], str(registration.ticket.token))
        self.assertIn("no-store", response["Cache-Control"])
        RegistrationService(self.participant).cancel(registration.pk)
        self.assertIsNone(self.client.get(url).json()["token"])

    def test_cancel_http_scope_confirmation_and_authentication(self):
        registration = self.register()
        url = reverse("registrations:cancel", args=[registration.pk])
        self.assertEqual(self.client.post(url, {"confirm": "on"}).status_code, 401)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"confirm": "on"}).status_code, 404)
        self.client.force_login(self.participant)
        self.assertEqual(self.client.post(url).status_code, 400)
        self.assertEqual(self.client.post(url, {"confirm": "on"}).status_code, 200)

    def test_participant_list_is_scoped_and_never_exposes_tokens(self):
        registration = self.register()
        url = reverse("registrations:participants", args=[self.event.pk])
        for user, expected in ((self.other, 404), (self.participant, 403), (self.owner, 200), (self.admin, 200)):
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, expected)
            self.assertNotContains(response, str(registration.ticket.token), status_code=expected)

    def test_admin_records_are_readonly_and_token_is_not_rendered(self):
        registration = self.register()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:registrations_ticket_change", args=[registration.ticket.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, str(registration.ticket.token))
        for operation in ("change", "delete"):
            response = self.client.post(reverse(
                f"admin:registrations_registration_{operation}", args=[registration.pk]
            ), {"status": "CANCELLED"})
            self.assertEqual(response.status_code, 403)

    def test_my_events_list_has_no_event_n_plus_one_queries(self):
        self.register()
        request = RequestFactory().get("/registrations/")
        request.user = self.participant
        with self.assertNumQueries(2):
            response = RegistrationListView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_suspended_participant_ticket_is_invalid(self):
        registration = self.register()
        type(self.participant).objects.filter(pk=self.participant.pk).update(is_active=False)
        self.assertFalse(Ticket.objects.get(registration=registration).is_valid)

    def test_cancel_requires_csrf_and_get_cannot_mutate(self):
        registration = self.register()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.participant)
        url = reverse("registrations:cancel", args=[registration.pk])
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url, {"confirm": "on"}).status_code, 403)
        registration.refresh_from_db()
        self.assertEqual(registration.status, RegistrationStatus.REGISTERED)

    def test_list_paginates_without_leaking_ticket_or_meeting_data(self):
        for index in range(21):
            event = EventWorkflow(self.owner).create(data=event_data(title=f"Event {index}"))
            Registration.objects.create(participant=self.participant, event=event)
        self.client.force_login(self.participant)
        url = reverse("registrations:list")
        first = self.client.get(url).json()
        second = self.client.get(url, {"page": 2}).json()
        self.assertEqual(len(first["results"]), 20)
        self.assertEqual(len(second["results"]), 1)
        self.assertEqual(first["pages"], 2)
        for record in first["results"]:
            self.assertNotIn("token", record)
            self.assertNotIn("meeting_url", record)
