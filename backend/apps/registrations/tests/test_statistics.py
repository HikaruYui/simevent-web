# Fungsi file: Pengujian app registrations: akurasi statistik, ownership, pagination, dan jumlah query.

import json

from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event, EventStatus
from apps.events.tests.support import event_data, setup_users
from apps.registrations.models import Attendance, Feedback, RATING_FIELDS, Registration
from apps.registrations.statistics_views import EventStatisticsView, StatisticsOverviewView


class StatisticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()

    def event(self, owner=None, status=EventStatus.COMPLETED):
        data = event_data()
        data["event_type_id"] = data.pop("event_type")
        return Event.objects.create(
            organizer=owner or self.owner, status=status,
            slug=f"statistics-{Event.objects.count()}", **data,
        )

    def registration(self, event, *, participant=None, attendance=None, rating=None, cancelled=False):
        participant = participant or User.objects.create_user(
            f"statistics-{User.objects.count()}@example.test", None,
        )
        registration = Registration.objects.create(event=event, participant=participant)
        if cancelled:
            Registration.objects.filter(pk=registration.pk).update(
                status="CANCELLED", cancelled_at=timezone.now(),
            )
        if attendance:
            record = Attendance.objects.create(registration=registration, verified_by=self.owner)
            if attendance == "VOIDED":
                Attendance.objects.filter(pk=record.pk).update(
                    status="VOIDED", voided_at=timezone.now(), voided_by=self.admin,
                    void_reason="Invalid check-in",
                )
        if rating:
            Feedback.objects.create(
                registration=registration, comment="private feedback",
                **{field: rating for field in RATING_FIELDS},
            )
        return registration

    def detail(self, event):
        self.client.force_login(self.owner)
        return self.client.get(reverse("registrations:event-statistics", args=[event.pk])).json()

    def overview(self, user=None, **params):
        self.client.force_login(user or self.owner)
        return self.client.get(reverse("registrations:statistics"), params)

    def test_authentication_role_and_object_ownership(self):
        event = self.event()
        detail = reverse("registrations:event-statistics", args=[event.pk])
        overview = reverse("registrations:statistics")
        for url in (detail, overview):
            self.assertEqual(self.client.get(url).status_code, 401)
        for user, status in ((self.participant, 403), (self.other, 404), (self.owner, 200), (self.admin, 200)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(detail).status_code, status)
        self.assertEqual(self.overview(self.other).json()["results"], [])

    def test_staff_flag_does_not_grant_global_access(self):
        self.participant.is_staff = True
        self.participant.save(update_fields=["is_staff"])
        self.assertEqual(self.overview(self.participant).status_code, 403)

    def test_revoked_organizer_cannot_access(self):
        self.owner.groups.clear()
        self.assertEqual(self.overview().status_code, 403)

    def test_feedback_permission_required(self):
        permission = Permission.objects.get(content_type__app_label="registrations", codename="view_feedback")
        Group.objects.get(name="Organizer").permissions.remove(permission)
        self.assertEqual(self.overview().status_code, 403)

    def test_scope_cannot_be_overridden_and_admin_sees_all(self):
        own = self.event()
        self.event(owner=self.other)
        data = self.overview(organizer=self.other.pk, user=self.owner).json()
        self.assertEqual(data["summary"]["total_events"], 1)
        self.assertEqual([row["id"] for row in data["results"]], [own.pk])
        self.assertEqual(self.overview(self.admin).json()["summary"]["total_events"], 2)

    def test_empty_dashboard(self):
        data = self.overview().json()
        self.assertEqual(data["results"], [])
        self.assertEqual(data["summary"]["total_events"], 0)
        self.assertEqual(data["summary"]["total_registrations"], 0)
        self.assertIsNone(data["summary"]["attendance_rate"])
        self.assertIsNone(data["summary"]["average_overall_rating"])

    def test_empty_event_has_no_rate_or_average(self):
        data = self.detail(self.event(status=EventStatus.DRAFT))
        self.assertEqual(data["total_registrations"], 0)
        self.assertIsNone(data["attendance_rate"])
        self.assertIsNone(data["average_overall_rating"])

    def test_counts_exclude_invalid_participation_without_losing_history(self):
        event = self.event()
        self.registration(event, attendance="PRESENT", rating=5)
        self.registration(event, attendance="VOIDED", rating=1)
        self.registration(event)
        self.registration(event, attendance="PRESENT", rating=1, cancelled=True)
        data = self.detail(event)
        for field, expected in {
            "total_registrations": 4, "active_registrations": 3,
            "cancelled_registrations": 1, "eligible_registrations": 3,
            "total_attendance": 1, "recorded_check_ins": 3,
            "voided_check_ins": 1, "feedback_count": 1, "unique_participants": 4,
            "attendance_rate": "33.33",
        }.items():
            self.assertEqual(data[field], expected, field)
        for field in RATING_FIELDS:
            self.assertEqual(data[f"average_{field}"], 5)

    def test_cancelled_event_has_history_but_no_eligible_attendance(self):
        event = self.event(status=EventStatus.CANCELLED)
        self.registration(event, attendance="PRESENT", rating=5)
        data = self.detail(event)
        self.assertEqual(data["active_registrations"], 1)
        self.assertEqual(data["recorded_check_ins"], 1)
        self.assertEqual(data["total_attendance"], 0)
        self.assertEqual(data["feedback_count"], 0)
        self.assertIsNone(data["attendance_rate"])

    def test_published_attendance_counts_but_feedback_requires_completion(self):
        event = self.event(status=EventStatus.PUBLISHED)
        self.registration(event, attendance="PRESENT", rating=5)
        data = self.detail(event)
        self.assertEqual(data["attendance_rate"], "100.00")
        self.assertEqual(data["feedback_count"], 0)
        self.assertIsNone(data["average_overall_rating"])

    def test_no_attendance_with_registrations_is_zero_percent(self):
        event = self.event()
        self.registration(event)
        self.assertEqual(self.detail(event)["attendance_rate"], "0.00")

    def test_reactivation_counts_registration_once(self):
        event = self.event()
        registration = self.registration(event, cancelled=True)
        Registration.objects.filter(pk=registration.pk).update(status="REGISTERED", cancelled_at=None)
        data = self.detail(event)
        self.assertEqual(data["total_registrations"], 1)
        self.assertEqual(data["cancelled_registrations"], 0)

    def test_summary_uses_weighted_totals_and_distinct_participants(self):
        first, second = self.event(), self.event()
        self.registration(first, participant=self.participant, attendance="PRESENT", rating=1)
        self.registration(second, participant=self.participant, attendance="PRESENT", rating=5)
        self.registration(second, attendance="PRESENT", rating=5)
        self.registration(second)
        data = self.overview().json()
        summary = data["summary"]
        self.assertEqual(summary["total_events"], 2)
        self.assertEqual(summary["events_by_status"]["COMPLETED"], 2)
        self.assertEqual(summary["unique_participants"], 3)
        self.assertEqual(summary["attendance_rate"], "75.00")
        self.assertAlmostEqual(summary["average_overall_rating"], 11 / 3)
        self.assertEqual(summary["feedback_count"], 3)
        second_data = next(row for row in data["results"] if row["id"] == second.pk)
        self.assertEqual(second_data["total_registrations"], 3)
        self.assertEqual(second_data["average_overall_rating"], 5)

    def test_summary_covers_every_page_and_status(self):
        for index in range(21):
            self.event(status=EventStatus.values[index % len(EventStatus.values)])
        data = self.overview(page=2).json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["summary"]["total_events"], 21)
        self.assertEqual(sum(data["summary"]["events_by_status"].values()), 21)
        self.assertEqual(data["pages"], 2)
        self.assertEqual(self.overview(page=3).status_code, 404)
        self.assertEqual(self.overview(page="invalid").status_code, 404)

    def test_readonly_uncached_and_no_sensitive_fields(self):
        event = self.event()
        self.registration(event, participant=self.participant, attendance="PRESENT", rating=5)
        self.client.force_login(self.owner)
        for url in (reverse("registrations:statistics"), reverse("registrations:event-statistics", args=[event.pk])):
            response = self.client.get(url)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertNotContains(response, self.participant.email)
            self.assertNotContains(response, "private feedback")
            for method in ("post", "put", "patch", "delete"):
                self.assertEqual(getattr(self.client, method)(url).status_code, 405)

    def test_detail_uses_two_data_queries(self):
        event = self.event()
        self.registration(event, attendance="PRESENT", rating=4)
        self.owner.get_all_permissions()
        request = RequestFactory().get("/")
        request.user = self.owner
        with self.assertNumQueries(2):
            response = EventStatisticsView.as_view()(request, event_id=event.pk)
        self.assertEqual(json.loads(response.content)["total_attendance"], 1)

    def test_overview_query_count_does_not_grow_with_event_count(self):
        self.owner.get_all_permissions()
        for count in (1, 20):
            while Event.objects.count() < count:
                self.registration(self.event(), attendance="PRESENT", rating=4)
            request = RequestFactory().get("/")
            request.user = self.owner
            with self.subTest(events=count), self.assertNumQueries(4):
                response = StatisticsOverviewView.as_view()(request)
            self.assertEqual(len(json.loads(response.content)["results"]), count)

    def test_feedback_statistics_match_existing_results(self):
        event = self.event()
        self.registration(event, attendance="PRESENT", rating=4)
        self.registration(event, attendance="VOIDED", rating=1)
        statistics = self.detail(event)
        summary = self.client.get(reverse("registrations:feedback-results", args=[event.pk])).json()["summary"]
        for field in ("feedback_count", *(f"average_{field}" for field in RATING_FIELDS)):
            self.assertEqual(statistics[field], summary[field])
