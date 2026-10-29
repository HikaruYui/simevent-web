# Fungsi file: Model, relasi, queryset, dan constraint database untuk proposal kerja sama dan approval Organizer.

from django.conf import settings
from django.db import models


# Inheritance: ProposalStatus mewarisi enum Django untuk pilihan nilai dan label.
class ProposalStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    NEEDS_REVISION = "NEEDS_REVISION", "Needs revision"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


OPEN_STATUSES = (ProposalStatus.DRAFT, ProposalStatus.SUBMITTED, ProposalStatus.NEEDS_REVISION)


# Inheritance: ProposalQuerySet mewarisi operasi query Django untuk menambahkan filter domain.
# OOP — Hierarchical inheritance: models.QuerySet juga menjadi induk class saudara lain di proyek.
class ProposalQuerySet(models.QuerySet):
    # Abstraction: owned_by() membungkus aturan filter agar pemanggil dapat memakai ulang query domain.
    def owned_by(self, user):
        return self.filter(applicant=user)


# Inheritance: OrganizerProposal mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class OrganizerProposal(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organizer_proposals")
    organization_name = models.CharField(max_length=200)
    contact_information = models.CharField(max_length=500)
    proposal_text = models.TextField(max_length=10000)
    status = models.CharField(max_length=20, choices=ProposalStatus.choices, default=ProposalStatus.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # OOP — Factory / delegation: as_manager() membentuk manager yang mengekspos method QuerySet khusus lewat objects.
    objects = ProposalQuerySet.as_manager()

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-created_at", "-pk")
        permissions = [("review_proposal", "Can review organizer proposals")]
        indexes = [models.Index(fields=["status", "submitted_at"], name="proposal_review_queue_idx")]
        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
        constraints = [
            models.UniqueConstraint(fields=["applicant"], condition=models.Q(status__in=OPEN_STATUSES), name="proposal_one_open_per_user"),
            models.CheckConstraint(condition=models.Q(status__in=ProposalStatus.values), name="proposal_status_valid"),
            models.CheckConstraint(
                condition=(models.Q(status=ProposalStatus.DRAFT, submitted_at__isnull=True)
                           | (~models.Q(status=ProposalStatus.DRAFT) & models.Q(submitted_at__isnull=False))),
                name="proposal_submission_time_valid",
            ),
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"{self.organization_name} ({self.status})"


# Inheritance: ProposalReview mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class ProposalReview(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke OrganizerProposal; relasi database bukan pewarisan class.
    proposal = models.ForeignKey(OrganizerProposal, on_delete=models.PROTECT, related_name="reviews")
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="proposal_reviews")
    from_status = models.CharField(max_length=20, choices=ProposalStatus.choices)
    to_status = models.CharField(max_length=20, choices=ProposalStatus.choices)
    reason = models.TextField(max_length=2000, blank=True)
    # OOP — Association (OneToOneField): menghubungkan objek ke 'accounts.AccountAccessChange'; relasi database bukan pewarisan class.
    access_change = models.OneToOneField("accounts.AccountAccessChange", on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("created_at", "pk")
        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
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
