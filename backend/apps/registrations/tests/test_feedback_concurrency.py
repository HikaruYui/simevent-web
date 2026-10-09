# Fungsi file: Pengujian app registrations: feedback bersamaan serta persaingan submit dan void attendance.

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from apps.events.tests.support import setup_users
from apps.registrations.attendance import AttendanceService
from apps.registrations.feedback import FeedbackService
from apps.registrations.models import Feedback

from .test_feedback import completed_registration, feedback_input


class FeedbackConcurrencyTests(TransactionTestCase):
    def setUp(self):
        owner, other, self.participant, self.admin = setup_users()
        self.event, self.registration = completed_registration(owner, self.admin, self.participant)

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

    def submit(self):
        return FeedbackService(self.participant).submit(
            self.registration.pk, data=feedback_input(),
        )

    def test_concurrent_submissions_create_one_feedback(self):
        self.assertCountEqual(self.race([self.submit, self.submit]), ["ok", "invalid"])
        self.assertEqual(Feedback.objects.count(), 1)

    def test_concurrent_void_and_submit_leave_no_eligible_feedback(self):
        attendance_id = self.registration.attendance.pk
        results = self.race([
            self.submit,
            lambda: AttendanceService(self.admin).void(attendance_id, reason="Wrong attendance"),
        ])
        self.assertEqual(results[1], "ok")
        self.assertLessEqual(Feedback.objects.count(), 1)
        self.assertFalse(Feedback.objects.eligible().exists())
