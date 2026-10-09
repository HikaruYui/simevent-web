# Fungsi file: Proses draft, pengajuan, review proposal, dan pemberian akses Organizer secara atomic.

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.models import AccountAccessChange, User
from apps.accounts.services import change_account_access, lock_accounts, require_platform_permission

from .forms import ProposalForm
from .models import OPEN_STATUSES, OrganizerProposal, ProposalReview, ProposalStatus


def _applicant(actor):
    if not actor.is_authenticated:
        raise PermissionDenied
    user = get_object_or_404(User.objects.select_for_update(), pk=actor.pk)
    if not user.is_active:
        raise PermissionDenied
    return user


def _require_participant(user):
    if user.has_perm("accounts.access_organizer") or user.has_perm("accounts.manage_platform"):
        raise ValidationError("This account already has organizer or administrator access.")


def _save_content(proposal, data):
    form = ProposalForm(data, instance=proposal)
    if not form.is_valid():
        raise ValidationError(form.errors.as_data())
    return form.save()


@transaction.atomic
def create_proposal(*, actor, data):
    applicant = _applicant(actor)
    _require_participant(applicant)
    if OrganizerProposal.objects.owned_by(applicant).filter(status__in=OPEN_STATUSES).exists():
        raise ValidationError("You already have an open proposal.")
    return _save_content(OrganizerProposal(applicant=applicant), data)


@transaction.atomic
def edit_proposal(*, actor, proposal_id, data):
    applicant = _applicant(actor)
    proposal = get_object_or_404(OrganizerProposal.objects.owned_by(applicant).select_for_update(), pk=proposal_id)
    _require_participant(applicant)
    if proposal.status not in (ProposalStatus.DRAFT, ProposalStatus.NEEDS_REVISION):
        raise ValidationError("Only drafts and proposals needing revision can be edited.")
    return _save_content(proposal, data)


@transaction.atomic
def submit_proposal(*, actor, proposal_id):
    applicant = _applicant(actor)
    proposal = get_object_or_404(OrganizerProposal.objects.owned_by(applicant).select_for_update(), pk=proposal_id)
    _require_participant(applicant)
    if proposal.status not in (ProposalStatus.DRAFT, ProposalStatus.NEEDS_REVISION):
        raise ValidationError("This proposal cannot be submitted from its current state.")
    proposal.full_clean()
    previous = proposal.status
    proposal.status = ProposalStatus.SUBMITTED
    proposal.submitted_at = timezone.now()
    proposal.save(update_fields=["status", "submitted_at", "updated_at"])
    ProposalReview.objects.create(proposal=proposal, actor=applicant, from_status=previous, to_status=proposal.status)
    return proposal


@transaction.atomic
def delete_draft(*, actor, proposal_id):
    applicant = _applicant(actor)
    proposal = get_object_or_404(OrganizerProposal.objects.owned_by(applicant).select_for_update(), pk=proposal_id)
    if proposal.status != ProposalStatus.DRAFT:
        raise ValidationError("Only an unsubmitted draft can be deleted.")
    proposal.delete()


@transaction.atomic
def review_proposal(*, actor, proposal_id, decision, reason=""):
    if not actor.is_authenticated:
        raise PermissionDenied
    # Refresh permissions before lookup so a stale caller cannot reuse revoked rights.
    actor = get_object_or_404(User, pk=actor.pk)
    require_platform_permission(actor, "partnerships.review_proposal")
    applicant_id = get_object_or_404(OrganizerProposal, pk=proposal_id).applicant_id
    users = lock_accounts(actor.pk, applicant_id)
    actor = users[actor.pk]
    require_platform_permission(actor, "partnerships.review_proposal")
    proposal = get_object_or_404(OrganizerProposal.objects.select_for_update(), pk=proposal_id)
    if actor.pk == applicant_id:
        raise PermissionDenied("Self-review is not allowed.")
    if proposal.status != ProposalStatus.SUBMITTED:
        raise ValidationError("Only submitted proposals can be reviewed.")
    if decision not in (ProposalStatus.APPROVED, ProposalStatus.NEEDS_REVISION, ProposalStatus.REJECTED):
        raise ValidationError("Invalid review decision.")
    reason = reason.strip()
    if len(reason) > 2000 or (decision != ProposalStatus.APPROVED and not reason):
        raise ValidationError("Revision and rejection require a reason (maximum 2000 characters).")
    access_change = None
    if decision == ProposalStatus.APPROVED:
        access_change = change_account_access(
            actor=actor, user_id=applicant_id, action=AccountAccessChange.Action.GRANT_ORGANIZER,
            reason=reason or f"Approved organizer proposal #{proposal.pk}.",
        )
    proposal.status = decision
    proposal.save(update_fields=["status", "updated_at"])
    ProposalReview.objects.create(
        proposal=proposal, actor=actor, from_status=ProposalStatus.SUBMITTED,
        to_status=decision, reason=reason, access_change=access_change,
    )
    return proposal
