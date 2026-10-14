# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk event, ownership, dan alur approval/publikasi.

from django.contrib import admin

from apps.accounts.admin_support import ReadOnlyAuditAdmin, ReasonActionForm, run_single_action

from .models import Event, EventAccess, EventTransition, EventType
from .workflow import EventWorkflow


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()

    def has_view_permission(self, request, obj=None):
        return (
            request.user.has_perm("accounts.manage_platform")
            and super().has_view_permission(request, obj)
        )

    def has_add_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and super().has_add_permission(request)
        )

    def has_change_permission(self, request, obj=None):
        return (
            request.user.has_perm("accounts.manage_platform")
            and super().has_change_permission(request, obj)
        )

    def has_delete_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_superuser
        )


@admin.register(Event)
class EventAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("title", "organizer", "event_type", "status", "start_datetime")
    list_select_related = ("organizer", "event_type")
    list_filter = ("status", "delivery_mode", "event_type")
    search_fields = ("title", "slug", "organizer__email")
    action_form = ReasonActionForm
    actions = ("approve", "request_revision", "reject", "publish", "unpublish", "complete", "cancel")

    def has_review_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.review_event")
        )

    def has_publish_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.publish_event")
        )

    def has_complete_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.complete_event")
        )

    def has_cancel_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.cancel_event")
        )

    def _transition(self, request, queryset, action):
        workflow = EventWorkflow(request.user)
        run_single_action(self, request, queryset, lambda pk, reason: workflow.transition(
            pk, action=action, reason=reason
        ))

    @admin.action(description="Setujui event", permissions=["review"])
    def approve(self, request, queryset):
        self._transition(request, queryset, "approve")

    @admin.action(description="Minta revisi event", permissions=["review"])
    def request_revision(self, request, queryset):
        self._transition(request, queryset, "request_revision")

    @admin.action(description="Tolak event", permissions=["review"])
    def reject(self, request, queryset):
        self._transition(request, queryset, "reject")

    @admin.action(description="Publikasikan event", permissions=["publish"])
    def publish(self, request, queryset):
        self._transition(request, queryset, "publish")

    @admin.action(description="Tarik publikasi event", permissions=["publish"])
    def unpublish(self, request, queryset):
        self._transition(request, queryset, "unpublish")

    @admin.action(description="Tandai event selesai", permissions=["complete"])
    def complete(self, request, queryset):
        self._transition(request, queryset, "complete")

    @admin.action(description="Batalkan event", permissions=["cancel"])
    def cancel(self, request, queryset):
        self._transition(request, queryset, "cancel")


@admin.register(EventAccess)
class EventAccessAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("event",)
    list_select_related = ("event",)


@admin.register(EventTransition)
class EventTransitionAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("event", "actor", "from_status", "to_status", "created_at")
    list_select_related = ("event", "actor")
    list_filter = ("to_status",)
