# Fungsi file: Model, relasi, queryset, dan constraint database untuk registrasi, tiket, attendance, feedback, dan statistik.

from uuid import uuid4
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone

from apps.events.models import EventStatus


# Inheritance: RegistrationStatus mewarisi enum Django untuk pilihan nilai dan label.
class RegistrationStatus(models.TextChoices):
    REGISTERED = "REGISTERED", "Registered"
    CANCELLED = "CANCELLED", "Cancelled"


# Inheritance: RegistrationQuerySet mewarisi operasi query Django untuk menambahkan filter domain.
# OOP — Hierarchical inheritance: models.QuerySet juga menjadi induk class saudara lain di proyek.
class RegistrationQuerySet(models.QuerySet):
    # Abstraction: satu aturan tiket sah dipakai oleh daftar panitia dan ringkasan semua peran.
    def ticketed(self):
        return self.active().filter(ticket__is_active=True).filter(
            models.Q(event__price=0, payment__isnull=True)
            | models.Q(payment__status="APPROVED")
        )

    # Encapsulation: aturan akses dokumentasi hanya ada di sini dan dipakai semua halaman peserta.
    def with_documentation(self):
        """Registrasi aktif, hadir, pada event COMPLETED yang sudah punya tautan dokumentasi."""
        return (
            self.active()
            .filter(event__status=EventStatus.COMPLETED, attendance__status="PRESENT")
            .exclude(event__documentation_url="")
        )

    # Abstraction: active() membungkus aturan filter agar pemanggil dapat memakai ulang query domain.
    def active(self):
        return self.filter(status=RegistrationStatus.REGISTERED)

    # Abstraction: owned_by() membungkus aturan filter agar pemanggil dapat memakai ulang query domain.
    def owned_by(self, user):
        if not user.is_authenticated or not user.is_active:
            return self.none()
        return self.filter(participant=user)


# Inheritance: Registration mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class Registration(models.Model):
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="registrations",
    )
    # OOP — Association (ForeignKey): menghubungkan objek ke 'events.Event'; relasi database bukan pewarisan class.
    event = models.ForeignKey(
        "events.Event", on_delete=models.PROTECT, related_name="registrations",
    )
    status = models.CharField(
        max_length=10, choices=RegistrationStatus.choices,
        default=RegistrationStatus.REGISTERED,
    )
    registered_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # OOP — Factory / delegation: as_manager() membentuk manager yang mengekspos method QuerySet khusus lewat objects.
    objects = RegistrationQuerySet.as_manager()

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-registered_at", "-pk")
        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "event"], name="registration_unique_participant_event",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="REGISTERED", cancelled_at__isnull=True)
                    | models.Q(status="CANCELLED", cancelled_at__isnull=False)
                ),
                name="registration_status_timestamp_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(cancelled_at__isnull=True)
                | models.Q(cancelled_at__gte=models.F("registered_at")),
                name="registration_cancel_after_registration",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="registration_event_status_idx"),
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"Registration #{self.pk} for event #{self.event_id}"


# Inheritance: Ticket mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class Ticket(models.Model):
    # OOP — Association (OneToOneField): menghubungkan objek ke Registration; relasi database bukan pewarisan class.
    registration = models.OneToOneField(
        Registration, on_delete=models.PROTECT, related_name="ticket",
    )
    identifier = models.UUIDField(default=uuid4, unique=True, editable=False)
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Encapsulation: aturan validitas tiket, registrasi, peserta, event, dan waktu dirangkum dalam property.
    # OOP — Property / descriptor: method diakses seperti atribut; nilai dihitung melalui getter.
    @property
    def is_valid(self):
        registration = self.registration
        return (
            self.is_active
            and registration.status == RegistrationStatus.REGISTERED
            and (
                not hasattr(registration, "payment")
                or registration.payment.status == Payment.Status.APPROVED
            )
            and registration.participant.is_active
            and registration.event.status == EventStatus.PUBLISHED
            and timezone.now() < registration.event.end_datetime
        )

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return str(self.identifier)


def payment_proof_upload_path(instance, filename):
    return f"payment-proofs/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_payment_proof_size(file):
    if file.size > 5 * 1024 * 1024:
        raise ValidationError("Ukuran bukti pembayaran maksimal 5 MB.")


# Inheritance: Payment mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class Payment(models.Model):
    # Inheritance: Status mewarisi enum Django untuk pilihan nilai dan label.
    class Status(models.TextChoices):
        AWAITING_PROOF = "AWAITING_PROOF", "Menunggu bukti"
        UNDER_REVIEW = "UNDER_REVIEW", "Menunggu verifikasi"
        REJECTED = "REJECTED", "Ditolak"
        APPROVED = "APPROVED", "Disetujui"

    # OOP — Association (OneToOneField): menghubungkan objek ke Registration; relasi database bukan pewarisan class.
    registration = models.OneToOneField(
        Registration, on_delete=models.PROTECT, related_name="payment",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.AWAITING_PROOF,
    )
    proof = models.FileField(
        upload_to=payment_proof_upload_path,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "pdf"]),
                    validate_payment_proof_size],
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_payments",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(max_length=2000, blank=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-submitted_at", "-pk")
        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=(
                        "AWAITING_PROOF",
                        "UNDER_REVIEW",
                        "REJECTED",
                        "APPROVED",
                    )
                ),
                name="payment_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="APPROVED", reviewed_at__isnull=False,
                             reviewed_by__isnull=False)
                    | ~models.Q(status="APPROVED")
                ),
                name="payment_approval_has_reviewer",
            ),
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"Payment for registration #{self.registration_id}"


# Inheritance: PaymentInstructions mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class PaymentInstructions(models.Model):
    is_active = models.BooleanField(default=True)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    account_holder = models.CharField(max_length=150)
    instructions = models.TextField(max_length=2000, blank=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("is_active",), condition=models.Q(is_active=True),
                name="payment_single_active_instructions",
            ),
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"{self.bank_name} — {self.account_number}"


def certificate_template_upload_path(instance, filename):
    return f"certificate-templates/{uuid4().hex}{Path(filename).suffix.lower()}"


# Inheritance: CertificateTemplate mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class CertificateTemplate(models.Model):
    background = models.ImageField(upload_to=certificate_template_upload_path)
    is_active = models.BooleanField(default=True)
    name_x = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    name_y = models.PositiveSmallIntegerField(default=48, validators=[MaxValueValidator(100)])
    event_x = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    event_y = models.PositiveSmallIntegerField(default=62, validators=[MaxValueValidator(100)])
    date_x = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    date_y = models.PositiveSmallIntegerField(default=72, validators=[MaxValueValidator(100)])
    number_x = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    number_y = models.PositiveSmallIntegerField(default=88, validators=[MaxValueValidator(100)])
    font_size = models.PositiveSmallIntegerField(
        default=42, validators=[MinValueValidator(8), MaxValueValidator(160)],
    )
    text_color = models.CharField(
        max_length=7, default="#3F422E",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Gunakan warna hex, contoh #3F422E.")],
    )

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("is_active",), condition=models.Q(is_active=True),
                name="certificate_single_active_template",
            ),
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"Template sertifikat #{self.pk}"


# Inheritance: Attendance mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class Attendance(models.Model):
    # Inheritance: Status mewarisi enum Django untuk pilihan nilai dan label.
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        VOIDED = "VOIDED", "Voided"

    # OOP — Association (OneToOneField): menghubungkan objek ke Registration; relasi database bukan pewarisan class.
    registration = models.OneToOneField(
        Registration, on_delete=models.PROTECT, related_name="attendance",
    )
    checked_in_at = models.DateTimeField(default=timezone.now)
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="verified_attendances",
    )
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.PRESENT)
    voided_at = models.DateTimeField(null=True, blank=True)
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="voided_attendances",
    )
    void_reason = models.TextField(max_length=2000, blank=True)

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-checked_in_at", "-pk")
        permissions = [
            ("scan_ticket", "Can scan tickets for managed events"),
            ("void_attendance", "Can void an attendance record"),
        ]
        # OOP — Operator overloading: | / & pada Q atau QuerySet menyusun kondisi/gabungan query melalui __or__/__and__.
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(status="PRESENT", voided_at__isnull=True,
                             voided_by__isnull=True, void_reason="")
                    | (
                        models.Q(status="VOIDED", voided_at__isnull=False,
                                 voided_by__isnull=False)
                        & ~models.Q(void_reason="")
                    )
                ),
                name="attendance_void_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(voided_at__isnull=True)
                | models.Q(voided_at__gte=models.F("checked_in_at")),
                name="attendance_void_after_checkin",
            ),
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"Attendance for registration #{self.registration_id}"


RATING_FIELDS = (
    "overall_rating", "material_rating", "speaker_rating", "organization_rating",
)


# Inheritance: FeedbackQuerySet mewarisi operasi query Django untuk menambahkan filter domain.
# OOP — Hierarchical inheritance: models.QuerySet juga menjadi induk class saudara lain di proyek.
class FeedbackQuerySet(models.QuerySet):
    # Abstraction: eligible() membungkus aturan filter agar pemanggil dapat memakai ulang query domain.
    def eligible(self):
        return self.filter(
            registration__status=RegistrationStatus.REGISTERED,
            registration__event__status=EventStatus.COMPLETED,
            registration__attendance__status=Attendance.Status.PRESENT,
        )


# Inheritance: Feedback mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class Feedback(models.Model):
    # OOP — Association (OneToOneField): menghubungkan objek ke Registration; relasi database bukan pewarisan class.
    registration = models.OneToOneField(
        Registration, on_delete=models.PROTECT, related_name="feedback",
    )
    overall_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    material_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    speaker_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    organization_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(max_length=2000, blank=True)
    suggestion = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # OOP — Factory / delegation: as_manager() membentuk manager yang mengekspos method QuerySet khusus lewat objects.
    objects = FeedbackQuerySet.as_manager()

    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(**{f"{field}__gte": 1, f"{field}__lte": 5}),
                name=f"feedback_{field}_range",
            )
            for field in RATING_FIELDS
        ]

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"Feedback for registration #{self.registration_id}"


def private_certificate_storage():
    # Disimpan di luar MEDIA_ROOT: hanya bisa diunduh lewat view yang memeriksa pemilik.
    return FileSystemStorage(location=settings.BASE_DIR / "private_media")


def uploaded_certificate_path(instance, filename):
    return f"uploaded-certificates/{uuid4().hex}{Path(filename).suffix.lower()}"


def validate_certificate_size(file):
    if file.size > 5 * 1024 * 1024:
        raise ValidationError("Ukuran file sertifikat maksimal 5 MB.")


# Inheritance: UploadedCertificate mewarisi pemetaan atribut ke database dan operasi ORM.
# OOP — Hierarchical inheritance: models.Model juga menjadi induk class saudara lain di proyek.
class UploadedCertificate(models.Model):
    """Sertifikat yang diunggah panitia untuk satu peserta (satu file per registrasi)."""

    # OOP — Association (OneToOneField): menghubungkan objek ke Registration; relasi database bukan pewarisan class.
    registration = models.OneToOneField(
        Registration, on_delete=models.CASCADE, related_name="uploaded_certificate",
    )
    file = models.FileField(
        upload_to=uploaded_certificate_path,
        storage=private_certificate_storage,
        validators=[
            FileExtensionValidator(["pdf", "png", "jpg", "jpeg"]),
            validate_certificate_size,
        ],
    )
    # OOP — Association (ForeignKey): menghubungkan objek ke settings.AUTH_USER_MODEL; relasi database bukan pewarisan class.
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_certificates",
    )
    uploaded_at = models.DateTimeField(auto_now=True)

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return f"Sertifikat registrasi #{self.registration_id}"
