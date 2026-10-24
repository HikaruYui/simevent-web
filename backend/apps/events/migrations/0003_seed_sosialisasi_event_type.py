# Fungsi file: Menambahkan kategori Sosialisasi ke daftar jenis event bawaan.

from django.db import migrations


def seed_sosialisasi(apps, schema_editor):
    event_type = apps.get_model("events", "EventType")
    event_type.objects.using(schema_editor.connection.alias).update_or_create(
        code="SOSIALISASI",
        defaults={"name": "Sosialisasi", "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [("events", "0002_seed_event_types")]

    operations = [
        migrations.RunPython(seed_sosialisasi, migrations.RunPython.noop),
    ]
