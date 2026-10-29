"""Kontrak integrasi: perubahan peserta dibaca ulang oleh semua peran dari DB."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, EventCommitteeAssignment
from apps.registrations.models import Attendance, Feedback, Payment, Registration, Ticket
from apps.registrations.services import RegistrationService
from config.views import _admin_event_rows, _admin_user_rows, _build_eo_dashboard_data


# Inheritance: TestCase menjaga perubahan skenario lintas peran terisolasi dari database aplikasi.
@override_settings(DEBUG=True)
class CrossRoleDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_simevent_initial", stdout=StringIO())
        User = get_user_model()
        cls.participant = User.objects.get(email="rizky.ananda@mail.com")
        cls.head = User.objects.get(email="budi@simevent.id")
        cls.admin = User.objects.get(email="admin@simevent.id")
        cls.committee = User.objects.get(email="siti.rahma@mail.com")
        cls.live = Event.objects.get(slug="demo-integrated-live")
        cls.upcoming = Event.objects.get(slug="demo-integrated-upcoming")
        cls.completed = Event.objects.get(slug="demo-integrated-completed")

    def page(self, user, name, **query):
        self.client.force_login(user)
        response = self.client.get(reverse(name), query)
        self.assertEqual(response.status_code, 200)
        return response

    def rows_for(self, user, event):
        if user == self.committee:
            return self.page(user, "panitia_biasa", event_id=event.pk).context["panitia_db_data"]["participants"]
        return [row for row in self.page(user, "eo_peserta").context["eo_peserta_data"]["participants"] if row["eventId"] == event.pk]

    def test_seed_links_named_participant_to_all_roles(self):
        registration = Registration.objects.get(participant=self.participant, event=self.live)
        for user in (self.head, self.committee):
            rows = self.rows_for(user, self.live)
            row = next(row for row in rows if row["email"] == self.participant.email)
            self.assertEqual(row["registrationId"], registration.pk)
            self.assertEqual(row["participantId"], self.participant.pk)
        users = self.page(self.admin, "admin_users").context["admin_backend_data"]["users"]
        row = next(row for row in users if row["id"] == self.participant.pk)
        self.assertEqual(row["daftar"], 3)
        self.assertContains(self.page(self.participant, "peserta_dashboard"), self.live.title)
        self.assertContains(self.page(self.participant, "peserta_achievement"), "Langkah Pertama")

    def test_scan_updates_same_attendance_and_role_counts(self):
        registration = Registration.objects.get(participant=self.participant, event=self.live)
        self.client.force_login(self.committee)
        for _ in range(2):
            response = self.client.post(reverse("registrations:scan", args=[self.live.pk]), {
                "token": str(registration.ticket.token),
            })
            self.assertEqual(response.status_code, 201 if _ == 0 else 200, response.content)
        self.assertEqual(Attendance.objects.filter(registration=registration).count(), 1)
        self.assertTrue(next(row for row in self.rows_for(self.committee, self.live) if row["registrationId"] == registration.pk)["present"])
        self.assertEqual(next(row for row in self.rows_for(self.head, self.live) if row["registrationId"] == registration.pk)["status"], "hadir")
        admin_event = next(row for row in _admin_event_rows() if row["id"] == self.live.pk)
        head_event = next(row for row in _build_eo_dashboard_data(self.head)["events"] if row["id"] == self.live.pk)
        self.assertEqual(admin_event["hadir"], 1)
        self.assertEqual(admin_event["hadir"], head_event["hadir"])

    def test_cancel_and_register_again_propagate_without_duplicates(self):
        reg = Registration.objects.get(participant=self.participant, event=self.upcoming)
        RegistrationService(self.participant).cancel(reg.pk)
        for user in (self.head, self.committee):
            self.assertNotIn(reg.pk, [r["registrationId"] for r in self.rows_for(user, self.upcoming)])
        self.assertEqual(next(r for r in _admin_user_rows() if r["id"] == self.participant.pk)["daftar"], 2)
        restored = RegistrationService(self.participant).register(self.upcoming.pk)
        self.assertEqual(restored.pk, reg.pk)
        for user in (self.head, self.committee):
            self.assertIn(reg.pk, [r["registrationId"] for r in self.rows_for(user, self.upcoming)])
        self.assertEqual(Ticket.objects.filter(registration=reg).count(), 1)

    def test_unassigned_committee_has_no_demo_or_other_event_participants(self):
        EventCommitteeAssignment.objects.filter(member=self.committee).delete()
        response = self.page(self.committee, "panitia_biasa")
        self.assertEqual(response.context["panitia_db_data"]["participants"], [])
        self.assertEqual(response.context["panitia_db_data"]["events"], [])
        for text in ("SIM-001", "localStorage.getItem", "localStorage.setItem", "Mode Demo", self.participant.email):
            self.assertNotContains(response, text)

    def test_pending_payment_and_inactive_ticket_excluded_consistently(self):
        reg = Registration.objects.get(participant=self.participant, event=self.upcoming)
        # A pending payment must not count even on a free event.
        Payment.objects.create(registration=reg, amount=100, status=Payment.Status.UNDER_REVIEW)
        for user in (self.head, self.committee):
            self.assertNotIn(reg.pk, [r["registrationId"] for r in self.rows_for(user, self.upcoming)])
        count = Registration.objects.ticketed().filter(event=self.upcoming).count()
        self.assertEqual(next(r for r in _admin_event_rows() if r["id"] == self.upcoming.pk)["terjual"], count)
        Payment.objects.filter(registration=reg).update(
            status=Payment.Status.APPROVED, reviewed_by=self.admin, reviewed_at=timezone.now(),
        )
        Ticket.objects.filter(registration=reg).update(is_active=False)
        self.assertFalse(Registration.objects.ticketed().filter(pk=reg.pk).exists())
        for user in (self.head, self.committee):
            self.assertNotIn(reg.pk, [r["registrationId"] for r in self.rows_for(user, self.upcoming)])

    def test_feedback_is_visible_in_organizer_statistics(self):
        reg = Registration.objects.get(participant=self.participant, event=self.completed)
        self.client.force_login(self.participant)
        response = self.client.post(reverse("registrations:feedback", args=[reg.pk]), {
            "overall_rating": 5, "material_rating": 4, "speaker_rating": 4, "organization_rating": 5,
            "comment": "Feedback lintas peran", "suggestion": "",
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Feedback.objects.filter(registration=reg).exists())
        self.client.force_login(self.head)
        response = self.client.get(reverse("registrations:event-statistics", args=[self.completed.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["feedback_count"], Feedback.objects.filter(registration__event=self.completed).count())

    def test_profile_edit_updates_participant_name_across_roles(self):
        self.participant.first_name = "Nama Terbaru <aman>"
        self.participant.save(update_fields=["first_name"])
        for user in (self.head, self.committee):
            row = next(r for r in self.rows_for(user, self.live) if r["email"] == self.participant.email)
            self.assertIn("Nama Terbaru <aman>", row.get("nama", row.get("name")))
        self.assertIn("Nama Terbaru <aman>", next(r for r in _admin_user_rows() if r["id"] == self.participant.pk)["nama"])

    def test_landing_and_runtime_pages_never_inject_demo_business_rows(self):
        response = self.client.get(reverse("landing"))
        for event in response.context["recommended_events"]:
            self.assertContains(response, event.title)
            self.assertContains(response, reverse("detail_event", args=[event.slug]))
        self.assertNotContains(response, "25k")
        for user, pages in ((self.admin, ("admin_dashboard", "admin_users")),
                            (self.head, ("eo_dashboard", "eo_peserta", "eo_event"))):
            for page in pages:
                response = self.page(user, page)
                self.assertNotContains(response, 'id="simevent-demo-seed"')
                self.assertNotContains(response, 'js/simevent_shared.js')
                self.assertContains(response, 'id="simevent-ui-config"')
