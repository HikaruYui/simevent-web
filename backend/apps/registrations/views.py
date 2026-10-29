# Fungsi file: Penanganan request HTTP, scope akses, dan respons untuk registrasi, tiket, attendance, feedback, dan statistik.

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import ListView

from apps.accounts.permissions import require_organizer
from apps.events.models import Event

from .forms import ConfirmationForm, PaymentProofForm
from .models import CertificateTemplate, Payment, PaymentInstructions, Registration, RegistrationStatus, Ticket
from .payments import PaymentService
from .services import RegistrationService
from .tickets import render_ticket_qr


def registration_data(registration):
    return {
        "id": registration.pk,
        "event_id": registration.event_id,
        "event_title": registration.event.title,
        "event_status": registration.event.status,
        "status": registration.status,
        "registered_at": registration.registered_at,
        "cancelled_at": registration.cancelled_at,
        "payment_status": getattr(
            getattr(registration, "payment", None), "status", None,
        ),
    }


def attendance_data(attendance):
    if attendance is None:
        return {"status": "NOT_CHECKED_IN", "checked_in_at": None}
    return {"status": attendance.status, "checked_in_at": attendance.checked_in_at}


# OOP mixin: mengemas aturan akses untuk dipakai ulang melalui pewarisan ganda.
@method_decorator(never_cache, name="dispatch")
class ParticipantAccessMixin:
    # Polymorphism: menambahkan pemeriksaan akses sebelum meneruskan request ke handler.
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({"error": "Authentication required."}, status=401)
        try:
            return super().dispatch(request, *args, **kwargs)
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
            return JsonResponse({"errors": errors}, status=400)


# Inheritance (pewarisan ganda): RegistrationListView menggabungkan perilaku ParticipantAccessMixin, ListView.
class RegistrationListView(ParticipantAccessMixin, ListView):
    paginate_by = 20
    http_method_names = ["get", "head", "options"]

    # Polymorphism: menyesuaikan kumpulan data yang digunakan oleh alur bawaan Django.
    def get_queryset(self):
        return Registration.objects.owned_by(self.request.user).select_related("event", "payment")

    # Polymorphism: mengganti respons bawaan generic view dengan respons aplikasi.
    def render_to_response(self, context, **response_kwargs):
        return JsonResponse({
            "results": [registration_data(item) for item in context["object_list"]],
            "page": context["page_obj"].number,
            "pages": context["paginator"].num_pages,
        })


# Inheritance (pewarisan ganda): RegistrationCreateView menggabungkan perilaku ParticipantAccessMixin, View.
class RegistrationCreateView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, event_id):
        form = ConfirmationForm(request.POST)
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        registration = RegistrationService(request.user).register(event_id)
        return JsonResponse(registration_data(registration), status=201)


# Inheritance (pewarisan ganda): PaidRegistrationCreateView menggabungkan perilaku ParticipantAccessMixin, View.
class PaidRegistrationCreateView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, event_id):
        registration = RegistrationService(request.user).start_paid_registration(event_id)
        payment = registration.payment
        return JsonResponse({
            **registration_data(registration),
            "payment_amount": payment.amount,
            "payment_status": payment.status,
        }, status=201)


# Inheritance (pewarisan ganda): PaymentProofView menggabungkan perilaku ParticipantAccessMixin, View.
class PaymentProofView(ParticipantAccessMixin, View):
    http_method_names = ["get", "post", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("registration__event"),
            registration_id=pk,
            registration__participant=request.user,
        )
        instructions = PaymentInstructions.objects.filter(is_active=True).first()
        return JsonResponse({
            "registration_id": payment.registration_id,
            "event_title": payment.registration.event.title,
            "amount": payment.amount,
            "status": payment.status,
            "review_note": payment.review_note,
            "proof_required": True,
            "bank": {
                "name": instructions.bank_name,
                "account_number": instructions.account_number,
                "account_holder": instructions.account_holder,
                "instructions": instructions.instructions,
            } if instructions else None,
        })

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("registration"),
            registration_id=pk,
            registration__participant=request.user,
        )
        if payment.registration.status != RegistrationStatus.REGISTERED:
            raise ValidationError("Pendaftaran ini sudah dibatalkan.")
        if payment.status not in (Payment.Status.AWAITING_PROOF, Payment.Status.REJECTED):
            raise ValidationError("Bukti pembayaran sedang ditinjau atau sudah disetujui.")
        form = PaymentProofForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse(
                {"errors": form.errors.get_json_data()},
                status=400,
            )
        payment.proof = form.cleaned_data["proof"]
        payment.status = Payment.Status.UNDER_REVIEW
        payment.submitted_at = timezone.now()
        payment.reviewed_by = None
        payment.reviewed_at = None
        payment.review_note = form.cleaned_data["note"].strip()
        payment.save()
        return JsonResponse({"status": payment.status}, status=202)


# Inheritance (pewarisan ganda): PaymentProofDownloadView menggabungkan perilaku ParticipantAccessMixin, View.
class PaymentProofDownloadView(ParticipantAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("registration__event"),
            pk=pk,
        )
        if not (
            request.user.has_perm("accounts.manage_platform")
            or (
                request.user.has_perm("accounts.access_organizer")
                and payment.registration.event.organizer_id == request.user.pk
            )
            or payment.registration.participant_id == request.user.pk
        ):
            raise PermissionDenied
        if not payment.proof:
            raise ValidationError("Bukti pembayaran belum tersedia.")
        response = HttpResponse(payment.proof.open("rb").read(), content_type="application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="{payment.proof.name.rsplit("/", 1)[-1]}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response


# Inheritance (pewarisan ganda): PaymentReviewView menggabungkan perilaku ParticipantAccessMixin, View.
class PaymentReviewView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, pk):
        action = request.POST.get("action")
        if action not in ("approve", "reject"):
            raise ValidationError("Tindakan verifikasi tidak valid.")
        payment = PaymentService(request.user).review(
            pk, approve=action == "approve", note=request.POST.get("note", ""),
        )
        return JsonResponse({"status": payment.status})


# Inheritance (pewarisan ganda): CertificatePDFView menggabungkan perilaku ParticipantAccessMixin, View.
class CertificatePDFView(ParticipantAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        registration = get_object_or_404(
            Registration.objects.select_related(
                "event", "participant", "attendance", "feedback", "payment",
            ),
            pk=pk,
            participant=request.user,
            status=RegistrationStatus.REGISTERED,
        )
        if (
            registration.event.end_datetime > timezone.now()
            or registration.event.status != "COMPLETED"
            or not hasattr(registration, "attendance")
            or registration.attendance.status != "PRESENT"
            or not hasattr(registration, "feedback")
            or (
                hasattr(registration, "payment")
                and registration.payment.status != Payment.Status.APPROVED
            )
        ):
            raise ValidationError("Sertifikat tersedia setelah event selesai, hadir, dan feedback dikirim.")
        template = CertificateTemplate.objects.filter(is_active=True).first()
        if not template:
            raise ValidationError("Template sertifikat belum diatur oleh admin.")
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="sertifikat-{registration.pk}.pdf"'
        generate_certificate_pdf(registration, template, response)
        return response


def generate_certificate_pdf(registration, template, response):
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont
    from pathlib import Path
    with template.background.open("rb") as image_file:
        background = Image.open(image_file).convert("RGB")
    draw = ImageDraw.Draw(background)
    font_candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    font_path = next((path for path in font_candidates if path.exists()), None)
    font = ImageFont.truetype(str(font_path), template.font_size) if font_path else ImageFont.load_default()
    width, height = background.size
    color = template.text_color
    event = registration.event
    draw.text((width * template.name_x / 100, height * template.name_y / 100),
              registration.participant.get_full_name(), fill=color, font=font, anchor="mm")
    draw.text((width * template.event_x / 100, height * template.event_y / 100),
              event.title, fill=color, font=font, anchor="mm")
    draw.text((width * template.date_x / 100, height * template.date_y / 100),
              timezone.localtime(event.start_datetime).strftime("%d %B %Y"), fill=color, font=font, anchor="mm")
    draw.text((width * template.number_x / 100, height * template.number_y / 100),
              f"SIMEVENT-{registration.pk:06d}", fill=color, font=font, anchor="mm")
    image_buffer = BytesIO()
    background.save(image_buffer, format="PDF", resolution=150)
    response.write(image_buffer.getvalue())

# Inheritance (pewarisan ganda): RegistrationCancelView menggabungkan perilaku ParticipantAccessMixin, View.
class RegistrationCancelView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, pk):
        get_object_or_404(Registration.objects.owned_by(request.user), pk=pk)
        form = ConfirmationForm(request.POST)
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        registration = RegistrationService(request.user).cancel(pk)
        return JsonResponse(registration_data(registration))


# Inheritance: TicketAccessMixin mewarisi perilaku ParticipantAccessMixin untuk diperluas sesuai kebutuhan class ini.
class TicketAccessMixin(ParticipantAccessMixin):
    def get_ticket(self, request, pk):
        return get_object_or_404(
            Ticket.objects.select_related(
                "registration__event", "registration__participant", "registration__payment",
            ).filter(registration__participant=request.user),
            registration_id=pk,
        )


# Inheritance (pewarisan ganda): TicketDetailView menggabungkan perilaku TicketAccessMixin, View.
class TicketDetailView(TicketAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        ticket = self.get_ticket(request, pk)
        is_valid = ticket.is_valid
        return JsonResponse({
            "identifier": ticket.identifier,
            "registration": registration_data(ticket.registration),
            "is_valid": is_valid,
            "token": ticket.token if is_valid else None,
        })


# Inheritance (pewarisan ganda): TicketQRView menggabungkan perilaku TicketAccessMixin, View.
class TicketQRView(TicketAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        ticket = self.get_ticket(request, pk)
        if not ticket.is_valid:
            raise ValidationError("This ticket is not valid.")
        response = HttpResponse(render_ticket_qr(ticket.token), content_type="image/png")
        response["Content-Disposition"] = 'inline; filename="ticket.png"'
        return response


# Inheritance (pewarisan ganda): MeetingAccessView menggabungkan perilaku TicketAccessMixin, View.
class MeetingAccessView(TicketAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        ticket = self.get_ticket(request, pk)
        if not ticket.is_valid:
            raise ValidationError("Active registration for a published event is required.")
        access = getattr(ticket.registration.event, "private_access", None)
        return JsonResponse({
            "meeting_url": access.meeting_url if access else "",
            "instructions": access.instructions if access else "",
        })


# Inheritance: ParticipantListView mewarisi perilaku RegistrationListView untuk diperluas sesuai kebutuhan class ini.
class ParticipantListView(RegistrationListView):
    # Polymorphism: menyesuaikan kumpulan data yang digunakan oleh alur bawaan Django.
    def get_queryset(self):
        require_organizer(self.request.user)
        event = get_object_or_404(
            Event.objects.managed_by(self.request.user), pk=self.kwargs["event_id"],
        )
        return Registration.objects.filter(event=event).select_related(
            "event", "participant", "attendance",
        )

    # Polymorphism: mengganti respons bawaan generic view dengan respons aplikasi.
    def render_to_response(self, context, **response_kwargs):
        response = {
            "results": [{
                **registration_data(item),
                "attendance": attendance_data(getattr(item, "attendance", None)),
                "participant": {
                    "id": item.participant_id,
                    "name": item.participant.get_full_name(),
                    "email": item.participant.email,
                    "nim": item.participant.nim,
                    "prodi": item.participant.prodi,
                },
            } for item in context["object_list"]],
            "page": context["page_obj"].number,
            "pages": context["paginator"].num_pages,
        }
        return JsonResponse(response)
