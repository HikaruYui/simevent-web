
# Fungsi file: Model, relasi, queryset, dan constraint database untuk event, ownership, dan alur approval/publikasi.

from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import FileExtensionValidator, URLValidator
from django.db import models
from django.utils import timezone


# Tautan dokumentasi tampil kepada peserta, jadi hanya host Google yang diterima.
DOCUMENTATION_HOSTS = frozenset({
    "drive.google.com",
    "photos.google.com",
    "photos.app.goo.gl",
})


def validate_documentation_url(value):
    if not value:
        return
    URLValidator(schemes=["https"])(value)
    host = (urlsplit(value).hostname or "").lower()
    if host not in DOCUMENTATION_HOSTS:
        raise ValidationError(
            "Gunakan tautan Google Drive atau Google Foto (https://drive.google.com/...)."
        )


# Inheritance: EventStatus mewarisi enum Django untuk pilihan nilai dan label.
class EventStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    NEEDS_REVISION = "NEEDS_REVISION", "Needs revision"
    APPROVED = "APPROVED", "Approved"
    PUBLISHED = "PUBLISHED", "Published"
    COMPLETED = "COMPLETED", "Completed"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


# Inheritance: DeliveryMode mewarisi enum Django untuk pilihan nilai dan label.
class DeliveryMode(models.TextChoices):
    OFFLINE = "OFFLINE", "Offline"
    ONLINE = "ONLINE", "Online"
    HYBRID = "HYBRID", "Hybrid"


def banner_upload_path(instance, filename):
    return f"event-banners/{uuid4().hex}{Path(filename).suffix.lower()}"


# Inheritance: EventType mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class EventType(models.Model):
    code = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("name",)

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return self.name


# Inheritance: EventQuerySet mewarisi operasi query Django untuk menambahkan filter domain.
# OOP — Hierarchical inheritance: models.QuerySet juga menjadi induk class saudara lain di proyek.
class EventQuerySet(models.QuerySet):
    # Abstraction: public() membungkus aturan filter agar pemanggil dapat memakai ulang query domain.
    def public(self):
        return self.filter(
            status__in=(
                EventStatus.PUBLISHED,
                EventStatus.COMPLETED,
            )
        )

    # Abstraction: managed_by() membungkus aturan filter agar pemanggil dapat memakai ulang query domain.
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


# =========================================================
# PENYIMPANAN PROPOSAL EVENT
# Diletakkan sebelum class Event agar dikenali Python.
# =========================================================

def private_proposal_storage():
    # Proposal disimpan di luar MEDIA_ROOT agar tidak
    # dapat diakses langsung melalui URL /media/.
    return FileSystemStorage(
        location=settings.BASE_DIR / "private_media"
    )


def proposal_upload_path(instance, filename):
    return f"event-proposals/{uuid4().hex}.pdf"


# =========================================================
# MODEL EVENT
# =========================================================

# Inheritance: Event mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class Event(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organized_events",
    )

    # OOP — Association (ForeignKey): menghubungkan objek ke EventType; relasi database bukan pewarisan class.
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.PROTECT,
        related_name="events",
    )

    title = models.CharField(max_length=200)

    slug = models.SlugField(
        max_length=220,
        unique=True,
        editable=False,
    )

    description = models.TextField(max_length=20000)

    delivery_mode = models.CharField(
        max_length=10,
        choices=DeliveryMode.choices,
    )

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    venue = models.CharField(
        max_length=500,
        blank=True,
    )

    capacity = models.PositiveIntegerField()

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    registration_open = models.DateTimeField()
    registration_close = models.DateTimeField()

    banner = models.ImageField(
        upload_to=banner_upload_path,
        blank=True,
    )

    # Proposal PDF disimpan secara privat.
    proposal = models.FileField(
        upload_to=proposal_upload_path,
        storage=private_proposal_storage,
        validators=[FileExtensionValidator(["pdf"])],
        blank=True,
    )

    # Tautan folder dokumentasi (Google Drive) yang diisi panitia.
    # Hanya dibuka untuk peserta yang hadir setelah event COMPLETED.
    documentation_url = models.URLField(
        max_length=1000,
        blank=True,
        validators=[validate_documentation_url],
    )
    hide_from_committee_documentation = models.BooleanField(
        default=False,
        help_text="Sembunyikan hanya dari daftar Dokumentasi Event Panitia Biasa.",
    )

    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # OOP — Factory / delegation: as_manager() membentuk manager yang mengekspos method QuerySet khusus lewat objects.
    objects = EventQuerySet.as_manager()

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("start_datetime", "pk")

        permissions = [
            ("submit_event", "Can submit an event"),
            (
                "review_event",
                "Can approve, reject or request event revision",
            ),
            (
                "publish_event",
                "Can publish or unpublish an event",
            ),
            ("complete_event", "Can complete an event"),
            ("cancel_event", "Can cancel an event"),
        ]

        indexes = [
            models.Index(
                fields=["status", "start_datetime"],
                name="event_public_schedule_idx",
            ),
            models.Index(
                fields=["organizer", "status"],
                name="event_owner_status_idx",
            ),
        ]

        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    end_datetime__gt=models.F("start_datetime")
                ),
                name="event_end_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        registration_open__lt=models.F(
                            "registration_close"
                        )
                    )
                    & models.Q(
                        registration_close__lte=models.F(
                            "start_datetime"
                        )
                    )
                ),
                name="event_registration_window_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(capacity__gt=0),
                name="event_capacity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="event_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=EventStatus.values),
                name="event_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    delivery_mode__in=DeliveryMode.values
                ),
                name="event_delivery_mode_valid",
            ),
        ]

    # Encapsulation: is_editable menyajikan hasil perhitungan sebagai atribut baca tanpa setter.
    # OOP — Property / descriptor: method diakses seperti atribut; nilai dihitung melalui getter.
    @property
    def is_editable(self):
        return self.status in (
            EventStatus.DRAFT,
            EventStatus.NEEDS_REVISION,
        )

    # Encapsulation: is_ongoing menyajikan hasil perhitungan sebagai atribut baca tanpa setter.
    # OOP — Property / descriptor: method diakses seperti atribut; nilai dihitung melalui getter.
    @property
    def is_ongoing(self):
        return (
            self.status == EventStatus.PUBLISHED
            and self.start_datetime
            <= timezone.now()
            < self.end_datetime
        )

    # Polymorphism: menambahkan validasi khusus pada hook clean() milik Django.
    def clean(self):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        super().clean()

        errors = {}

        if (
            self.start_datetime
            and self.end_datetime
            and self.end_datetime <= self.start_datetime
        ):
            errors["end_datetime"] = (
                "End must be after start."
            )

        if (
            self.registration_open
            and self.registration_close
        ):
            if (
                self.registration_open
                >= self.registration_close
            ):
                errors["registration_close"] = (
                    "Registration must close after it opens."
                )

        if (
            self.registration_close
            and self.start_datetime
        ):
            if (
                self.registration_close
                > self.start_datetime
            ):
                errors["registration_close"] = (
                    "Registration must close by event start."
                )

        if errors:
            raise ValidationError(errors)

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return self.title


# =========================================================
# AKSES PRIVAT EVENT ONLINE / HYBRID
# =========================================================

# Inheritance: EventAccess mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class EventAccess(models.Model):
    # OOP — Association (OneToOneField): menghubungkan objek ke Event; relasi database bukan pewarisan class.
    event = models.OneToOneField(
        Event,
        on_delete=models.CASCADE,
        related_name="private_access",
    )

    meeting_url = models.URLField(
        max_length=1000,
        blank=True,
        validators=[
            URLValidator(schemes=["https"])
        ],
    )

    instructions = models.TextField(
        max_length=5000,
        blank=True,
    )

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"Private access for event #{self.event_id}"


# =========================================================
# RIWAYAT PERUBAHAN STATUS EVENT
# =========================================================

# Inheritance: EventTransition mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class EventTransition(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke Event; relasi database bukan pewarisan class.
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="transitions",
    )

    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="event_transitions",
    )

    from_status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
    )

    to_status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
    )

    reason = models.TextField(
        max_length=2000,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("created_at", "pk")

        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        from_status__in=EventStatus.values
                    )
                    & models.Q(
                        to_status__in=EventStatus.values
                    )
                    & ~models.Q(
                        from_status=models.F("to_status")
                    )
                ),
                name="event_transition_states_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(
                        to_status__in=[
                            "NEEDS_REVISION",
                            "REJECTED",
                            "CANCELLED",
                        ]
                    )
                    | ~models.Q(reason="")
                ),
                name="event_transition_reason_required",
            ),
        ]


# Inheritance: EventCommitteeAssignment mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class EventCommitteeAssignment(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke 'events.Event'; relasi database bukan pewarisan class.
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="committee_assignments",
    )
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="committee_assignments",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "member"],
                name="unique_event_committee_assignment",
            ),
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"{self.member_id} - {self.event_id}"


# Inheritance: CommitteePreference mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class CommitteePreference(models.Model):
    # OOP — Association (OneToOneField): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    member = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="committee_preference",
    )
    # OOP — Association (ForeignKey): menghubungkan objek ke Event; relasi database bukan pewarisan class.
    selected_event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="committee_preferences",
    )
    updated_at = models.DateTimeField(auto_now=True)


# Inheritance: OrganizerPreference mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class OrganizerPreference(models.Model):
    # OOP — Association (OneToOneField): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organizer_preferences",
    )
    organization_name = models.CharField(max_length=80, blank=True)
    notifications = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


# Inheritance: OrganizerInvitation mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class OrganizerInvitation(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organizer_invitations",
    )
    email = models.EmailField()
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    message = models.CharField(max_length=200, blank=True)
    access_all = models.BooleanField(default=True)
    # OOP — Association (ManyToManyField): menghubungkan objek ke Event; relasi database bukan pewarisan class.
    events = models.ManyToManyField(Event, related_name="committee_invitations", blank=True)
    sent_at = models.DateTimeField(default=timezone.now)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-sent_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("organizer", "email"),
                name="organizer_invitation_email_unique",
            ),
        ]


# Inheritance: OrganizerSupportTicket mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class OrganizerSupportTicket(models.Model):
    # Inheritance: Status mewarisi enum Django untuk pilihan nilai dan label.
    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "Sedang ditangani"
        RESOLVED = "RESOLVED", "Selesai"

    code = models.CharField(max_length=20, unique=True)
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
    )
    # OOP — Association (ForeignKey): menghubungkan objek ke Event; relasi database bukan pewarisan class.
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="organizer_support_tickets",
    )
    reporter = models.CharField(max_length=150)
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=3000)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    reply = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-created_at", "-pk")


# Inheritance: PlatformSettings mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    message = models.TextField(max_length=3000)
    reply = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=20, choices=OrganizerSupportTicket.Status.choices,
                              default=OrganizerSupportTicket.Status.IN_PROGRESS)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")


class PlatformSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    platform_fee_percent = models.DecimalField(max_digits=4, decimal_places=2, default=5)
    event_approval_required = models.BooleanField(default=True)
    notifications = models.JSONField(default=dict, blank=True)
    category_enabled = models.JSONField(default=dict, blank=True)
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_settings_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="platform_settings_singleton_id",
            ),
            models.CheckConstraint(
                condition=models.Q(platform_fee_percent__gte=0, platform_fee_percent__lte=20),
                name="platform_fee_percent_range",
            ),
        ]


# Inheritance: PlatformPayout mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class PlatformPayout(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="platform_payouts",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_platform_payouts",
    )
    created_at = models.DateTimeField(default=timezone.now)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="platform_payout_amount_positive",
            ),
        ]


# Inheritance: PlatformAuditLog mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class PlatformAuditLog(models.Model):
    category = models.CharField(max_length=20)
    description = models.CharField(max_length=500)
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_audit_entries",
    )
    actor_label = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=80, default="Admin Platform")
    seed_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-created_at", "-pk")

