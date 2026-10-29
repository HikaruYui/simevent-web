# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk akun, autentikasi, dan hak akses.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .admin_support import ReadOnlyAuditAdmin, ReasonActionForm, run_single_action
from .forms import AccountChangeForm, RegistrationForm
from .models import AccountAccessChange, User
from .role_service import set_account_role, promote_platform_admin
from .services import change_account_access


# Inheritance: AccountAdmin mewarisi perilaku UserAdmin untuk diperluas sesuai kebutuhan class ini.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(User)
class AccountAdmin(UserAdmin):
    add_form = RegistrationForm
    form = AccountChangeForm

    ordering = ("email",)

    list_display = (
        "email",
        "first_name",
        "last_name",
        "role_label",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
        "nim",
        "prodi",
        "ktp_number",
    )

    fieldsets = (
        (None, {"fields": ("email",)}),
        (
            "Profil",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "nim",
                    "prodi",
                    "ktp_number",
                    "gender",
                    "birth_place",
                    "birth_date",
                    "address",
                    "phone_number",
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
        ("Tanggal", {"fields": ("last_login", "date_joined")}),
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
        "set_participant",
        "set_committee",
        "set_organizer",
        "suspend_account",
        "activate_account",
        "set_platform_admin",
    )

    # OOP — Encapsulation: method role_label mengelompokkan operasi terkait objek AccountAdmin.
    # OOP — Method decorator: menambahkan metadata presentasi yang dibaca Django admin.
    @admin.display(description="Role")
    def role_label(self, obj):
        return {
            "PARTICIPANT": "Peserta",
            "COMMITTEE": "Panitia",
            "ORGANIZER": "Ketua Panitia",
            "ADMIN": "Admin Platform",
        }.get(obj.role, obj.role)

    # Polymorphism: menyesuaikan izin melihat objek pada Django admin.
    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.has_perm("accounts.manage_platform")
    
    # OOP — Polymorphism: has_promote_admin_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_promote_admin_permission(self, request):
        return (
            request.user.is_authenticated
            and request.user.is_active
            and request.user.is_superuser
        )

    # OOP — Encapsulation: method set_platform_admin mengelompokkan operasi terkait objek AccountAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(
        description="Jadikan Admin Platform",
        permissions=["promote_admin"],
    )
    def set_platform_admin(self, request, queryset):
        run_single_action(
            self,
            request,
            queryset,
            lambda pk, reason: promote_platform_admin(
                actor=request.user,
                user_id=pk,
                reason=reason,
            ),
        )

    # Polymorphism: menyesuaikan izin menambah objek pada Django admin.
    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    # Polymorphism: menyesuaikan izin mengubah objek pada Django admin.
    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    # Polymorphism: menyesuaikan izin menghapus objek pada Django admin.
    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    # OOP — Polymorphism: has_organizer_access_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_organizer_access_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("accounts.manage_organizer_access")
        )

    # OOP — Polymorphism: has_account_state_permission menyediakan hook khusus yang dipanggil melalui kontrak framework.
    def has_account_state_permission(self, request):
        return (
            request.user.has_perm("accounts.manage_platform")
            and request.user.has_perm("accounts.manage_accounts")
        )

    # Encapsulation: helper berawalan _ menandai detail internal class menurut konvensi Python.
    def _access_action(self, request, queryset, action):
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

    # OOP — Encapsulation: _role_action adalah helper internal menurut konvensi underscore Python, bukan akses private yang dipaksakan.
    def _role_action(self, request, queryset, role):
        run_single_action(
            self,
            request,
            queryset,
            lambda pk, reason: set_account_role(
                actor=request.user,
                user_id=pk,
                role=role,
                reason=reason,
            ),
        )

    # OOP — Encapsulation: method set_participant mengelompokkan operasi terkait objek AccountAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Jadikan Peserta", permissions=["organizer_access"])
    def set_participant(self, request, queryset):
        self._role_action(request, queryset, "PARTICIPANT")

    # OOP — Encapsulation: method set_committee mengelompokkan operasi terkait objek AccountAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Jadikan Panitia", permissions=["organizer_access"])
    def set_committee(self, request, queryset):
        self._role_action(request, queryset, "COMMITTEE")

    # OOP — Encapsulation: method set_organizer mengelompokkan operasi terkait objek AccountAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Jadikan Ketua Panitia", permissions=["organizer_access"])
    def set_organizer(self, request, queryset):
        self._role_action(request, queryset, "ORGANIZER")

    # OOP — Encapsulation: method suspend_account mengelompokkan operasi terkait objek AccountAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Tangguhkan akun", permissions=["account_state"])
    def suspend_account(self, request, queryset):
        self._access_action(request, queryset, AccountAccessChange.Action.SUSPEND)

    # OOP — Encapsulation: method activate_account mengelompokkan operasi terkait objek AccountAdmin.
    # OOP — Method decorator: menambahkan metadata action yang dibaca Django admin.
    @admin.action(description="Aktifkan akun", permissions=["account_state"])
    def activate_account(self, request, queryset):
        self._access_action(request, queryset, AccountAccessChange.Action.ACTIVATE)


# Inheritance (pewarisan ganda): AccountAccessChangeAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(AccountAccessChange)
class AccountAccessChangeAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("user", "action", "actor", "created_at")
    list_select_related = ("user", "actor")
    list_filter = ("action",)
    search_fields = ("user__email", "actor__email")
