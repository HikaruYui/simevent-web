# Fungsi file: Pengujian app registrations: scan bersamaan agar hanya satu attendance tercatat.

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.events.models import Event
from apps.events.tests.support import published_event, setup_users
from apps.registrations.attendance import AttendanceService
from apps.registrations.models import Attendance
from apps.registrations.services import RegistrationService


class AttendanceConcurrencyTests(TransactionTestCase):
    def test_concurrent_scanners_preserve_one_attendance(self):
        owner, other, participant, admin = setup_users()
        event = published_event(owner, admin)
        registration = RegistrationService(participant).register(event.pk)
        token = registration.ticket.token
        now = timezone.now()
        Event.objects.filter(pk=event.pk).update(
            registration_open=now - timedelta(hours=1),
            registration_close=now, start_datetime=now,
        )
        barrier = Barrier(2)

        def scan(actor):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                attendance, created = AttendanceService(actor).scan(event.pk, token=token)
                return attendance.pk, created
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(scan, actor) for actor in (owner, admin)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(results[0][0], results[1][0])
        self.assertCountEqual([created for _, created in results], [True, False])
        self.assertEqual(Attendance.objects.count(), 1)
