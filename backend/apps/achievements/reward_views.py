# Fungsi file: Endpoint policy reward milik event dan preview diskon untuk pengguna yang login.

from dataclasses import asdict
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from apps.events.models import Event
from apps.events.views import EventManagementMixin
from apps.registrations.views import ParticipantAccessMixin

from .discounts import DiscountService, RewardPolicyService
from .models import EventRewardPolicy


def policy_data(policy):
    return {
        "accept_achievement_discount": bool(policy and policy.accept_achievement_discount),
        "max_discount_percentage": policy.max_discount_percentage if policy else Decimal("0.00"),
    }


class EventRewardPolicyView(EventManagementMixin, View):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request, event_id):
        event = get_object_or_404(Event.objects.managed_by(request.user), pk=event_id)
        policy = EventRewardPolicy.objects.filter(event=event).first()
        return JsonResponse(policy_data(policy))

    def post(self, request, event_id):
        policy = RewardPolicyService(request.user).update(event_id, data=request.POST)
        return JsonResponse(policy_data(policy))


class DiscountQuoteView(ParticipantAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    def get(self, request, event_id):
        quote = DiscountService(request.user).quote(event_id)
        return JsonResponse({**asdict(quote), "preview_only": True})
