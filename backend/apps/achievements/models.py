# Fungsi file: Model, relasi, queryset, dan constraint database untuk achievement, reward, dan kebijakan diskon.

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Achievement(models.Model):
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(max_length=2000, blank=True)
    event_type = models.ForeignKey(
        "events.EventType", on_delete=models.PROTECT,
        null=True, blank=True, related_name="achievements",
    )
    required_count = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("required_count", "name")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(required_count__gt=0),
                name="achievement_required_count_positive",
            ),
        ]

    @property
    def scope_label(self):
        return self.event_type.name if self.event_type_id else "All event types"

    def __str__(self):
        return self.name


class UserAchievementQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def eligible_for(self, user):
        if not user.is_authenticated or not user.is_active:
            return self.none()
        valid_attendance = models.Q(
            user__registrations__status="REGISTERED",
            user__registrations__attendance__status="PRESENT",
            user__registrations__event__status="COMPLETED",
        )
        matching_type = (
            models.Q(achievement__event_type__isnull=True)
            | models.Q(
                user__registrations__event__event_type_id=models.F("achievement__event_type_id")
            )
        )
        return self.active().filter(
            user=user, user__is_active=True, achievement__is_active=True,
        ).annotate(
            current_count=models.Count(
                "user__registrations", filter=valid_attendance & matching_type, distinct=True,
            ),
        ).filter(current_count__gte=models.F("achievement__required_count"))


class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="achievements",
    )
    achievement = models.ForeignKey(
        Achievement, on_delete=models.PROTECT, related_name="user_awards",
    )
    awarded_at = models.DateTimeField(default=timezone.now)
    qualifying_count = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = UserAchievementQuerySet.as_manager()

    class Meta:
        ordering = ("-awarded_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement"],
                name="user_achievement_unique_assignment",
            ),
            models.CheckConstraint(
                condition=models.Q(qualifying_count__gt=0),
                name="user_achievement_count_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(is_active=True, revoked_at__isnull=True)
                | models.Q(is_active=False, revoked_at__isnull=False),
                name="user_achievement_active_state_valid",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.achievement}"


class Reward(models.Model):
    achievement = models.OneToOneField(
        Achievement, on_delete=models.PROTECT, related_name="reward",
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100.00"))],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(percentage__gt=0, percentage__lte=100),
                name="reward_percentage_valid",
            ),
        ]

    def __str__(self):
        return f"{self.achievement}: {self.percentage}%"


class EventRewardPolicy(models.Model):
    event = models.OneToOneField(
        "events.Event", on_delete=models.CASCADE, related_name="reward_policy",
    )
    accept_achievement_discount = models.BooleanField(default=False)
    max_discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(accept_achievement_discount=False, max_discount_percentage=0)
                    | models.Q(
                        accept_achievement_discount=True,
                        max_discount_percentage__gt=0,
                        max_discount_percentage__lte=100,
                    )
                ),
                name="event_reward_policy_valid",
            ),
        ]

    def __str__(self):
        return f"Reward policy for event #{self.event_id}"
