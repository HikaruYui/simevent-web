# Fungsi file: Endpoint scan token tiket dan pembacaan status attendance milik peserta.

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from .attendance import AttendanceService
from .models import Attendance, Registration
from .views import ParticipantAccessMixin, attendance_data


# Inheritance (pewarisan ganda): TicketScanView menggabungkan perilaku ParticipantAccessMixin, View.
# OOP — Multiple inheritance: ParticipantAccessMixin, View digabung; pencarian method mengikuti MRO C3 Python.
# OOP — Method decorator: mengadaptasi decorator fungsi ke method class yang disebutkan, tanpa mengganti pewarisan.
@method_decorator(sensitive_post_parameters("token"), name="dispatch")
class TicketScanView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, event_id):
        attendance, created = AttendanceService(request.user).scan(
            event_id, token=request.POST.get("token", ""),
        )
        return JsonResponse({
            **attendance_data(attendance),
            "registration_id": attendance.registration_id,
            "already_checked_in": not created,
        }, status=201 if created else 200)


# Inheritance (pewarisan ganda): AttendanceDetailView menggabungkan perilaku ParticipantAccessMixin, View.
# OOP — Multiple inheritance: ParticipantAccessMixin, View digabung; pencarian method mengikuti MRO C3 Python.
class AttendanceVoidView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        attendance = get_object_or_404(Attendance, registration_id=pk)
        result = AttendanceService(request.user).void(
            attendance.pk, reason=request.POST.get("reason", ""),
        )
        return JsonResponse(attendance_data(result))


class AttendanceDetailView(ParticipantAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        registration = get_object_or_404(
            Registration.objects.owned_by(request.user).select_related("attendance"),
            pk=pk,
        )
        return JsonResponse(attendance_data(getattr(registration, "attendance", None)))
