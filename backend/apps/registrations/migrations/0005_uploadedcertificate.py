import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.registrations.models


class Migration(migrations.Migration):

    dependencies = [
        ("registrations", "0004_payment_certificate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UploadedCertificate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(
                    storage=apps.registrations.models.private_certificate_storage,
                    upload_to=apps.registrations.models.uploaded_certificate_path,
                    validators=[
                        django.core.validators.FileExtensionValidator(["pdf", "png", "jpg", "jpeg"]),
                        apps.registrations.models.validate_certificate_size,
                    ],
                )),
                ("uploaded_at", models.DateTimeField(auto_now=True)),
                ("registration", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="uploaded_certificate", to="registrations.registration")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uploaded_certificates", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
