# Fungsi file: Perubahan policy reward dan perhitungan preview diskon dari achievement yang masih layak.

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import require_organizer
from apps.accounts.services import lock_accounts
from apps.events.models import Event, EventStatus

from .forms import EventRewardPolicyForm
from .models import EventRewardPolicy, UserAchievement


class RewardPolicyService:
    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk

    @transaction.atomic
    def update(self, event_id, *, data):
        actor = lock_accounts(self._actor_id).get(self._actor_id)
        if actor is None:
            raise PermissionDenied
        require_organizer(actor)
        event = get_object_or_404(
            Event.objects.managed_by(actor).select_for_update(), pk=event_id,
        )
        if not actor.has_perm("events.change_event"):
            raise PermissionDenied
        if not event.is_editable:
            raise ValidationError("Reward policy can only change in draft or revision.")
        policy = EventRewardPolicy.objects.filter(event=event).first()
        form = EventRewardPolicyForm(data, instance=policy or EventRewardPolicy(event=event))
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        return form.save()


@dataclass(frozen=True)
class DiscountQuote:
    original_price: Decimal
    discount_percentage: Decimal
    discount_amount: Decimal
    final_price: Decimal
    reward_id: int | None


class DiscountService:
    """Return a nonbinding preview using current eligibility; never charge money."""

    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk

    # OOP — Abstraction: menyediakan hasil preview tanpa pemanggil mengatur pemilihan reward dan pembulatan diskon.
    def quote(self, event_id):
        actor = get_object_or_404(User, pk=self._actor_id)
        if not actor.is_active:
            raise PermissionDenied
        visible = Event.objects.public() | Event.objects.managed_by(actor)
        event = get_object_or_404(visible, pk=event_id)
        if event.status in (EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.REJECTED):
            raise ValidationError("This event no longer accepts a discount preview.")
        if event.start_datetime <= timezone.now():
            raise ValidationError("Discount previews require an upcoming event.")
        policy = EventRewardPolicy.objects.filter(event=event).first()
        percentage = Decimal("0.00")
        reward_id = None
        if policy and policy.accept_achievement_discount:
            best = (
                UserAchievement.objects.eligible_for(actor)
                .filter(achievement__reward__is_active=True)
                .order_by("-achievement__reward__percentage", "achievement__reward__pk")
                .values("achievement__reward__percentage", "achievement__reward__pk")
                .first()
            )
            if best:
                percentage = min(
                    best["achievement__reward__percentage"], policy.max_discount_percentage,
                )
                reward_id = best["achievement__reward__pk"]
        amount = (event.price * percentage / Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        return DiscountQuote(event.price, percentage, amount, event.price - amount, reward_id)
