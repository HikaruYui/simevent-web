# Fungsi file: Migration app events: mengisi empat jenis event awal; operasi dan dependensi migration tetap dipertahankan.

from django.db import migrations


def seed_event_types(apps, schema_editor):
    event_type = apps.get_model("events", "EventType")
    for code, name in (
        ("CONFERENCE", "Conference"),
        ("WORKSHOP", "Workshop"),
        ("SEMINAR", "Seminar"),
        ("WEBINAR", "Webinar"),
    ):
        event_type.objects.using(schema_editor.connection.alias).get_or_create(
            code=code, defaults={"name": name}
        )


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]
    # Keep potentially referenced event types when reversing the seed alone.
    operations = [migrations.RunPython(seed_event_types, migrations.RunPython.noop)]
