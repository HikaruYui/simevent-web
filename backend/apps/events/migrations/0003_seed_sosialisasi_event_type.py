# Fungsi file: Menambahkan kategori Sosialisasi ke daftar jenis event bawaan.

from django.db import migrations


def seed_sosialisasi(apps, schema_editor):
    event_type = apps.get_model("events", "EventType")
    event_type.objects.using(schema_editor.connection.alias).update_or_create(
        code="SOSIALISASI",
        defaults={"name": "Sosialisasi", "is_active": True},
    )


# OOP — Single inheritance: Migration mewarisi migrations.Migration dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: migrations.Migration juga menjadi induk class saudara lain di proyek.
class Migration(migrations.Migration):
    dependencies = [("events", "0002_seed_event_types")]

    operations = [
        migrations.RunPython(seed_sosialisasi, migrations.RunPython.noop),
    ]
