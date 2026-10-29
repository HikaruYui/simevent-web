from pathlib import Path
import json
from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from apps.accounts.forms import ProfileForm
from apps.accounts.permissions import require_organizer
from apps.events.forms import AdminEventForm, EventForm
from apps.achievements.models import Achievement
from django.core.exceptions import PermissionDenied
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from apps.registrations.models import Ticket
from apps.registrations.models import (
    Attendance,
    CertificateTemplate,
    Payment,
    Registration,
    RegistrationStatus,
    UploadedCertificate,
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
)
from apps.accounts.forms import RegistrationForm


@never_cache
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
        .select_related("event_type")
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


@require_GET
def tentang(request):
    return render(
        request,
        "tentang.html",
    )
@require_GET
def bantuan(request):
    return render(
        request,
        "bantuan.html",
    )


@never_cache
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



@never_cache
@require_GET
def detail_event(request, slug):
    event = get_object_or_404(
        Event.objects
        .public()
        .select_related(
            "event_type",
            "organizer",
        ),
        slug=slug,
    )

    return render(
        request,
        "events/detail.html",
        {
            "event": event,
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

@never_cache
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


@never_cache
@require_POST
def logout_page(request):
    logout(request)

    return redirect(
        "landing"
    )


@never_cache
@require_GET
@login_required(login_url="login_page")
def after_login(request):
    if not request.user.is_active:
        raise PermissionDenied("Akun Anda tidak aktif.")

    return redirect(_dashboard_name(request.user))


@never_cache
@require_http_methods(["GET", "POST"])
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


@never_cache
@require_POST
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


@never_cache
@require_GET
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


@never_cache
@require_GET
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


@never_cache
@require_GET
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


@never_cache
@require_GET
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
    registered_ids = set(
        Registration.objects.owned_by(request.user)
        .filter(status=RegistrationStatus.REGISTERED)
        .values_list("event_id", flat=True)
    )
    documentation_ids = _documentation_event_ids(request.user)
    for event in events:
        event.is_registered = event.pk in registered_ids
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
    })


@never_cache
@require_GET
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


@never_cache
@require_GET
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


@never_cache
@require_GET
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


@never_cache
@require_http_methods(["GET", "POST"])
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

        registrations = (
            Registration.objects.filter(
                event=selected_event,
                status=RegistrationStatus.REGISTERED,
                ticket__is_active=True,
            )
            .filter(
                Q(
                    event__price=0,
                    payment__isnull=True,
                )
                | Q(
                    payment__status=Payment.Status.APPROVED,
                )
            )
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
                "code": str(registration.ticket.identifier),
                "name": (
                    participant.get_full_name().strip()
                    or participant.email
                ),
                "email": participant.email,
                "present": is_present,
                "checkinTime": checkin_time,
            })

    panitia_db_data = None

    if selected_event:
        panitia_db_data = {
            "eventId": selected_event.pk,
            "eventName": selected_event.title,
            "selectedEventId": selected_event.pk,
            "documentationUrl": selected_event.documentation_url,
            "events": [
                {
                    "id": event.pk,
                    "name": event.title,
                }
                for event in event_list
            ],
            "participants": participant_rows,
        }

    return render(
        request,
        "panitia_biasa_page.html",
        {
            "panitia_db_data": panitia_db_data,
            "documentation_events": event_list,
            "certificate_rows": certificate_rows,
            "certificate_event": selected_event,
            "certificate_events": event_list,
        },
    )


@never_cache
@require_GET
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
    @never_cache
    @require_GET
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
    tickets = list(
        Ticket.objects.filter(
            registration__event_id__in=event_ids,
            registration__status=RegistrationStatus.REGISTERED,
            is_active=True,
        )
        .filter(
            Q(registration__payment__status=Payment.Status.APPROVED)
            | Q(
                registration__event__price=0,
                registration__payment__isnull=True,
            )
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


@never_cache
@require_GET
@login_required(login_url="login_page")
def eo_dashboard(request):
    _require_role(request, "ORGANIZER")
    dashboard_data = _build_eo_dashboard_data(request.user)

    return render(
        request,
        "ketua_panitia/dashboard.html",
        {"eo_dashboard_data": dashboard_data},
    )


@never_cache
@require_GET
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
    registrations = (
        Registration.objects.filter(
            event_id__in=event_ids,
            status=RegistrationStatus.REGISTERED,
        )
        .filter(
            Q(
                event__price=0,
                payment__isnull=True,
            )
            | Q(
                payment__status=Payment.Status.APPROVED,
            )
        )
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

@never_cache
@require_GET
@login_required(login_url="login_page")
def eo_pendapatan(request):
    _require_role(request, "ORGANIZER")
    return render(request, "ketua_panitia/pendapatan.html", {
        "eo_dashboard_data": _build_eo_dashboard_data(request.user),
    })


@never_cache
@require_GET
@login_required(login_url="login_page")
def eo_log(request):
    _require_role(request, "ORGANIZER")
    return render(request, "ketua_panitia/log_aktivitas.html", {
        "eo_dashboard_data": _build_eo_dashboard_data(request.user),
    })


@never_cache
@require_GET
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


@never_cache
@require_GET
@login_required(login_url="login_page")
def eo_pengaturan(request):
    _require_role(request, "ORGANIZER")
    return render(request, "ketua_panitia/pengaturan.html", {
        "eo_settings_data": _eo_settings_payload(request.user),
        "eo_dashboard_data": _build_eo_dashboard_data(request.user),
    })


@login_required(login_url="login_page")
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


@login_required(login_url="login_page")
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


@login_required(login_url="login_page")
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


@login_required(login_url="login_page")
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


@login_required(login_url="login_page")
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


@login_required(login_url="login_page")
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
    return JsonResponse({"ok": True, "settings": _eo_settings_payload(request.user)})


@login_required(login_url="login_page")
@require_POST
def eo_settings_invitation_action(request, pk):
    _require_role(request, "ORGANIZER")
    invitation = get_object_or_404(
        OrganizerInvitation.objects.filter(organizer=request.user), pk=pk,
    )
    action = request.POST.get("action")
    if action == "cancel":
        invitation.delete()
    elif action == "resend":
        invitation.sent_at = timezone.now()
        invitation.expires_at = invitation.sent_at + timedelta(days=7)
        invitation.save(update_fields=("sent_at", "expires_at"))
    else:
        return JsonResponse({"error": "Aksi undangan tidak dikenal."}, status=400)
    return JsonResponse({"ok": True, "settings": _eo_settings_payload(request.user)})


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


@never_cache
@require_GET
@login_required(login_url="login_page")
def eo_event(request):
    _require_role(request, "ORGANIZER")

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


@never_cache
@require_GET
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

def _admin_panel(template):
    @never_cache
    @require_GET
    @login_required(login_url="login_page")
    def view(request):
        _require_role(request, "ADMIN")

        return render(
            request,
            f"admin/{template}.html",
        )

    return view

admin_dashboard = _admin_panel("dashboard_admin")
admin_users = _admin_panel("kelola_pengguna")

@never_cache
@require_GET
@login_required(login_url="login_page")
def admin_events(request):
    _require_role(request, "ADMIN")

    now = timezone.now()

    # Ambil seluruh event dari PostgreSQL.
    # Halaman ini hanya boleh diakses Admin Platform.
    events = list(
        Event.objects
        .select_related("event_type", "organizer")
        .annotate(
            ticket_count=Count(
                "registrations",
                filter=(
                    Q(
                        registrations__status=RegistrationStatus.REGISTERED,
                        registrations__ticket__is_active=True,
                    )
                    & (
                        Q(price=0)
                        | Q(
                            registrations__payment__status=
                            Payment.Status.APPROVED
                        )
                    )
                ),
                distinct=True,
            )
        )
        .order_by("-created_at", "-pk")
    )

    # Ambil catatan keputusan terbaru dari database.
    reasons = {}

    for transition in (
        EventTransition.objects
        .filter(event_id__in=[e.pk for e in events])
        .order_by("-created_at", "-pk")
    ):
        reasons.setdefault(
            transition.event_id,
            transition.reason,
        )

    status_map = {
        EventStatus.DRAFT: "draft",
        EventStatus.SUBMITTED: "diajukan",
        EventStatus.NEEDS_REVISION: "revisi",
        EventStatus.APPROVED: "disetujui",
        EventStatus.REJECTED: "ditolak",
        EventStatus.COMPLETED: "selesai",
        EventStatus.CANCELLED: "dibatalkan",
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
            status = status_map.get(
                event.status,
                "draft",
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
            "organizer": (
                event.organizer.get_full_name().strip()
                or event.organizer.email
            ),
            "organizer_email": event.organizer.email,
            "deskripsi": event.description,
            "has_proposal": bool(event.proposal),
            "alasan": reasons.get(event.pk, ""),
        })

    return render(
        request,
        "admin/event_admin.html",
        {
            "backend_admin_event_rows": event_rows,
        },
    )

admin_support = _admin_panel("support_admin")
admin_finance = _admin_panel("keuangan_admin")
admin_audit = _admin_panel("audit_admin")
admin_settings = _admin_panel("pengaturan_admin")

@never_cache
@require_http_methods(["GET", "POST"])
@login_required(login_url="login_page")
def panitia_akun(request):
    _require_role(request, "COMMITTEE")

    return peserta_akun(
        request,
        template_name="panitia_biasa/akun_panitia_biasa.html",
        success_url="panitia_akun",
    )


@never_cache
@require_POST
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



@require_POST
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


@require_POST
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


@require_POST
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


@never_cache
@require_GET
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
