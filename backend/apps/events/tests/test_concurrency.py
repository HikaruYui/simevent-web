# Fungsi file: Pengujian app events: konsistensi operasi bersamaan dan penguncian transaksi.

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from apps.events.models import EventStatus
from apps.events.workflow import EventWorkflow

from .support import event_data, setup_users


class EventConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner, self.other, self.participant, self.admin = setup_users()

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

    def test_concurrent_approvals_create_one_transition(self):
        event = EventWorkflow(self.owner).create(data=event_data())
        EventWorkflow(self.owner).transition(event.pk, action="submit")
        approve = lambda: EventWorkflow(self.admin).transition(event.pk, action="approve")
        self.assertCountEqual(self.race([approve, approve]), ["ok", "invalid"])
        self.assertEqual(event.transitions.filter(to_status=EventStatus.APPROVED).count(), 1)

    def test_concurrent_submit_and_edit_cannot_modify_submitted_content(self):
        event = EventWorkflow(self.owner).create(data=event_data())
        results = self.race([
            lambda: EventWorkflow(self.owner).transition(event.pk, action="submit"),
            lambda: EventWorkflow(self.owner).update(event.pk, data=event_data(title="Updated before submission")),
        ])
        self.assertEqual(results[0], "ok")
        event.refresh_from_db()
        expected_title = "Updated before submission" if results[1] == "ok" else "Seminar SIMEVENT"
        self.assertEqual(event.title, expected_title)
        self.assertEqual(event.status, EventStatus.SUBMITTED)
        self.assertEqual(event.transitions.count(), 1)
