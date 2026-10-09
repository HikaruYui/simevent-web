# Fungsi file: Pengujian app events: transisi status, approval, izin, dan aturan proses bisnis.

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import AccountAccessChange, User
from apps.accounts.services import change_account_access
from apps.events.models import Event, EventAccess, EventStatus, EventTransition, EventType
from apps.events.workflow import EventWorkflow

from .support import event_data, published_event, setup_users


class EventWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()

    def draft(self, **overrides):
        return EventWorkflow(self.owner).create(data=event_data(**overrides))

    def test_four_initial_types_are_seeded(self):
        self.assertSetEqual(set(EventType.objects.values_list("code", flat=True)), {
            "CONFERENCE", "WORKSHOP", "SEMINAR", "WEBINAR",
        })

    def test_owner_creates_draft_and_slug_is_unique_and_stable(self):
        first = self.draft()
        second = self.draft()
        self.assertEqual(first.organizer, self.owner)
        self.assertEqual(first.status, EventStatus.DRAFT)
        self.assertNotEqual(first.slug, second.slug)
        updated = EventWorkflow(self.owner).update(first.pk, data=event_data(title="Judul berubah"))
        self.assertEqual(updated.slug, first.slug)

    def test_admin_creates_with_explicit_organizer(self):
        with self.assertRaises(ValidationError):
            EventWorkflow(self.admin).create(data=event_data())
        event = EventWorkflow(self.admin).create(data=event_data(organizer=self.owner.pk))
        self.assertEqual(event.organizer, self.owner)
        with self.assertRaises(ValidationError):
            EventWorkflow(self.admin).create(data=event_data(organizer=self.participant.pk))

    def test_creation_cannot_override_status_or_owner(self):
        event = self.draft(organizer=self.other.pk, status="PUBLISHED", slug="forged")
        self.assertEqual(event.organizer, self.owner)
        self.assertEqual(event.status, EventStatus.DRAFT)
        self.assertNotEqual(event.slug, "forged")

    def test_participant_and_staff_cannot_create_events(self):
        for staff in (False, True):
            self.participant.is_staff = staff
            self.participant.save()
            with self.subTest(staff=staff), self.assertRaises(PermissionDenied):
                EventWorkflow(self.participant).create(data=event_data())

    def test_services_reject_other_organizer_event(self):
        event = self.draft()
        workflow = EventWorkflow(self.other)
        for operation in (
            lambda: workflow.update(event.pk, data=event_data()),
            lambda: workflow.delete_draft(event.pk),
            lambda: workflow.transition(event.pk, action="submit"),
            lambda: workflow.transition(event.pk, action="cancel", reason="Attempt"),
        ):
            with self.assertRaises(Http404):
                operation()

    def test_organizer_cannot_review_publish_or_unpublish_even_with_direct_permission(self):
        event = self.draft()
        self.owner.user_permissions.add(Permission.objects.get(codename="publish_event"))
        for action in ("approve", "publish", "unpublish", "reject", "request_revision"):
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                EventWorkflow(self.owner).transition(event.pk, action=action, reason="Attempt")

    def test_draft_cannot_skip_to_published_even_for_admin(self):
        event = self.draft()
        with self.assertRaises(ValidationError):
            EventWorkflow(self.admin).transition(event.pk, action="publish")
        self.assertFalse(event.transitions.exists())

    def test_revision_then_approval_publication_and_unpublish(self):
        event = self.draft()
        owner, admin = EventWorkflow(self.owner), EventWorkflow(self.admin)
        owner.transition(event.pk, action="submit")
        admin.transition(event.pk, action="request_revision", reason="Lengkapi deskripsi")
        owner.update(event.pk, data=event_data(description="Deskripsi telah dilengkapi."))
        owner.transition(event.pk, action="submit")
        admin.transition(event.pk, action="approve")
        admin.transition(event.pk, action="publish")
        admin.transition(event.pk, action="unpublish", reason="Tinjau ulang")
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.APPROVED)
        self.assertEqual(list(event.transitions.values_list("to_status", flat=True)), [
            EventStatus.SUBMITTED, EventStatus.NEEDS_REVISION, EventStatus.SUBMITTED,
            EventStatus.APPROVED, EventStatus.PUBLISHED, EventStatus.APPROVED,
        ])
        self.assertFalse(Event.objects.public().filter(pk=event.pk).exists())
        admin.transition(event.pk, action="request_revision", reason="Perubahan substansial")
        owner.update(event.pk, data=event_data())

    def test_approve_and_unpublish_are_distinct_actions(self):
        event = self.draft()
        EventWorkflow(self.owner).transition(event.pk, action="submit")
        with self.assertRaises(ValidationError):
            EventWorkflow(self.admin).transition(event.pk, action="unpublish")
        EventWorkflow(self.admin).transition(event.pk, action="approve")
        EventWorkflow(self.admin).transition(event.pk, action="publish")
        with self.assertRaises(ValidationError):
            EventWorkflow(self.admin).transition(event.pk, action="approve")

    def test_submitted_and_published_content_cannot_be_edited_by_anyone(self):
        event = self.draft()
        EventWorkflow(self.owner).transition(event.pk, action="submit")
        for actor in (self.owner, self.admin):
            with self.assertRaises(ValidationError):
                EventWorkflow(actor).update(event.pk, data=event_data())
        EventWorkflow(self.admin).transition(event.pk, action="approve")
        EventWorkflow(self.admin).transition(event.pk, action="publish")
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).update(event.pk, data=event_data())

    def test_cancel_and_reject_require_reason_and_are_terminal(self):
        for action in ("cancel", "reject", "request_revision"):
            event = self.draft()
            EventWorkflow(self.owner).transition(event.pk, action="submit")
            with self.subTest(action=action), self.assertRaises(ValidationError):
                EventWorkflow(self.admin).transition(event.pk, action=action, reason="  ")
        for action in ("cancel", "reject"):
            event = self.draft()
            EventWorkflow(self.owner).transition(event.pk, action="submit")
            EventWorkflow(self.admin).transition(event.pk, action=action, reason="Keputusan admin")
            with self.assertRaises(ValidationError):
                EventWorkflow(self.owner).transition(event.pk, action="submit")

    def test_complete_only_after_end_and_no_unpublish_after_start(self):
        event = published_event(self.owner, self.admin)
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).transition(event.pk, action="complete")
        with patch("apps.events.workflow.timezone.now", return_value=event.start_datetime):
            self.assertTrue(event.is_ongoing)
            with self.assertRaises(ValidationError):
                EventWorkflow(self.admin).transition(event.pk, action="unpublish")
        with patch("apps.events.workflow.timezone.now", return_value=event.end_datetime):
            with self.assertRaises(ValidationError):
                EventWorkflow(self.owner).transition(event.pk, action="cancel", reason="Too late")
            completed = EventWorkflow(self.owner).transition(event.pk, action="complete")
        self.assertEqual(completed.status, EventStatus.COMPLETED)
        self.assertFalse(completed.is_ongoing)

    def test_paid_events_can_only_remain_drafts(self):
        event = self.draft(price="50000.00")
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).transition(event.pk, action="submit")

    def test_online_hybrid_and_offline_require_correct_information_at_submission(self):
        for mode, venue, url in (
            ("OFFLINE", "", ""), ("ONLINE", "", ""),
            ("HYBRID", "Auditorium", ""), ("HYBRID", "", "https://meeting.example/secret"),
        ):
            event = self.draft(delivery_mode=mode, venue=venue, meeting_url=url)
            with self.subTest(mode=mode, venue=venue, url=url), self.assertRaises(ValidationError):
                EventWorkflow(self.owner).transition(event.pk, action="submit")
        event = self.draft(delivery_mode="ONLINE", venue="", meeting_url="https://meeting.example/secret")
        self.assertEqual(EventWorkflow(self.owner).transition(event.pk, action="submit").status, EventStatus.SUBMITTED)

    def test_inactive_event_type_and_past_event_fail_submission(self):
        event = self.draft()
        EventType.objects.filter(pk=event.event_type_id).update(is_active=False)
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).transition(event.pk, action="submit")
        EventType.objects.filter(pk=event.event_type_id).update(is_active=True)
        with patch("apps.events.workflow.timezone.now", return_value=event.start_datetime):
            with self.assertRaises(ValidationError):
                EventWorkflow(self.owner).transition(event.pk, action="submit")

    def test_stale_owner_cannot_edit_after_revocation(self):
        event = self.draft()
        self.assertTrue(self.owner.has_perm("events.change_event"))
        change_account_access(actor=self.admin, user_id=self.owner.pk,
                              action=AccountAccessChange.Action.REVOKE_ORGANIZER, reason="Revoked")
        with self.assertRaises(PermissionDenied):
            EventWorkflow(self.owner).update(event.pk, data=event_data())

    def test_admin_can_unpublish_when_owner_is_suspended(self):
        event = published_event(self.owner, self.admin)
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        updated = EventWorkflow(self.admin).transition(event.pk, action="unpublish")
        self.assertEqual(updated.status, EventStatus.APPROVED)
        with self.assertRaises(ValidationError):
            EventWorkflow(self.admin).transition(event.pk, action="publish")

    def test_transition_audit_failure_rolls_back_status(self):
        event = self.draft()
        with patch("apps.events.workflow.EventTransition.objects.create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                EventWorkflow(self.owner).transition(event.pk, action="submit")
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.DRAFT)
        self.assertFalse(EventTransition.objects.exists())

    def test_event_and_access_are_atomic(self):
        with patch("apps.events.workflow.EventAccess.objects.update_or_create", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                self.draft()
        self.assertFalse(Event.objects.exists())

    def test_only_draft_can_be_deleted_and_private_access_is_removed(self):
        event = self.draft()
        EventWorkflow(self.owner).delete_draft(event.pk)
        self.assertFalse(Event.objects.exists())
        self.assertFalse(EventAccess.objects.exists())
        event = self.draft()
        EventWorkflow(self.owner).transition(event.pk, action="submit")
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).delete_draft(event.pk)

    def test_form_and_database_invariants(self):
        now = timezone.now()
        for invalid in (
            {"capacity": 0}, {"price": "-1"}, {"delivery_mode": "OTHER"},
            {"end_datetime": now}, {"registration_close": now - timedelta(days=2)},
            {"registration_close": now + timedelta(days=20)},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.draft(**invalid)
        event = self.draft()
        for invalid in (
            {"capacity": 0}, {"price": -1}, {"delivery_mode": "OTHER"},
            {"status": "OTHER"}, {"end_datetime": event.start_datetime},
            {"registration_close": event.registration_open},
            {"registration_close": event.end_datetime},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(IntegrityError), transaction.atomic():
                Event.objects.filter(pk=event.pk).update(**invalid)
