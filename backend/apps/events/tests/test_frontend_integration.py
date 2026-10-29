from io import StringIO
import re

from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import (
    ContactMessage, Event, EventAccess, EventCommitteeAssignment, EventStatus,
    OrganizerSupportTicket, PlatformAuditLog, PlatformSettings,
)
from apps.events.workflow import EventWorkflow
from apps.registrations.models import Attendance, Payment, Registration, Ticket, UploadedCertificate
from .support import event_data


@override_settings(DEBUG=True)
class FrontendIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_simevent_initial", stdout=StringIO())
        cls.admin = User.objects.get(email="admin@simevent.id")
        cls.owner = User.objects.get(email="budi@simevent.id")
        cls.committee = User.objects.get(email="siti.rahma@mail.com")
        cls.participant = User.objects.get(email="rizky.ananda@mail.com")
        cls.live = Event.objects.get(slug="demo-integrated-live")
        cls.upcoming = Event.objects.get(slug="demo-integrated-upcoming")

    def test_contact_reaches_admin_and_reply_returns_only_to_sending_session(self):
        response = self.client.post(reverse("bantuan"), {
            "nama": "Pengunjung", "email": "visitor@example.com", "pesan": "Perlu bantuan tiket.",
        })
        self.assertEqual(response.status_code, 201)
        code = response.json()["code"]
        admin_client = Client()
        admin_client.force_login(self.admin)
        self.assertContains(admin_client.get(reverse("admin_support")), code)
        response = admin_client.post(reverse("admin_support_mutation", args=[code]), {
            "action": "resolve", "reply": "Silakan periksa Event Saya.",
        })
        self.assertEqual(response.status_code, 200)
        contact = ContactMessage.objects.get()
        self.assertEqual(contact.status, OrganizerSupportTicket.Status.RESOLVED)
        self.assertContains(self.client.get(reverse("bantuan")), "Silakan periksa Event Saya.")
        self.assertNotContains(Client().get(reverse("bantuan")), "Silakan periksa Event Saya.")

    def test_contact_validation_csrf_and_test_only_removal(self):
        self.assertEqual(self.client.post(reverse("bantuan"), {
            "nama": "A", "email": "invalid", "pesan": "",
        }).status_code, 400)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse("bantuan"), {}).status_code, 403)
        message = ContactMessage.objects.create(name="Test", email="test@example.com", message="Testing")
        url = reverse("admin_support_mutation", args=[f"CONTACT-{message.pk}"])
        self.client.force_login(self.participant)
        self.assertEqual(self.client.post(url, {"action": "delete"}).status_code, 403)
        self.client.force_login(self.admin)
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.post(url, {"action": "delete"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"action": "delete"}).status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())

    def test_payment_queue_review_activates_ticket_and_reject_allows_retry(self):
        reg = Registration.objects.get(event=self.upcoming, participant=self.participant)
        Ticket.objects.filter(registration=reg).delete()
        payment = Payment.objects.create(registration=reg, amount=50000,
            status=Payment.Status.UNDER_REVIEW, submitted_at=timezone.now(), proof="proof.pdf")
        self.client.force_login(self.admin)
        page = self.client.get(reverse("admin_finance"))
        self.assertContains(page, reverse("registrations:payment-review", args=[payment.pk]))
        url = reverse("registrations:payment-review", args=[payment.pk])
        self.assertEqual(self.client.post(url, {"action": "reject"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"action": "reject", "note": "Bukti tidak jelas"}).status_code, 200)
        self.assertFalse(Ticket.objects.filter(registration=reg).exists())
        payment.refresh_from_db()
        payment.status = Payment.Status.UNDER_REVIEW
        payment.save(update_fields=["status"])
        self.assertEqual(self.client.post(url, {"action": "approve"}).status_code, 200)
        self.assertTrue(Ticket.objects.get(registration=reg).is_active)
        self.assertEqual(self.client.post(url, {"action": "approve"}).status_code, 400)
        self.assertNotContains(self.client.get(reverse("admin_finance")), url)

    def test_assigned_committee_can_void_with_audit_but_other_roles_cannot(self):
        reg = Registration.objects.get(event=self.live, participant=self.participant)
        attendance = Attendance.objects.create(registration=reg, verified_by=self.committee)
        url = reverse("registrations:attendance-void", args=[reg.pk])
        self.client.force_login(self.participant)
        self.assertEqual(self.client.post(url, {"reason": "Salah scan"}).status_code, 403)
        self.client.force_login(self.committee)
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        assignment = EventCommitteeAssignment.objects.get(event=self.live, member=self.committee)
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(url, {"reason": "Salah scan"}).status_code, 404)
        assignment.is_active = True
        assignment.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(url, {"reason": "Salah scan"}).status_code, 200)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, Attendance.Status.VOIDED)
        self.assertEqual(attendance.voided_by, self.committee)
        self.assertTrue(PlatformAuditLog.objects.filter(actor=self.committee, description__contains="Salah scan").exists())
        page = self.client.get(reverse("panitia_biasa"), {"event_id": self.live.pk})
        row = next(item for item in page.context["panitia_db_data"]["participants"] if item["registrationId"] == reg.pk)
        self.assertTrue(row["voided"])
        self.assertFalse(row["present"])
        UploadedCertificate.objects.create(registration=reg, file="certificate.pdf", uploaded_by=self.committee)
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get(reverse("peserta_sertifikat_unggahan", args=[reg.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("peserta_sertifikat")), reverse("peserta_sertifikat_unggahan", args=[reg.pk]))

    def test_event_approval_setting_and_paid_submission(self):
        setting = PlatformSettings.objects.get(pk=1)
        setting.event_approval_required = False
        setting.save(update_fields=["event_approval_required"])
        workflow = EventWorkflow(self.owner)
        event = workflow.create(data=event_data(price="50000.00"))
        event = workflow.transition(event.pk, action="submit")
        self.assertEqual(event.status, EventStatus.APPROVED)
        self.assertFalse(Event.objects.public().filter(pk=event.pk).exists())
        with self.assertRaises(PermissionDenied):
            workflow.transition(event.pk, action="publish")
        EventWorkflow(self.admin).transition(event.pk, action="publish")
        setting.event_approval_required = True
        setting.save(update_fields=["event_approval_required"])
        event = workflow.create(data=event_data())
        event = workflow.transition(event.pk, action="submit")
        self.assertEqual(event.status, EventStatus.SUBMITTED)
        with self.assertRaises(PermissionDenied):
            workflow.transition(event.pk, action="approve")

    def test_my_events_connects_cancel_and_private_meeting(self):
        reg = Registration.objects.get(event=self.upcoming, participant=self.participant)
        self.upcoming.delivery_mode = "ONLINE"
        self.upcoming.save(update_fields=["delivery_mode"])
        EventAccess.objects.update_or_create(event=self.upcoming, defaults={"meeting_url": "https://example.com/private-meeting"})
        self.client.force_login(self.participant)
        page = self.client.get(reverse("peserta_event_saya"))
        self.assertContains(page, reverse("registrations:cancel", args=[reg.pk]))
        self.assertContains(page, reverse("registrations:meeting", args=[reg.pk]))
        self.assertNotContains(page, "https://example.com/private-meeting")
        self.assertEqual(self.client.get(reverse("registrations:meeting", args=[reg.pk])).json()["meeting_url"], "https://example.com/private-meeting")
        self.assertEqual(self.client.post(reverse("registrations:cancel", args=[reg.pk]), {"confirm": "on"}).status_code, 200)
        self.assertFalse(Ticket.objects.get(registration=reg).is_active)
        self.assertNotContains(self.client.get(reverse("peserta_event_saya")), reverse("registrations:cancel", args=[reg.pk]))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_link_changes_password_and_is_single_use(self):
        self.participant.set_password("Old-test-password-123!")
        self.participant.save(update_fields=["password"])
        self.assertContains(self.client.get(reverse("login_page")), reverse("password_reset"))
        self.assertContains(self.client.get(reverse("password_reset")), "Kirim Tautan Reset")
        response = self.client.post(reverse("password_reset"), {"email": self.participant.email})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        url = re.search(r"https?://[^\s]+", mail.outbox[0].body).group(0)
        confirm = self.client.get(url, follow=True)
        self.assertTrue(confirm.context["validlink"])
        response = self.client.post(confirm.request["PATH_INFO"], {
            "new_password1": "New-test-password-987!", "new_password2": "New-test-password-987!",
        })
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.check_password("New-test-password-987!"))
        self.assertFalse(Client().get(url, follow=True).context["validlink"])
        self.assertRedirects(self.client.post(reverse("password_reset"), {"email": "unknown@example.com"}), reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
