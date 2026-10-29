# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk event, ownership, dan alur approval/publikasi.

from django.contrib import admin

from apps.accounts.admin_support import ReadOnlyAuditAdmin, ReasonActionForm, run_single_action

from .models import Event, EventAccess, EventTransition, EventType
from .workflow import EventWorkflow


# Inheritance: EventTypeAdmin mewarisi tampilan dan operasi pengelolaan model di Django admin.
# OOP — Hierarchical inheritance: admin.ModelAdmin juga menjadi induk class saudara lain di proyek.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    actions = None

    # Polymorphism: menentukan field admin yang hanya dapat dibaca.
    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()

    # Polymorphism: menyesuaikan izin melihat objek pada Django admin.
    def has_view_permission(self, request, obj=None):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        return (
            request.user.has_perm("accounts.manage_platform")
            and super().has_view_permission(request, obj)
        )

    # Polymorphism: menyesuaikan izin menambah objek pada Django admin.
    def has_add_permission(self, request):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        return (
            request.user.has_perm("accounts.manage_platform")
            and super().has_add_permission(request)
        )

    # Polymorphism: menyesuaikan izin mengubah objek pada Django admin.
    def has_change_permission(self, request, obj=None):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        return (
            request.user.has_perm("accounts.manage_platform")
            and super().has_change_permission(request, obj)
        )

    # Polymorphism: menyesuaikan izin menghapus objek pada Django admin.
    def has_delete_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_superuser
        )


# Inheritance (pewarisan ganda): EventAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Event)
class EventAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("title", "organizer", "event_type", "status", "start_datetime")
    list_select_related = ("organizer", "event_type")
    list_filter = ("status", "delivery_mode", "event_type")
    search_fields = ("title", "slug", "organizer__email")
    action_form = ReasonActionForm
    actions = ("approve", "request_revision", "reject", "publish", "unpublish", "complete", "cancel")

    # OOP — Polymorphism: has_review_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_review_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.review_event")
        )

    # OOP — Polymorphism: has_publish_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_publish_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.publish_event")
        )

    # OOP — Polymorphism: has_complete_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_complete_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.complete_event")
        )

    # OOP — Polymorphism: has_cancel_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_cancel_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("events.cancel_event")
        )

    # Encapsulation: helper berawalan _ menandai detail internal class menurut konvensi Python.
    def _transition(self, request, queryset, action):
        workflow = EventWorkflow(request.user)
        run_single_action(self, request, queryset, lambda pk, reason: workflow.transition(
            pk, action=action, reason=reason
        ))

    # OOP — Encapsulation: method approve mengelompokkan operasi terkait objek EventAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Setujui event", permissions=["review"])
    def approve(self, request, queryset):
        self._transition(request, queryset, "approve")

    # OOP — Encapsulation: method request_revision mengelompokkan operasi terkait objek EventAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Minta revisi event", permissions=["review"])
    def request_revision(self, request, queryset):
        self._transition(request, queryset, "request_revision")

    # OOP — Encapsulation: method reject mengelompokkan operasi terkait objek EventAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Tolak event", permissions=["review"])
    def reject(self, request, queryset):
        self._transition(request, queryset, "reject")

    # OOP — Encapsulation: method publish mengelompokkan operasi terkait objek EventAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Publikasikan event", permissions=["publish"])
    def publish(self, request, queryset):
        self._transition(request, queryset, "publish")

    # OOP — Encapsulation: method unpublish mengelompokkan operasi terkait objek EventAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Tarik publikasi event", permissions=["publish"])
    def unpublish(self, request, queryset):
        self._transition(request, queryset, "unpublish")

    # OOP — Encapsulation: method complete mengelompokkan operasi terkait objek EventAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Tandai event selesai", permissions=["complete"])
    def complete(self, request, queryset):
        self._transition(request, queryset, "complete")

    # OOP — Encapsulation: method cancel mengelompokkan operasi terkait objek EventAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Batalkan event", permissions=["cancel"])
    def cancel(self, request, queryset):
        self._transition(request, queryset, "cancel")


# Inheritance (pewarisan ganda): EventAccessAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(EventAccess)
class EventAccessAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("event",)
    list_select_related = ("event",)


# Inheritance (pewarisan ganda): EventTransitionAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(EventTransition)
class EventTransitionAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("event", "actor", "from_status", "to_status", "created_at")
    list_select_related = ("event", "actor")
    list_filter = ("to_status",)
