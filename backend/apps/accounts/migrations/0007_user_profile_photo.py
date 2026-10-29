from django.core.validators import FileExtensionValidator
from django.db import migrations, models


# OOP — Single inheritance: Migration mewarisi migrations.Migration dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: migrations.Migration juga menjadi induk class saudara lain di proyek.
class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_user_ktp_document_gender_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_photo",
            field=models.ImageField(
                blank=True,
                upload_to="profile_photos/",
                validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
                verbose_name="Foto profil",
            ),
        ),
    ]
