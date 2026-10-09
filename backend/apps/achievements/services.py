# Fungsi file: Evaluasi threshold achievement serta pemberian, pencabutan, dan reaktivasi assignment.

from collections import defaultdict

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import lock_accounts
from apps.events.models import Event, EventStatus
from apps.registrations.models import Attendance, Registration, RegistrationStatus

from .models import Achievement, UserAchievement


class AchievementService:
    """Evaluate configurable achievement thresholds from valid attendance."""

    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk

    @staticmethod
    def _counts_for(user):
        rows = (
            Registration.objects.filter(
                participant=user,
                status=RegistrationStatus.REGISTERED,
                event__status=EventStatus.COMPLETED,
                attendance__status=Attendance.Status.PRESENT,
            )
            .values("event__event_type_id")
            .annotate(total=Count("event_id", distinct=True))
        )
        by_type = defaultdict(int)
        for row in rows:
            by_type[row["event__event_type_id"]] = row["total"]
        total = sum(by_type.values())
        return total, by_type

    # OOP — Abstraction: pemanggil meminta evaluasi tanpa mengatur penghitungan attendance dan pembaruan award.
    @transaction.atomic
    def evaluate(self, user_id=None):
        target_id = self._actor_id if user_id is None else user_id
        users = lock_accounts(self._actor_id, target_id)
        actor = users.get(self._actor_id)
        if actor is None or not actor.is_active:
            raise PermissionDenied
        if target_id != actor.pk and not actor.has_perm("accounts.manage_platform"):
            raise PermissionDenied
        target = get_object_or_404(User, pk=target_id)
        if not target.is_active:
            raise PermissionDenied
        list(Event.objects.filter(
            registrations__participant=target,
        ).order_by("pk").select_for_update(of=("self",)))
        achievements = list(Achievement.objects.order_by("pk").select_for_update())
        total, by_type = self._counts_for(target)
        assignments = {
            item.achievement_id: item
            for item in UserAchievement.objects.filter(user=target)
        }
        awarded = []
        for achievement in achievements:
            count = by_type[achievement.event_type_id] if achievement.event_type_id else total
            qualifies = achievement.is_active and count >= achievement.required_count
            assignment = assignments.get(achievement.pk)
            if qualifies and assignment is None:
                assignment = UserAchievement.objects.create(
                    user=target, achievement=achievement, qualifying_count=count,
                )
            elif qualifies and assignment and not assignment.is_active:
                assignment.is_active = True
                assignment.revoked_at = None
                assignment.qualifying_count = count
                assignment.save(update_fields=[
                    "is_active", "revoked_at", "qualifying_count",
                ])
            elif qualifies and assignment:
                if assignment.qualifying_count != count:
                    assignment.qualifying_count = count
                    assignment.save(update_fields=["qualifying_count"])
            elif assignment and assignment.is_active:
                assignment.is_active = False
                assignment.revoked_at = timezone.now()
                assignment.save(update_fields=["is_active", "revoked_at"])
            if assignment and assignment.is_active:
                awarded.append(assignment)
        return awarded

    def evaluate_all(self):
        actor = get_object_or_404(User, pk=self._actor_id)
        if not actor.has_perm("accounts.manage_platform"):
            raise PermissionDenied
        return [
            self.evaluate(user_id=user.pk)
            for user in User.objects.filter(is_active=True).only("pk")
        ]
