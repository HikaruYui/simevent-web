# Menambah tautan dokumentasi event (Google Drive) yang diisi panitia.

import apps.events.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_event_proposal'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='documentation_url',
            field=models.URLField(blank=True, max_length=1000, validators=[apps.events.models.validate_documentation_url]),
        ),
    ]
