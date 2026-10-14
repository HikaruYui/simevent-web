# Fungsi file: Pengujian app achievements: eligibility, threshold, assignment, dan authorization achievement.

from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event, EventType
from apps.events.tests.support import published_event, setup_users
from apps.events.workflow import EventWorkflow
from apps.registrations.attendance import AttendanceService
from apps.registrations.services import RegistrationService

from ..models import Achievement, UserAchievement
from ..services import AchievementService


def completed_registration(owner, admin, participant, event_type=None):
    options = {"event_type": event_type.pk} if event_type else {}
    event = published_event(owner, admin, **options)
    registration = RegistrationService(participant).register(event.pk)
    now = timezone.now()
    Event.objects.filter(pk=event.pk).update(
        registration_open=now - timedelta(days=2),
        registration_close=now - timedelta(hours=3),
        start_datetime=now - timedelta(hours=2),
        end_datetime=now - timedelta(hours=1),
    )
    event.refresh_from_db()
    with patch("apps.registrations.attendance.timezone.now", return_value=event.start_datetime):
        AttendanceService(owner).scan(event.pk, token=registration.ticket.token)
    EventWorkflow(owner).transition(event.pk, action="complete")
    event.refresh_from_db()
    return event, registration


class AchievementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.seminar = EventType.objects.get(code="SEMINAR")
        cls.workshop = EventType.objects.get_or_create(
            code="WORKSHOP", defaults={"name": "Workshop"},
        )[0]

    def setUp(self):
        self.achievement = Achievement.objects.create(
            code="seminar-hero", name="Seminar Hero", event_type=self.seminar,
            required_count=2,
        )

    def complete(self, participant=None, event_type=None):
        return completed_registration(
            self.owner, self.admin, participant or self.participant, event_type or self.seminar,
        )

    def test_registration_or_attendance_before_completion_does_not_award(self):
        event = published_event(self.owner, self.admin, event_type=self.seminar.pk)
        registration = RegistrationService(self.participant).register(event.pk)
        self.assertEqual(AchievementService(self.participant).evaluate(), [])
        with patch("apps.registrations.attendance.timezone.now", return_value=event.start_datetime):
            AttendanceService(self.owner).scan(event.pk, token=registration.ticket.token)
        self.assertEqual(AchievementService(self.participant).evaluate(), [])
        self.assertFalse(UserAchievement.objects.exists())

    def test_type_and_total_thresholds_are_configurable(self):
        total = Achievement.objects.create(
            code="event-explorer", name="Event Explorer", required_count=2,
        )
        self.complete()
        self.complete()
        awards = AchievementService(self.participant).evaluate()
        self.assertCountEqual([item.achievement_id for item in awards], [self.achievement.pk, total.pk])

    def test_type_scope_excludes_other_event_types(self):
        self.complete(event_type=self.workshop)
        self.complete(event_type=self.seminar)
        self.assertEqual(AchievementService(self.participant).evaluate(), [])
        self.complete(event_type=self.seminar)
        self.assertEqual(len(AchievementService(self.participant).evaluate()), 1)

    def test_voided_attendance_is_not_counted_and_revokes_active_assignment(self):
        self.complete()
        self.complete()
        awards = AchievementService(self.participant).evaluate()
        self.assertEqual(len(awards), 1)
        AttendanceService(self.admin).void(
            self.participant.registrations.first().attendance.pk, reason="Invalid scan",
        )
        self.assertEqual(AchievementService(self.participant).evaluate(), [])
        assignment = UserAchievement.objects.get()
        self.assertFalse(assignment.is_active)
        self.assertIsNotNone(assignment.revoked_at)

    def test_cancelled_registration_is_not_counted(self):
        event, registration = self.complete()
        registration.status = "CANCELLED"
        registration.cancelled_at = timezone.now()
        registration.save(update_fields=["status", "cancelled_at", "updated_at"])
        self.assertEqual(AchievementService(self.participant).evaluate(), [])

    def test_assignment_is_unique_and_reactivation_preserves_award(self):
        self.complete()
        self.complete()
        first = AchievementService(self.participant).evaluate()[0]
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserAchievement.objects.create(
                user=self.participant, achievement=self.achievement,
                qualifying_count=2,
            )
        self.assertEqual(AchievementService(self.participant).evaluate()[0].pk, first.pk)

    def test_suspended_actor_and_other_user_are_denied(self):
        with self.assertRaises(PermissionDenied):
            AchievementService(self.participant).evaluate(user_id=self.other.pk)
        User.objects.filter(pk=self.participant.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            AchievementService(self.participant).evaluate()

    def test_admin_can_evaluate_other_users(self):
        self.complete(self.other)
        self.assertEqual(AchievementService(self.admin).evaluate(user_id=self.other.pk), [])

    def test_deactivated_achievement_is_hidden_and_revoked(self):
        self.complete()
        self.complete()
        self.assertEqual(len(AchievementService(self.participant).evaluate()), 1)
        Achievement.objects.filter(pk=self.achievement.pk).update(is_active=False)
        self.assertEqual(AchievementService(self.participant).evaluate(), [])
        self.assertFalse(UserAchievement.objects.get().is_active)

    def test_database_constraints(self):
        for value in (0, -1):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Achievement.objects.create(
                    code=f"bad-{value}", name="Bad", required_count=value,
                )
        self.complete()
        self.complete()
        assignment = AchievementService(self.participant).evaluate()[0]
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserAchievement.objects.filter(pk=assignment.pk).update(
                is_active=False, revoked_at=None,
            )

    def test_http_is_private_and_evaluates_current_user(self):
        url = reverse("achievements:list")
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_login(self.participant)
        self.assertEqual(self.client.post(url).status_code, 405)
        self.complete()
        self.complete()
        self.assertEqual(self.client.get(url).json()["results"], [])
        self.assertFalse(UserAchievement.objects.exists())
        self.assertEqual(self.client.post(reverse("achievements:reconcile")).status_code, 200)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotContains(response, self.participant.email)

    def test_admin_manage_definitions_but_not_assignments(self):
        self.client.force_login(self.admin)
        add_url = reverse("admin:achievements_achievement_add")
        self.assertEqual(self.client.post(add_url, {
            "code": "new-badge", "name": "New Badge", "required_count": 3,
        }).status_code, 302)
        achievement = Achievement.objects.get(code="new-badge")
        self.assertEqual(self.client.post(
            reverse("admin:achievements_achievement_delete", args=[achievement.pk]),
        ).status_code, 403)
        self.client.get(reverse("admin:achievements_userachievement_changelist"))
        self.assertEqual(self.client.post(
            reverse("admin:achievements_userachievement_change", args=[1]),
        ).status_code, 403)
