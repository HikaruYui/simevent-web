# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk achievement, reward, dan kebijakan diskon.

from django.contrib import admin

from apps.accounts.admin_support import ReadOnlyAuditAdmin

from .models import Achievement, EventRewardPolicy, Reward, UserAchievement


# Inheritance: PlatformDefinitionAdmin mewarisi tampilan dan operasi pengelolaan model di Django admin.
# OOP — Hierarchical inheritance: class ini menjadi induk bersama bagi AchievementAdmin, RewardAdmin.
class PlatformDefinitionAdmin(admin.ModelAdmin):
    # Polymorphism: menyesuaikan izin melihat objek pada Django admin.
    def has_view_permission(self, request, obj=None):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        return request.user.has_perm("accounts.manage_platform") and super().has_view_permission(
            request, obj,
        )

    # Polymorphism: menyesuaikan izin menambah objek pada Django admin.
    def has_add_permission(self, request):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        return request.user.has_perm("accounts.manage_platform") and super().has_add_permission(request)

    # Polymorphism: menyesuaikan izin mengubah objek pada Django admin.
    def has_change_permission(self, request, obj=None):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        return request.user.has_perm("accounts.manage_platform") and super().has_change_permission(
            request, obj,
        )

    # Polymorphism: menyesuaikan izin menghapus objek pada Django admin.
    def has_delete_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_superuser
        )


# Inheritance: AchievementAdmin mewarisi perilaku PlatformDefinitionAdmin untuk diperluas sesuai kebutuhan class ini.
# OOP — Multilevel inheritance: admin.ModelAdmin → PlatformDefinitionAdmin → AchievementAdmin.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Achievement)
class AchievementAdmin(PlatformDefinitionAdmin):
    list_display = ("code", "name", "scope_label", "required_count", "is_active")
    list_filter = ("is_active", "event_type")
    search_fields = ("code", "name")
    list_select_related = ("event_type",)


# Inheritance: RewardAdmin mewarisi perilaku PlatformDefinitionAdmin untuk diperluas sesuai kebutuhan class ini.
# OOP — Multilevel inheritance: admin.ModelAdmin → PlatformDefinitionAdmin → RewardAdmin.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(Reward)
class RewardAdmin(PlatformDefinitionAdmin):
    list_display = ("achievement", "percentage", "is_active")
    list_filter = ("is_active",)
    list_select_related = ("achievement",)
    search_fields = ("achievement__name",)


# Inheritance (pewarisan ganda): EventRewardPolicyAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(EventRewardPolicy)
class EventRewardPolicyAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("event", "accept_achievement_discount", "max_discount_percentage")
    list_select_related = ("event",)


# Inheritance (pewarisan ganda): UserAchievementAdmin menggabungkan perilaku ReadOnlyAuditAdmin, admin.ModelAdmin.
# OOP — Multiple inheritance: ReadOnlyAuditAdmin, admin.ModelAdmin digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Class decorator / registration: mendaftarkan class ModelAdmin untuk model terkait.
@admin.register(UserAchievement)
class UserAchievementAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("user", "achievement", "qualifying_count", "is_active", "awarded_at")
    list_filter = ("is_active", "achievement")
    list_select_related = ("user", "achievement")
