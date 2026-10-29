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


# Inheritance (pewarisan ganda): EventRewardPolicyView menggabungkan perilaku EventManagementMixin, View.
class EventRewardPolicyView(EventManagementMixin, View):
    http_method_names = ["get", "post", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, event_id):
        event = get_object_or_404(Event.objects.managed_by(request.user), pk=event_id)
        policy = EventRewardPolicy.objects.filter(event=event).first()
        return JsonResponse(policy_data(policy))

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, event_id):
        policy = RewardPolicyService(request.user).update(event_id, data=request.POST)
        return JsonResponse(policy_data(policy))


# Inheritance (pewarisan ganda): DiscountQuoteView menggabungkan perilaku ParticipantAccessMixin, View.
class DiscountQuoteView(ParticipantAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, event_id):
        quote = DiscountService(request.user).quote(event_id)
        return JsonResponse({**asdict(quote), "preview_only": True})
