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



@transaction.atomic
def promote_platform_admin(*, actor, user_id, reason):
    reason = (reason or "").strip()

    if not reason or len(reason) > 2000:
        raise ValidationError(
            "Alasan wajib diisi (maksimal 2000 karakter)."
        )

    if not actor.is_authenticated:
        raise PermissionDenied("Silakan login terlebih dahulu.")

    actor_db = User.objects.select_for_update().get(pk=actor.pk)

    if not actor_db.is_active or not actor_db.is_superuser:
        raise PermissionDenied(
            "Hanya superuser aktif yang boleh memberikan akses admin."
        )

    user = User.objects.select_for_update().get(pk=user_id)

    if user.pk == actor_db.pk or user.is_superuser:
        raise PermissionDenied("Akun ini tidak dapat dipromosikan.")

    if not user.is_active:
        raise ValidationError("Aktifkan akun tujuan terlebih dahulu.")

    if user.has_perm("accounts.manage_platform"):
        raise ValidationError(
            "Pengguna sudah memiliki akses Admin Platform."
        )

    try:
        admin_group = Group.objects.get(name="Platform Admin")
    except Group.DoesNotExist:
        raise ValidationError(
            "Grup Platform Admin belum tersedia. Jalankan bootstrap_roles."
        )

    if not admin_group.permissions.filter(
        content_type__app_label="accounts",
        codename="manage_platform",
    ).exists():
        raise ValidationError(
            "Permission Platform Admin belum dikonfigurasi."
        )

    # Hapus grup role panitia sebelumnya
    old_groups = user.groups.filter(
        name__in=["Organizer", "ketua-panitia"]
    )
    user.groups.remove(*old_groups)

    # Hapus permission role panitia sebelumnya
    old_permissions = Permission.objects.filter(
        content_type__app_label="accounts",
        codename__in=[
            "access_organizer",
            "access_head_organizer",
        ],
    )
    user.user_permissions.remove(*old_permissions)

    # Tambahkan akses Admin Platform
    user.groups.add(admin_group)
    user.is_staff = True
    user.save(update_fields=["is_staff"])

    # Hapus cache permission
    for cache_name in (
        "_perm_cache",
        "_user_perm_cache",
        "_group_perm_cache",
    ):
        user.__dict__.pop(cache_name, None)

    # Simpan riwayat perubahan
    AccountAccessChange.objects.create(
        user=user,
        actor=actor_db,
        action=AccountAccessChange.Action.SET_ADMIN,
        reason=reason,
    )

    return user

    

