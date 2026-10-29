from pathlib import Path
import json
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from apps.accounts.forms import ProfileForm
from apps.accounts.permissions import require_organizer
from apps.events.forms import AdminEventForm, ContactForm, EventForm
from apps.events.invitations import send_invitation_emails
from apps.achievements.models import Achievement
from django.core.exceptions import PermissionDenied
from collections import Counter, defaultdict
from decimal import Decimal
from django.utils.text import slugify
from apps.registrations.models import Ticket
from apps.registrations.models import (
    Attendance,
    CertificateTemplate,
    Payment,
    Registration,
    RegistrationStatus,
    UploadedCertificate,
    PaymentInstructions,
)
from django.core.exceptions import ValidationError
from apps.events.models import (
    Event,
    EventCommitteeAssignment,
    CommitteePreference,
    EventStatus,
    EventType,
    EventTransition,
    validate_documentation_url,
    OrganizerInvitation,
    OrganizerPreference,
    OrganizerSupportTicket,
    ContactMessage,
    PlatformAuditLog,
    PlatformPayout,
    PlatformSettings,
)
from apps.accounts.forms import RegistrationForm
from apps.accounts.models import AccountAccessChange
from apps.accounts.services import change_account_access
from apps.accounts.role_service import set_account_role
from apps.partnerships.models import OrganizerProposal, ProposalStatus, ProposalReview
from apps.partnerships.services import review_proposal


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
def landing_page(request):
    now = timezone.now()

    recommended_events = (
        Event.objects
        .public()
        .filter(
            status=EventStatus.PUBLISHED,
            end_datetime__gt=now,
        )
        .select_related("event_type", "organizer")
        .order_by(
            "start_datetime",
            "pk",
        )[:4]
    )

    categories = (
        EventType.objects
        .filter(is_active=True)
        .annotate(
            event_count=Count(
                "events",
                filter=Q(
                    events__status=EventStatus.PUBLISHED,
                    events__end_datetime__gt=now,
                ),
            )
        )
        .order_by("name")
    )

    participant_count = (
        Registration.objects
        .filter(
            event__in=Event.objects.public(),
            status="REGISTERED",
        )
        .values("participant_id")
        .distinct()
        .count()
    )

    organizer_count = (
        Event.objects
        .public()
        .values("organizer_id")
        .distinct()
        .count()
    )

    completed_count = (
        Event.objects
        .filter(status=EventStatus.COMPLETED)
        .count()
    )

    return render(
        request,
        "landing_page.html",
        {
            "recommended_events": recommended_events,
            "categories": categories,
            "participant_count": participant_count,
            "organizer_count": organizer_count,
            "completed_count": completed_count,
            "now": now,
        },
    )


# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
def tentang(request):
    return render(
        request,
        "tentang.html",
    )
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_http_methods(["GET", "POST"])
def bantuan(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        contact = ContactMessage.objects.create(
            name=form.cleaned_data["nama"], email=form.cleaned_data["email"],
            message=form.cleaned_data["pesan"],
        )
        request.session["contact_message_id"] = contact.pk
        return JsonResponse({"ok": True, "code": f"CONTACT-{contact.pk}"}, status=201)
    contact = ContactMessage.objects.filter(pk=request.session.get("contact_message_id")).first()
    return render(request, "bantuan.html", {"contact_message": contact})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
def jelajah(request):
    now = timezone.now()

    registered_event_ids = set()
    if request.user.is_authenticated and request.user.is_active:
        registered_event_ids = set(
            Registration.objects.owned_by(request.user)
            .filter(status=RegistrationStatus.REGISTERED)
            .values_list("event_id", flat=True)
        )


    # Hanya event publik dari PostgreSQL.
    events = (
        Event.objects
        .public()
        .select_related(
            "event_type",
            "organizer",
        )
        .order_by(
            "start_datetime",
            "pk",
        )
    )

    event_data = []

    for event in events:

        # Status tampilan berdasarkan jadwal event.
        if (
            event.status == EventStatus.COMPLETED
            or event.end_datetime <= now
        ):
            ui_status = "done"

        elif event.start_datetime <= now < event.end_datetime:
            ui_status = "live"

        else:
            ui_status = "soon"

        # Nama penyelenggara asli.
        organizer_name = (
            event.organizer
            .get_full_name()
            .strip()
        )

        if not organizer_name:
            organizer_name = event.organizer.email

        # Konversi waktu mengikuti timezone Django.
        local_start = timezone.localtime(
            event.start_datetime
        )

        # Pendaftaran hanya boleh dilakukan ketika
        # event sudah PUBLISHED dan dalam periode daftar.
        registration_open = (
            event.status == EventStatus.PUBLISHED
            and event.registration_open <= now
            and now < event.registration_close
            and event.start_datetime > now
        )

        event_data.append(
            {
                "id": event.pk,
                "isRegistered": event.pk in registered_event_ids,
                "slug": event.slug,
                "detailUrl": reverse("detail_event", args=[event.slug]),
                "registrationUrl": reverse("registrations:create", args=[event.pk]),

                "category": event.event_type.code.lower(),
                "categoryName": event.event_type.name,

                "status": ui_status,
                "registrationOpen": registration_open,

                "date": local_start.date().isoformat(),
                "dateLabel": local_start.strftime(
                    "%d %b %Y"
                ).lstrip("0"),

                "amount": int(event.price),
                "title": event.title,
                "venue": event.venue or "Online",
                "organizer": organizer_name,

                "bannerUrl": (
                    event.banner.url
                    if event.banner
                    else ""
                ),
            }
        )

    # Pilihan filter kategori dari PostgreSQL.
    kategori_list = (
        EventType.objects
        .filter(is_active=True)
        .order_by("name")
    )

    return render(
        request,
        "jelajah.html",
        {
            "event_data": event_data,
            "kategori_list": kategori_list,
        },
    )



# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.

@never_cache
@require_GET
def detail_event(request, slug):
    event = get_object_or_404(
        Event.objects.public().select_related(
            "event_type",
            "organizer",
        ),
        slug=slug,
    )

    now = timezone.now()

    registration_open = (
        event.status == EventStatus.PUBLISHED
        and event.registration_open <= now < event.registration_close
        and now < event.start_datetime
    )

    already_registered = False

    if request.user.is_authenticated:
        already_registered = (
            Registration.objects.owned_by(request.user)
            .filter(
                event=event,
                status=RegistrationStatus.REGISTERED,
            )
            .exists()
        )

    return render(
        request,
        "events/detail.html",
        {
            "event": event,
            "registration_open": registration_open,
            "already_registered": already_registered,
        },
    )


def _participant_redirect(request):
    # Admin dan ketua tetap diarahkan ke dashboard masing-masing.
    if request.user.role in ("ADMIN", "ORGANIZER"):
        return redirect(_dashboard_name(request.user))

    # Peserta dan panitia biasa boleh memakai halaman peserta.
    if not request.user.profile_complete:
        return redirect("peserta_akun")

    return None

def _require_role(request, *allowed_roles):
    user = request.user

    if (
        not user.is_authenticated
        or not user.is_active
        or user.role not in allowed_roles
    ):
        raise PermissionDenied(
            "Akun Anda tidak memiliki akses ke halaman ini."
        )

def _dashboard_name(user):
    destinations = {
        "ADMIN": "admin_dashboard",
        "ORGANIZER": "eo_dashboard",
        "COMMITTEE": "panitia_biasa",
    }

    if user.role in destinations:
        return destinations[user.role]

    return (
        "peserta_dashboard"
        if user.profile_complete
        else "peserta_akun"
    )

# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
def login_page(request):
    if request.user.is_authenticated:
        return redirect(
            "after_login"
        )

    return render(
        request,
        "masuk-preview.html",
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def logout_page(request):
    logout(request)

    return redirect(
        "landing"
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def after_login(request):
    if not request.user.is_active:
        raise PermissionDenied("Akun Anda tidak aktif.")

    return redirect(_dashboard_name(request.user))


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_http_methods): membatasi view ke daftar metode HTTP yang diberikan; tidak menambah pewarisan class.
@require_http_methods(["GET", "POST"])
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_akun(request, template_name="peserta/akun.html", success_url="peserta_dashboard"):
    if (
        template_name == "peserta/akun.html"
        and request.user.role in ("ADMIN", "ORGANIZER")
    ):
        return redirect(_dashboard_name(request.user))
        
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Biodata berhasil disimpan. Akun Anda siap digunakan.")
            return redirect(success_url)
    else:
        form = ProfileForm(instance=request.user)

    # Read values from the form so the progress ring also reflects fields
    # submitted on an invalid POST, before they have been saved to the user.
    profile_values = (
        form["full_name"].value(),
        form["ktp_number"].value(),
        form["gender"].value(),
        form["birth_place"].value(),
        form["birth_date"].value(),
        form["address"].value(),
        form["phone_number"].value(),
    )
    completed_profile_fields = sum(
        bool(value.strip() if isinstance(value, str) else value)
        for value in profile_values
    )

    return render(request, template_name, {
        "form": form,
        "profile_complete": request.user.profile_complete,
        "completed_profile_fields": completed_profile_fields,
        "profile_progress": round(completed_profile_fields * 100 / len(profile_values)),
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_hapus_foto(request):
    if request.user.role != "PARTICIPANT":
        return JsonResponse({"error": "Aksi ini hanya tersedia untuk peserta."}, status=403)

    photo = request.user.profile_photo
    if not photo:
        return JsonResponse({"deleted": False})

    photo_name = photo.name
    photo_storage = photo.storage
    request.user.profile_photo = ""
    request.user.save(update_fields=["profile_photo"])
    if photo_name:
        photo_storage.delete(photo_name)

    return JsonResponse({"deleted": True})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def foto_profil(request):
    photo = request.user.profile_photo
    if not photo:
        raise Http404("Foto profil tidak ditemukan.")

    try:
        image_file = photo.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("File foto profil tidak ditemukan.")

    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(photo.name[photo.name.rfind("."):].lower(), "application/octet-stream")
    return FileResponse(image_file, content_type=content_type)


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_dashboard(request):
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect

    now = timezone.now()
    registrations = list(
        Registration.objects.owned_by(request.user)
        .filter(status=RegistrationStatus.REGISTERED)
        .select_related(
            "event",
            "event__event_type",
            "event__organizer",
            "attendance",
            "feedback",
            "payment",
        )
        .order_by("-registered_at", "-pk")
    )
    attended = [
        registration for registration in registrations
        if (
            registration.event.status == EventStatus.COMPLETED
            and getattr(registration, "attendance", None)
            and registration.attendance.status == Attendance.Status.PRESENT
        )
    ]
    completed_registrations = [
        registration for registration in registrations
        if registration.event.status == EventStatus.COMPLETED
    ]
    template_available = CertificateTemplate.objects.filter(is_active=True).exists()
    certificates = [
        registration for registration in attended
        if (
            template_available
            and registration.event.end_datetime <= now
            and getattr(registration, "feedback", None)
            and (
                not hasattr(registration, "payment")
                or registration.payment.status == Payment.Status.APPROVED
            )
        )
    ]

    levels = (
        {"name": "Perak", "required": 5, "icon": "fa-star", "color": "silver"},
        {"name": "Emas", "required": 10, "icon": "fa-lock", "color": "gold"},
        {"name": "Platinum", "required": 25, "icon": "fa-lock", "color": "platinum"},
        {"name": "Legenda", "required": 50, "icon": "fa-lock", "color": "legend"},
    )
    # Level participant follows the number of active event registrations, as
    # shown by the dashboard. Attendance remains the source for certificates
    # and the separate, configurable achievement records below.
    level_count = len(registrations)
    completed_levels = [
        level for level in levels if level_count >= level["required"]
    ]
    current_level = completed_levels[-1] if completed_levels else None
    next_level = next(
        (level for level in levels if level_count < level["required"]),
        levels[-1],
    )
    dashboard_level_names = {
        "Perak": "Silver",
        "Emas": "Gold",
        "Platinum": "Platinum",
        "Legenda": "Legend",
    }
    next_threshold = next_level["required"]
    attendance_rate = (
        round(len(attended) * 100 / len(completed_registrations))
        if completed_registrations else 0
    )

    documentation_ids = _documentation_event_ids(request.user)
    for registration in registrations:
        registration.certificate_ready = registration in certificates
        registration.documentation_ready = registration.event_id in documentation_ids

    return render(request, "peserta_page.html", {
        "registrations": registrations,
        "total_registrations": len(registrations),
        "attended_count": len(attended),
        "certificate_count": len(certificates),
        "attendance_rate": attendance_rate,
        "levels": levels,
        "completed_levels": completed_levels,
        "current_level": current_level,
        "current_level_display": dashboard_level_names.get(
            current_level["name"] if current_level else "", "Belum Ada",
        ),
        "next_level": next_level,
        "next_level_display": dashboard_level_names[next_level["name"]],
        "next_threshold": next_threshold,
        "progress_percent": min(100, round(level_count * 100 / next_threshold)),
        "track_segment": min(3, max(0, len(completed_levels) - 1)),
        "progress_remaining": max(0, next_threshold - level_count),
        "level_count": level_count,
        "feedback_ratings": (
            ("overall_rating", "Penilaian keseluruhan"),
            ("material_rating", "Materi"),
            ("speaker_rating", "Pembicara"),
            ("organization_rating", "Penyelenggaraan"),
        ),
        "latest_certificate": certificates[0] if certificates else None,
        "now": now,
    })


def _documentation_event_ids(user):
    """Id event yang dokumentasinya boleh dibuka user (aturan ada di RegistrationQuerySet)."""
    return set(
        Registration.objects.owned_by(user)
        .with_documentation()
        .values_list("event_id", flat=True)
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_dokumentasi(request, event_id):
    """Gerbang dokumentasi: tautan Drive tidak pernah ada di HTML untuk peserta yang tidak berhak."""
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect

    registration = get_object_or_404(
        Registration.objects.owned_by(request.user)
        .with_documentation()
        .select_related("event"),
        event_id=event_id,
    )
    url = registration.event.documentation_url
    try:
        # Periksa ulang host walau sudah divalidasi saat disimpan (mis. data diubah lewat Admin).
        validate_documentation_url(url)
    except ValidationError:
        raise Http404("Tautan dokumentasi tidak valid.")
    return redirect(url)


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_daftar_event(request):
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect

    now = timezone.now()
    events = list(
        Event.objects.public()
        .select_related("event_type", "organizer")
        .order_by("start_datetime", "pk")
    )
    participant_registrations = (
        Registration.objects.owned_by(request.user)
        .filter(status=RegistrationStatus.REGISTERED)
        .select_related("payment")
    )
    registrations_by_event = {
        registration.event_id: registration
        for registration in participant_registrations
    }
    documentation_ids = _documentation_event_ids(request.user)
    for event in events:
        registration = registrations_by_event.get(event.pk)
        event.is_registered = registration is not None
        event.documentation_ready = event.pk in documentation_ids
        _attach_payment_details(event, registration)
        event.is_registration_open = (
            event.status == EventStatus.PUBLISHED
            and event.registration_open <= now < event.registration_close
            and event.start_datetime > now
        )
        event.ui_status = (
            "Selesai" if event.status == EventStatus.COMPLETED or event.end_datetime <= now
            else "Sedang Berlangsung" if event.start_datetime <= now
            else "Akan Datang"
        )
    categories = list(
        EventType.objects.filter(is_active=True).values_list("name", flat=True)
    )
    if not any(category.casefold() == "sosialisasi" for category in categories):
        categories.append("Sosialisasi")
    categories.sort(key=str.casefold)
    return render(request, "peserta/daftar_event.html", {
        "events": events,
        "categories": categories,
        "now": now,
        "payment_instructions": PaymentInstructions.objects.filter(
            is_active=True
        ).first(),
    })


def _attach_payment_details(event, registration):
    event.payment_status_code = ""
    event.payment_status_display = ""
    event.payment_proof_url = ""
    event.payment_upload_url = ""
    event.payment_review_note = ""
    if not registration or event.price <= 0:
        return

    payment = getattr(registration, "payment", None)
    if not payment:
        return

    event.payment_status_code = payment.status
    event.payment_status_display = payment.get_status_display()
    event.payment_review_note = payment.review_note
    event.payment_upload_url = reverse("registrations:payment", args=[registration.pk])
    if payment.proof:
        event.payment_proof_url = reverse(
            "registrations:payment-proof-download", args=[payment.pk],
        )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_event_saya(request):
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect

    now = timezone.now()
    registrations = list(
        Registration.objects.owned_by(request.user)
        .filter(status=RegistrationStatus.REGISTERED)
        .select_related("event", "event__event_type", "event__organizer", "payment", "ticket", "participant")
        .order_by("-registered_at", "-pk")
    )
    documentation_ids = _documentation_event_ids(request.user)
    events = []
    for registration in registrations:
        event = registration.event
        event.is_registered = True
        event.cancel_url = reverse("registrations:cancel", args=[registration.pk]) if (
            event.status == EventStatus.CANCELLED or now < event.start_datetime
        ) else ""
        ticket = getattr(registration, "ticket", None)
        event.meeting_url = reverse("registrations:meeting", args=[registration.pk]) if (
            ticket and ticket.is_valid and event.delivery_mode in ("ONLINE", "HYBRID")
        ) else ""
        event.documentation_ready = event.pk in documentation_ids
        event.is_registration_open = (
            event.status == EventStatus.PUBLISHED
            and event.registration_open <= now < event.registration_close
            and event.start_datetime > now
        )
        event.ui_status = (
            "Selesai" if event.status == EventStatus.COMPLETED or event.end_datetime <= now
            else "Sedang Berlangsung" if event.start_datetime <= now
            else "Akan Datang"
        )
        _attach_payment_details(event, registration)
        events.append(event)

    categories = list(
        EventType.objects.filter(is_active=True).values_list("name", flat=True)
    )
    if not any(category.casefold() == "sosialisasi" for category in categories):
        categories.append("Sosialisasi")
    categories.sort(key=str.casefold)
    return render(request, "peserta/daftar_event.html", {
        "events": events,
        "categories": categories,
        "now": now,
        "my_registrations": True,
        "payment_instructions": PaymentInstructions.objects.filter(is_active=True).first(),
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_sertifikat(request):
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect

    has_template = CertificateTemplate.objects.filter(is_active=True).exists()
    registrations = list(
        Registration.objects.owned_by(request.user)
        .filter(status=RegistrationStatus.REGISTERED)
        .select_related(
            "event", "event__organizer", "attendance", "feedback", "payment",
            "uploaded_certificate",
        )
        .order_by("-event__start_datetime", "-pk")
    )
    documentation_ids = _documentation_event_ids(request.user)
    for registration in registrations:
        registration.documentation_ready = registration.event_id in documentation_ids
        registration.certificate_ready = (
            has_template
            and registration.event.status == EventStatus.COMPLETED
            and registration.event.end_datetime <= timezone.now()
            and getattr(registration, "attendance", None) is not None
            and registration.attendance.status == Attendance.Status.PRESENT
            and getattr(registration, "feedback", None) is not None
            and (
                not hasattr(registration, "payment")
                or registration.payment.status == Payment.Status.APPROVED
            )
        )
    return render(request, "peserta/sertifikat.html", {
        "registrations": registrations,
        "has_certificate_template": has_template,
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_sertifikat_detail(request, pk):
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect
    registration = get_object_or_404(
        Registration.objects.owned_by(request.user)
        .select_related("event", "event__organizer", "attendance", "feedback", "payment"),
        pk=pk,
        status=RegistrationStatus.REGISTERED,
        event__status=EventStatus.COMPLETED,
        event__end_datetime__lte=timezone.now(),
        attendance__status=Attendance.Status.PRESENT,
        feedback__isnull=False,
    )
    if (
        hasattr(registration, "payment")
        and registration.payment.status != Payment.Status.APPROVED
    ):
        return redirect("peserta_sertifikat")
    return render(request, "peserta/sertifikat_detail.html", {
        "registration": registration,
        "has_certificate_template": CertificateTemplate.objects.filter(is_active=True).exists(),
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_achievement(request):
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect

    totals = {
        row["event__event_type_id"]: row["total"]
        for row in Registration.objects.filter(
            participant=request.user,
            status=RegistrationStatus.REGISTERED,
            event__status=EventStatus.COMPLETED,
            attendance__status=Attendance.Status.PRESENT,
        ).values("event__event_type_id").annotate(
            total=Count("event_id", distinct=True)
        )
    }
    total_attended = sum(totals.values())
    achievements = list(
        Achievement.objects.filter(is_active=True)
        .select_related("event_type")
        .order_by("required_count", "name")
    )
    for achievement in achievements:
        achievement.progress = (
            totals.get(achievement.event_type_id, 0)
            if achievement.event_type_id else total_attended
        )
        achievement.progress_percent = min(
            100,
            round(achievement.progress * 100 / achievement.required_count),
        )
        achievement.is_completed = achievement.progress >= achievement.required_count

    level_count = (
        Registration.objects.owned_by(request.user)
        .filter(status=RegistrationStatus.REGISTERED)
        .values("event_id").distinct().count()
    )
    levels = (
        {"name": "Perak", "required": 5, "icon": "fa-star"},
        {"name": "Emas", "required": 10, "icon": "fa-lock"},
        {"name": "Platinum", "required": 25, "icon": "fa-lock"},
        {"name": "Legenda", "required": 50, "icon": "fa-lock"},
    )
    for level in levels:
        level["completed"] = level_count >= level["required"]
        level["progress"] = min(level_count, level["required"])
    completed_count = sum(item["completed"] for item in levels)
    completed_levels = [level for level in levels if level["completed"]]
    next_level = next(
        (level for level in levels if level_count < level["required"]),
        levels[-1],
    )
    next_threshold = next_level["required"]
    progress_percent = min(100, round(level_count * 100 / next_threshold))

    return render(request, "peserta/achievement.html", {
        "achievements": achievements,
        "levels": levels,
        "attended_count": total_attended,
        "level_count": level_count,
        "completed_count": completed_count,
        "completed_percentage": round(completed_count * 100 / len(levels)),
        "completed_levels": completed_levels,
        "next_level": next_level,
        "next_threshold": next_threshold,
        "progress_percent": progress_percent,
        "progress_remaining": max(0, next_threshold - level_count),
        "track_segment": min(3, max(0, len(completed_levels) - 1)),
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_http_methods): membatasi view ke daftar metode HTTP yang diberikan; tidak menambah pewarisan class.
@require_http_methods(["GET", "POST"])
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_biasa_dashboard(request):
    _require_role(request, "COMMITTEE")

    assigned_events = (
        Event.objects.filter(
            committee_assignments__member=request.user,
            committee_assignments__is_active=True,
        )
        .distinct()
        .order_by("-start_datetime", "-pk")
    )

    event_list = list(assigned_events)
    selected_event = None
    participant_rows = []
    certificate_rows = []

    if request.method == "POST":
        selected_event = get_object_or_404(
            assigned_events,
            pk=request.POST.get("event_id"),
        )
        preference, _ = CommitteePreference.objects.get_or_create(
            member=request.user,
        )
        preference.selected_event = selected_event
        preference.save(update_fields=("selected_event", "updated_at"))
        return_to = request.POST.get("return_to")
        tab = "profil" if return_to == "profil" else "peserta"
        return redirect(
            f"{reverse('panitia_biasa')}?event_id={selected_event.pk}#tab-{tab}"
        )

    if event_list:
        selected_id = request.GET.get("event_id")

        if selected_id:
            selected_event = get_object_or_404(
                assigned_events,
                pk=selected_id,
            )
        else:
            preference = CommitteePreference.objects.filter(
                member=request.user,
            ).first()
            preferred_event = (
                assigned_events.filter(pk=preference.selected_event_id).first()
                if preference and preference.selected_event_id
                else None
            )
            if preferred_event:
                selected_event = preferred_event
            else:
                selected_event = None

        if selected_event is None:
            selected_event = event_list[0]

        preference, _ = CommitteePreference.objects.get_or_create(
            member=request.user,
            defaults={"selected_event": selected_event},
        )
        if preference.selected_event_id not in {event.pk for event in event_list}:
            preference.selected_event = selected_event
            preference.save(update_fields=("selected_event", "updated_at"))

        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
        registrations = (
            Registration.objects.ticketed().filter(event=selected_event)
            .select_related(
                "participant",
                "ticket",
                "attendance",
                "uploaded_certificate",
            )
            .order_by("registered_at", "pk")
        )

        for registration in registrations:
            participant = registration.participant
            attendance = getattr(
                registration, "attendance", None
            )

            is_present = bool(
                attendance
                and attendance.status == Attendance.Status.PRESENT
            )

            checkin_time = "-"

            if is_present:
                checkin_time = (
                    timezone.localtime(
                        attendance.checked_in_at
                    ).strftime("%H:%M") + " WITA"
                )

            if is_present:
                uploaded = getattr(registration, "uploaded_certificate", None)
                certificate_rows.append({
                    "registrationId": registration.pk,
                    "name": (
                        participant.get_full_name().strip()
                        or participant.email
                    ),
                    "email": participant.email,
                    "uploadedAt": uploaded.uploaded_at if uploaded else None,
                })

            participant_rows.append({
                "registrationId": registration.pk,
                "participantId": participant.pk,
                "code": str(registration.ticket.identifier),
                "name": (
                    participant.get_full_name().strip()
                    or participant.email
                ),
                "email": participant.email,
                "present": is_present,
                "voided": attendance is not None and attendance.status == Attendance.Status.VOIDED,
                "checkinTime": checkin_time,
            })

    # Tidak ada penugasan berarti data kosong, bukan peserta simulasi dari browser.
    panitia_db_data = {
        "eventId": selected_event.pk if selected_event else None,
        "eventName": selected_event.title if selected_event else "Belum ada penugasan event",
        "selectedEventId": selected_event.pk if selected_event else None,
        "documentationUrl": selected_event.documentation_url if selected_event else "",
        "events": [{"id": event.pk, "name": event.title} for event in event_list],
        "participants": participant_rows,
    }

    return render(
        request,
        "panitia_biasa_page.html",
        {
            "panitia_db_data": panitia_db_data,
            "documentation_events": [
                event for event in event_list
                if not event.hide_from_committee_documentation
            ],
            "certificate_rows": certificate_rows,
            "certificate_event": selected_event,
            "certificate_events": event_list,
        },
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_dashboard(request):
    _require_role(
        request,
        "ADMIN",
        "ORGANIZER",
        "COMMITTEE",
    )

    return redirect(_dashboard_name(request.user))

def _ketua_panitia(template):
    # OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
    @never_cache
    # OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
    @require_GET
    # OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
    @login_required(login_url="login_page")
    def view(request):
        _require_role(request, "ORGANIZER")

        return render(
            request,
            f"ketua_panitia/{template}.html",
        )

    return view


def _build_eo_dashboard_data(user):
    now = timezone.now()

    # Hanya event yang dapat dikelola akun yang sedang login.
    events = list(
        Event.objects.managed_by(user)
        .select_related("event_type")
        .order_by("-start_datetime", "-pk")
    )
    event_ids = [event.pk for event in events]
    event_by_id = {event.pk: event for event in events}

    # Tiket valid: registrasi aktif, tiket aktif, dan
    # pembayaran disetujui (atau event gratis).
    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    tickets = list(
        Ticket.objects.filter(
            registration__in=Registration.objects.ticketed().filter(event_id__in=event_ids),
        )
        .select_related(
            "registration__participant",
            "registration__event",
        )
    )

    # Pendapatan hanya dari pembayaran yang APPROVED.
    payments = list(
        Payment.objects.filter(
            registration__event_id__in=event_ids,
            registration__status=RegistrationStatus.REGISTERED,
            status=Payment.Status.APPROVED,
        )
        .select_related("registration__event")
    )

    valid_registration_ids = [
        ticket.registration_id for ticket in tickets
    ]

    attendances = list(
        Attendance.objects.filter(
            registration_id__in=valid_registration_ids,
            status=Attendance.Status.PRESENT,
        )
        .select_related("registration__event")
    )

    sold_by_event = Counter(
        ticket.registration.event_id for ticket in tickets
    )
    present_by_event = Counter(
        attendance.registration.event_id
        for attendance in attendances
    )

    revenue_by_event = defaultdict(lambda: Decimal("0"))
    for payment in payments:
        revenue_by_event[payment.registration.event_id] += payment.amount

    
    # Status event mengikuti waktu sebenarnya.
    
    status_map = {
        "DRAFT": "draft",
        "SUBMITTED": "diajukan",
        "APPROVED": "disetujui",
        "NEEDS_REVISION": "revisi",
        "REJECTED": "ditolak",
        "COMPLETED": "selesai",
        "CANCELLED": "dibatalkan",
    }

    event_rows = []

    for event in events:
        if event.status == EventStatus.PUBLISHED:
            if event.end_datetime <= now:
                status = "selesai"
            elif event.start_datetime <= now:
                status = "berlangsung"
            else:
                status = "mendatang"
        else:
            status = status_map.get(event.status, "draft")

        # Ambil alasan dari keputusan Admin terbaru
        alasan = ""

        if event.status in (
            EventStatus.REJECTED,
            EventStatus.NEEDS_REVISION,
            EventStatus.CANCELLED,
        ):
            alasan = (
                EventTransition.objects
                .filter(
                    event_id=event.pk,
                    to_status=event.status,
                )
                .order_by("-created_at", "-pk")
                .values_list("reason", flat=True)
                .first()
                or ""
            )
        event_rows.append({
            "id": event.pk,
            "nama": event.title,
            "jenis": event.event_type.name,
            "tanggal": timezone.localtime(
                event.start_datetime
            ).strftime("%Y-%m-%d"),
            "lokasi": event.venue or "Online",
            "kuota": event.capacity,
            "terjual": sold_by_event[event.pk],
            "hadir": present_by_event[event.pk],
            "harga": float(event.price),
            "pendapatan": float(revenue_by_event[event.pk]),
            "status": status,
            "alasan": alasan,
        })

    
    # Grafik pendapatan dan tiket 6 bulan terakhir.
    
    nama_bulan = [
        "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
    ]

    current_month = now.year * 12 + now.month - 1

    months = []
    for offset in range(5, -1, -1):
        year, month_zero = divmod(current_month - offset, 12)
        months.append((year, month_zero + 1))

    month_index = {
        key: index for index, key in enumerate(months)
    }

    monthly_tickets = [0] * 6
    monthly_revenue = [0.0] * 6

    for ticket in tickets:
        dt = timezone.localtime(ticket.registration.registered_at)
        index = month_index.get((dt.year, dt.month))
        if index is not None:
            monthly_tickets[index] += 1

    for payment in payments:
        if not payment.reviewed_at:
            continue

        dt = timezone.localtime(payment.reviewed_at)
        index = month_index.get((dt.year, dt.month))

        if index is not None:
            monthly_revenue[index] += float(payment.amount)

    monthly = {
        "labels": [nama_bulan[m - 1] for _, m in months],
        "pendapatan": monthly_revenue,
        "tiket": monthly_tickets,
    }

    
    # Grafik kehadiran per event.
    # onsite/online: jam 08.00 sampai 14.00
    # daftar: H-6 sampai hari H.
    
    attendance_series = {
        str(event.pk): {
            "onsite": [0] * 7,
            "online": [0] * 7,
            "daftar": [0] * 7,
        }
        for event in events
    }

    for ticket in tickets:
        reg = ticket.registration
        event = event_by_id[reg.event_id]

        registered_date = timezone.localtime(
            reg.registered_at
        ).date()
        event_date = timezone.localtime(
            event.start_datetime
        ).date()

        days_before = (event_date - registered_date).days

        if 0 <= days_before <= 6:
            index = 6 - days_before
            attendance_series[str(event.pk)]["daftar"][index] += 1

    for attendance in attendances:
        event = event_by_id[attendance.registration.event_id]

        checked_at = timezone.localtime(
            attendance.checked_in_at
        )
        event_date = timezone.localtime(
            event.start_datetime
        ).date()

        if checked_at.date() != event_date:
            continue

        hour_index = checked_at.hour - 8

        if not 0 <= hour_index < 7:
            continue

        # Model Attendance belum membedakan mode
        # kehadiran dalam event HYBRID.
        metric = (
            "online"
            if event.delivery_mode == "ONLINE"
            else "onsite"
        )

        attendance_series[str(event.pk)][metric][hour_index] += 1

    
    # Log aktivitas dari registrasi, pembayaran,
    # dan kehadiran yang benar-benar tersimpan.
    
    activity_records = []

    latest_tickets = sorted(
        tickets,
        key=lambda ticket: ticket.registration.registered_at,
        reverse=True,
    )[:8]

    for ticket in latest_tickets:
        reg = ticket.registration
        name = (
            reg.participant.get_full_name().strip()
            or reg.participant.email
        )

        activity_records.append((
            reg.registered_at,
            "daftar",
            f"{name} mendaftar ke {reg.event.title}",
        ))

    latest_payments = sorted(
        payments,
        key=lambda p: p.reviewed_at or p.registration.registered_at,
        reverse=True,
    )[:8]

    for payment in latest_payments:
        activity_records.append((
            payment.reviewed_at or payment.registration.registered_at,
            "bayar",
            f"Pembayaran Rp {payment.amount:,.0f} "
            f"untuk {payment.registration.event.title} disetujui",
        ))

    latest_attendances = sorted(
        attendances,
        key=lambda attendance: attendance.checked_in_at,
        reverse=True,
    )[:8]

    for attendance in latest_attendances:
        activity_records.append((
            attendance.checked_in_at,
            "hadir",
            f"Peserta check-in di "
            f"{attendance.registration.event.title}",
        ))

    # Aktivitas bantuan berasal dari tiket support yang tersimpan.
    support_tickets = list(
        OrganizerSupportTicket.objects.filter(organizer=user)
        .select_related("event")
        .order_by("-updated_at", "-pk")
    )
    for ticket in support_tickets[:8]:
        activity_records.append((
            ticket.updated_at,
            "support",
            f"Tiket {ticket.code} "
            f"{'ditandai selesai' if ticket.status == OrganizerSupportTicket.Status.RESOLVED else 'sedang ditangani'}",
        ))

    transitions = list(
        EventTransition.objects.filter(event_id__in=event_ids)
        .select_related("event")
        .order_by("-created_at", "-pk")[:8]
    )
    for transition in transitions:
        activity_records.append((
            transition.created_at,
            "event",
            f"Status event {transition.event.title} diperbarui menjadi {transition.get_to_status_display()}",
        ))

    activity_records.sort(key=lambda item: item[0], reverse=True)
    activity = [
        {
            "tipe": kind,
            "teks": message,
            "waktu": timezone.localtime(dt).strftime("%d %b %Y, %H:%M"),
        }
        for dt, kind, message in activity_records[:50]
    ]

    dashboard_data = {
        "events": event_rows,
        "monthly": monthly,
        "activity": activity,
        "attendance_series": attendance_series,
        "tickets": [{
            "id": ticket.code,
            "eventId": ticket.event_id,
            "status": (
                "selesai"
                if ticket.status == OrganizerSupportTicket.Status.RESOLVED
                else "diaudit"
            ),
        } for ticket in support_tickets],
    }

    return dashboard_data


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def eo_dashboard(request):
    _require_role(request, "ORGANIZER")
    dashboard_data = _build_eo_dashboard_data(request.user)

    return render(
        request,
        "ketua_panitia/dashboard.html",
        {"eo_dashboard_data": dashboard_data},
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def eo_peserta(request):
    _require_role(request, "ORGANIZER")

    # Ambil event asli yang boleh dikelola akun ini.
    events = list(
        Event.objects.managed_by(request.user)
        .order_by("-created_at", "-pk")
    )

    event_ids = [event.pk for event in events]

    # Format mengikuti kebutuhan JS Ketua Panitia.
    event_rows = [
        {
            "id": event.pk,
            "nama": event.title,
        }
        for event in events
    ]

    # Ambil registrasi aktif yang sudah valid pembayarannya.
    # Event gratis tidak membutuhkan pembayaran.
    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    registrations = (
        Registration.objects.ticketed().filter(event_id__in=event_ids)
        .select_related(
            "event",
            "participant",
            "attendance",
        )
        .order_by("-registered_at", "-pk")
    )

    participant_rows = []

    for index, registration in enumerate(registrations, start=1):
        user = registration.participant
        attendance = getattr(registration, "attendance", None)

        is_present = (
            attendance is not None
            and attendance.status == Attendance.Status.PRESENT
        )

        participant_rows.append({
            "no": index,
            "registrationId": registration.pk,
            "participantId": user.pk,
            "eventId": registration.event_id,
            "nama": user.get_full_name().strip() or user.email,
            "email": user.email,
            "terdaftar": timezone.localtime(
                registration.registered_at
            ).strftime("%Y-%m-%d"),
            "status": "hadir" if is_present else "terdaftar",
        })

    return render(
        request,
        "ketua_panitia/peserta.html",
        {
            "eo_peserta_data": {
                "events": event_rows,
                "participants": participant_rows,
            }
        },
    )

# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def eo_pendapatan(request):
    _require_role(request, "ORGANIZER")
    return render(request, "ketua_panitia/pendapatan.html", {
        "eo_dashboard_data": _build_eo_dashboard_data(request.user),
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def eo_log(request):
    _require_role(request, "ORGANIZER")
    return render(request, "ketua_panitia/log_aktivitas.html", {
        "eo_dashboard_data": _build_eo_dashboard_data(request.user),
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def eo_support(request):
    _require_role(request, "ORGANIZER")
    tickets = OrganizerSupportTicket.objects.filter(
        organizer=request.user,
    ).select_related("event")
    ticket_rows = [{
        "id": ticket.code,
        "judul": ticket.title,
        "pelapor": ticket.reporter,
        "eventId": ticket.event_id,
        "tanggal": timezone.localtime(ticket.created_at).date().isoformat(),
        "status": (
            "selesai"
            if ticket.status == OrganizerSupportTicket.Status.RESOLVED
            else "diaudit"
        ),
        "isi": ticket.description,
        "balasan": ticket.reply,
    } for ticket in tickets]
    return render(request, "ketua_panitia/support.html", {
        "eo_support_data": {"tickets": ticket_rows},
        "eo_dashboard_data": _build_eo_dashboard_data(request.user),
    })


def _eo_settings_payload(user):
    now = timezone.now()
    events = list(
        Event.objects.managed_by(user).order_by("start_datetime", "pk")
    )
    event_by_id = {event.pk: event for event in events}
    assignments = list(
        EventCommitteeAssignment.objects.filter(event_id__in=event_by_id)
        .select_related("member", "event")
        .order_by("member__first_name", "member__email", "event__start_datetime")
    )
    team_by_user = {}
    for assignment in assignments:
        member = assignment.member
        row = team_by_user.setdefault(member.pk, {
            "id": member.pk,
            "nama": member.get_full_name().strip() or member.email,
            "email": member.email,
            "peran": "panitia",
            "akses": [],
            "status": "ditangguhkan",
            "terakhir": (
                timezone.localtime(member.last_login).strftime("%d %b %Y")
                if member.last_login else "Belum masuk"
            ),
        })
        row["akses"].append(assignment.event_id)
        if assignment.is_active and member.is_active:
            row["status"] = "aktif"

    for row in team_by_user.values():
        if len(set(row["akses"])) == len(events):
            row["akses"] = "semua"

    invitations = []
    for invitation in OrganizerInvitation.objects.filter(organizer=user).prefetch_related("events"):
        remaining_seconds = (invitation.expires_at - now).total_seconds()
        remaining_days = max(0, int((remaining_seconds + 86399) // 86400))
        invitations.append({
            "id": invitation.pk,
            "email": invitation.email,
            "peran": "panitia",
            "kirim": timezone.localtime(invitation.sent_at).strftime("%d %b %Y"),
            "email_sent": invitation.email_sent_at is not None,
            "email_sent_at": (
                timezone.localtime(invitation.email_sent_at).strftime("%d %b %Y, %H:%M")
                if invitation.email_sent_at else ""
            ),
            "sisa": remaining_days,
            "url": reverse("eo_invitation_accept", args=[invitation.token]),
        })

    preference, _ = OrganizerPreference.objects.get_or_create(user=user)
    return {
        "profile": {
            "name": user.get_full_name().strip(),
            "phone": user.phone_number,
            "organization": preference.organization_name,
            "photo": user.profile_photo.url if user.profile_photo else "",
        },
        "team": list(team_by_user.values()),
        "invitations": invitations,
        "events": [{"id": event.pk, "nama": event.title} for event in events],
        "notifications": preference.notifications,
    }


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def eo_pengaturan(request):
    _require_role(request, "ORGANIZER")
    return render(request, "ketua_panitia/pengaturan.html", {
        "eo_settings_data": _eo_settings_payload(request.user),
        "eo_dashboard_data": _build_eo_dashboard_data(request.user),
    })


# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def eo_support_resolve(request, code):
    _require_role(request, "ORGANIZER")
    ticket = get_object_or_404(
        OrganizerSupportTicket.objects.filter(organizer=request.user),
        code=code,
    )
    if ticket.status != OrganizerSupportTicket.Status.RESOLVED:
        ticket.status = OrganizerSupportTicket.Status.RESOLVED
        ticket.resolved_at = timezone.now()
        ticket.save(update_fields=("status", "resolved_at", "updated_at"))
    return JsonResponse({"ok": True, "status": "selesai"})


# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def eo_settings_profile(request):
    _require_role(request, "ORGANIZER")
    user = request.user
    name = " ".join(request.POST.get("name", "").split())
    phone = request.POST.get("phone", "").strip()
    organization = request.POST.get("organization", "").strip()
    if not 3 <= len(name) <= 80:
        return JsonResponse({"error": "Nama harus berisi 3–80 karakter."}, status=400)
    if len(phone) > 20 or len(organization) > 80:
        return JsonResponse({"error": "Nomor HP atau nama organisasi terlalu panjang."}, status=400)

    upload = request.FILES.get("photo")
    if upload:
        if upload.size > 5 * 1024 * 1024:
            return JsonResponse({"error": "Ukuran foto maksimal 5 MB."}, status=400)
        if upload.name.rsplit(".", 1)[-1].lower() not in {"jpg", "jpeg", "png", "webp"}:
            return JsonResponse({"error": "Gunakan foto JPG, PNG, atau WebP."}, status=400)
        try:
            upload = forms.ImageField().clean(upload)
        except ValidationError as exc:
            return JsonResponse({"error": exc.messages[0]}, status=400)

    parts = name.split(" ", 1)
    user.first_name = parts[0]
    user.last_name = parts[1] if len(parts) > 1 else ""
    user.phone_number = phone
    user_fields = ["first_name", "last_name", "phone_number"]
    if upload:
        user.profile_photo = upload
        user_fields.append("profile_photo")
    elif request.POST.get("remove_photo") == "1":
        if user.profile_photo:
            user.profile_photo.delete(save=False)
        user.profile_photo = ""
        user_fields.append("profile_photo")
    user.save(update_fields=user_fields)

    preference, _ = OrganizerPreference.objects.get_or_create(user=user)
    preference.organization_name = organization
    preference.save(update_fields=("organization_name", "updated_at"))
    return JsonResponse({"ok": True, "profile": _eo_settings_payload(user)["profile"]})


# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def eo_settings_password(request):
    _require_role(request, "ORGANIZER")
    form = PasswordChangeForm(request.user, {
        "old_password": request.POST.get("current", ""),
        "new_password1": request.POST.get("password", ""),
        "new_password2": request.POST.get("confirm", ""),
    })
    if not form.is_valid():
        errors = [str(error) for items in form.errors.values() for error in items]
        return JsonResponse({"error": " ".join(errors)}, status=400)
    user = form.save()
    update_session_auth_hash(request, user)
    return JsonResponse({"ok": True})


# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def eo_settings_notification(request):
    _require_role(request, "ORGANIZER")
    key = request.POST.get("key", "")
    if key not in {"daftar", "bayar", "support", "h1", "tim"}:
        return JsonResponse({"error": "Preferensi tidak dikenal."}, status=400)
    preference, _ = OrganizerPreference.objects.get_or_create(user=request.user)
    notifications = dict(preference.notifications)
    notifications[key] = request.POST.get("enabled") == "true"
    preference.notifications = notifications
    preference.save(update_fields=("notifications", "updated_at"))
    return JsonResponse({"ok": True, "notifications": notifications})


# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def eo_settings_team(request):
    _require_role(request, "ORGANIZER")
    event_ids = list(Event.objects.managed_by(request.user).values_list("pk", flat=True))
    try:
        member_id = int(request.POST.get("member_id", ""))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Anggota tim tidak valid."}, status=400)
    action = request.POST.get("action")
    assignments = EventCommitteeAssignment.objects.filter(
        event_id__in=event_ids, member_id=member_id,
    )
    if not assignments.exists():
        return JsonResponse({"error": "Anggota tim tidak ditemukan."}, status=404)
    if action == "remove":
        assignments.delete()
    elif action == "toggle":
        member = assignments.select_related("member").first().member
        enabled = request.POST.get("enabled") == "true"
        if enabled and not member.is_active:
            return JsonResponse({"error": "Akun ini dinonaktifkan Admin Platform."}, status=400)
        assignments.update(is_active=enabled)
    else:
        return JsonResponse({"error": "Aksi tim tidak dikenal."}, status=400)
    return JsonResponse({"ok": True, "settings": _eo_settings_payload(request.user)})


# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def eo_settings_invite(request):
    _require_role(request, "ORGANIZER")
    try:
        payload = json.loads(request.body or "{}")
        if not isinstance(payload, dict):
            raise ValueError
        emails = payload.get("emails", [])
        selected_ids = [int(value) for value in payload.get("event_ids", [])]
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"error": "Data undangan tidak valid."}, status=400)
    if not isinstance(emails, list) or not 1 <= len(emails) <= 10:
        return JsonResponse({"error": "Undang 1–10 email sekaligus."}, status=400)
    normalized = []
    validator = forms.EmailField()
    try:
        normalized = [validator.clean(str(email).strip()).lower() for email in emails]
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=400)
    if len(set(normalized)) != len(normalized):
        return JsonResponse({"error": "Ada email duplikat di daftar undangan."}, status=400)
    managed_events = Event.objects.managed_by(request.user)
    access_all = payload.get("access_all") is True
    if not access_all and not selected_ids:
        return JsonResponse({"error": "Pilih minimal satu event untuk undangan ini."}, status=400)
    if len(selected_ids) != len(set(selected_ids)):
        return JsonResponse({"error": "Daftar event undangan berisi duplikat."}, status=400)
    if selected_ids and managed_events.filter(pk__in=selected_ids).count() != len(selected_ids):
        return JsonResponse({"error": "Ada event yang tidak bisa diakses."}, status=400)
    existing_members = EventCommitteeAssignment.objects.filter(
        event__in=managed_events, member__email__in=normalized,
    ).values_list("member__email", flat=True).distinct()
    existing_invites = OrganizerInvitation.objects.filter(
        organizer=request.user, email__in=normalized,
    ).values_list("email", flat=True)
    existing_accounts = get_user_model().objects.filter(
        email__in=normalized,
    ).values_list("email", flat=True)
    duplicates = set(existing_members) | set(existing_invites) | set(existing_accounts)
    if duplicates:
        return JsonResponse({"error": "Sudah ada di tim atau undangan: " + ", ".join(sorted(duplicates))}, status=400)

    now = timezone.now()
    message = str(payload.get("message", ""))[:200]
    invitations = []
    # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
    with transaction.atomic():
        for email in normalized:
            invitation = OrganizerInvitation.objects.create(
                organizer=request.user,
                email=email,
                message=message,
                access_all=access_all,
                sent_at=now,
                expires_at=now + timedelta(days=7),
            )
            if not access_all:
                invitation.events.set(managed_events.filter(pk__in=selected_ids))
            invitations.append(invitation)
    delivery = send_invitation_emails(invitations, site_url=request.build_absolute_uri("/"))
    return JsonResponse({
        "ok": True,
        "delivery": delivery,
        "settings": _eo_settings_payload(request.user),
    })


# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def eo_settings_invitation_action(request, pk):
    _require_role(request, "ORGANIZER")
    invitation = get_object_or_404(
        OrganizerInvitation.objects.filter(organizer=request.user), pk=pk,
    )
    action = request.POST.get("action")
    delivery = None
    if action == "cancel":
        invitation.delete()
    elif action == "resend":
        invitation.sent_at = timezone.now()
        invitation.expires_at = invitation.sent_at + timedelta(days=7)
        invitation.save(update_fields=("sent_at", "expires_at"))
        delivery = send_invitation_emails(
            [invitation], site_url=request.build_absolute_uri("/"),
        )
    else:
        return JsonResponse({"error": "Aksi undangan tidak dikenal."}, status=400)
    return JsonResponse({
        "ok": True,
        "delivery": delivery,
        "settings": _eo_settings_payload(request.user),
    })


def eo_invitation_accept(request, token):
    invitation = get_object_or_404(OrganizerInvitation, token=token)
    if invitation.expires_at <= timezone.now():
        return render(request, "ketua_panitia/invitation_expired.html", status=410)
    User = get_user_model()
    if User.objects.filter(email__iexact=invitation.email).exists():
        return render(request, "ketua_panitia/invitation_expired.html", {
            "message": "Email ini sudah memiliki akun. Hubungi Ketua Panitia untuk akses tim.",
        }, status=409)
    if request.method == "POST":
        form_data = request.POST.copy()
        form_data["email"] = invitation.email
        form = RegistrationForm(form_data)
        if form.is_valid():
            # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
            with transaction.atomic():
                member = form.save()
                organizer_group, _ = Group.objects.get_or_create(name="Organizer")
                permission = Permission.objects.get(
                    content_type__app_label="accounts", codename="access_organizer",
                )
                organizer_group.permissions.add(permission)
                member.groups.add(organizer_group)
                if invitation.access_all:
                    events = Event.objects.managed_by(invitation.organizer)
                else:
                    events = invitation.events.all()
                EventCommitteeAssignment.objects.bulk_create([
                    EventCommitteeAssignment(event=event, member=member)
                    for event in events
                ], ignore_conflicts=True)
                invitation.delete()
            authenticated = authenticate(
                request, email=member.email, password=request.POST.get("password1"),
            )
            if authenticated:
                login(request, authenticated)
            return redirect("after_login")
    else:
        form = RegistrationForm(initial={"email": invitation.email})
    return render(request, "ketua_panitia/invitation_accept.html", {
        "form": form,
        "invitation": invitation,
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.

@login_required(login_url="login_page")
@require_http_methods(["GET", "POST"])
def eo_event_committee(request, event_id):
    _require_role(request, "ORGANIZER")

    # Ketua Panitia hanya boleh mengatur event miliknya.
    event = get_object_or_404(
        Event.objects.managed_by(request.user),
        pk=event_id,
    )

    if request.method == "POST":
        action = request.POST.get("action", "assign")

        if action == "assign":
            try:
                email = forms.EmailField().clean(
                    request.POST.get("email", "").strip()
                )
            except ValidationError:
                return JsonResponse(
                    {"error": "Format email tidak valid."},
                    status=400,
                )

            member = get_user_model().objects.filter(
                email__iexact=email
            ).first()

            if member is None:
                return JsonResponse(
                    {"error": "Akun dengan email tersebut tidak ditemukan."},
                    status=404,
                )

            if not member.is_active:
                return JsonResponse(
                    {"error": "Akun panitia tidak aktif."},
                    status=400,
                )

            if member.role != "COMMITTEE":
                return JsonResponse(
                    {"error": "Akun harus memiliki role Panitia Biasa."},
                    status=400,
                )

            assignment, created = (
                EventCommitteeAssignment.objects.update_or_create(
                    event=event,
                    member=member,
                    defaults={"is_active": True},
                )
            )

        elif action == "remove":
            try:
                member_id = int(request.POST.get("member_id", ""))
            except (TypeError, ValueError):
                return JsonResponse(
                    {"error": "ID panitia tidak valid."},
                    status=400,
                )

            updated = EventCommitteeAssignment.objects.filter(
                event=event,
                member_id=member_id,
                is_active=True,
            ).update(is_active=False)

            if not updated:
                return JsonResponse(
                    {"error": "Penugasan aktif tidak ditemukan."},
                    status=404,
                )

        else:
            return JsonResponse(
                {"error": "Aksi tidak dikenal."},
                status=400,
            )

    members = list(
        EventCommitteeAssignment.objects.filter(
            event=event,
            is_active=True,
        )
        .select_related("member")
        .order_by("member__email")
        .values(
            "member_id",
            "member__email",
            "member__first_name",
            "member__last_name",
        )
    )

    return JsonResponse({
        "ok": True,
        "event_id": event.pk,
        "members": [
            {
                "id": row["member_id"],
                "email": row["member__email"],
                "name": (
                    f'{row["member__first_name"]} '
                    f'{row["member__last_name"]}'
                ).strip() or row["member__email"],
            }
            for row in members
        ],
    })

@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def eo_event(request):
    _require_role(request, "ORGANIZER")

    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    events = (
        Event.objects.managed_by(request.user)
        .select_related("event_type")
        .annotate(
            ticket_count=Count(
                "registrations",
                filter=Q(
                    registrations__status=RegistrationStatus.REGISTERED,
                ) & (
                    Q(registrations__payment__isnull=True)
                    | Q(
                        registrations__payment__status=
                        Payment.Status.APPROVED
                    )
                ),
                distinct=True,
            ),
        )
        .order_by("-created_at", "-pk")
    )

    status_map = {
        "DRAFT": "draft",
        "SUBMITTED": "diajukan",
        "APPROVED": "disetujui",
        "NEEDS_REVISION": "revisi",
        "REJECTED": "ditolak",
        "COMPLETED": "selesai",
        "CANCELLED": "dibatalkan",
    }

    now = timezone.now()
    event_rows = []

    for event in events:
        if event.status == EventStatus.PUBLISHED:
            if event.end_datetime <= now:
                status = "selesai"
            elif event.start_datetime <= now:
                status = "berlangsung"
            else:
                status = "mendatang"
        else:
            status = status_map.get(event.status, "draft")

        # Ambil alasan keputusan Admin dari PostgreSQL.
        alasan = ""

        if event.status in (
            EventStatus.REJECTED,
            EventStatus.NEEDS_REVISION,
            EventStatus.CANCELLED,
        ):
            alasan = (
                EventTransition.objects
                .filter(
                    event_id=event.pk,
                    to_status=event.status,
                )
                .order_by("-created_at", "-pk")
                .values_list("reason", flat=True)
                .first()
                or ""
            )

        event_rows.append({
            "id": event.pk,
            "nama": event.title,
            "jenis": event.event_type.name,
            "tanggal": timezone.localtime(
                event.start_datetime
            ).strftime("%Y-%m-%d"),
            "lokasi": event.venue or "Online",
            "kuota": event.capacity,
            "terjual": event.ticket_count,
            "harga": float(event.price),
            "status": status,
            "has_proposal": bool(event.proposal),
            "alasan": alasan,
            "deskripsi": event.description,
        })

    return render(
        request,
        "ketua_panitia/event.html",
        {
            "backend_event_rows": event_rows,
            "event_types": EventType.objects.filter(
                is_active=True
            ).order_by("name"),
        },
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_event_detail(
    request,
    pk,
):
    require_organizer(
        request.user
    )

    event = get_object_or_404(
        Event.objects
        .managed_by(request.user)
        .select_related(
            "event_type",
            "organizer",
        ),
        pk=pk,
    )

    return render(
        request,
        "events/detail.html",
        {
            "event": event,
        },
    )

def _admin_event_rows():
    now = timezone.now()
    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    events = list(
        Event.objects.select_related("event_type", "organizer")
        .annotate(
            attendance_count=Count(
                "registrations",
                filter=Q(registrations__in=Registration.objects.ticketed(),
                         registrations__attendance__status=Attendance.Status.PRESENT),
                distinct=True,
            ),
            ticket_count=Count(
                "registrations",
                filter=Q(registrations__in=Registration.objects.ticketed()),
                distinct=True,
            )
        )
        .order_by("-created_at", "-pk")
    )
    reasons = {}
    for transition in EventTransition.objects.filter(
        event_id__in=[event.pk for event in events]
    ).order_by("-created_at", "-pk"):
        reasons.setdefault(transition.event_id, transition.reason)
    status_map = {
        EventStatus.DRAFT: "draft",
        EventStatus.SUBMITTED: "diajukan",
        EventStatus.NEEDS_REVISION: "revisi",
        EventStatus.APPROVED: "disetujui",
        EventStatus.REJECTED: "ditolak",
        EventStatus.COMPLETED: "selesai",
        EventStatus.CANCELLED: "dibatalkan",
    }
    rows = []
    for event in events:
        if event.status == EventStatus.PUBLISHED:
            status = (
                "selesai" if event.end_datetime <= now
                else "berlangsung" if event.start_datetime <= now
                else "mendatang"
            )
        else:
            status = status_map.get(event.status, "draft")
        rows.append({
            "id": event.pk,
            "nama": event.title,
            "jenis": event.event_type.name,
            "tanggal": timezone.localtime(event.start_datetime).strftime("%Y-%m-%d"),
            "lokasi": event.venue or "Online",
            "kuota": event.capacity,
            "terjual": event.ticket_count,
            "hadir": event.attendance_count,
            "harga": float(event.price),
            "status": status,
            "organizer": event.organizer.get_full_name().strip() or event.organizer.email,
            "organizer_id": event.organizer_id,
            "organizer_email": event.organizer.email,
            "deskripsi": event.description,
            "has_proposal": bool(event.proposal),
            "alasan": reasons.get(event.pk, ""),
        })
    return rows


def _admin_user_rows():
    User = get_user_model()
    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    admin_ids = set(User.objects.filter(
        Q(is_superuser=True)
        | Q(user_permissions__content_type__app_label="accounts", user_permissions__codename="manage_platform")
        | Q(groups__permissions__content_type__app_label="accounts", groups__permissions__codename="manage_platform")
    ).values_list("pk", flat=True).distinct())
    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    organizer_ids = set(User.objects.filter(
        Q(user_permissions__content_type__app_label="accounts", user_permissions__codename="access_head_organizer")
        | Q(groups__permissions__content_type__app_label="accounts", groups__permissions__codename="access_head_organizer")
    ).values_list("pk", flat=True).distinct())
    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    committee_ids = set(User.objects.filter(
        Q(user_permissions__content_type__app_label="accounts", user_permissions__codename="access_organizer")
        | Q(groups__permissions__content_type__app_label="accounts", groups__permissions__codename="access_organizer")
    ).values_list("pk", flat=True).distinct())
    users = list(User.objects.annotate(
        registration_count=Count(
            "registrations",
            filter=Q(registrations__status=RegistrationStatus.REGISTERED),
            distinct=True,
        )
    ).order_by("email"))
    organizer_preferences = {
        item.user_id: item.organization_name
        for item in OrganizerPreference.objects.filter(user_id__in=[u.pk for u in users])
    }
    committee_orgs = {}
    for assignment in EventCommitteeAssignment.objects.filter(
        member_id__in=[u.pk for u in users], is_active=True,
    ).select_related("event__organizer"):
        committee_orgs.setdefault(
            assignment.member_id,
            assignment.event.organizer.get_full_name().strip() or assignment.event.organizer.email,
        )
    rows = []
    for user in users:
        role = (
            "admin" if user.pk in admin_ids
            else "penyelenggara" if user.pk in organizer_ids
            else "panitia" if user.pk in committee_ids
            else "peserta"
        )
        rows.append({
            "id": user.pk,
            "email": user.email,
            "nama": user.get_full_name().strip() or user.email,
            "peran": role,
            "org": organizer_preferences.get(user.pk) or committee_orgs.get(user.pk) or ("Platform SIMEVENT" if role == "admin" else "-"),
            "daftar": user.registration_count,
            "status": "aktif" if user.is_active else "dibekukan",
            "is_superuser": user.is_superuser,
        })
    return rows


def _admin_proposal_rows():
    statuses = {
        ProposalStatus.SUBMITTED: "diajukan",
        ProposalStatus.NEEDS_REVISION: "revisi",
        ProposalStatus.APPROVED: "disetujui",
        ProposalStatus.REJECTED: "ditolak",
        ProposalStatus.DRAFT: "draft",
    }
    proposals = OrganizerProposal.objects.select_related("applicant").prefetch_related(
        Prefetch(
            "reviews",
            queryset=ProposalReview.objects.order_by("-created_at", "-pk"),
            to_attr="admin_reviews",
        )
    )
    return [{
        "id": proposal.pk,
        "nama": proposal.applicant.get_full_name().strip() or proposal.applicant.email,
        "email": proposal.applicant.email,
        "org": proposal.organization_name,
        "rencana": proposal.proposal_text,
        "tanggal": timezone.localtime(proposal.submitted_at or proposal.created_at).strftime("%Y-%m-%d"),
        "status": statuses[proposal.status],
        "alasan": proposal.admin_reviews[0].reason if proposal.admin_reviews else "",
    } for proposal in proposals]


def _admin_ticket_rows():
    rows = [{
        "id": ticket.code,
        "judul": ticket.title,
        "pelapor": ticket.reporter,
        "org": ticket.organizer.get_full_name().strip() or ticket.organizer.email,
        "eventId": ticket.event_id,
        "tanggal": timezone.localtime(ticket.created_at).date().isoformat(),
        "status": "selesai" if ticket.status == OrganizerSupportTicket.Status.RESOLVED else "diaudit",
        "isi": ticket.description,
        "balasan": ticket.reply,
    } for ticket in OrganizerSupportTicket.objects.select_related("organizer", "event")]
    rows.extend({
        "id": f"CONTACT-{contact.pk}", "judul": f"Bantuan dari {contact.name}",
        "pelapor": f"{contact.name} ({contact.email})", "org": "Pengunjung",
        "eventId": None, "tanggal": timezone.localtime(contact.created_at).date().isoformat(),
        "status": "selesai" if contact.status == OrganizerSupportTicket.Status.RESOLVED else "diaudit",
        "isi": contact.message, "balasan": contact.reply, "contact": True,
        "can_delete": settings.DEBUG,
    } for contact in ContactMessage.objects.all())
    return sorted(rows, key=lambda row: row["tanggal"], reverse=True)


def _admin_finance_payload():
    settings_row, _ = PlatformSettings.objects.get_or_create(pk=1)
    fee = Decimal(settings_row.platform_fee_percent)
    events = list(Event.objects.select_related("organizer"))
    # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
    valid_registrations = Registration.objects.ticketed().filter(
        event_id__in=[event.pk for event in events],
    )
    ticket_counts = dict(valid_registrations.values("event__organizer_id").annotate(total=Count("pk")).values_list("event__organizer_id", "total"))
    payments = list(Payment.objects.filter(
        registration__event_id__in=[event.pk for event in events],
        registration__status=RegistrationStatus.REGISTERED,
        status=Payment.Status.APPROVED,
    ).select_related("registration__event__organizer"))
    paid_amounts = defaultdict(lambda: Decimal("0"))
    completed_amounts = defaultdict(lambda: Decimal("0"))
    monthly = defaultdict(lambda: Decimal("0"))
    event_count = defaultdict(int)
    for event in events:
        if event.status not in (EventStatus.SUBMITTED, EventStatus.REJECTED, EventStatus.DRAFT):
            event_count[event.organizer_id] += 1
    for payment in payments:
        organizer_id = payment.registration.event.organizer_id
        paid_amounts[organizer_id] += payment.amount
        if payment.registration.event.status == EventStatus.COMPLETED:
            completed_amounts[organizer_id] += payment.amount
        if payment.reviewed_at:
            key = timezone.localtime(payment.reviewed_at).strftime("%Y-%m")
            monthly[key] += payment.amount * fee / Decimal("100")
    payout_totals = defaultdict(lambda: Decimal("0"))
    for payout in PlatformPayout.objects.all():
        payout_totals[payout.organizer_id] += payout.amount
    organizer_ids = set(ticket_counts) | set(paid_amounts) | set(event_count)
    users = get_user_model().objects.filter(pk__in=organizer_ids).order_by("email")
    rows = []
    for user in users:
        gross = paid_amounts[user.pk]
        fee_amount = (gross * fee / Decimal("100")).quantize(Decimal("1"))
        net_completed = completed_amounts[user.pk] - (
            completed_amounts[user.pk] * fee / Decimal("100")
        ).quantize(Decimal("1"))
        withdrawn = payout_totals[user.pk]
        rows.append({
            "organizer_id": user.pk,
            "nama": user.get_full_name().strip() or user.email,
            "event": event_count[user.pk],
            "tiket": ticket_counts.get(user.pk, 0),
            "kotor": float(gross),
            "fee": float(fee_amount),
            "bersih": float(gross - fee_amount),
            "cair": float(withdrawn),
            "tersedia": float(max(Decimal("0"), net_completed - withdrawn)),
        })
    rows.sort(key=lambda row: row["kotor"], reverse=True)
    now = timezone.localtime(timezone.now())
    current_month = now.year * 12 + now.month - 1
    month_keys = []
    for offset in range(5, -1, -1):
        year, month_zero = divmod(current_month - offset, 12)
        month_keys.append(f"{year:04d}-{month_zero + 1:02d}")
    labels = [datetime.strptime(key, "%Y-%m").strftime("%b") for key in month_keys]
    values = [float(monthly[key]) for key in month_keys]
    return {
        "rows": rows,
        "fee": float(fee),
        "kotor": float(sum((Decimal(str(row["kotor"])) for row in rows), Decimal("0"))),
        "feeTotal": float(sum((Decimal(str(row["fee"])) for row in rows), Decimal("0"))),
        "cair": float(sum((Decimal(str(row["cair"])) for row in rows), Decimal("0"))),
        "tersedia": float(sum((Decimal(str(row["tersedia"])) for row in rows), Decimal("0"))),
        "monthly": {"labels": labels, "values": values},
    }


def _admin_audit_rows():
    rows = []
    for entry in PlatformAuditLog.objects.select_related("actor"):
        rows.append({
            "tipe": entry.category,
            "teks": entry.description,
            "aktor": entry.actor.get_full_name().strip() if entry.actor else entry.actor_label,
            "peran": entry.actor_role,
            "waktu": timezone.localtime(entry.created_at).strftime("%d %b %Y, %H:%M"),
            "sort": entry.created_at.isoformat(),
        })
    for change in AccountAccessChange.objects.select_related("actor", "user"):
        rows.append({
            "tipe": "pengguna", "teks": f"{change.get_action_display()}: {change.user.email} — {change.reason}",
            "aktor": change.actor.get_full_name().strip() or change.actor.email,
            "peran": "Admin Platform", "waktu": timezone.localtime(change.created_at).strftime("%d %b %Y, %H:%M"), "sort": change.created_at.isoformat(),
        })
    for transition in EventTransition.objects.select_related("actor", "event"):
        rows.append({
            "tipe": "event", "teks": f"Status event {transition.event.title} diperbarui: {transition.get_to_status_display()} {transition.reason}".strip(),
            "aktor": transition.actor.get_full_name().strip() or transition.actor.email,
            "peran": "Admin Platform", "waktu": timezone.localtime(transition.created_at).strftime("%d %b %Y, %H:%M"), "sort": transition.created_at.isoformat(),
        })
    for review in ProposalReview.objects.select_related("actor", "proposal__applicant"):
        review_status = {
            ProposalStatus.APPROVED: "disetujui",
            ProposalStatus.NEEDS_REVISION: "perlu revisi",
            ProposalStatus.REJECTED: "ditolak",
            ProposalStatus.SUBMITTED: "diajukan",
        }.get(review.to_status, review.to_status)
        rows.append({
            "tipe": "pengguna", "teks": f"Pengajuan {review.proposal.organization_name}: {review_status} {review.reason}".strip(),
            "aktor": review.actor.get_full_name().strip() or review.actor.email,
            "peran": "Admin Platform", "waktu": timezone.localtime(review.created_at).strftime("%d %b %Y, %H:%M"), "sort": review.created_at.isoformat(),
        })
    for payment in Payment.objects.filter(
        status=Payment.Status.APPROVED,
        reviewed_at__isnull=False,
    ).select_related("reviewed_by", "registration__participant", "registration__event"):
        if not payment.reviewed_by:
            continue
        rows.append({
            "tipe": "keuangan",
            "teks": f"Pembayaran Rp {payment.amount:,.0f} untuk {payment.registration.event.title} disetujui.",
            "aktor": payment.reviewed_by.get_full_name().strip() or payment.reviewed_by.email,
            "peran": "Admin Platform",
            "waktu": timezone.localtime(payment.reviewed_at).strftime("%d %b %Y, %H:%M"),
            "sort": payment.reviewed_at.isoformat(),
        })
    rows.sort(key=lambda row: row["sort"], reverse=True)
    return rows


def _admin_backend_payload(request):
    setting_row, _ = PlatformSettings.objects.get_or_create(pk=1)
    categories = [{"name": item.name, "active": item.is_active} for item in EventType.objects.order_by("name")]
    profile = request.user
    return {
        "events": _admin_event_rows(),
        "users": _admin_user_rows(),
        "proposals": _admin_proposal_rows(),
        "tickets": _admin_ticket_rows(),
        "finance": _admin_finance_payload(),
        "audit": _admin_audit_rows(),
        "settings": {
            "feePct": float(setting_row.platform_fee_percent),
            "approvalRequired": setting_row.event_approval_required,
            "categories": {item.name: item.is_active for item in EventType.objects.all()},
            "categoryRows": categories,
            "notif": setting_row.notifications,
        },
        "profile": {
            "nama": profile.get_full_name().strip(),
            "email": profile.email,
            "foto": profile.profile_photo.url if profile.profile_photo else "",
        },
    }


def _admin_panel(template):
    # OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
    @never_cache
    # OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
    @require_GET
    # OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
    @login_required(login_url="login_page")
    def view(request):
        _require_role(request, "ADMIN")
        context = {
            "admin_backend_data": _admin_backend_payload(request),
        }
        if template == "keuangan_admin":
            context["pending_payments"] = Payment.objects.filter(
                status=Payment.Status.UNDER_REVIEW,
                registration__status=RegistrationStatus.REGISTERED,
            ).select_related("registration__participant", "registration__event").order_by("submitted_at", "pk")
        return render(request, f"admin/{template}.html", context)

    return view

admin_dashboard = _admin_panel("dashboard_admin")
admin_users = _admin_panel("kelola_pengguna")

# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def admin_events(request):
    _require_role(request, "ADMIN")
    data = _admin_backend_payload(request)
    return render(
        request,
        "admin/event_admin.html",
        {
            "backend_admin_event_rows": data["events"],
            "admin_backend_data": data,
        },
    )

admin_support = _admin_panel("support_admin")
admin_finance = _admin_panel("keuangan_admin")
admin_audit = _admin_panel("audit_admin")
admin_settings = _admin_panel("pengaturan_admin")


def _admin_audit_write(request, category, description):
    PlatformAuditLog.objects.create(
        category=category,
        description=description[:500],
        actor=request.user,
        actor_label=request.user.get_full_name().strip() or request.user.email,
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def admin_user_mutation(request, pk=None):
    _require_role(request, "ADMIN")
    User = get_user_model()
    action = request.POST.get("action", "save")
    if pk is None:
        name = " ".join(request.POST.get("nama", "").split())
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("peran", "peserta")
        password = request.POST.get("password", "")
        if not 3 <= len(name) <= 80:
            return JsonResponse({"error": "Nama harus berisi 3–80 karakter."}, status=400)
        try:
            email = forms.EmailField().clean(email).lower()
        except ValidationError as exc:
            return JsonResponse({"error": exc.messages[0]}, status=400)
        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({"error": "Email sudah terdaftar."}, status=400)
        if len(password) < 12:
            return JsonResponse({"error": "Kata sandi awal minimal 12 karakter."}, status=400)
        role_map = {"peserta": "PARTICIPANT", "panitia": "COMMITTEE", "penyelenggara": "ORGANIZER"}
        if role not in role_map:
            return JsonResponse({"error": "Role akun tidak dapat dibuat dari menu ini."}, status=400)
        first, _, last = name.partition(" ")
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with transaction.atomic():
            user = User.objects.create_user(email=email, password=password, first_name=first, last_name=last)
            if role != "peserta":
                set_account_role(actor=request.user, user_id=user.pk, role=role_map[role], reason="Role ditetapkan saat akun dibuat Admin.")
            if role == "penyelenggara":
                OrganizerPreference.objects.update_or_create(
                    user=user,
                    defaults={"organization_name": request.POST.get("org", "").strip()[:80]},
                )
            _admin_audit_write(request, "pengguna", f"Akun {email} dibuat sebagai {role}.")
        return JsonResponse({"ok": True, "id": user.pk})

    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk or user.is_superuser or user.has_perm("accounts.manage_platform"):
        return JsonResponse({"error": "Akun admin tidak dapat diubah dari menu ini."}, status=403)
    if action in {"freeze", "activate"}:
        access_action = (
            AccountAccessChange.Action.SUSPEND
            if action == "freeze" else AccountAccessChange.Action.ACTIVATE
        )
        try:
            change = change_account_access(
                actor=request.user,
                user_id=user.pk,
                action=access_action,
                reason=request.POST.get("reason", "").strip(),
            )
        except (ValidationError, PermissionDenied) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            return JsonResponse({"error": message}, status=400)
        return JsonResponse({"ok": True})

    if action != "save":
        return JsonResponse({"error": "Aksi pengguna tidak dikenal."}, status=400)
    name = " ".join(request.POST.get("nama", "").split())
    role = request.POST.get("peran", "peserta")
    if not 3 <= len(name) <= 80:
        return JsonResponse({"error": "Nama harus berisi 3–80 karakter."}, status=400)
    role_map = {"peserta": "PARTICIPANT", "panitia": "COMMITTEE", "penyelenggara": "ORGANIZER"}
    if role not in role_map:
        return JsonResponse({"error": "Role tidak valid."}, status=400)
    first, _, last = name.partition(" ")
    current_role = user.role
    current_role_label = {"PARTICIPANT": "peserta", "COMMITTEE": "panitia", "ORGANIZER": "penyelenggara", "ADMIN": "admin"}[current_role]
    try:
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with transaction.atomic():
            if current_role_label != role:
                set_account_role(actor=request.user, user_id=user.pk, role=role_map[role], reason="Role diperbarui melalui menu Kelola Pengguna.")
            user.first_name, user.last_name = first, last
            user.save(update_fields=("first_name", "last_name"))
            if role == "penyelenggara":
                OrganizerPreference.objects.update_or_create(
                    user=user,
                    defaults={"organization_name": request.POST.get("org", "").strip()[:80]},
                )
            _admin_audit_write(request, "pengguna", f"Profil akun {user.email} diperbarui.")
    except (ValidationError, PermissionDenied) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
        return JsonResponse({"error": message}, status=400)
    return JsonResponse({"ok": True})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def admin_proposal_review(request, pk):
    _require_role(request, "ADMIN")
    decisions = {
        "approve": ProposalStatus.APPROVED,
        "revision": ProposalStatus.NEEDS_REVISION,
        "reject": ProposalStatus.REJECTED,
    }
    decision = decisions.get(request.POST.get("decision"))
    if not decision:
        return JsonResponse({"error": "Keputusan proposal tidak valid."}, status=400)
    try:
        proposal = review_proposal(
            actor=request.user,
            proposal_id=pk,
            decision=decision,
            reason=request.POST.get("reason", ""),
        )
    except (ValidationError, PermissionDenied) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
        return JsonResponse({"error": message}, status=400)
    return JsonResponse({"ok": True, "status": proposal.status})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def admin_support_mutation(request, code):
    _require_role(request, "ADMIN")
    is_contact = code.startswith("CONTACT-") and code[8:].isdigit()
    ticket = (get_object_or_404(ContactMessage, pk=int(code[8:])) if is_contact
              else get_object_or_404(OrganizerSupportTicket, code=code))
    action = request.POST.get("action")
    if action == "delete" and is_contact and settings.DEBUG:
        ticket.delete()
        _admin_audit_write(request, "support", f"Pesan pengujian {code} dihapus.")
        return JsonResponse({"ok": True})
    reply = request.POST.get("reply", "").strip()
    if action not in {"reply", "resolve"}:
        return JsonResponse({"error": "Aksi tiket tidak valid."}, status=400)
    if not reply or len(reply) > 2000:
        return JsonResponse({"error": "Balasan wajib diisi, maksimal 2000 karakter."}, status=400)
    ticket.reply = reply
    ticket.status = (
        OrganizerSupportTicket.Status.RESOLVED
        if action == "resolve" else OrganizerSupportTicket.Status.IN_PROGRESS
    )
    ticket.resolved_at = timezone.now() if action == "resolve" else None
    ticket.save(update_fields=("reply", "status", "resolved_at", "updated_at"))
    _admin_audit_write(request, "support", f"Tiket {code} {'diselesaikan' if action == 'resolve' else 'dibalas'}.")
    return JsonResponse({"ok": True})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def admin_payout(request):
    _require_role(request, "ADMIN")
    try:
        organizer_id = int(request.POST.get("organizer_id", ""))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Penyelenggara tidak valid."}, status=400)
    try:
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with transaction.atomic():
            organizer = get_object_or_404(get_user_model().objects.select_for_update(), pk=organizer_id)
            row = next((item for item in _admin_finance_payload()["rows"] if item["organizer_id"] == organizer.pk), None)
            amount = Decimal(str(row["tersedia"])) if row else Decimal("0")
            if amount <= 0:
                return JsonResponse({"error": "Tidak ada dana yang siap dicairkan."}, status=400)
            payout = PlatformPayout.objects.create(organizer=organizer, actor=request.user, amount=amount)
            _admin_audit_write(request, "keuangan", f"Pencairan demo Rp {amount:,.0f} dicatat untuk {organizer.email}.")
    except (ValidationError, PermissionDenied) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
        return JsonResponse({"error": message}, status=400)
    return JsonResponse({"ok": True, "amount": float(payout.amount)})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def admin_settings_mutation(request):
    _require_role(request, "ADMIN")
    setting_row, _ = PlatformSettings.objects.get_or_create(pk=1)
    action = request.POST.get("action")
    if action == "platform":
        try:
            fee = Decimal(request.POST.get("fee", ""))
        except Exception:
            return JsonResponse({"error": "Biaya platform harus berupa angka."}, status=400)
        if not Decimal("0") <= fee <= Decimal("20"):
            return JsonResponse({"error": "Biaya platform harus antara 0 dan 20 persen."}, status=400)
        approval = request.POST.get("approval") == "true"
        setting_row.platform_fee_percent = fee
        setting_row.event_approval_required = approval
        setting_row.updated_by = request.user
        setting_row.save(update_fields=("platform_fee_percent", "event_approval_required", "updated_by", "updated_at"))
        description = f"Pengaturan platform diubah: biaya {fee}% dan persetujuan event {'wajib' if approval else 'tidak wajib'}."
        category = "pengaturan"
    elif action in {"category-toggle", "category-add"}:
        name = " ".join(request.POST.get("name", "").split())
        if action == "category-add":
            if len(name) < 3 or len(name) > 100:
                return JsonResponse({"error": "Nama kategori harus berisi 3–100 karakter."}, status=400)
            code = slugify(name)[:32]
            if not code:
                return JsonResponse({"error": "Nama kategori tidak valid."}, status=400)
            event_type, created = EventType.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})
            if not created:
                return JsonResponse({"error": "Kategori sudah ada."}, status=400)
            setting_row.category_enabled[name] = True
            description = f'Kategori "{name}" ditambahkan.'
        else:
            event_type = get_object_or_404(EventType, name=name)
            if event_type.is_active and EventType.objects.filter(is_active=True).count() <= 1:
                return JsonResponse({"error": "Minimal satu kategori harus tetap aktif."}, status=400)
            event_type.is_active = not event_type.is_active
            event_type.save(update_fields=("is_active",))
            setting_row.category_enabled[event_type.name] = event_type.is_active
            description = f'Kategori "{event_type.name}" {"diaktifkan" if event_type.is_active else "dinonaktifkan"}.'
        setting_row.updated_by = request.user
        setting_row.save(update_fields=("category_enabled", "updated_by", "updated_at"))
        category = "pengaturan"
    elif action == "notification":
        key = request.POST.get("key", "")
        if key not in {"event", "support", "pengajuan", "keuangan"}:
            return JsonResponse({"error": "Preferensi notifikasi tidak dikenal."}, status=400)
        setting_row.notifications = dict(setting_row.notifications)
        setting_row.notifications[key] = request.POST.get("enabled") == "true"
        setting_row.updated_by = request.user
        setting_row.save(update_fields=("notifications", "updated_by", "updated_at"))
        description = f"Notifikasi {key} {'diaktifkan' if setting_row.notifications[key] else 'dinonaktifkan'}."
        category = "pengaturan"
    else:
        return JsonResponse({"error": "Aksi pengaturan tidak dikenal."}, status=400)
    _admin_audit_write(request, category, description)
    return JsonResponse({"ok": True})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def admin_profile_mutation(request):
    _require_role(request, "ADMIN")
    user = request.user
    action = request.POST.get("action")
    if action == "password":
        form = PasswordChangeForm(user, {
            "old_password": request.POST.get("current", ""),
            "new_password1": request.POST.get("password", ""),
            "new_password2": request.POST.get("confirm", ""),
        })
        if not form.is_valid():
            errors = [str(error) for items in form.errors.values() for error in items]
            return JsonResponse({"error": " ".join(errors)}, status=400)
        user = form.save()
        update_session_auth_hash(request, user)
        _admin_audit_write(request, "pengaturan", "Admin mengganti kata sandi akun.")
        return JsonResponse({"ok": True})
    if action != "profile":
        return JsonResponse({"error": "Aksi profil tidak valid."}, status=400)
    name = " ".join(request.POST.get("name", "").split())
    email = request.POST.get("email", "").strip().lower()
    if not 3 <= len(name) <= 80:
        return JsonResponse({"error": "Nama harus berisi 3–80 karakter."}, status=400)
    try:
        email = forms.EmailField().clean(email).lower()
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=400)
    if get_user_model().objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        return JsonResponse({"error": "Email sudah digunakan akun lain."}, status=400)
    upload = request.FILES.get("photo")
    if upload:
        if upload.size > 5 * 1024 * 1024 or upload.name.rsplit(".", 1)[-1].lower() not in {"jpg", "jpeg", "png", "webp"}:
            return JsonResponse({"error": "Gunakan foto JPG, PNG, atau WebP maksimal 5 MB."}, status=400)
        try:
            upload = forms.ImageField().clean(upload)
        except ValidationError as exc:
            return JsonResponse({"error": exc.messages[0]}, status=400)
    remove_photo = request.POST.get("remove_photo") == "1"
    old_name = user.profile_photo.name if user.profile_photo else ""
    storage = user.profile_photo.storage if user.profile_photo else None
    first, _, last = name.partition(" ")
    user.first_name, user.last_name, user.email = first, last, email
    fields = ["first_name", "last_name", "email"]
    if upload:
        user.profile_photo = upload
        fields.append("profile_photo")
    elif remove_photo:
        user.profile_photo = ""
        fields.append("profile_photo")
    user.save(update_fields=fields)
    if old_name and storage and (upload or remove_photo):
        storage.delete(old_name)
    _admin_audit_write(request, "pengaturan", "Profil Admin diperbarui.")
    return JsonResponse({"ok": True})

# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_http_methods): membatasi view ke daftar metode HTTP yang diberikan; tidak menambah pewarisan class.
@require_http_methods(["GET", "POST"])
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_akun(request):
    _require_role(request, "COMMITTEE")

    return peserta_akun(
        request,
        template_name="panitia_biasa/akun_panitia_biasa.html",
        success_url="panitia_akun",
    )


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_simpan_profil(request):
    _require_role(request, "COMMITTEE")
    user = request.user
    name = " ".join(request.POST.get("name", "").split())
    if not 3 <= len(name) <= 80:
        return JsonResponse({"error": "Nama harus berisi 3–80 karakter."}, status=400)

    password_form = None
    password_values = (
        request.POST.get("current_password", ""),
        request.POST.get("new_password", ""),
        request.POST.get("confirm_password", ""),
    )
    if any(password_values):
        password_form = PasswordChangeForm(user, {
            "old_password": password_values[0],
            "new_password1": password_values[1],
            "new_password2": password_values[2],
        })
        if not password_form.is_valid():
            errors = [str(error) for items in password_form.errors.values() for error in items]
            return JsonResponse({"error": " ".join(errors)}, status=400)

    upload = request.FILES.get("photo")
    if upload:
        if upload.size > 5 * 1024 * 1024:
            return JsonResponse({"error": "Ukuran foto maksimal 5 MB."}, status=400)
        if upload.name.rsplit(".", 1)[-1].lower() not in {"jpg", "jpeg", "png", "webp"}:
            return JsonResponse({"error": "Gunakan foto JPG, PNG, atau WebP."}, status=400)
        try:
            upload = forms.ImageField().clean(upload)
        except ValidationError as exc:
            return JsonResponse({"error": exc.messages[0]}, status=400)

    parts = name.split(" ", 1)
    user.first_name = parts[0]
    user.last_name = parts[1] if len(parts) > 1 else ""
    fields = ["first_name", "last_name"]
    old_photo_name = user.profile_photo.name if user.profile_photo else ""
    old_photo_storage = user.profile_photo.storage if user.profile_photo else None
    remove_photo = request.POST.get("remove_photo") == "1"
    if upload:
        user.profile_photo = upload
        fields.append("profile_photo")
    elif remove_photo:
        user.profile_photo = ""
        fields.append("profile_photo")
    user.save(update_fields=fields)
    if password_form:
        user = password_form.save()
        update_session_auth_hash(request, user)
    if old_photo_name and old_photo_storage and (upload or remove_photo):
        old_photo_storage.delete(old_photo_name)

    return JsonResponse({
        "ok": True,
        "name": user.get_full_name().strip(),
        "photo_url": user.profile_photo.url if user.profile_photo else "",
        "password_updated": bool(password_form),
    })



# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_simpan_dokumentasi(request):
    """Simpan tautan dokumentasi oleh panitia yang ditugaskan pada event tersebut (respons JSON)."""
    if request.user.role != "COMMITTEE" or not request.user.is_active:
        raise PermissionDenied

    event = get_object_or_404(
        Event.objects.filter(
            committee_assignments__member=request.user,
            committee_assignments__is_active=True,
            status__in=(EventStatus.PUBLISHED, EventStatus.COMPLETED),
        ),
        pk=request.POST.get("event_id"),
    )

    url = request.POST.get("documentation_url", "").strip()
    try:
        # Aturan yang sama dengan model: URLField + validator host Google.
        event._meta.get_field("documentation_url").clean(url, event)
    except ValidationError as exc:
        return JsonResponse({"errors": {"documentation_url": exc.messages}}, status=400)

    event.documentation_url = url
    event.save(update_fields=["documentation_url", "updated_at"])
    return JsonResponse({
        "id": event.pk,
        "documentation_url": event.documentation_url,
        "status": event.status,
    })


# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_upload_sertifikat(request):
    """Panitia yang ditugaskan mengunggah (atau mengganti) sertifikat peserta yang hadir."""
    _require_role(request, "COMMITTEE")

    registration = get_object_or_404(
        Registration.objects.select_related("event", "attendance"),
        pk=request.POST.get("registration_id"),
        status=RegistrationStatus.REGISTERED,
        attendance__status=Attendance.Status.PRESENT,
        event__committee_assignments__member=request.user,
        event__committee_assignments__is_active=True,
    )

    uploaded_file = request.FILES.get("certificate_file")
    if uploaded_file is None:
        return JsonResponse({"errors": ["Pilih file sertifikat terlebih dahulu."]}, status=400)

    # OOP — Duck typing: objek unggahan dipakai melalui read()/seek(); implementasi file di memori atau disk dapat memenuhi protokol yang sama.
    head = uploaded_file.read(8)
    uploaded_file.seek(0)
    if not (head.startswith(b"%PDF") or head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8\xff")):
        return JsonResponse({"errors": ["Isi file bukan PDF, PNG, atau JPG yang valid."]}, status=400)

    certificate = getattr(registration, "uploaded_certificate", None)
    old_name = certificate.file.name if certificate else None
    if certificate is None:
        certificate = UploadedCertificate(registration=registration)
    certificate.file = uploaded_file
    certificate.uploaded_by = request.user
    try:
        certificate.full_clean()
    except ValidationError as exc:
        return JsonResponse({"errors": exc.messages}, status=400)
    certificate.save()
    if old_name and old_name != certificate.file.name:
        certificate.file.storage.delete(old_name)

    return JsonResponse({
        "registration_id": registration.pk,
        "uploaded_at": timezone.localtime(certificate.uploaded_at).strftime("%d/%m/%Y %H:%M"),
    })


# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def panitia_hapus_sertifikat(request):
    _require_role(request, "COMMITTEE")

    certificate = get_object_or_404(
        UploadedCertificate,
        registration_id=request.POST.get("registration_id"),
        registration__event__committee_assignments__member=request.user,
        registration__event__committee_assignments__is_active=True,
    )
    name, storage = certificate.file.name, certificate.file.storage
    certificate.delete()
    storage.delete(name)
    return JsonResponse({"registration_id": request.POST.get("registration_id")})


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
def peserta_sertifikat_unggahan(request, pk):
    """Peserta mengunduh sertifikat yang diunggah panitia; hanya pemilik registrasi."""
    participant_redirect = _participant_redirect(request)
    if participant_redirect:
        return participant_redirect

    registration = get_object_or_404(
        Registration.objects.owned_by(request.user).select_related("uploaded_certificate"),
        pk=pk,
        status=RegistrationStatus.REGISTERED,
        uploaded_certificate__isnull=False,
        attendance__status=Attendance.Status.PRESENT,
    )
    certificate = registration.uploaded_certificate
    try:
        handle = certificate.file.open("rb")
    except OSError:
        raise Http404("File sertifikat tidak ditemukan.")
    extension = Path(certificate.file.name).suffix.lower()
    return FileResponse(
        handle, as_attachment=True,
        filename=f"sertifikat-simevent-{registration.pk:06d}{extension}",
    )
