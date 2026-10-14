# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk akun, autentikasi, dan hak akses.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .admin_support import (
    ReadOnlyAuditAdmin,
    ReasonActionForm,
    run_single_action,
)
from .forms import AccountChangeForm, RegistrationForm
from .models import AccountAccessChange, User
from .services import change_account_access


@admin.register(User)
class AccountAdmin(UserAdmin):
    add_form = RegistrationForm
    form = AccountChangeForm

    ordering = ("email",)

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
    )

    fieldsets = (
    (
        None,
        {
            "fields": (
                "email",
            )
        },
    ),
    (
        "Profil",
        {
            "fields": (
                "first_name",
                "last_name",
            )
        },
    ),
    (
        "Akses",
        {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        },
    ),
    (
        "Tanggal",
        {
            "fields": (
                "last_login",
                "date_joined",
            )
        },
    ),
)

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    readonly_fields = (
        "last_login",
        "date_joined",
        "is_active",
        "groups",
        "user_permissions",
    )

    action_form = ReasonActionForm

    actions = (
        "grant_organizer",
        "revoke_organizer",
        "suspend_account",
        "activate_account",
    )

    def has_view_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.has_perm(
                "accounts.manage_platform"
            )
        )

    def has_add_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_superuser
        )

    def has_change_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_superuser
        )

    def has_delete_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_superuser
        )

    def has_organizer_access_permission(
        self,
        request,
    ):
        return (
            request.user.has_perm(
                "accounts.manage_platform"
            )
            and request.user.has_perm(
                "accounts.manage_organizer_access"
            )
        )

    def has_account_state_permission(
        self,
        request,
    ):
        return (
            request.user.has_perm(
                "accounts.manage_platform"
            )
            and request.user.has_perm(
                "accounts.manage_accounts"
            )
        )

    def _access_action(
        self,
        request,
        queryset,
        action,
    ):
        run_single_action(
            self,
            request,
            queryset,
            lambda pk, reason: change_account_access(
                actor=request.user,
                user_id=pk,
                action=action,
                reason=reason,
            ),
        )

    @admin.action(
        description="Berikan akses Panitia",
        permissions=["organizer_access"],
    )
    def grant_organizer(
        self,
        request,
        queryset,
    ):
        self._access_action(
            request,
            queryset,
            AccountAccessChange.Action.GRANT_ORGANIZER,
        )

    @admin.action(
        description="Cabut akses Panitia",
        permissions=["organizer_access"],
    )
    def revoke_organizer(
        self,
        request,
        queryset,
    ):
        self._access_action(
            request,
            queryset,
            AccountAccessChange.Action.REVOKE_ORGANIZER,
        )

    @admin.action(
        description="Tangguhkan akun",
        permissions=["account_state"],
    )
    def suspend_account(
        self,
        request,
        queryset,
    ):
        self._access_action(
            request,
            queryset,
            AccountAccessChange.Action.SUSPEND,
        )

    @admin.action(
        description="Aktifkan akun",
        permissions=["account_state"],
    )
    def activate_account(
        self,
        request,
        queryset,
    ):
        self._access_action(
            request,
            queryset,
            AccountAccessChange.Action.ACTIVATE,
        )


@admin.register(AccountAccessChange)
class AccountAccessChangeAdmin(
    ReadOnlyAuditAdmin,
    admin.ModelAdmin,
):
    list_display = (
        "user",
        "action",
        "actor",
        "created_at",
    )

    list_select_related = (
        "user",
        "actor",
    )

    list_filter = (
        "action",
    )

    search_fields = (
        "user__email",
        "actor__email",
    )
