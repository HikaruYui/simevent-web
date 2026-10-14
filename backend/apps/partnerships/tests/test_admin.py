# Fungsi file: Pengujian app partnerships: action, pembatasan edit, konfirmasi, serta rendering Django Admin.

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import AccountAccessChange, User
from apps.partnerships.models import ProposalStatus
from apps.partnerships.services import create_proposal, submit_proposal

from .test_workflow import CONTENT, setup_users


class ProposalAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant, cls.other, cls.admin = setup_users()
        cls.proposal = create_proposal(actor=cls.participant, data=CONTENT)
        submit_proposal(actor=cls.participant, proposal_id=cls.proposal.pk)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_review_uses_transactional_workflow(self):
        response = self.client.post(reverse("admin:partnerships_organizerproposal_changelist"), {
            "action": "approve", "_selected_action": str(self.proposal.pk), "reason": "Disetujui", "confirm": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, ProposalStatus.APPROVED)
        self.assertEqual(User.objects.get(pk=self.participant.pk).role, "ORGANIZER")
        self.assertEqual(AccountAccessChange.objects.count(), 1)

    def test_admin_does_not_review_without_confirmation(self):
        self.client.post(reverse("admin:partnerships_organizerproposal_changelist"), {
            "action": "approve", "_selected_action": str(self.proposal.pk), "reason": "Disetujui",
        })
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, ProposalStatus.SUBMITTED)

    def test_superuser_cannot_edit_status_or_delete_history(self):
        root = User.objects.create_superuser("root@example.com", "password")
        self.client.force_login(root)
        for name in ("change", "delete"):
            with self.subTest(name=name):
                response = self.client.post(reverse(f"admin:partnerships_organizerproposal_{name}", args=[self.proposal.pk]), {"status": "APPROVED"})
                self.assertEqual(response.status_code, 403)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, ProposalStatus.SUBMITTED)

    def test_native_admin_pages_render_and_escape_content(self):
        self.proposal.organization_name = "<script>alert(1)</script>"
        self.proposal.save()
        response = self.client.get(reverse("admin:partnerships_organizerproposal_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Konfirmasi tindakan")
        self.assertNotContains(response, "<script>alert(1)</script>")
        response = self.client.get(reverse("admin:partnerships_organizerproposal_change", args=[self.proposal.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="status"')
