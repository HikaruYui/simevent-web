# Fungsi file: Operasi pemberian/pencabutan akses Organizer dan status akun dengan transaksi serta audit.

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404

from .models import AccountAccessChange, User


def lock_accounts(*user_ids):
    return {
        user.pk: user
        for user in User.objects
        .select_for_update()
        .filter(pk__in=user_ids)
        .order_by("pk")
    }


def require_platform_permission(actor, permission):
    if (
        not actor.is_authenticated
        or not actor.is_active
        or not actor.has_perm("accounts.manage_platform")
        or not actor.has_perm(permission)
    ):
        raise PermissionDenied


@transaction.atomic
def change_account_access(*, actor, user_id, action, reason):
    if not actor.is_authenticated:
        raise PermissionDenied

    users = lock_accounts(actor.pk, user_id)

    actor = users.get(actor.pk)

    if actor is None:
        raise PermissionDenied

    if action not in AccountAccessChange.Action.values:
        raise ValidationError(
            "Tindakan perubahan akun tidak valid."
        )

    organizer_action = action in (
        AccountAccessChange.Action.GRANT_ORGANIZER,
        AccountAccessChange.Action.REVOKE_ORGANIZER,
    )

    if organizer_action:
        required_permission = (
            "accounts.manage_organizer_access"
        )
    else:
        required_permission = (
            "accounts.manage_accounts"
        )

    require_platform_permission(
        actor,
        required_permission,
    )

    target = users.get(user_id)

    if target is None:
        raise Http404

    if (
        target.pk == actor.pk
        or target.is_superuser
        or target.has_perm("accounts.manage_platform")
    ):
        raise PermissionDenied(
            "Akun administrator tidak dapat dikelola "
            "melalui proses ini."
        )

    has_stored_admin_access = (
        target.groups.filter(
            permissions__codename="manage_platform",
            permissions__content_type__app_label="accounts",
        ).exists()
        or target.user_permissions.filter(
            codename="manage_platform",
            content_type__app_label="accounts",
        ).exists()
    )

    if has_stored_admin_access:
        raise PermissionDenied(
            "Akun administrator tidak dapat dikelola "
            "melalui proses ini."
        )

    reason = reason.strip()

    if not reason or len(reason) > 2000:
        raise ValidationError(
            "Alasan wajib diisi antara 1 sampai 2000 karakter."
        )

    if organizer_action:
        try:
            group = Group.objects.get(
                name="Organizer"
            )

            organizer_permission = (
                Permission.objects.get(
                    content_type__app_label="accounts",
                    content_type__model="user",
                    codename="access_organizer",
                )
            )

        except (
            Group.DoesNotExist,
            Permission.DoesNotExist,
        ):
            raise ValidationError(
                "Konfigurasi role Organizer belum tersedia. "
                "Jalankan bootstrap_roles terlebih dahulu."
            )

        if not group.permissions.filter(
            pk=organizer_permission.pk
        ).exists():
            raise ValidationError(
                "Permission Organizer belum terpasang "
                "pada group Organizer."
            )

        if (
            action
            == AccountAccessChange.Action.GRANT_ORGANIZER
        ):
            if not target.is_active:
                raise ValidationError(
                    "Aktifkan akun terlebih dahulu sebelum "
                    "memberikan akses panitia."
                )

            if target.has_perm(
                "accounts.access_organizer"
            ):
                raise ValidationError(
                    "Akun ini sudah memiliki akses panitia."
                )

            target.groups.add(group)

        else:
            has_other_group = (
                target.groups
                .exclude(pk=group.pk)
                .filter(
                    permissions=organizer_permission
                )
                .exists()
            )

            if has_other_group:
                raise ValidationError(
                    "Akses panitia juga berasal dari group lain. "
                    "Selesaikan assignment tersebut terlebih dahulu."
                )

            has_group = target.groups.filter(
                pk=group.pk
            ).exists()

            has_direct_permission = (
                target.user_permissions.filter(
                    pk=organizer_permission.pk
                ).exists()
            )

            if not has_group and not has_direct_permission:
                raise ValidationError(
                    "Akun ini tidak memiliki akses panitia."
                )

            target.groups.remove(group)

            target.user_permissions.remove(
                organizer_permission
            )

    else:
        active = (
            action
            == AccountAccessChange.Action.ACTIVATE
        )

        if target.is_active == active:
            raise ValidationError(
                "Status akun sudah sesuai dengan "
                "tindakan yang diminta."
            )

        target.is_active = active

        target.save(
            update_fields=["is_active"]
        )

    return AccountAccessChange.objects.create(
        user=target,
        actor=actor,
        action=action,
        reason=reason,
    )
