from datetime import timedelta
from smtplib import SMTPRecipientsRefused
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core import mail
from django.core.mail import EmailMessage
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import EventCommitteeAssignment, OrganizerInvitation
from apps.events.workflow import EventWorkflow

from .support import event_data, setup_users


# OOP — Single inheritance: InvitationEmailTests mewarisi TestCase dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: TestCase juga menjadi induk class saudara lain di proyek.
# OOP — Decorator Python (override_settings): mengganti settings selama konteks pengujian lalu memulihkannya; tidak menambah pewarisan class.
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="SIMEVENT <no-reply@example.com>",
)
class InvitationEmailTests(TestCase):
    # OOP — Method overriding: framework pengujian memanggil hook setUpTestData milik subclass untuk menyiapkan/membersihkan fixture.
    # OOP — Class method: menerima cls sehingga operasi terikat pada class dan tetap mengikuti subclass.
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        head_permission = Permission.objects.get(
            content_type__app_label="accounts", codename="access_head_organizer",
        )
        for user in (cls.owner, cls.other):
            user.user_permissions.add(head_permission)
        cls.event = EventWorkflow(cls.owner).create(data=event_data(title="Seminar tim"))
        cls.foreign_event = EventWorkflow(cls.other).create(data=event_data(title="Event lain"))

    # OOP — Method overriding: framework pengujian memanggil hook setUp milik subclass untuk menyiapkan/membersihkan fixture.
    def setUp(self):
        self.client.force_login(self.owner)

    # OOP — Encapsulation: method invite mengelompokkan operasi terkait objek InvitationEmailTests.
    def invite(self, emails=None, **overrides):
        return self.client.post(reverse("eo_settings_invite"), {
            "emails": emails or ["new-member@example.com"],
            "access_all": True,
            **overrides,
        }, content_type="application/json")

    # OOP — Encapsulation: method invitation_action mengelompokkan operasi terkait objek InvitationEmailTests.
    def invitation_action(self, invitation, action):
        return self.client.post(
            reverse("eo_settings_invitation_action", args=[invitation.pk]),
            {"action": action},
        )

    def test_create_sends_private_email_with_real_link_scope_and_message(self):
        emails = ["first@example.com", "second@example.com"]
        response = self.invite(
            emails, access_all=False, event_ids=[self.event.pk],
            message="Bantu check-in & dokumentasi, ya.",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery"], {"sent": emails, "failed": []})
        self.assertEqual(len(mail.outbox), 2)
        for message, email in zip(mail.outbox, emails):
            invitation = OrganizerInvitation.objects.get(email=email)
            self.assertEqual(message.to, [email])
            self.assertEqual(message.from_email, "SIMEVENT <no-reply@example.com>")
            self.assertIn(self.event.title, message.body)
            self.assertNotIn(self.foreign_event.title, message.body)
            self.assertIn("Bantu check-in & dokumentasi, ya.", message.body)
            url = reverse("eo_invitation_accept", args=[invitation.token])
            self.assertIn("http://testserver" + url, message.body)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertIsNotNone(invitation.email_sent_at)
        self.assertTrue(all(row["email_sent"] for row in response.json()["settings"]["invitations"]))

    def test_smtp_connection_failure_keeps_invitations_for_retry(self):
        emails = ["first@example.com", "second@example.com"]
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with patch("apps.events.invitations.get_connection") as connection:
            connection.return_value.__enter__.side_effect = OSError("Unavailable")
            response = self.invite(emails)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery"], {"sent": [], "failed": emails})
        self.assertEqual(OrganizerInvitation.objects.count(), 2)
        self.assertFalse(OrganizerInvitation.objects.exclude(email_sent_at=None).exists())
        self.assertFalse(any(row["email_sent"] for row in response.json()["settings"]["invitations"]))
        self.assertEqual(len(mail.outbox), 0)

    def test_one_rejected_recipient_does_not_block_the_next_email(self):
        real_send = EmailMessage.send

        def deliver(message, **kwargs):
            if message.to == ["rejected@example.com"]:
                raise SMTPRecipientsRefused({"rejected@example.com": (550, b"Rejected")})
            return real_send(message, **kwargs)

        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with patch("apps.events.invitations.EmailMessage.send", autospec=True, side_effect=deliver):
            response = self.invite(["rejected@example.com", "accepted@example.com"])
        self.assertEqual(response.json()["delivery"], {
            "sent": ["accepted@example.com"], "failed": ["rejected@example.com"],
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIsNone(OrganizerInvitation.objects.get(email="rejected@example.com").email_sent_at)
        self.assertIsNotNone(OrganizerInvitation.objects.get(email="accepted@example.com").email_sent_at)

    def test_resend_retries_failed_email_and_renews_expired_invitation(self):
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with patch("apps.events.invitations.EmailMessage.send", return_value=0):
            self.invite()
        invitation = OrganizerInvitation.objects.get()
        self.assertIsNone(invitation.email_sent_at)
        token = invitation.token
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save(update_fields=("expires_at",))
        url = reverse("eo_invitation_accept", args=[token])
        self.assertEqual(self.client.get(url).status_code, 410)
        response = self.invitation_action(invitation, "resend")
        invitation.refresh_from_db()
        self.assertEqual(response.json()["delivery"]["sent"], [invitation.email])
        self.assertEqual(invitation.token, token)
        self.assertEqual(invitation.expires_at - invitation.sent_at, timedelta(days=7))
        self.assertIsNotNone(invitation.email_sent_at)
        self.assertIn("Akses: semua event", mail.outbox[0].body)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_failed_resend_preserves_last_successful_delivery_timestamp(self):
        self.invite()
        invitation = OrganizerInvitation.objects.get()
        last_sent = invitation.email_sent_at
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with patch("apps.events.invitations.EmailMessage.send", side_effect=OSError("Timeout")):
            response = self.invitation_action(invitation, "resend")
        invitation.refresh_from_db()
        self.assertEqual(response.json()["delivery"]["failed"], [invitation.email])
        self.assertEqual(invitation.email_sent_at, last_sent)

    def test_invalid_addresses_or_foreign_event_send_nothing(self):
        for payload in (
            {"emails": ["invalid"]},
            {"emails": ["same@example.com", "same@example.com"]},
            {"event_ids": [self.foreign_event.pk], "access_all": False},
        ):
            # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
            with self.subTest(payload=payload):
                self.assertEqual(self.invite(**payload).status_code, 400)
        self.assertFalse(OrganizerInvitation.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_other_organizer_cannot_resend_or_cancel_and_participant_cannot_invite(self):
        self.invite()
        invitation = OrganizerInvitation.objects.get()
        self.client.force_login(self.other)
        for action in ("resend", "cancel"):
            self.assertEqual(self.invitation_action(invitation, action).status_code, 404)
        self.client.force_login(self.participant)
        self.assertEqual(self.invite(["another@example.com"]).status_code, 403)
        self.assertEqual(len(mail.outbox), 1)

    def test_cancel_invalidates_link_without_sending_an_email(self):
        self.invite()
        invitation = OrganizerInvitation.objects.get()
        url = reverse("eo_invitation_accept", args=[invitation.token])
        self.assertEqual(self.invitation_action(invitation, "cancel").status_code, 200)
        self.assertFalse(OrganizerInvitation.objects.exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_email_link_creates_committee_with_only_invited_event_access(self):
        self.invite(access_all=False, event_ids=[self.event.pk])
        invitation = OrganizerInvitation.objects.get()
        url = reverse("eo_invitation_accept", args=[invitation.token])
        self.client.logout()
        response = self.client.post(url, {
            "email": "forged@example.com",
            "first_name": "New", "last_name": "Member",
            "password1": "New-member-test-password-123!",
            "password2": "New-member-test-password-123!",
        })
        self.assertRedirects(response, reverse("after_login"), fetch_redirect_response=False)
        member = User.objects.get(email=invitation.email)
        self.assertEqual(member.role, "COMMITTEE")
        self.assertEqual(
            list(EventCommitteeAssignment.objects.filter(member=member).values_list("event_id", flat=True)),
            [self.event.pk],
        )
        self.assertFalse(User.objects.filter(email="forged@example.com").exists())
        self.assertFalse(OrganizerInvitation.objects.exists())
        self.assertEqual(self.client.get(url).status_code, 404)
