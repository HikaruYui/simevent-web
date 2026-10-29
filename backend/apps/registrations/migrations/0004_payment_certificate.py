import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

import apps.registrations.models


# OOP — Single inheritance: Migration mewarisi migrations.Migration dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: migrations.Migration juga menjadi induk class saudara lain di proyek.
class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_profile"),
        ("registrations", "0003_feedback"),
    ]

    operations = [
        migrations.CreateModel(
            name="CertificateTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("background", models.ImageField(upload_to=apps.registrations.models.certificate_template_upload_path)),
                ("is_active", models.BooleanField(default=True)),
                ("name_x", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MaxValueValidator(100)])),
                ("name_y", models.PositiveSmallIntegerField(default=48, validators=[django.core.validators.MaxValueValidator(100)])),
                ("event_x", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MaxValueValidator(100)])),
                ("event_y", models.PositiveSmallIntegerField(default=62, validators=[django.core.validators.MaxValueValidator(100)])),
                ("date_x", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MaxValueValidator(100)])),
                ("date_y", models.PositiveSmallIntegerField(default=72, validators=[django.core.validators.MaxValueValidator(100)])),
                ("number_x", models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MaxValueValidator(100)])),
                ("number_y", models.PositiveSmallIntegerField(default=88, validators=[django.core.validators.MaxValueValidator(100)])),
                ("font_size", models.PositiveSmallIntegerField(default=42, validators=[django.core.validators.MinValueValidator(8), django.core.validators.MaxValueValidator(160)])),
                ("text_color", models.CharField(default="#3F422E", max_length=7, validators=[django.core.validators.RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Gunakan warna hex, contoh #3F422E.")])),
            ],
        ),
        migrations.CreateModel(
            name="PaymentInstructions",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("bank_name", models.CharField(max_length=100)),
                ("account_number", models.CharField(max_length=50)),
                ("account_holder", models.CharField(max_length=150)),
                ("instructions", models.TextField(blank=True, max_length=2000)),
            ],
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("status", models.CharField(choices=[("AWAITING_PROOF", "Menunggu bukti"), ("UNDER_REVIEW", "Menunggu verifikasi"), ("REJECTED", "Ditolak"), ("APPROVED", "Disetujui")], default="AWAITING_PROOF", max_length=20)),
                ("proof", models.FileField(blank=True, upload_to=apps.registrations.models.payment_proof_upload_path, validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "pdf"]), apps.registrations.models.validate_payment_proof_size])),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.TextField(blank=True, max_length=2000)),
                ("registration", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="payment", to="registrations.registration")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_payments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-submitted_at", "-pk"),
            },
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="payment_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(condition=models.Q(("status__in", ["AWAITING_PROOF", "UNDER_REVIEW", "REJECTED", "APPROVED"])), name="payment_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("reviewed_at__isnull", False), ("reviewed_by__isnull", False), ("status", "APPROVED")), models.Q(("status", "APPROVED"), _negated=True), _connector="OR"), name="payment_approval_has_reviewer"),
        ),
        migrations.AddConstraint(
            model_name="paymentinstructions",
            constraint=models.UniqueConstraint(condition=models.Q(("is_active", True)), fields=("is_active",), name="payment_single_active_instructions"),
        ),
        migrations.AddConstraint(
            model_name="certificatetemplate",
            constraint=models.UniqueConstraint(condition=models.Q(("is_active", True)), fields=("is_active",), name="certificate_single_active_template"),
        ),
    ]
