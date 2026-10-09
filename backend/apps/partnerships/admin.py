# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk proposal kerja sama dan approval Organizer.

from django.contrib import admin

from apps.accounts.admin_support import ReadOnlyAuditAdmin, ReasonActionForm, run_single_action

from .models import OrganizerProposal, ProposalReview, ProposalStatus
from .services import review_proposal


@admin.register(OrganizerProposal)
class OrganizerProposalAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("organization_name", "applicant", "status", "submitted_at")
    list_select_related = ("applicant",)
    list_filter = ("status",)
    search_fields = ("organization_name", "applicant__email")
    action_form = ReasonActionForm
    actions = ("approve", "request_revision", "reject")

    def has_review_permission(self, request):
        return request.user.has_perm("accounts.manage_platform") and request.user.has_perm("partnerships.review_proposal")

    def _review(self, request, queryset, decision):
        run_single_action(self, request, queryset, lambda pk, reason: review_proposal(
            actor=request.user, proposal_id=pk, decision=decision, reason=reason,
        ))

    @admin.action(description="Setujui proposal", permissions=["review"])
    def approve(self, request, queryset):
        self._review(request, queryset, ProposalStatus.APPROVED)

    @admin.action(description="Minta revisi", permissions=["review"])
    def request_revision(self, request, queryset):
        self._review(request, queryset, ProposalStatus.NEEDS_REVISION)

    @admin.action(description="Tolak proposal", permissions=["review"])
    def reject(self, request, queryset):
        self._review(request, queryset, ProposalStatus.REJECTED)


@admin.register(ProposalReview)
class ProposalReviewAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("proposal", "actor", "from_status", "to_status", "created_at")
    list_select_related = ("proposal", "actor")
    list_filter = ("to_status",)
