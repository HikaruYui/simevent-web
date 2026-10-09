# Fungsi file: Konfigurasi tampilan, action, dan pembatasan akses Django Admin untuk achievement, reward, dan kebijakan diskon.

from django.contrib import admin

from apps.accounts.admin_support import ReadOnlyAuditAdmin

from .models import Achievement, EventRewardPolicy, Reward, UserAchievement


class PlatformDefinitionAdmin(admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("accounts.manage_platform") and super().has_view_permission(
            request, obj,
        )

    def has_add_permission(self, request):
        return request.user.has_perm("accounts.manage_platform") and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("accounts.manage_platform") and super().has_change_permission(
            request, obj,
        )

    def has_delete_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_superuser
        )


@admin.register(Achievement)
class AchievementAdmin(PlatformDefinitionAdmin):
    list_display = ("code", "name", "scope_label", "required_count", "is_active")
    list_filter = ("is_active", "event_type")
    search_fields = ("code", "name")
    list_select_related = ("event_type",)


@admin.register(Reward)
class RewardAdmin(PlatformDefinitionAdmin):
    list_display = ("achievement", "percentage", "is_active")
    list_filter = ("is_active",)
    list_select_related = ("achievement",)
    search_fields = ("achievement__name",)


@admin.register(EventRewardPolicy)
class EventRewardPolicyAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("event", "accept_achievement_discount", "max_discount_percentage")
    list_select_related = ("event",)


@admin.register(UserAchievement)
class UserAchievementAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin):
    list_display = ("user", "achievement", "qualifying_count", "is_active", "awarded_at")
    list_filter = ("is_active", "achievement")
    list_select_related = ("user", "achievement")
