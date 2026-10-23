from django.core.validators import FileExtensionValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_alter_accountaccesschange_options_alter_user_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="ktp_document",
            field=models.FileField(
                blank=True,
                upload_to="private/ktp_documents/",
                validators=[FileExtensionValidator(["pdf"])],
                verbose_name="Dokumen KTP (PDF)",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("L", "Laki-laki"), ("P", "Perempuan")],
                max_length=1,
                verbose_name="Jenis kelamin",
            ),
        ),
    ]
