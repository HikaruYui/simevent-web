from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower


# Inheritance: UserManager mewarisi perilaku BaseUserManager untuk diperluas sesuai kebutuhan class ini.
class UserManager(BaseUserManager):
    use_in_migrations = True

    # Polymorphism: memperluas normalisasi email dari manager induk.
    @classmethod
    def normalize_email(cls, email):
        return super().normalize_email(email).strip().lower()

    # Polymorphism: menyesuaikan pencarian akun menggunakan email tanpa membedakan huruf besar/kecil.
    def get_by_natural_key(self, email):
        email = self.normalize_email(email)
        return self.get(email__iexact=email)

    # Polymorphism: menyediakan pencarian akun asinkron dengan aturan email yang sama.
    async def aget_by_natural_key(self, email):
        email = self.normalize_email(email)
        return await self.aget(email__iexact=email)

    def create_user(self, email, password=None, **extra_fields):
        if not email or not email.strip():
            raise ValueError("Email wajib diisi.")

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        user = self.model(
            email=self.normalize_email(email),
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError(
                "Superuser harus memiliki is_staff=True."
            )

        if not extra_fields.get("is_superuser"):
            raise ValueError(
                "Superuser harus memiliki is_superuser=True."
            )

        if not extra_fields.get("is_active"):
            raise ValueError(
                "Superuser harus memiliki is_active=True."
            )

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )

# Inheritance: memperluas AbstractUser dengan identitas login berupa email.
class User(AbstractUser):
    username = None
    email = models.EmailField(
        "email",
        unique=True,
    )
    nim = models.CharField("NIM", max_length=30, blank=True)
    prodi = models.CharField("Program studi", max_length=150, blank=True)
    ktp_number = models.CharField(
        "Nomor KTP",
        max_length=16,
        blank=True,
        validators=[RegexValidator(r"^\d{16}$", "Nomor KTP harus terdiri dari 16 digit.")],
    )
    ktp_document = models.FileField(
        "Dokumen KTP (PDF)",
        upload_to="private/ktp_documents/",
        blank=True,
        validators=[FileExtensionValidator(["pdf"])],
    )
    profile_photo = models.ImageField(
        "Foto profil",
        upload_to="profile_photos/",
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    gender = models.CharField(
        "Jenis kelamin",
        max_length=1,
        blank=True,
        choices=(
            ("L", "Laki-laki"),
            ("P", "Perempuan"),
        ),
    )
    birth_place = models.CharField("Tempat lahir", max_length=100, blank=True)
    birth_date = models.DateField("Tanggal lahir", null=True, blank=True)
    address = models.TextField("Alamat", blank=True)
    phone_number = models.CharField("Nomor HP", max_length=20, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Pengguna"
        verbose_name_plural = "Pengguna"

        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(email=""),
                name="accounts_user_email_not_empty",
            ),
        ]

        permissions = [
            (
                "access_organizer",
                "Dapat mengakses fitur panitia",
            ),
            (
                "access_head_organizer",
                "Dapat mengakses fitur khusus ketua panitia",
            ),
            (
                "manage_platform",
                "Dapat mengelola platform secara global",
            ),
            (
                "manage_organizer_access",
                "Dapat memberikan dan mencabut akses panitia",
            ),
            (
                "manage_accounts",
                "Dapat menangguhkan dan mengaktifkan akun",
            ),
        ]

    # Polymorphism: menyesuaikan proses penyimpanan sebelum meneruskan ke implementasi induk.
    def save(self, *args, **kwargs):
        self.email = type(self).objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    # Role dihitung dari permission yang diberikan melalui grup Role.
    # Encapsulation: role menyajikan hasil perhitungan sebagai atribut baca tanpa setter.
    @property
    def role(self):
        if self.has_perm("accounts.manage_platform"):
            return "ADMIN"
        if self.has_perm("accounts.access_head_organizer"):
            return "ORGANIZER"
        if self.has_perm("accounts.access_organizer"):
            return "COMMITTEE"
        return "PARTICIPANT"

    # Encapsulation: profile_complete menyajikan hasil perhitungan sebagai atribut baca tanpa setter.
    @property
    def profile_complete(self):
        return all((
            self.first_name.strip(),
            self.ktp_number.strip(),
            self.gender,
            self.birth_place.strip(),
            self.birth_date,
            self.address.strip(),
            self.phone_number.strip(),
        ))

    # Polymorphism: menentukan representasi teks objek saat str() dipanggil.
    def __str__(self):
        return self.email


# Inheritance: AccountAccessChange mewarisi pemetaan atribut ke database dan operasi ORM.
class AccountAccessChange(models.Model):

    # Inheritance: Action mewarisi enum Django untuk pilihan nilai dan label.
    class Action(models.TextChoices):
        SET_PARTICIPANT = ("SET_PARTICIPANT", "Jadikan Peserta")
        SET_COMMITTEE = ("SET_COMMITTEE", "Jadikan Panitia")
        SET_ORGANIZER = ("SET_ORGANIZER", "Jadikan Ketua Panitia")
        SET_ADMIN=("SET_ADMIN", "Jadikan Admin Platform")

        # Tetap disimpan agar riwayat dan service lama tidak rusak.
        GRANT_ORGANIZER = (
            "GRANT_ORGANIZER",
            "Berikan akses panitia",
        )
        REVOKE_ORGANIZER = (
            "REVOKE_ORGANIZER",
            "Cabut akses panitia",
        )
        SUSPEND = (
            "SUSPEND",
            "Tangguhkan akun",
        )
        ACTIVATE = (
            "ACTIVATE",
            "Aktifkan akun",
        )

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="access_changes",
        verbose_name="akun yang diubah",
    )

    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="performed_access_changes",
        verbose_name="pelaku perubahan",
    )

    action = models.CharField(
        "tindakan",
        max_length=20,
        choices=Action.choices,
    )

    reason = models.TextField(
        "alasan",
        max_length=2000,
    )

    created_at = models.DateTimeField(
        "waktu perubahan",
        auto_now_add=True,
    )

    
    class Meta:
        verbose_name = "Riwayat Perubahan Akses"
        verbose_name_plural = "Riwayat Perubahan Akses"

        ordering = (
            "-created_at",
            "-pk",
        )

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    action__in=[
                        "SET_PARTICIPANT",
                        "SET_COMMITTEE",
                        "SET_ORGANIZER",
                        "SET_ADMIN",
                        "GRANT_ORGANIZER",
                        "REVOKE_ORGANIZER",
                        "SUSPEND",
                        "ACTIVATE",
                    ]
                ),
                name="accounts_access_action_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="accounts_access_reason_required",
            ),
        ]
