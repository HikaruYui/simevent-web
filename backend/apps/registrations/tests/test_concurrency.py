# Fungsi file: Pengujian app registrations: konsistensi operasi bersamaan dan penguncian transaksi.

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.http import Http404
from django.test import TransactionTestCase

from apps.events.models import EventStatus
from apps.events.tests.support import published_event, setup_users
from apps.events.workflow import EventWorkflow
from apps.registrations.models import Registration, Ticket
from apps.registrations.services import RegistrationService


# OOP — Single inheritance: RegistrationConcurrencyTests mewarisi TransactionTestCase dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: TransactionTestCase juga menjadi induk class saudara lain di proyek.
class RegistrationConcurrencyTests(TransactionTestCase):
    # OOP — Method overriding: framework pengujian memanggil hook setUp milik subclass untuk menyiapkan/membersihkan fixture.
    def setUp(self):
        self.owner, self.other, self.participant, self.admin = setup_users()
        self.event = published_event(self.owner, self.admin, capacity=1)

    # OOP — Encapsulation: method race mengelompokkan operasi terkait objek RegistrationConcurrencyTests.
    def race(self, operations):
        barrier = Barrier(len(operations))

        def worker(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
                return "ok"
            except (ValidationError, Http404):
                return "invalid"
            finally:
                connections.close_all()

        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(worker, operation) for operation in operations]
            return [future.result(timeout=20) for future in futures]

    def test_two_participants_cannot_take_last_seat(self):
        results = self.race([
            lambda: RegistrationService(self.participant).register(self.event.pk),
            lambda: RegistrationService(self.other).register(self.event.pk),
        ])
        self.assertCountEqual(results, ["ok", "invalid"])
        self.assertEqual(Registration.objects.active().count(), 1)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_duplicate_requests_issue_one_ticket(self):
        register = lambda: RegistrationService(self.participant).register(self.event.pk)
        self.assertCountEqual(self.race([register, register]), ["ok", "invalid"])
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_registration_and_event_cancellation_are_serialized(self):
        results = self.race([
            lambda: RegistrationService(self.participant).register(self.event.pk),
            lambda: EventWorkflow(self.owner).transition(
                self.event.pk, action="cancel", reason="Event cancelled",
            ),
        ])
        self.assertEqual(results[1], "ok")
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.CANCELLED)
        for ticket in Ticket.objects.all():
            self.assertFalse(ticket.is_valid)
