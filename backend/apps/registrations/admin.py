# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk registrasi, tiket, attendance, feedback, dan statistik.

from django.contrib import admin

from apps.accounts.admin_support import ReadOnlyAuditAdmin, ReasonActionForm, run_single_action

from .attendance import AttendanceService
from .models import Attendance, Feedback, Registration, Ticket


@admin.register(Registration)
class RegistrationAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("id", "event", "participant", "status", "registered_at")
    list_select_related = ("event", "participant")
    list_filter = ("status",)
    search_fields = ("event__title", "participant__email")


@admin.register(Ticket)
class TicketAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    fields = ("identifier", "registration", "is_active", "created_at")
    list_display = ("identifier", "registration", "is_active")
    list_select_related = ("registration",)


@admin.register(Attendance)
class AttendanceAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("registration", "status", "checked_in_at", "verified_by")
    list_select_related = ("registration", "verified_by")
    list_filter = ("status",)
    action_form = ReasonActionForm
    actions = ("void",)

    def has_void_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("registrations.void_attendance")
        )

    @admin.action(description="Batalkan attendance", permissions=["void"])
    def void(self, request, queryset):
        run_single_action(
            self, request, queryset,
            lambda pk, reason: AttendanceService(request.user).void(pk, reason=reason),
        )


@admin.register(Feedback)
class FeedbackAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("registration", "overall_rating", "created_at")
    list_select_related = ("registration",)
    list_filter = ("overall_rating",)
    search_fields = ("registration__event__title", "comment", "suggestion")
