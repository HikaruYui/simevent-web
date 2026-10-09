# Fungsi file: Model, relasi, queryset, dan constraint database untuk akun, autentikasi, dan hak akses.

# from django.contrib.auth.base_user import BaseUserManager
# from django.contrib.auth.models import AbstractUser
# from django.db import models
# from django.db.models.functions import Lower


# class UserManager(BaseUserManager):
#     use_in_migrations = True

#     @classmethod
#     def normalize_email(cls, email):
#         return super().normalize_email(email).strip().lower()

#     def get_by_natural_key(self, email):
#         return self.get(email__iexact=self.normalize_email(email))

#     async def aget_by_natural_key(self, email):
#         return await self.aget(email__iexact=self.normalize_email(email))

#     def create_user(self, email, password=None, **extra_fields):
#         if not email or not email.strip():
#             raise ValueError("Email is required.")
#         extra_fields.setdefault("is_staff", False)
#         extra_fields.setdefault("is_superuser", False)
#         user = self.model(email=self.normalize_email(email), **extra_fields)
#         user.set_password(password)
#         user.save(using=self._db)
#         return user

#     def create_superuser(self, email, password=None, **extra_fields):
#         extra_fields.setdefault("is_staff", True)
#         extra_fields.setdefault("is_superuser", True)
#         extra_fields.setdefault("is_active", True)
#         if not all(extra_fields[field] for field in ("is_staff", "is_superuser", "is_active")):
#             raise ValueError("Superusers must be active staff with is_superuser=True.")
#         return self.create_user(email, password, **extra_fields)


# class User(AbstractUser):
#     username = None
#     email = models.EmailField(unique=True)

#     USERNAME_FIELD = "email"
#     REQUIRED_FIELDS = []
#     objects = UserManager()

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
#             models.CheckConstraint(condition=~models.Q(email=""), name="accounts_user_email_not_empty"),
#         ]
#         permissions = [
#             ("access_organizer", "Can access organizer functionality"),
#             ("manage_platform", "Can access global platform administration"),
#             ("manage_organizer_access", "Can grant and revoke organizer access"),
#             ("manage_accounts", "Can suspend and activate participant accounts"),
#         ]

#     def save(self, *args, **kwargs):
#         self.email = type(self).objects.normalize_email(self.email)
#         super().save(*args, **kwargs)

#     @property
#     def role(self):
#         if self.is_active and self.has_perm("accounts.manage_platform"):
#             return "ADMIN"
#         if self.is_active and self.has_perm("accounts.access_organizer"):
#             return "ORGANIZER"
#         return "PARTICIPANT"

#     def __str__(self):
#         return self.email


# class AccountAccessChange(models.Model):
#     class Action(models.TextChoices):
#         GRANT_ORGANIZER = "GRANT_ORGANIZER", "Grant organizer"
#         REVOKE_ORGANIZER = "REVOKE_ORGANIZER", "Revoke organizer"
#         SUSPEND = "SUSPEND", "Suspend account"
#         ACTIVATE = "ACTIVATE", "Activate account"

#     user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="access_changes")
#     actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="performed_access_changes")
#     action = models.CharField(max_length=20, choices=Action.choices)
#     reason = models.TextField(max_length=2000)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ("-created_at", "-pk")
#         constraints = [
#             models.CheckConstraint(
#                 condition=models.Q(action__in=["GRANT_ORGANIZER", "REVOKE_ORGANIZER", "SUSPEND", "ACTIVATE"]),
#                 name="accounts_access_action_valid",
#             ),
#             models.CheckConstraint(condition=~models.Q(reason=""), name="accounts_access_reason_required"),
#         ]


from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return super().normalize_email(email).strip().lower()

    def get_by_natural_key(self, email):
        email = self.normalize_email(email)
        return self.get(email__iexact=email)

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

    def save(self, *args, **kwargs):
        self.email = type(self).objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    # Encapsulation: interpretasi role dari permission dipusatkan dalam property ini.
    @property
    def role(self):
        if self.has_perm("accounts.manage_platform"):
            return "ADMIN"

        if self.has_perm("accounts.access_organizer"):
            return "ORGANIZER"

        return "PARTICIPANT"

    def __str__(self):
        return self.email


class AccountAccessChange(models.Model):

    class Action(models.TextChoices):
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

    def __str__(self):
        return (
            f"{self.actor} - "
            f"{self.get_action_display()} - "
            f"{self.user}"
        )
