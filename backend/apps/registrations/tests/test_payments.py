from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.events.tests.support import published_event, setup_users
from apps.registrations.models import Payment, PaymentInstructions, Ticket
from apps.registrations.payments import PaymentService
from apps.registrations.services import RegistrationService


# OOP — Single inheritance: PaymentWorkflowTests mewarisi TestCase dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: TestCase juga menjadi induk class saudara lain di proyek.
class PaymentWorkflowTests(TestCase):
    # OOP — Method overriding: framework pengujian memanggil hook setUpTestData milik subclass untuk menyiapkan/membersihkan fixture.
    # OOP — Class method: menerima cls sehingga operasi terikat pada class dan tetap mengikuti subclass.
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.event = published_event(cls.owner, cls.admin, price="25000.00")
        cls.registration = RegistrationService(cls.participant).start_paid_registration(cls.event.pk)
        cls.payment = cls.registration.payment

    def test_participant_submits_proof_and_ticket_waits_for_approval(self):
        self.client.force_login(self.participant)
        instructions = PaymentInstructions.objects.create(
            bank_name="Bank Kampus",
            account_number="1234567890",
            account_holder="SIMEVENT",
        )
        response = self.client.get(reverse(
            "registrations:payment", args=[self.registration.pk],
        ))
        self.assertEqual(response.json()["bank"]["account_number"], instructions.account_number)
        self.assertEqual(response.json()["amount"], "25000.00")

        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("registrations:payment", args=[self.registration.pk]),
                {"proof": SimpleUploadedFile(
                    "proof.png", b"\x89PNG\r\n\x1a\nproof", content_type="image/png",
                )},
            )
            self.assertEqual(response.status_code, 202)
            self.payment.refresh_from_db()
            self.assertEqual(self.payment.status, Payment.Status.UNDER_REVIEW)
            self.assertTrue(self.payment.proof)
            self.assertFalse(Ticket.objects.filter(registration=self.registration).exists())

        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with self.assertRaises(PermissionDenied):
            PaymentService(self.participant).review(self.payment.pk, approve=True)

    def test_rejection_requires_reason_and_approved_payment_issues_ticket(self):
        self.payment.status = Payment.Status.UNDER_REVIEW
        self.payment.submitted_at = timezone.now()
        self.payment.save(update_fields=["status", "submitted_at"])
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with self.assertRaisesMessage(ValidationError, "Alasan"):
            PaymentService(self.owner).review(self.payment.pk, approve=False)
        reviewed = PaymentService(self.owner).review(
            self.payment.pk, approve=True,
        )
        self.assertEqual(reviewed.status, Payment.Status.APPROVED)
        self.assertTrue(Ticket.objects.get(registration=self.registration).is_valid)

    def test_participant_cannot_access_another_users_payment_or_review(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(
            reverse("registrations:payment", args=[self.registration.pk]),
        ).status_code, 404)
        response = self.client.post(reverse(
            "registrations:payment-review", args=[self.payment.pk],
        ), {"action": "approve"})
        self.assertEqual(response.status_code, 404)
