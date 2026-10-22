"""Pengaturan role akun lewat aksi Django Admin, dengan audit dan pembatasan izin."""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import AccountAccessChange, User

ROLE_ACTIONS = {
    "PARTICIPANT": AccountAccessChange.Action.SET_PARTICIPANT,
    "COMMITTEE": AccountAccessChange.Action.SET_COMMITTEE,
    "ORGANIZER": AccountAccessChange.Action.SET_ORGANIZER,
}


def set_account_role(*, actor, user_id, role, reason):
    """Tetapkan role peserta/panitia/ketua tanpa memberikan akses admin platform."""
    if role not in ROLE_ACTIONS:
        raise ValidationError("Role tidak dikenal.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Alasan perubahan role wajib diisi.")
    if not (
        actor.is_active
        and actor.has_perm("accounts.manage_platform")
        and actor.has_perm("accounts.manage_organizer_access")
    ):
        raise PermissionDenied("Tidak berwenang mengubah role.")

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)

        # Akun admin tidak boleh diturunkan lewat aksi penetapan role biasa.
        if user.pk == actor.pk or user.is_superuser or user.has_perm("accounts.manage_platform"):
            raise PermissionDenied("Role akun administrator atau akun sendiri tidak boleh diubah lewat aksi ini.")

        ct = ContentType.objects.get_for_model(User)
        committee_permission = Permission.objects.get(content_type=ct, codename="access_organizer")
        head_permission = Permission.objects.get(content_type=ct, codename="access_head_organizer")

        # Menyesuaikan grup yang sudah digunakan di proyek lama.
        committee_group, _ = Group.objects.get_or_create(name="Organizer")
        head_group, _ = Group.objects.get_or_create(name="ketua-panitia")

        # Hindari grup role memberikan kewenangan administrator platform.
        privileged = {"manage_platform", "manage_organizer_access", "manage_accounts"}
        for group in (committee_group, head_group):
            if group.permissions.filter(content_type=ct, codename__in=privileged).exists():
                raise ValidationError(
                    f"Grup {group.name} memiliki izin admin platform. "
                    "Periksa hak akses grup sebelum menetapkan role."
                )

        # Bila permission role juga diberikan oleh grup lain, jangan diam-diam
        # menyisakan izin lama sewaktu pengguna dijadikan Peserta.
        conflicting_groups = (
            user.groups.exclude(pk__in=(committee_group.pk, head_group.pk))
            .filter(permissions__in=(committee_permission, head_permission)).distinct()
        )
        if conflicting_groups.exists():
            raise ValidationError(
                "Pengguna memiliki permission role dari grup lain: "
                + ", ".join(conflicting_groups.values_list("name", flat=True))
                + ". Periksa grup tersebut terlebih dahulu."
            )

        # Jangan memodifikasi permission grup bersama: perubahan grup dapat
        # memengaruhi semua anggotanya. Permission role dipasang per pengguna.
        # Hapus penugasan role sebelumnya, tanpa menyentuh grup lain.
        user.groups.remove(committee_group, head_group)
        user.user_permissions.remove(committee_permission, head_permission)

        if role == "COMMITTEE":
            user.groups.add(committee_group)
            user.user_permissions.add(committee_permission)
        elif role == "ORGANIZER":
            user.groups.add(committee_group, head_group)
            user.user_permissions.add(committee_permission, head_permission)

        # Panitia memakai dashboard aplikasi, bukan situs /admin/.
        if user.is_staff:
            user.is_staff = False
            user.save(update_fields=("is_staff",))

        AccountAccessChange.objects.create(
            user=user,
            actor=actor,
            action=ROLE_ACTIONS[role],
            reason=reason,
        )
        return user
