# Fungsi file: Pengujian tautan dokumentasi event: izin panitia, validasi host, dan akses peserta yang hadir.

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase
from django.urls import reverse

from apps.events.models import Event, EventStatus
from apps.events.workflow import EventWorkflow
from apps.registrations.models import Attendance, Registration

from .support import event_data, published_event, setup_users

DRIVE_URL = "https://drive.google.com/drive/folders/abc123"


class DocumentationWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()

    def event(self):
        return published_event(self.owner, self.admin)

    def test_owner_saves_and_clears_link_on_published_event(self):
        event = self.event()
        saved = EventWorkflow(self.owner).set_documentation(event.pk, url=f"  {DRIVE_URL}  ")
        self.assertEqual(saved.documentation_url, DRIVE_URL)
        self.assertEqual(saved.status, EventStatus.PUBLISHED)
        cleared = EventWorkflow(self.owner).set_documentation(event.pk, url="")
        self.assertEqual(cleared.documentation_url, "")

    def test_admin_can_save_link_for_any_event(self):
        event = self.event()
        saved = EventWorkflow(self.admin).set_documentation(event.pk, url=DRIVE_URL)
        self.assertEqual(saved.documentation_url, DRIVE_URL)

    def test_draft_event_cannot_receive_link(self):
        draft = EventWorkflow(self.owner).create(data=event_data())
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).set_documentation(draft.pk, url=DRIVE_URL)

    def test_only_google_https_links_are_accepted(self):
        event = self.event()
        for bad in (
            "http://drive.google.com/drive/folders/abc",
            "https://evil.example.com/drive.google.com",
            "https://drive.google.com.evil.example/folders/abc",
            "javascript:alert(1)",
            "bukan url",
        ):
            with self.subTest(url=bad), self.assertRaises(ValidationError):
                EventWorkflow(self.owner).set_documentation(event.pk, url=bad)
        event.refresh_from_db()
        self.assertEqual(event.documentation_url, "")

    def test_other_organizer_and_participant_cannot_change_link(self):
        event = self.event()
        with self.assertRaises(Http404):
            EventWorkflow(self.other).set_documentation(event.pk, url=DRIVE_URL)
        with self.assertRaises(PermissionDenied):
            EventWorkflow(self.participant).set_documentation(event.pk, url=DRIVE_URL)

    def test_manage_endpoint_returns_json_and_rejects_participants(self):
        event = self.event()
        url = reverse("events:documentation", args=[event.pk])
        self.client.force_login(self.owner)
        response = self.client.post(url, {"documentation_url": DRIVE_URL})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documentation_url"], DRIVE_URL)
        response = self.client.post(url, {"documentation_url": "https://example.com/x"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("documentation_url", response.json()["errors"])
        self.client.force_login(self.participant)
        self.assertEqual(self.client.post(url, {"documentation_url": DRIVE_URL}).status_code, 403)


class DocumentationAccessTests(TestCase):
    """Peserta hanya boleh membuka dokumentasi jika hadir dan event sudah COMPLETED."""

    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.participant.ktp_number = "1234567890123456"
        cls.participant.gender = "L"
        cls.participant.birth_place = "Samarinda"
        cls.participant.birth_date = "2000-01-01"
        cls.participant.address = "Jl. Contoh 1"
        cls.participant.phone_number = "081234567890"
        cls.participant.save()

    def completed_event(self, documentation_url=DRIVE_URL, status=EventStatus.COMPLETED):
        event = published_event(self.owner, self.admin)
        Event.objects.filter(pk=event.pk).update(
            status=status, documentation_url=documentation_url,
        )
        event.refresh_from_db()
        return event

    def attend(self, event, status=Attendance.Status.PRESENT):
        registration = Registration.objects.create(participant=self.participant, event=event)
        attendance = Attendance.objects.create(registration=registration, verified_by=self.owner)
        if status == Attendance.Status.VOIDED:
            from django.utils import timezone
            Attendance.objects.filter(pk=attendance.pk).update(
                status=status, voided_at=timezone.now(),
                voided_by=self.admin, void_reason="Salah scan",
            )
        return registration

    def gate(self, event):
        self.client.force_login(self.participant)
        return self.client.get(reverse("peserta_dokumentasi", args=[event.pk]))

    def test_attended_participant_is_redirected_to_drive(self):
        event = self.completed_event()
        self.attend(event)
        response = self.gate(event)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], DRIVE_URL)

    def test_registered_but_absent_participant_is_denied(self):
        event = self.completed_event()
        Registration.objects.create(participant=self.participant, event=event)
        self.assertEqual(self.gate(event).status_code, 404)

    def test_voided_attendance_is_denied(self):
        event = self.completed_event()
        self.attend(event, status=Attendance.Status.VOIDED)
        self.assertEqual(self.gate(event).status_code, 404)

    def test_unregistered_participant_is_denied(self):
        event = self.completed_event()
        self.assertEqual(self.gate(event).status_code, 404)

    def test_event_not_completed_or_without_link_is_denied(self):
        not_completed = self.completed_event(status=EventStatus.PUBLISHED)
        self.attend(not_completed)
        self.assertEqual(self.gate(not_completed).status_code, 404)
        no_link = self.completed_event(documentation_url="")
        self.attend(no_link)
        self.assertEqual(self.gate(no_link).status_code, 404)

    def test_link_changed_to_foreign_host_via_admin_is_not_followed(self):
        event = self.completed_event(documentation_url="https://evil.example.com/photos")
        self.attend(event)
        self.assertEqual(self.gate(event).status_code, 404)

    def test_anonymous_user_is_sent_to_login(self):
        event = self.completed_event()
        response = self.client.get(reverse("peserta_dokumentasi", args=[event.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login_page"), response["Location"])

    def test_event_list_exposes_gate_url_only_to_eligible_participant(self):
        event = self.completed_event()
        self.client.force_login(self.participant)
        gate_url = reverse("peserta_dokumentasi", args=[event.pk])
        page = self.client.get(reverse("peserta_daftar_event"))
        self.assertNotContains(page, gate_url)
        self.assertNotContains(page, DRIVE_URL)
        self.attend(event)
        page = self.client.get(reverse("peserta_daftar_event"))
        self.assertContains(page, gate_url)
        self.assertNotContains(page, DRIVE_URL)
