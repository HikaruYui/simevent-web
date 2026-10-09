# Fungsi file: Pengujian app partnerships: transisi status, approval, izin, dan aturan proses bisnis.

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.http import Http404
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AccountAccessChange, User
from apps.accounts.services import change_account_access
from apps.partnerships.models import OrganizerProposal, ProposalReview, ProposalStatus
from apps.partnerships.services import create_proposal, delete_draft, edit_proposal, review_proposal, submit_proposal

CONTENT = {
    "organization_name": "Komunitas SIMEVENT",
    "contact_information": "panitia@example.com",
    "proposal_text": "Rencana kegiatan seminar formal untuk mahasiswa.",
}


def setup_users():
    call_command("bootstrap_roles", stdout=StringIO())
    participant = User.objects.create_user("participant@example.com", "A-long-password-123!")
    other = User.objects.create_user("other@example.com", "A-long-password-123!")
    admin = User.objects.create_user("reviewer@example.com", "A-long-password-123!", is_staff=True)
    admin.groups.add(Group.objects.get(name="Platform Admin"))
    return participant, other, admin


class ProposalWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant, cls.other, cls.admin = setup_users()

    def draft(self):
        return create_proposal(actor=self.participant, data=CONTENT)

    def submitted(self):
        proposal = self.draft()
        return submit_proposal(actor=self.participant, proposal_id=proposal.pk)

    def review(self, proposal, decision=ProposalStatus.APPROVED, reason="Hasil review admin"):
        return review_proposal(actor=self.admin, proposal_id=proposal.pk, decision=decision, reason=reason)

    def test_draft_submission_approval_grants_only_organizer(self):
        proposal = self.draft()
        self.assertEqual(proposal.status, ProposalStatus.DRAFT)
        self.assertIsNone(proposal.submitted_at)
        submit_proposal(actor=self.participant, proposal_id=proposal.pk)
        self.review(proposal)
        proposal.refresh_from_db()
        user = User.objects.get(pk=self.participant.pk)
        self.assertEqual(proposal.status, ProposalStatus.APPROVED)
        self.assertEqual(user.role, "ORGANIZER")
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertFalse(user.has_perm("accounts.manage_platform"))
        self.assertEqual(proposal.reviews.count(), 2)
        review = proposal.reviews.get(to_status=ProposalStatus.APPROVED)
        self.assertEqual(review.access_change.user, user)
        self.assertEqual(review.access_change.actor, self.admin)

    def test_revision_edit_and_resubmit(self):
        proposal = self.submitted()
        self.review(proposal, ProposalStatus.NEEDS_REVISION)
        edit_proposal(actor=self.participant, proposal_id=proposal.pk, data={**CONTENT, "proposal_text": "Revisi yang lengkap."})
        submit_proposal(actor=self.participant, proposal_id=proposal.pk)
        self.review(proposal)
        self.assertEqual(proposal.reviews.count(), 4)

    def test_rejection_preserves_participant_and_allows_new_proposal(self):
        proposal = self.submitted()
        self.review(proposal, ProposalStatus.REJECTED)
        self.assertEqual(User.objects.get(pk=self.participant.pk).role, "PARTICIPANT")
        self.assertFalse(AccountAccessChange.objects.exists())
        self.assertNotEqual(self.draft().pk, proposal.pk)

    def test_only_one_open_proposal(self):
        self.draft()
        with self.assertRaises(ValidationError):
            self.draft()
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizerProposal.objects.create(applicant=self.participant, **CONTENT)

    def test_state_and_submission_timestamp_constraints(self):
        for values in ({"status": "UNKNOWN"}, {"status": ProposalStatus.SUBMITTED},
                       {"status": ProposalStatus.DRAFT, "submitted_at": timezone.now()}):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                OrganizerProposal.objects.create(applicant=self.participant, **CONTENT, **values)

    def test_invalid_transitions_and_revision_reason(self):
        proposal = self.draft()
        with self.assertRaises(ValidationError):
            self.review(proposal)
        submit_proposal(actor=self.participant, proposal_id=proposal.pk)
        for decision in (ProposalStatus.REJECTED, ProposalStatus.NEEDS_REVISION, "PUBLISHED"):
            with self.subTest(decision=decision), self.assertRaises(ValidationError):
                self.review(proposal, decision, reason="   ")
        with self.assertRaises(ValidationError):
            submit_proposal(actor=self.participant, proposal_id=proposal.pk)
        with self.assertRaises(ValidationError):
            edit_proposal(actor=self.participant, proposal_id=proposal.pk, data=CONTENT)

    def test_owner_scope_is_enforced_inside_services(self):
        proposal = self.draft()
        for operation in (
            lambda: edit_proposal(actor=self.other, proposal_id=proposal.pk, data=CONTENT),
            lambda: submit_proposal(actor=self.other, proposal_id=proposal.pk),
            lambda: delete_draft(actor=self.other, proposal_id=proposal.pk),
        ):
            with self.assertRaises(Http404):
                operation()

    def test_participant_organizer_and_staff_cannot_review(self):
        proposal = self.submitted()
        for mode in ("participant", "organizer", "staff"):
            if mode == "organizer":
                self.other.groups.add(Group.objects.get(name="Organizer"))
            if mode == "staff":
                self.other.groups.clear()
                self.other.is_staff = True
                self.other.save()
            with self.subTest(mode=mode), self.assertRaises(PermissionDenied):
                review_proposal(actor=self.other, proposal_id=proposal.pk, decision=ProposalStatus.APPROVED)

    def test_review_permission_alone_is_not_platform_authority(self):
        proposal = self.submitted()
        self.other.user_permissions.add(Permission.objects.get(codename="review_proposal"))
        with self.assertRaises(PermissionDenied):
            review_proposal(actor=self.other, proposal_id=proposal.pk, decision=ProposalStatus.REJECTED, reason="Reason")

    def test_self_review_denied(self):
        proposal = self.submitted()
        self.participant.groups.add(Group.objects.get(name="Platform Admin"))
        with self.assertRaises(PermissionDenied):
            review_proposal(actor=self.participant, proposal_id=proposal.pk, decision=ProposalStatus.APPROVED)

    def test_approval_replay_cannot_restore_revoked_access(self):
        proposal = self.submitted()
        self.review(proposal)
        change_account_access(actor=self.admin, user_id=self.participant.pk,
                              action=AccountAccessChange.Action.REVOKE_ORGANIZER, reason="Partnership ended")
        with self.assertRaises(ValidationError):
            self.review(proposal)
        self.assertEqual(User.objects.get(pk=self.participant.pk).role, "PARTICIPANT")
        self.assertEqual(AccountAccessChange.objects.count(), 2)

    def test_approval_rollback_includes_permission_and_access_log(self):
        proposal = self.submitted()
        with patch("apps.partnerships.services.ProposalReview.objects.create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.review(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ProposalStatus.SUBMITTED)
        self.assertFalse(self.participant.groups.exists())
        self.assertFalse(AccountAccessChange.objects.exists())

    def test_suspended_applicant_cannot_submit_or_be_approved(self):
        proposal = self.submitted()
        User.objects.filter(pk=self.participant.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.review(proposal)
        with self.assertRaises(PermissionDenied):
            submit_proposal(actor=self.participant, proposal_id=proposal.pk)

    def test_revoked_reviewer_permission_not_reused_from_cache(self):
        proposal = self.submitted()
        self.assertTrue(self.admin.has_perm("partnerships.review_proposal"))
        self.admin.groups.clear()
        with self.assertRaises(PermissionDenied):
            self.review(proposal)

    def test_approval_requires_separate_grant_permission(self):
        proposal = self.submitted()
        Group.objects.get(name="Platform Admin").permissions.remove(
            Permission.objects.get(codename="manage_organizer_access")
        )
        with self.assertRaises(PermissionDenied):
            self.review(proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ProposalStatus.SUBMITTED)
        self.assertFalse(AccountAccessChange.objects.exists())

    def test_review_constraints_reject_invalid_audit_records(self):
        proposal = self.submitted()
        for values in (
            {"from_status": ProposalStatus.DRAFT, "to_status": ProposalStatus.APPROVED},
            {"from_status": ProposalStatus.SUBMITTED, "to_status": ProposalStatus.REJECTED},
            {"from_status": ProposalStatus.SUBMITTED, "to_status": ProposalStatus.APPROVED},
        ):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                ProposalReview.objects.create(proposal=proposal, actor=self.admin, **values)

    def test_organizer_cannot_open_new_proposal(self):
        self.participant.groups.add(Group.objects.get(name="Organizer"))
        with self.assertRaises(ValidationError):
            self.draft()

    def test_delete_only_unsubmitted_draft(self):
        proposal = self.draft()
        delete_draft(actor=self.participant, proposal_id=proposal.pk)
        self.assertFalse(OrganizerProposal.objects.exists())
        proposal = self.submitted()
        with self.assertRaises(ValidationError):
            delete_draft(actor=self.participant, proposal_id=proposal.pk)


class ProposalHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant, cls.other, cls.admin = setup_users()

    def setUp(self):
        self.client.force_login(self.participant)
        self.proposal = create_proposal(actor=self.participant, data=CONTENT)

    def test_create_ignores_owner_status_and_timestamps(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("partnerships:list"), {
            **CONTENT, "applicant": self.participant.pk, "status": "APPROVED", "submitted_at": timezone.now(),
        })
        self.assertEqual(response.status_code, 201)
        proposal = OrganizerProposal.objects.get(pk=response.json()["id"])
        self.assertEqual(proposal.applicant, self.other)
        self.assertEqual(proposal.status, ProposalStatus.DRAFT)
        self.assertIsNone(proposal.submitted_at)

    def test_list_and_detail_are_private(self):
        other = create_proposal(actor=self.other, data=CONTENT)
        response = self.client.get(reverse("partnerships:list"))
        self.assertEqual([item["id"] for item in response.json()["results"]], [self.proposal.pk])
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.get(reverse("partnerships:detail", args=[other.pk])).status_code, 404)

    def test_cross_account_posts_are_404(self):
        self.client.force_login(self.other)
        for name in ("detail", "submit", "delete"):
            with self.subTest(name=name):
                response = self.client.post(reverse(f"partnerships:{name}", args=[self.proposal.pk]), {**CONTENT, "confirm": True})
                self.assertEqual(response.status_code, 404)

    def test_detail_returns_revision_reason_without_reviewer_identity(self):
        submit_proposal(actor=self.participant, proposal_id=self.proposal.pk)
        review_proposal(actor=self.admin, proposal_id=self.proposal.pk,
                        decision=ProposalStatus.NEEDS_REVISION, reason="Lengkapi susunan acara.")
        response = self.client.get(reverse("partnerships:detail", args=[self.proposal.pk]))
        self.assertEqual(response.json()["reviews"][-1]["reason"], "Lengkapi susunan acara.")
        self.assertNotContains(response, self.admin.email)

    def test_delete_requires_confirmation_and_post(self):
        url = reverse("partnerships:delete", args=[self.proposal.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 400)
        self.assertTrue(OrganizerProposal.objects.filter(pk=self.proposal.pk).exists())
        self.assertEqual(self.client.post(url, {"confirm": "on"}).status_code, 200)

    def test_auth_and_csrf_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("partnerships:list")).status_code, 401)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.participant)
        for name in ("detail", "submit", "delete"):
            with self.subTest(name=name):
                self.assertEqual(client.post(reverse(f"partnerships:{name}", args=[self.proposal.pk]), CONTENT).status_code, 403)
        self.assertEqual(client.post(reverse("partnerships:list"), CONTENT).status_code, 403)

    def test_invalid_content_and_transition_return_errors(self):
        response = self.client.post(reverse("partnerships:detail", args=[self.proposal.pk]), {**CONTENT, "proposal_text": " "})
        self.assertEqual(response.status_code, 400)
        url = reverse("partnerships:submit", args=[self.proposal.pk])
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 400)


class ProposalConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.participant, self.other, self.admin = setup_users()

    def race(self, operation):
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
                return "ok"
            except ValidationError:
                return "invalid"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_concurrent_creation_has_one_open_proposal(self):
        results = self.race(lambda: create_proposal(actor=self.participant, data=CONTENT))
        self.assertCountEqual(results, ["ok", "invalid"])
        self.assertEqual(OrganizerProposal.objects.count(), 1)

    def test_concurrent_approval_has_one_grant_and_review(self):
        proposal = create_proposal(actor=self.participant, data=CONTENT)
        submit_proposal(actor=self.participant, proposal_id=proposal.pk)
        results = self.race(lambda: review_proposal(actor=self.admin, proposal_id=proposal.pk, decision=ProposalStatus.APPROVED))
        self.assertCountEqual(results, ["ok", "invalid"])
        self.assertEqual(AccountAccessChange.objects.count(), 1)
        self.assertEqual(ProposalReview.objects.filter(to_status=ProposalStatus.APPROVED).count(), 1)
