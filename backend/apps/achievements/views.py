# Fungsi file: Penanganan request HTTP, scope akses, dan respons untuk achievement, reward, dan kebijakan diskon.

from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from .models import UserAchievement
from .services import AchievementService


def achievement_data(assignment):
    achievement = assignment.achievement
    return {
        "id": achievement.pk,
        "code": achievement.code,
        "name": achievement.name,
        "description": achievement.description,
        "scope": achievement.scope_label,
        "required_count": achievement.required_count,
        "qualifying_count": assignment.current_count,
        "awarded_at": assignment.awarded_at,
    }


@method_decorator(never_cache, name="dispatch")
class MyAchievementsView(View):
    http_method_names = ["get", "head", "options"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({"error": "Authentication required."}, status=401)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        assignments = UserAchievement.objects.eligible_for(request.user).select_related(
            "achievement", "achievement__event_type",
        )
        return JsonResponse({
            "results": [achievement_data(item) for item in assignments],
        })


class ReconcileAchievementsView(MyAchievementsView):
    http_method_names = ["post", "options"]

    def post(self, request):
        AchievementService(request.user).evaluate()
        return self.get(request)
