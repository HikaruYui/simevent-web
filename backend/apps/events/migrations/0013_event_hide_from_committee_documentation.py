from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0012_organizerinvitation_email_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="hide_from_committee_documentation",
            field=models.BooleanField(
                default=False,
                help_text="Sembunyikan hanya dari daftar Dokumentasi Event Panitia Biasa.",
            ),
        ),
    ]
