# Halaman MVT publik, autentikasi halaman, dan dashboard pengelolaan event.

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.forms import ProfileForm
from apps.accounts.permissions import require_organizer
from apps.events.forms import AdminEventForm, EventForm
from apps.events.models import Event, EventStatus, EventType
from apps.achievements.models import Achievement
from apps.registrations.models import (
    Attendance,
    CertificateTemplate,
    Payment,
    Registration,
    RegistrationStatus,
)


# =========================================================
# HALAMAN PUBLIK
# =========================================================

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
        if (
            event.status == EventStatus.COMPLETED
            or event.end_datetime <= now
        ):
            ui_status = "done"

        elif event.start_datetime <= now < event.end_datetime:
            ui_status = "live"

        else:
            ui_status = "soon"

        organizer_name = (
            event.organizer
            .get_full_name()
            .strip()
        )

        if not organizer_name:
            organizer_name = event.organizer.email

        local_start = timezone.localtime(
            event.start_datetime
        )

        event_data.append(
            {
                "id": event.pk,
                "slug": event.slug,
                "category": event.event_type.code.lower(),
                "categoryName": event.event_type.name,
                "status": ui_status,
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


# =========================================================
# AUTENTIKASI
# =========================================================

def _participant_redirect(request):
    if request.user.role == "ORGANIZER":
        return redirect("eo_dashboard")
    if request.user.role == "ADMIN":
        return redirect("panitia_dashboard")
    if not request.user.profile_complete:
        return redirect("peserta_akun")
    return None

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
    if request.user.role == "ORGANIZER":
        return redirect(
            "eo_dashboard"
        )

    if request.user.role == "ADMIN":
        return redirect(
            "panitia_dashboard"
        )

    return redirect("peserta_dashboard" if request.user.profile_complete else "peserta_akun")


@never_cache
@require_http_methods(["GET", "POST"])
@login_required(login_url="login_page")
def peserta_akun(request):
    if request.user.role in ("ADMIN", "ORGANIZER"):
        return redirect("panitia_dashboard")

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Biodata berhasil disimpan. Akun Anda siap digunakan.")
            return redirect("peserta_dashboard")
    else:
        form = ProfileForm(instance=request.user)

    profile_values = (
        request.user.first_name,
        request.user.email,
        request.user.ktp_number,
        request.user.gender,
        request.user.birth_place,
        request.user.birth_date,
        request.user.address,
        request.user.phone_number,
    )
    completed_profile_fields = sum(
        bool(value.strip() if isinstance(value, str) else value)
        for value in profile_values
    )

    return render(request, "peserta/akun.html", {
        "form": form,
        "profile_complete": request.user.profile_complete,
        "completed_profile_fields": completed_profile_fields,
        "profile_progress": round(completed_profile_fields * 100 / len(profile_values)),
    })


# =========================================================
# DASHBOARD PESERTA
# =========================================================

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

    for registration in registrations:
        registration.certificate_ready = registration in certificates

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
    for event in events:
        event.is_registered = event.pk in registered_ids
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
    return render(request, "peserta/daftar_event.html", {
        "events": events,
        "categories": list(
            EventType.objects.filter(is_active=True).values_list("name", flat=True)
        ),
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
        .select_related("event", "event__organizer", "attendance", "feedback", "payment")
        .order_by("-event__start_datetime", "-pk")
    )
    for registration in registrations:
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


# =========================================================
# DASHBOARD PANITIA / ADMIN
# =========================================================

@never_cache
@require_GET
@login_required(login_url="login_page")
def panitia_biasa_dashboard(request):
    # Bypass pengecekan permission (require_organizer) untuk panitia biasa
    return render(request, "panitia_biasa_page.html")

@never_cache
@require_GET
@login_required(login_url="login_page")
def panitia_dashboard(request):
    require_organizer(
        request.user
    )

    events = (
        Event.objects
        .managed_by(request.user)
        .select_related("event_type")
    )

    if request.user.has_perm(
        "accounts.manage_platform"
    ):
        create_event_form = (
            AdminEventForm()
        )

    else:
        create_event_form = (
            EventForm()
        )

    return render(
        request,
        "panitia_page.html",
        {
            "managed_events": (
                events.order_by(
                    "-created_at",
                    "-pk",
                )
            ),

            "total_events": (
                events.count()
            ),

            "draft_events": (
                events
                .filter(
                    status=EventStatus.DRAFT
                )
                .count()
            ),

            "published_events": (
                events
                .filter(
                    status=EventStatus.PUBLISHED
                )
                .count()
            ),

            "completed_events": (
                events
                .filter(
                    status=EventStatus.COMPLETED
                )
                .count()
            ),

            "display_name": (
                request.user
                .get_full_name()
                .strip()
                or request.user.email
            ),

            "role_label": (
                "Admin"
                if request.user.role == "ADMIN"
                else "Panitia"
            ),

            "create_event_form": (
                create_event_form
            ),
        },
    )


# =========================================================
# DASHBOARD KETUA PANITIA (data contoh, belum dari database)
# =========================================================

def _ketua_panitia(template):
    @never_cache
    @require_GET
    @login_required(login_url="login_page")
    def view(request):
        require_organizer(request.user)
        return render(request, f"ketua_panitia/{template}.html")
    return view

eo_dashboard = _ketua_panitia("dashboard")
eo_event = _ketua_panitia("event")
eo_peserta = _ketua_panitia("peserta")
eo_pendapatan = _ketua_panitia("pendapatan")
eo_log = _ketua_panitia("log_aktivitas")
eo_support = _ketua_panitia("support")
eo_pengaturan = _ketua_panitia("pengaturan")

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
        if getattr(request.user, 'role', None) != "ADMIN" and not request.user.is_staff:
            return redirect("landing")
        return render(request, f"admin/{template}.html")
    return view

admin_dashboard = _admin_panel("dashboard_admin")
admin_users = _admin_panel("kelola_pengguna")
admin_events = _admin_panel("event_admin")
admin_support = _admin_panel("support_admin")
admin_finance = _admin_panel("keuangan_admin")
admin_audit = _admin_panel("audit_admin")
admin_settings = _admin_panel("pengaturan_admin")