# Halaman MVT publik, autentikasi halaman, dan dashboard pengelolaan event.

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import require_organizer
from apps.events.forms import AdminEventForm, EventForm
from apps.events.models import Event, EventStatus, EventType
from apps.registrations.models import Registration


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
    if request.user.role in (
        "ADMIN",
        "ORGANIZER",
    ):
        return redirect(
            "panitia_dashboard"
        )

    return redirect(
        "peserta_dashboard"
    )


# =========================================================
# DASHBOARD PESERTA
# =========================================================

@never_cache
@require_GET
@login_required(login_url="login_page")
def peserta_dashboard(request):
    if request.user.role in (
        "ADMIN",
        "ORGANIZER",
    ):
        return redirect(
            "panitia_dashboard"
        )

    return render(
        request,
        "peserta_page.html",
    )


# =========================================================
# DASHBOARD PANITIA / ADMIN
# =========================================================

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