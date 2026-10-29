# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk registrasi, tiket, attendance, feedback, dan statistik.

from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils.html import format_html

from apps.accounts.admin_support import ReadOnlyAuditAdmin, ReasonActionForm, run_single_action
from .attendance import AttendanceService
from .models import (
    Attendance,
    CertificateTemplate,
    Feedback,
    Payment,
    PaymentInstructions,
    Registration,
    Ticket,
)
from .payments import PaymentService


# Inheritance (pewarisan ganda): RegistrationAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Registration)
class RegistrationAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("id", "event", "participant", "status", "registered_at")
    list_select_related = ("event", "participant")
    list_filter = ("status",)
    search_fields = ("event__title", "participant__email")


# Inheritance (pewarisan ganda): TicketAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Ticket)
class TicketAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    fields = ("identifier", "registration", "is_active", "created_at")
    list_display = ("identifier", "registration", "is_active")
    list_select_related = ("registration",)


# Inheritance (pewarisan ganda): AttendanceAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Attendance)
class AttendanceAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("registration", "status", "checked_in_at", "verified_by")
    list_select_related = ("registration", "verified_by")
    list_filter = ("status",)
    action_form = ReasonActionForm
    actions = ("void",)

    # OOP — Polymorphism: has_void_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_void_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("registrations.void_attendance")
        )

    # OOP — Encapsulation: method void mengelompokkan operasi terkait objek AttendanceAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Batalkan attendance", permissions=["void"])
    def void(self, request, queryset):
        run_single_action(
            self, request, queryset,
            lambda pk, reason: AttendanceService(request.user).void(pk, reason=reason),
        )


# Inheritance (pewarisan ganda): FeedbackAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Feedback)
class FeedbackAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("registration", "overall_rating", "created_at")
    list_select_related = ("registration",)
    list_filter = ("overall_rating",)
    search_fields = ("registration__event__title", "comment", "suggestion")


# Inheritance: PaymentAdmin mewarisi tampilan dan operasi pengelolaan model di Django admin.
# OOP — Hierarchical inheritance: admin.ModelAdmin juga menjadi induk class saudara lain di proyek.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "registration", "amount", "status", "submitted_at", "proof_link")
    list_select_related = ("registration__event", "registration__participant")
    list_filter = ("status",)
    search_fields = ("registration__event__title", "registration__participant__email")
    readonly_fields = (
        "registration", "amount", "status", "proof_link", "submitted_at",
        "reviewed_by", "reviewed_at", "review_note",
    )
    fields = readonly_fields
    action_form = ReasonActionForm
    actions = ("approve_payments", "reject_payments")

    # Polymorphism: menyesuaikan izin melihat objek pada Django admin.
    def has_view_permission(self, request, obj=None):
        return request.user.is_active and (
            request.user.has_perm("accounts.access_organizer")
            or request.user.has_perm("accounts.manage_platform")
        )

    # Polymorphism: menyesuaikan izin menambah objek pada Django admin.
    def has_add_permission(self, request):
        return False

    # Polymorphism: menyesuaikan izin mengubah objek pada Django admin.
    def has_change_permission(self, request, obj=None):
        return False

    # Polymorphism: menyesuaikan izin menghapus objek pada Django admin.
    def has_delete_permission(self, request, obj=None):
        return False

    # Polymorphism: menyesuaikan kumpulan data yang digunakan oleh alur bawaan Django.
    def get_queryset(self, request):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        queryset = super().get_queryset(request).select_related(
            "registration__event", "registration__participant",
        )
        if request.user.has_perm("accounts.manage_platform"):
            return queryset
        if request.user.has_perm("accounts.access_organizer"):
            return queryset.filter(registration__event__organizer=request.user)
        return queryset.none()

    # OOP — Encapsulation: method proof_link mengelompokkan operasi terkait objek PaymentAdmin.
    # OOP — Method decorator: menambahkan metadata presentasi yang dibaca Django admin.
    @admin.display(description="Bukti transfer")
    def proof_link(self, obj):
        if not obj.proof:
            return "Belum diunggah"
        url = reverse("registrations:payment-proof-download", args=[obj.pk])
        return format_html('<a href="{}">Unduh bukti</a>', url)

    # Encapsulation: helper berawalan _ menandai detail internal class menurut konvensi Python.
    def _review(self, request, queryset, *, approve):
        note = request.POST.get("reason", "").strip()
        if not approve and not note:
            self.message_user(request, "Alasan penolakan wajib diisi.", messages.ERROR)
            return
        for payment in queryset:
            try:
                PaymentService(request.user).review(
                    payment.pk, approve=approve, note=note,
                )
            except (PermissionDenied, ValidationError) as exc:
                message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                self.message_user(request, f"Pembayaran #{payment.pk}: {message}", messages.ERROR)
            else:
                self.log_change(request, payment, note or "Pembayaran disetujui.")
                self.message_user(
                    request, f"Pembayaran #{payment.pk} berhasil ditinjau.", messages.SUCCESS,
                )

    # OOP — Encapsulation: method approve_payments mengelompokkan operasi terkait objek PaymentAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Setujui bukti pembayaran")
    def approve_payments(self, request, queryset):
        self._review(request, queryset, approve=True)

    # OOP — Encapsulation: method reject_payments mengelompokkan operasi terkait objek PaymentAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Tolak bukti pembayaran")
    def reject_payments(self, request, queryset):
        self._review(request, queryset, approve=False)


# Inheritance: PaymentInstructionsAdmin mewarisi tampilan dan operasi pengelolaan model di Django admin.
# OOP — Hierarchical inheritance: admin.ModelAdmin juga menjadi induk class saudara lain di proyek.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(PaymentInstructions)
class PaymentInstructionsAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "account_number", "account_holder", "is_active")
    fields = ("bank_name", "account_number", "account_holder", "instructions", "is_active")

    # Polymorphism: menyesuaikan izin akses modul pada Django admin.
    def has_module_permission(self, request):
        return request.user.is_active and request.user.has_perm("accounts.manage_platform")

    # Polymorphism: menyesuaikan izin melihat objek pada Django admin.
    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    # Polymorphism: menyesuaikan izin menambah objek pada Django admin.
    def has_add_permission(self, request):
        return self.has_module_permission(request)

    # Polymorphism: menyesuaikan izin mengubah objek pada Django admin.
    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    # Polymorphism: menyesuaikan izin menghapus objek pada Django admin.
    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


# Inheritance: CertificateTemplateAdmin mewarisi tampilan dan operasi pengelolaan model di Django admin.
# OOP — Hierarchical inheritance: admin.ModelAdmin juga menjadi induk class saudara lain di proyek.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "background", "is_active")
    fields = (
        "background", "is_active", "font_size", "text_color",
        ("name_x", "name_y"), ("event_x", "event_y"),
        ("date_x", "date_y"), ("number_x", "number_y"),
    )

    # Polymorphism: menyesuaikan izin akses modul pada Django admin.
    def has_module_permission(self, request):
        return request.user.is_active and request.user.has_perm("accounts.manage_platform")

    # Polymorphism: menyesuaikan izin melihat objek pada Django admin.
    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    # Polymorphism: menyesuaikan izin menambah objek pada Django admin.
    def has_add_permission(self, request):
        return self.has_module_permission(request)

    # Polymorphism: menyesuaikan izin mengubah objek pada Django admin.
    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    # Polymorphism: menyesuaikan izin menghapus objek pada Django admin.
    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)
