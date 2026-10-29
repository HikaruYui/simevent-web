from django.db import migrations, models


# OOP — Single inheritance: Migration mewarisi migrations.Migration dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: migrations.Migration juga menjadi induk class saudara lain di proyek.
class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_options_accountaccesschange"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="nim",
            field=models.CharField(blank=True, max_length=30, verbose_name="NIM"),
        ),
        migrations.AddField(
            model_name="user",
            name="prodi",
            field=models.CharField(blank=True, max_length=150, verbose_name="Program studi"),
        ),
    ]
