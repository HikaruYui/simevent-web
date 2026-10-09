# Fungsi file: Model, relasi, queryset, dan constraint database untuk proposal kerja sama dan approval Organizer.

from django.conf import settings
from django.db import models


class ProposalStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    NEEDS_REVISION = "NEEDS_REVISION", "Needs revision"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


OPEN_STATUSES = (ProposalStatus.DRAFT, ProposalStatus.SUBMITTED, ProposalStatus.NEEDS_REVISION)


class ProposalQuerySet(models.QuerySet):
    def owned_by(self, user):
        return self.filter(applicant=user)


class OrganizerProposal(models.Model):
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organizer_proposals")
    organization_name = models.CharField(max_length=200)
    contact_information = models.CharField(max_length=500)
    proposal_text = models.TextField(max_length=10000)
    status = models.CharField(max_length=20, choices=ProposalStatus.choices, default=ProposalStatus.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProposalQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-pk")
        permissions = [("review_proposal", "Can review organizer proposals")]
        indexes = [models.Index(fields=["status", "submitted_at"], name="proposal_review_queue_idx")]
        constraints = [
            models.UniqueConstraint(fields=["applicant"], condition=models.Q(status__in=OPEN_STATUSES), name="proposal_one_open_per_user"),
            models.CheckConstraint(condition=models.Q(status__in=ProposalStatus.values), name="proposal_status_valid"),
            models.CheckConstraint(
                condition=(models.Q(status=ProposalStatus.DRAFT, submitted_at__isnull=True)
                           | (~models.Q(status=ProposalStatus.DRAFT) & models.Q(submitted_at__isnull=False))),
                name="proposal_submission_time_valid",
            ),
        ]

    def __str__(self):
        return f"{self.organization_name} ({self.status})"


class ProposalReview(models.Model):
    proposal = models.ForeignKey(OrganizerProposal, on_delete=models.PROTECT, related_name="reviews")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="proposal_reviews")
    from_status = models.CharField(max_length=20, choices=ProposalStatus.choices)
    to_status = models.CharField(max_length=20, choices=ProposalStatus.choices)
    reason = models.TextField(max_length=2000, blank=True)
    access_change = models.OneToOneField("accounts.AccountAccessChange", on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(from_status__in=[ProposalStatus.DRAFT, ProposalStatus.NEEDS_REVISION], to_status=ProposalStatus.SUBMITTED)
                           | models.Q(from_status=ProposalStatus.SUBMITTED, to_status__in=[ProposalStatus.APPROVED, ProposalStatus.NEEDS_REVISION, ProposalStatus.REJECTED])),
                name="proposal_review_transition_valid",
            ),
            models.CheckConstraint(
                condition=(~models.Q(to_status__in=[ProposalStatus.NEEDS_REVISION, ProposalStatus.REJECTED]) | ~models.Q(reason="")),
                name="proposal_review_reason_required",
            ),
            models.CheckConstraint(
                condition=(models.Q(to_status=ProposalStatus.APPROVED, access_change__isnull=False)
                           | (~models.Q(to_status=ProposalStatus.APPROVED) & models.Q(access_change__isnull=True))),
                name="proposal_approval_access_required",
            ),
        ]
