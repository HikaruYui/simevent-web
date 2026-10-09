# Fungsi file: Pemetaan URL ke view untuk achievement, reward, dan kebijakan diskon.

from django.urls import path

from .views import MyAchievementsView, ReconcileAchievementsView
from .reward_views import DiscountQuoteView, EventRewardPolicyView

app_name = "achievements"

urlpatterns = [
    path("events/<int:event_id>/policy/", EventRewardPolicyView.as_view(), name="policy"),
    path("events/<int:event_id>/discount/", DiscountQuoteView.as_view(), name="discount"),
    path("", MyAchievementsView.as_view(), name="list"),
    path("reconcile/", ReconcileAchievementsView.as_view(), name="reconcile"),
]
