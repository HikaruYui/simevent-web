# Fungsi file: Pemeriksaan capability Organizer/Admin; ownership event diperiksa terpisah pada queryset.

from django.core.exceptions import PermissionDenied


def require_organizer(user):

    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied
    if not (
        user.has_perm("accounts.access_organizer")
        or user.has_perm("accounts.manage_platform")
    ):
        raise PermissionDenied
