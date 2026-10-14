# Fungsi file: Pengujian app achievements: konsistensi operasi bersamaan dan penguncian transaksi.

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from apps.events.tests.support import event_data, setup_users
from apps.events.workflow import EventWorkflow
from apps.registrations.attendance import AttendanceService

from ..discounts import RewardPolicyService
from ..models import Achievement, UserAchievement
from ..services import AchievementService
from .test_achievements import completed_registration


class AchievementConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner, self.other, self.participant, self.admin = setup_users()
        self.event, self.registration = completed_registration(
            self.owner, self.admin, self.participant,
        )
        Achievement.objects.create(code="one", name="One", required_count=1)

    def race(self, operations):
        barrier = Barrier(len(operations))

        def worker(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
                return "ok"
            except ValidationError:
                return "invalid"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(worker, operation) for operation in operations]
            return [future.result(timeout=20) for future in futures]

    def test_two_evaluations_assign_once(self):
        evaluate = lambda: AchievementService(self.participant).evaluate()
        self.assertEqual(self.race([evaluate, evaluate]), ["ok", "ok"])
        self.assertEqual(UserAchievement.objects.count(), 1)

    def test_evaluate_and_void_never_expose_stale_award(self):
        attendance_id = self.registration.attendance.pk
        results = self.race([
            lambda: AchievementService(self.participant).evaluate(),
            lambda: AttendanceService(self.admin).void(attendance_id, reason="Wrong scan"),
        ])
        self.assertEqual(results, ["ok", "ok"])
        self.assertFalse(UserAchievement.objects.eligible_for(self.participant).exists())
        AchievementService(self.participant).evaluate()
        self.assertFalse(UserAchievement.objects.active().exists())

    def test_policy_update_and_submit_share_event_lock(self):
        event = EventWorkflow(self.owner).create(data=event_data())
        results = self.race([
            lambda: EventWorkflow(self.owner).transition(event.pk, action="submit"),
            lambda: RewardPolicyService(self.owner).update(event.pk, data={
                "accept_achievement_discount": True, "max_discount_percentage": 10,
            }),
        ])
        self.assertEqual(results[0], "ok")
        with self.assertRaises(ValidationError):
            RewardPolicyService(self.owner).update(event.pk, data={
                "accept_achievement_discount": False, "max_discount_percentage": 0,
            })
