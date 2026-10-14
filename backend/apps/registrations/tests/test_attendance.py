# Fungsi file: Pengujian app registrations: scan QR, validitas tiket, attendance, void, dan pembatasan akses.

from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.events.models import Event, EventAccess, EventStatus
from apps.events.tests.support import published_event, setup_users
from apps.registrations.attendance import AttendanceService
from apps.registrations.models import Attendance, Ticket
from apps.registrations.services import RegistrationService


class AttendanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.event = published_event(cls.owner, cls.admin)
        cls.registration = RegistrationService(cls.participant).register(cls.event.pk)
        cls.token = cls.registration.ticket.token

    def scan(self, actor=None, token=None):
        with patch("apps.registrations.attendance.timezone.now", return_value=self.event.start_datetime):
            return AttendanceService(actor or self.owner).scan(
                self.event.pk, token=token or self.token,
            )

    def test_valid_scan_and_duplicate_preserve_original_verifier(self):
        attendance, created = self.scan()
        repeated, created_again = self.scan(self.admin)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(attendance.pk, repeated.pk)
        self.assertEqual(repeated.verified_by, self.owner)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_only_owner_or_platform_admin_can_scan(self):
        with self.assertRaises(Http404):
            self.scan(self.other)
        with self.assertRaises(PermissionDenied):
            self.scan(self.participant)
        self.assertTrue(self.scan(self.admin)[1])

    def test_invalid_and_wrong_event_tokens_are_rejected(self):
        other_event = published_event(self.owner, self.admin)
        other_registration = RegistrationService(self.participant).register(other_event.pk)
        for token in ("invalid", str(uuid4()), other_registration.ticket.token):
            with self.subTest(token=token), self.assertRaises(ValidationError):
                self.scan(token=token)
        self.assertFalse(Attendance.objects.exists())

    def test_scan_time_boundaries(self):
        service = AttendanceService(self.owner)
        for now in (self.event.start_datetime - timedelta(microseconds=1), self.event.end_datetime):
            with patch("apps.registrations.attendance.timezone.now", return_value=now):
                with self.assertRaises(ValidationError):
                    service.scan(self.event.pk, token=self.token)
        self.assertTrue(self.scan()[1])

    def test_cancelled_registration_and_rotated_token_are_rejected(self):
        RegistrationService(self.participant).cancel(self.registration.pk)
        with self.assertRaises(ValidationError):
            self.scan()
        renewed = RegistrationService(self.participant).register(self.event.pk)
        with self.assertRaises(ValidationError):
            self.scan()
        self.assertTrue(self.scan(token=renewed.ticket.token)[1])

    def test_inactive_ticket_participant_and_scanner_are_rejected(self):
        Ticket.objects.filter(registration=self.registration).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.scan()
        Ticket.objects.filter(registration=self.registration).update(is_active=True)
        type(self.participant).objects.filter(pk=self.participant.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.scan()
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.scan()

    def test_event_must_still_be_published(self):
        for status in EventStatus.values:
            if status == EventStatus.PUBLISHED:
                continue
            Event.objects.filter(pk=self.event.pk).update(status=status)
            with self.subTest(status=status), self.assertRaises(ValidationError):
                self.scan()
        self.assertFalse(Attendance.objects.exists())

    def test_stale_scanner_permissions_are_rechecked(self):
        self.owner.get_all_permissions()
        self.owner.groups.clear()
        with self.assertRaises(PermissionDenied):
            self.scan()

    def test_attendance_failure_does_not_consume_ticket(self):
        with patch("apps.registrations.attendance.Attendance.objects.create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.scan()
        self.assertFalse(Attendance.objects.exists())
        self.assertTrue(Ticket.objects.get(registration=self.registration).is_active)

    def test_unique_attendance_enforced_by_database(self):
        self.scan()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attendance.objects.create(registration=self.registration, verified_by=self.owner)

    def test_void_is_admin_only_and_cannot_be_undone_by_rescan(self):
        attendance, _ = self.scan()
        with self.assertRaises(PermissionDenied):
            AttendanceService(self.owner).void(attendance.pk, reason="Mistake")
        with self.assertRaises(ValidationError):
            AttendanceService(self.admin).void(attendance.pk, reason="")
        with patch("apps.registrations.attendance.timezone.now", return_value=self.event.end_datetime):
            result = AttendanceService(self.admin).void(attendance.pk, reason="Wrong attendee")
        self.assertEqual(result.status, Attendance.Status.VOIDED)
        self.assertEqual(result.voided_by, self.admin)
        with self.assertRaises(ValidationError):
            self.scan()
        with self.assertRaises(ValidationError):
            AttendanceService(self.admin).void(attendance.pk, reason="Again")

    def test_void_state_database_constraints(self):
        attendance, _ = self.scan()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attendance.objects.filter(pk=attendance.pk).update(status="VOIDED")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attendance.objects.filter(pk=attendance.pk).update(
                status="VOIDED", void_reason="Reason", voided_by=self.admin,
                voided_at=attendance.checked_in_at - timedelta(seconds=1),
            )

    def test_scan_http_csrf_methods_and_duplicate_response(self):
        url = reverse("registrations:scan", args=[self.event.pk])
        self.assertEqual(self.client.post(url, {"token": self.token}).status_code, 401)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(url, {"token": self.token}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch("apps.registrations.attendance.timezone.now", return_value=self.event.start_datetime):
            first = self.client.post(url, {"token": self.token, "verified_by": self.other.pk})
            second = self.client.post(url, {"token": self.token})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["already_checked_in"])
        self.assertNotContains(second, str(self.token))
        self.assertIn("no-store", second["Cache-Control"])
        self.assertEqual(Attendance.objects.get().verified_by, self.owner)

    def test_attendance_detail_scope_and_participant_list(self):
        url = reverse("registrations:attendance", args=[self.registration.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get(url).json()["status"], "NOT_CHECKED_IN")
        self.scan()
        self.assertEqual(self.client.get(url).json()["status"], "PRESENT")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("registrations:participants", args=[self.event.pk]))
        self.assertEqual(response.json()["results"][0]["attendance"]["status"], "PRESENT")

    def test_qr_is_private_png_and_contains_only_token(self):
        url = reverse("registrations:ticket-qr", args=[self.registration.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.participant)
        response = self.client.get(url)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("no-store", response["Cache-Control"])
        image = Image.open(BytesIO(response.content))
        self.assertEqual(image.width, image.height)
        self.assertGreater(image.width, 200)
        self.assertEqual(image.getpixel((0, 0)), 255)
        with patch("apps.registrations.tickets.qrcode.make", wraps=__import__("qrcode").make) as encode:
            self.client.get(url)
        self.assertEqual(encode.call_args.args, (str(self.token),))
        RegistrationService(self.participant).cancel(self.registration.pk)
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_meeting_access_requires_own_valid_registration(self):
        EventAccess.objects.filter(event=self.event).update(meeting_url="https://meeting.example/secret")
        url = reverse("registrations:meeting", args=[self.registration.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get(url).json()["meeting_url"], "https://meeting.example/secret")
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.CANCELLED)
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_admin_void_action_uses_workflow_and_generic_edit_is_denied(self):
        attendance, _ = self.scan()
        self.client.force_login(self.admin)
        url = reverse("admin:registrations_attendance_changelist")
        data = {"action": "void", "_selected_action": attendance.pk, "reason": "Wrong scan"}
        self.client.post(url, data)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, Attendance.Status.PRESENT)
        with patch("apps.registrations.attendance.timezone.now", return_value=self.event.end_datetime):
            response = self.client.post(url, {**data, "confirm": "on"})
        self.assertEqual(response.status_code, 302)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, Attendance.Status.VOIDED)
        self.assertEqual(self.client.post(
            reverse("admin:registrations_attendance_change", args=[attendance.pk]),
            {"status": "PRESENT"},
        ).status_code, 403)
