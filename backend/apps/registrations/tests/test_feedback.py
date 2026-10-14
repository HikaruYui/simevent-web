# Fungsi file: Pengujian app registrations: syarat feedback, satu kali kirim, validasi rating, dan hasil dalam scope event.

import json
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event, EventStatus
from apps.events.tests.support import published_event, setup_users
from apps.events.workflow import EventWorkflow
from apps.registrations.attendance import AttendanceService
from apps.registrations.feedback import FeedbackService
from apps.registrations.feedback_views import FeedbackResultsView
from apps.registrations.models import Attendance, Feedback, RATING_FIELDS, Registration
from apps.registrations.services import RegistrationService


def feedback_input(**overrides):
    return {**{field: 4 for field in RATING_FIELDS}, "comment": "Bermanfaat", **overrides}


def completed_registration(owner, admin, participant):
    event = published_event(owner, admin)
    registration = RegistrationService(participant).register(event.pk)
    now = timezone.now()
    Event.objects.filter(pk=event.pk).update(
        registration_open=now - timedelta(days=2),
        registration_close=now - timedelta(hours=3),
        start_datetime=now - timedelta(hours=2),
        end_datetime=now - timedelta(hours=1),
    )
    event.refresh_from_db()
    with patch("apps.registrations.attendance.timezone.now", return_value=event.start_datetime):
        AttendanceService(owner).scan(event.pk, token=registration.ticket.token)
    EventWorkflow(owner).transition(event.pk, action="complete")
    event.refresh_from_db()
    return event, registration


class FeedbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.event, cls.registration = completed_registration(
            cls.owner, cls.admin, cls.participant,
        )

    def submit(self, **overrides):
        return FeedbackService(self.participant).submit(
            self.registration.pk, data=feedback_input(**overrides),
        )

    def test_valid_attended_participant_can_submit(self):
        feedback = self.submit()
        self.assertEqual(feedback.registration_id, self.registration.pk)
        self.assertEqual(feedback.overall_rating, 4)
        self.assertEqual(Feedback.objects.eligible().count(), 1)

    def test_registration_without_attendance_cannot_submit(self):
        registration = Registration.objects.create(participant=self.other, event=self.event)
        with self.assertRaises(ValidationError):
            FeedbackService(self.other).submit(registration.pk, data=feedback_input())

    def test_voided_attendance_cannot_submit(self):
        AttendanceService(self.admin).void(self.registration.attendance.pk, reason="Wrong check-in")
        with self.assertRaises(ValidationError):
            self.submit()

    def test_uncompleted_or_cancelled_event_cannot_receive_feedback(self):
        for status in EventStatus.values:
            if status == EventStatus.COMPLETED:
                continue
            Event.objects.filter(pk=self.event.pk).update(status=status)
            with self.subTest(status=status), self.assertRaises(ValidationError):
                self.submit()
        self.assertFalse(Feedback.objects.exists())

    def test_cancelled_registration_cannot_submit(self):
        Registration.objects.filter(pk=self.registration.pk).update(
            status="CANCELLED", cancelled_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            self.submit()

    def test_other_participant_or_admin_cannot_submit_for_someone_else(self):
        for actor in (self.other, self.admin):
            with self.subTest(actor=actor), self.assertRaises(Http404):
                FeedbackService(actor).submit(self.registration.pk, data=feedback_input())

    def test_suspended_actor_is_rechecked(self):
        service = FeedbackService(self.participant)
        User.objects.filter(pk=self.participant.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            service.submit(self.registration.pk, data=feedback_input())

    def test_second_submission_does_not_edit_original(self):
        feedback = self.submit()
        with self.assertRaises(ValidationError):
            self.submit(overall_rating=1, comment="Replacement")
        feedback.refresh_from_db()
        self.assertEqual(feedback.overall_rating, 4)
        self.assertEqual(feedback.comment, "Bermanfaat")
        self.assertEqual(Feedback.objects.count(), 1)

    def test_rating_form_validates_every_dimension_and_integer(self):
        for field in RATING_FIELDS:
            for value in (0, 6, "invalid", "2.5", ""):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    self.submit(**{field: value})
        self.assertFalse(Feedback.objects.exists())
        self.assertEqual(self.submit(overall_rating=1, material_rating=5).material_rating, 5)

    def test_text_limits_and_optional_comments(self):
        for field in ("comment", "suggestion"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.submit(**{field: "x" * 2001})
        feedback = self.submit(comment="", suggestion="")
        self.assertEqual(feedback.comment, "")

    def test_database_constraints_prevent_duplicates_and_out_of_range_ratings(self):
        feedback = self.submit()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Feedback.objects.create(registration=self.registration, **feedback_input())
        for field in RATING_FIELDS:
            for value in (0, 6):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        Feedback.objects.filter(pk=feedback.pk).update(**{field: value})

    def test_http_auth_csrf_and_immutable_methods(self):
        url = reverse("registrations:feedback", args=[self.registration.pk])
        self.assertEqual(self.client.post(url, feedback_input()).status_code, 401)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.participant)
        self.assertEqual(csrf.post(url, feedback_input()).status_code, 403)
        self.client.force_login(self.participant)
        self.assertEqual(self.client.post(url, feedback_input()).status_code, 201)
        self.assertEqual(self.client.post(url, feedback_input()).status_code, 400)
        for method in ("put", "patch", "delete"):
            self.assertEqual(getattr(self.client, method)(url).status_code, 405)

    def test_mass_assignment_cannot_change_registration_or_created_time(self):
        self.client.force_login(self.participant)
        response = self.client.post(reverse("registrations:feedback", args=[self.registration.pk]), {
            **feedback_input(), "registration": 999, "participant": self.other.pk,
            "event": 999, "created_at": "2000-01-01", "id": 999,
        })
        self.assertEqual(response.status_code, 201)
        feedback = Feedback.objects.get()
        self.assertEqual(feedback.registration_id, self.registration.pk)
        self.assertNotEqual(feedback.created_at.year, 2000)

    def test_read_is_owner_scoped_and_not_cached(self):
        self.submit()
        url = reverse("registrations:feedback", args=[self.registration.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.participant)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_results_require_owner_or_admin_and_feedback_permission(self):
        self.submit()
        url = reverse("registrations:feedback-results", args=[self.event.pk])
        for user, status in ((self.participant, 403), (self.other, 404), (self.owner, 200), (self.admin, 200)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, status)
        self.owner.groups.clear()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_results_summary_and_no_identity_or_ticket_leaks(self):
        self.submit(overall_rating=2)
        registration = Registration.objects.create(participant=self.other, event=self.event)
        Attendance.objects.create(registration=registration, verified_by=self.owner)
        FeedbackService(self.other).submit(registration.pk, data=feedback_input(overall_rating=4))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("registrations:feedback-results", args=[self.event.pk]))
        data = response.json()
        self.assertEqual(data["summary"]["feedback_count"], 2)
        self.assertEqual(data["summary"]["average_overall_rating"], 3)
        self.assertNotContains(response, self.participant.email)
        self.assertNotContains(response, str(self.registration.ticket.token))
        for result in data["results"]:
            self.assertNotIn("registration_id", result)
        self.assertIn("no-store", response["Cache-Control"])

    def test_void_after_submission_excludes_results_but_retains_history(self):
        feedback = self.submit()
        AttendanceService(self.admin).void(self.registration.attendance.pk, reason="Invalid attendance")
        self.assertTrue(Feedback.objects.filter(pk=feedback.pk).exists())
        self.assertFalse(Feedback.objects.eligible().exists())
        self.client.force_login(self.owner)
        data = self.client.get(reverse("registrations:feedback-results", args=[self.event.pk])).json()
        self.assertEqual(data["results"], [])
        self.assertEqual(data["summary"]["feedback_count"], 0)
        self.assertIsNone(data["summary"]["average_overall_rating"])
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get(
            reverse("registrations:feedback", args=[self.registration.pk]),
        ).status_code, 200)

    def test_summary_is_for_whole_event_not_only_requested_page(self):
        for index in range(21):
            user = User.objects.create_user(f"feedback{index}@example.test", None)
            registration = Registration.objects.create(participant=user, event=self.event)
            Attendance.objects.create(registration=registration, verified_by=self.owner)
            Feedback.objects.create(registration=registration, **feedback_input(overall_rating=5))
        self.owner.get_all_permissions()
        request = RequestFactory().get("/", {"page": 2})
        request.user = self.owner
        with self.assertNumQueries(4):
            response = FeedbackResultsView.as_view()(request, event_id=self.event.pk)
        data = json.loads(response.content)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["summary"]["feedback_count"], 21)
        self.assertEqual(data["summary"]["average_overall_rating"], 5)

    def test_admin_is_readonly_and_escapes_untrusted_comment(self):
        feedback = self.submit(comment="<script>alert(1)</script>")
        self.client.force_login(self.admin)
        url = reverse("admin:registrations_feedback_change", args=[feedback.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertEqual(self.client.post(url, {"overall_rating": 1}).status_code, 403)
        self.assertEqual(self.client.post(reverse(
            "admin:registrations_feedback_delete", args=[feedback.pk],
        )).status_code, 403)
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(
            reverse("admin:registrations_feedback_changelist"),
        ).status_code, 403)
