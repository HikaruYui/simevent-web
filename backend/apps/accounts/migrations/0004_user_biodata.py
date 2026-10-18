from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="ktp_number",
            field=models.CharField(
                blank=True,
                max_length=16,
                validators=[RegexValidator(r"^\d{16}$", "Nomor KTP harus terdiri dari 16 digit.")],
                verbose_name="Nomor KTP",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("L", "Laki-laki"), ("P", "Perempuan"), ("O", "Lainnya")],
                max_length=1,
                verbose_name="Jenis kelamin",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="birth_place",
            field=models.CharField(blank=True, max_length=100, verbose_name="Tempat lahir"),
        ),
        migrations.AddField(
            model_name="user",
            name="birth_date",
            field=models.DateField(blank=True, null=True, verbose_name="Tanggal lahir"),
        ),
        migrations.AddField(
            model_name="user",
            name="address",
            field=models.TextField(blank=True, verbose_name="Alamat"),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_number",
            field=models.CharField(blank=True, max_length=20, verbose_name="Nomor HP"),
        ),
    ]
