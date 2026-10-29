# Fungsi file: Komponen bersama untuk action Admin dengan alasan/konfirmasi dan akses audit read-only.

from django import forms
from django.contrib import messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction


# Inheritance: ReasonActionForm mewarisi perilaku ActionForm untuk diperluas sesuai kebutuhan class ini.
# OOP — Object composition: objek field disusun sebagai bagian form; validasi didelegasikan ke masing-masing field.
class ReasonActionForm(ActionForm):
    reason = forms.CharField(
        label="Alasan",
        max_length=2000,
        required=False,
    )

    confirm = forms.BooleanField(
        label="Konfirmasi tindakan",
        required=False,
    )


# OOP — Duck typing: model_admin cukup menyediakan message_user/log_change; operation cukup callable.
# OOP — Polymorphism berbasis callable: operasi admin berbeda dijalankan melalui kontrak operation(pk, reason).
def run_single_action(
    model_admin,
    request,
    queryset,
    operation,
):
    objects = list(queryset[:2])

    reason = request.POST.get(
        "reason",
        "",
    ).strip()

    confirmed = (
        request.POST.get("confirm") == "on"
    )

    if (
        len(objects) != 1
        or not reason
        or len(reason) > 2000
        or not confirmed
    ):
        model_admin.message_user(
            request,
            (
                "Pilih satu data, isi alasan, "
                "dan konfirmasi tindakan."
            ),
            messages.ERROR,
        )
        return

    obj = objects[0]

    try:
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with transaction.atomic():
            operation(
                obj.pk,
                reason,
            )

            model_admin.log_change(
                request,
                obj,
                reason,
            )

    except ValidationError as exc:
        model_admin.message_user(
            request,
            "; ".join(exc.messages),
            messages.ERROR,
        )

    except PermissionDenied as exc:
        model_admin.message_user(
            request,
            str(exc) or "Tindakan tidak diizinkan.",
            messages.ERROR,
        )

    else:
        model_admin.message_user(
            request,
            "Tindakan berhasil dicatat.",
            messages.SUCCESS,
        )


# OOP mixin: mengemas aturan akses untuk dipakai ulang melalui pewarisan ganda.
# OOP — Hierarchical inheritance: class ini menjadi induk bersama bagi AccountAccessChangeAdmin, AttendanceAdmin, EventAccessAdmin, EventAdmin, EventRewardPolicyAdmin, EventTransitionAdmin, FeedbackAdmin, OrganizerProposalAdmin, ProposalReviewAdmin, RegistrationAdmin, TicketAdmin, UserAchievementAdmin.
class ReadOnlyAuditAdmin:
    # Polymorphism: menyesuaikan izin melihat objek pada Django admin.
    def has_view_permission(
        self,
        request,
        obj=None,
    ):
        return (
            request.user.is_active
            and request.user.has_perm(
                "accounts.manage_platform"
            )
        )

    # Polymorphism: menyesuaikan izin menambah objek pada Django admin.
    def has_add_permission(self, request):
        return False

    # Polymorphism: menyesuaikan izin mengubah objek pada Django admin.
    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    # Polymorphism: menyesuaikan izin menghapus objek pada Django admin.
    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
