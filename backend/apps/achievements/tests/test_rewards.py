# Fungsi file: Pengujian app achievements: policy reward, perhitungan diskon, eligibility, dan akses endpoint.

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.events.models import Event, EventStatus, EventType
from apps.events.tests.support import event_data, setup_users
from apps.events.workflow import EventWorkflow
from apps.registrations.attendance import AttendanceService

from ..discounts import DiscountService, RewardPolicyService
from ..models import Achievement, EventRewardPolicy, Reward, UserAchievement
from ..services import AchievementService
from ..views import MyAchievementsView
from .test_achievements import completed_registration


class RewardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.source, cls.registration = completed_registration(
            cls.owner, cls.admin, cls.participant,
        )
        cls.achievement = Achievement.objects.create(code="attended", name="Attended", required_count=1)
        cls.reward = Reward.objects.create(achievement=cls.achievement, percentage="15.00")
        AchievementService(cls.participant).evaluate()
        cls.event = EventWorkflow(cls.owner).create(data=event_data(price="199.99"))
        RewardPolicyService(cls.owner).update(cls.event.pk, data={
            "accept_achievement_discount": True, "max_discount_percentage": "20.00",
        })

    def public_quote(self):
        # Paid publication remains unavailable in MVP. Trusted fixture lets pricing
        # tests exercise future published paid events without changing that rule.
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.PUBLISHED)
        return DiscountService(self.participant).quote(self.event.pk)

    def test_eligible_reward_uses_decimal_rounding(self):
        quote = self.public_quote()
        self.assertEqual(quote.discount_percentage, Decimal("15.00"))
        self.assertEqual(quote.discount_amount, Decimal("30.00"))
        self.assertEqual(quote.final_price, Decimal("169.99"))

    def test_highest_reward_wins_without_stacking_and_cap_applies(self):
        badge = Achievement.objects.create(code="second", name="Second", required_count=1)
        Reward.objects.create(achievement=badge, percentage=10)
        AchievementService(self.participant).evaluate()
        self.assertEqual(self.public_quote().discount_percentage, Decimal(15))
        EventRewardPolicy.objects.filter(event=self.event).update(max_discount_percentage=12)
        self.assertEqual(self.public_quote().discount_percentage, Decimal(12))

    def test_no_policy_or_refused_policy_gives_zero(self):
        EventRewardPolicy.objects.filter(event=self.event).delete()
        self.assertEqual(self.public_quote().discount_amount, Decimal(0))
        EventRewardPolicy.objects.create(event=self.event)
        self.assertEqual(self.public_quote().final_price, self.event.price)

    def test_no_award_no_attendance_or_disabled_reward_gives_zero(self):
        UserAchievement.objects.filter(user=self.participant).update(
            qualifying_count=999,
        )
        AttendanceService(self.admin).void(self.registration.attendance.pk, reason="Wrong check-in")
        self.assertEqual(self.public_quote().discount_amount, 0)
        self.assertTrue(UserAchievement.objects.get(user=self.participant).is_active)

    def test_inactive_reward_and_achievement_give_zero(self):
        Reward.objects.filter(pk=self.reward.pk).update(is_active=False)
        self.assertEqual(self.public_quote().discount_percentage, 0)
        Reward.objects.filter(pk=self.reward.pk).update(is_active=True)
        Achievement.objects.filter(pk=self.achievement.pk).update(is_active=False)
        self.assertEqual(self.public_quote().discount_percentage, 0)

    def test_changed_rule_and_type_are_checked_without_reconcile(self):
        Achievement.objects.filter(pk=self.achievement.pk).update(required_count=2)
        self.assertEqual(self.public_quote().discount_percentage, 0)
        workshop = EventType.objects.get(code="WORKSHOP")
        Achievement.objects.filter(pk=self.achievement.pk).update(
            required_count=1, event_type=workshop,
        )
        self.assertEqual(self.public_quote().discount_percentage, 0)

    def test_empty_awards_do_not_synthesize_discount(self):
        UserAchievement.objects.all().delete()
        self.assertEqual(self.public_quote().discount_percentage, 0)
        self.assertFalse(UserAchievement.objects.exists())

    def test_free_event_and_full_discount_never_go_negative(self):
        Event.objects.filter(pk=self.event.pk).update(price=0)
        self.assertEqual(self.public_quote().final_price, 0)
        Event.objects.filter(pk=self.event.pk).update(price=100)
        Reward.objects.filter(pk=self.reward.pk).update(percentage=100)
        EventRewardPolicy.objects.filter(event=self.event).update(max_discount_percentage=100)
        self.assertEqual(self.public_quote().final_price, 0)

    def test_draft_scope_and_current_account_are_enforced(self):
        for user in (self.participant, self.other):
            with self.assertRaises(Http404):
                DiscountService(user).quote(self.event.pk)
        self.assertEqual(DiscountService(self.owner).quote(self.event.pk).discount_percentage, 0)
        service = DiscountService(self.admin)
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            service.quote(self.event.pk)

    def test_organizer_cannot_update_other_policy_or_publish_paid_event(self):
        with self.assertRaises(Http404):
            RewardPolicyService(self.other).update(self.event.pk, data={})
        with self.assertRaises(PermissionDenied):
            RewardPolicyService(self.participant).update(self.event.pk, data={})
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).transition(self.event.pk, action="submit")

    def test_policy_is_frozen_during_review_approval_and_publication(self):
        for status in EventStatus.values:
            if status in (EventStatus.DRAFT, EventStatus.NEEDS_REVISION):
                continue
            Event.objects.filter(pk=self.event.pk).update(status=status)
            with self.subTest(status=status), self.assertRaises(ValidationError):
                RewardPolicyService(self.admin).update(self.event.pk, data={
                    "accept_achievement_discount": False, "max_discount_percentage": 0,
                })

    def test_disable_policy_and_reenable_during_revision(self):
        data = {"accept_achievement_discount": False, "max_discount_percentage": 0}
        policy = RewardPolicyService(self.owner).update(self.event.pk, data=data)
        self.assertFalse(policy.accept_achievement_discount)
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.NEEDS_REVISION)
        policy = RewardPolicyService(self.owner).update(self.event.pk, data={
            "accept_achievement_discount": True, "max_discount_percentage": 5,
        })
        self.assertEqual(policy.max_discount_percentage, 5)

    def test_invalid_policy_form_and_database_constraints(self):
        for enabled, value in ((True, 0), (True, 101), (True, -1), (False, 10)):
            with self.subTest(enabled=enabled, value=value):
                with self.assertRaises(ValidationError):
                    RewardPolicyService(self.owner).update(self.event.pk, data={
                        "accept_achievement_discount": enabled, "max_discount_percentage": value,
                    })
                with self.assertRaises(IntegrityError), transaction.atomic():
                    EventRewardPolicy.objects.filter(event=self.event).update(
                        accept_achievement_discount=enabled, max_discount_percentage=value,
                    )

    def test_reward_form_and_database_range_and_unique_relationship(self):
        for percentage in (0, -1, 101):
            self.reward.percentage = Decimal(percentage)
            with self.assertRaises(ValidationError):
                self.reward.full_clean()
            with self.assertRaises(IntegrityError), transaction.atomic():
                Reward.objects.filter(pk=self.reward.pk).update(percentage=percentage)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reward.objects.create(achievement=self.achievement, percentage=10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventRewardPolicy.objects.create(event=self.event)

    def test_http_policy_mass_assignment_and_csrf(self):
        url = reverse("achievements:policy", args=[self.event.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url, {}).status_code, 403)
        response = self.client.post(url, {
            "accept_achievement_discount": "on", "max_discount_percentage": "9.00",
            "event": self.source.pk, "organizer": self.other.pk, "status": "PUBLISHED",
        })
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.DRAFT)
        self.assertEqual(EventRewardPolicy.objects.get(event=self.event).max_discount_percentage, 9)

    def test_quote_is_private_readonly_and_ignores_client_price(self):
        self.public_quote()
        url = reverse("achievements:discount", args=[self.event.pk])
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_login(self.participant)
        response = self.client.get(url, {"price": 1, "percentage": 100, "user_id": self.owner.pk})
        self.assertEqual(response.json()["final_price"], "169.99")
        self.assertTrue(response.json()["preview_only"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_reconcile_csrf_and_get_has_no_writes(self):
        self.client.force_login(self.participant)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.participant)
        url = reverse("achievements:reconcile")
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 405)
        AttendanceService(self.admin).void(self.registration.attendance.pk, reason="Invalid")
        response = self.client.get(reverse("achievements:list"))
        self.assertEqual(response.json()["results"], [])
        assignment = UserAchievement.objects.get(user=self.participant)
        self.assertTrue(assignment.is_active)
        self.client.post(url, {"user_id": self.other.pk})
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_achievement_listing_does_not_have_n_plus_one(self):
        request = RequestFactory().get("/achievements/")
        request.user = self.participant
        with self.assertNumQueries(1):
            response = MyAchievementsView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_native_admin_reward_management_and_readonly_policy(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin:achievements_reward_change", args=[self.reward.pk]),
            {"achievement": self.achievement.pk, "percentage": "10.00", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.percentage, 10)
        policy = EventRewardPolicy.objects.get(event=self.event)
        self.assertEqual(self.client.post(
            reverse("admin:achievements_eventrewardpolicy_change", args=[policy.pk]),
            {"max_discount_percentage": 99},
        ).status_code, 403)
        self.owner.is_staff = True
        self.owner.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("admin:achievements_reward_changelist")).status_code, 403)

    def test_reactivation_reuses_assignment_after_new_valid_attendance(self):
        original = UserAchievement.objects.get(user=self.participant)
        AttendanceService(self.admin).void(self.registration.attendance.pk, reason="Invalid")
        AchievementService(self.participant).evaluate()
        completed_registration(self.owner, self.admin, self.participant)
        restored = AchievementService(self.participant).evaluate()[0]
        self.assertEqual(restored.pk, original.pk)
        self.assertEqual(restored.awarded_at, original.awarded_at)
        self.assertIsNone(restored.revoked_at)
