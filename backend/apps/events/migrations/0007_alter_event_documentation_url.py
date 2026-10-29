# Memperpanjang tautan dokumentasi (max 1000) dan menambah validator host Google.

import apps.events.models
from django.db import migrations, models


# OOP — Single inheritance: Migration mewarisi migrations.Migration dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: migrations.Migration juga menjadi induk class saudara lain di proyek.
class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_event_documentation_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='documentation_url',
            field=models.URLField(blank=True, max_length=1000, validators=[apps.events.models.validate_documentation_url]),
        ),
    ]
