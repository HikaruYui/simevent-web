# Fungsi file: Model, relasi, queryset, dan constraint database untuk event, ownership, dan alur approval/publikasi.

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone


class EventStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    NEEDS_REVISION = "NEEDS_REVISION", "Needs revision"
    APPROVED = "APPROVED", "Approved"
    PUBLISHED = "PUBLISHED", "Published"
    COMPLETED = "COMPLETED", "Completed"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


class DeliveryMode(models.TextChoices):
    OFFLINE = "OFFLINE", "Offline"
    ONLINE = "ONLINE", "Online"
    HYBRID = "HYBRID", "Hybrid"


def banner_upload_path(instance, filename):
    return f"event-banners/{uuid4().hex}{Path(filename).suffix.lower()}"


class EventType(models.Model):
    code = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class EventQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status__in=(EventStatus.PUBLISHED, EventStatus.COMPLETED))

    def managed_by(self, user):
        if not user.is_authenticated or not user.is_active:
            return self.none()
        if not user.has_perm("events.view_event"):
            return self.none()
        if user.has_perm("accounts.manage_platform"):
            return self.all()
        if user.has_perm("accounts.access_organizer"):
            return self.filter(organizer=user)
        return self.none()


class Event(models.Model):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organized_events"
    )
    event_type = models.ForeignKey(EventType, on_delete=models.PROTECT, related_name="events")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, editable=False)
    description = models.TextField(max_length=20000)
    delivery_mode = models.CharField(max_length=10, choices=DeliveryMode.choices)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    venue = models.CharField(max_length=500, blank=True)
    capacity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    registration_open = models.DateTimeField()
    registration_close = models.DateTimeField()
    banner = models.ImageField(upload_to=banner_upload_path, blank=True)
    status = models.CharField(
        max_length=20, choices=EventStatus.choices, default=EventStatus.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ("start_datetime", "pk")
        permissions = [
            ("submit_event", "Can submit an event"),
            ("review_event", "Can approve, reject or request event revision"),
            ("publish_event", "Can publish or unpublish an event"),
            ("complete_event", "Can complete an event"),
            ("cancel_event", "Can cancel an event"),
        ]
        indexes = [
            models.Index(fields=["status", "start_datetime"], name="event_public_schedule_idx"),
            models.Index(fields=["organizer", "status"], name="event_owner_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_datetime__gt=models.F("start_datetime")),
                name="event_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(registration_open__lt=models.F("registration_close"))
                & models.Q(registration_close__lte=models.F("start_datetime")),
                name="event_registration_window_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(capacity__gt=0), name="event_capacity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="event_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=EventStatus.values), name="event_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(delivery_mode__in=DeliveryMode.values),
                name="event_delivery_mode_valid",
            ),
        ]

    @property
    def is_editable(self):
        return self.status in (EventStatus.DRAFT, EventStatus.NEEDS_REVISION)

    @property
    def is_ongoing(self):
        return (
            self.status == EventStatus.PUBLISHED
            and self.start_datetime <= timezone.now() < self.end_datetime
        )

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.start_datetime and self.end_datetime
            and self.end_datetime <= self.start_datetime
        ):
            errors["end_datetime"] = "End must be after start."
        if self.registration_open and self.registration_close:
            if self.registration_open >= self.registration_close:
                errors["registration_close"] = "Registration must close after it opens."
        if self.registration_close and self.start_datetime:
            if self.registration_close > self.start_datetime:
                errors["registration_close"] = "Registration must close by event start."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class EventAccess(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="private_access")
    meeting_url = models.URLField(
        max_length=1000, blank=True, validators=[URLValidator(schemes=["https"])]
    )
    instructions = models.TextField(max_length=5000, blank=True)

    def __str__(self):
        return f"Private access for event #{self.event_id}"


class EventTransition(models.Model):
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="transitions")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="event_transitions"
    )
    from_status = models.CharField(max_length=20, choices=EventStatus.choices)
    to_status = models.CharField(max_length=20, choices=EventStatus.choices)
    reason = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(from_status__in=EventStatus.values)
                & models.Q(to_status__in=EventStatus.values)
                & ~models.Q(from_status=models.F("to_status")),
                name="event_transition_states_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(to_status__in=["NEEDS_REVISION", "REJECTED", "CANCELLED"])
                | ~models.Q(reason=""),
                name="event_transition_reason_required",
            ),
        ]
