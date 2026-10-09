# Fungsi file: Helper data pengguna, event, dan banner untuk skenario pengujian backend.

from datetime import timedelta
from io import BytesIO, StringIO

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.events.models import EventType
from apps.events.workflow import EventWorkflow


def setup_users():
    call_command("bootstrap_roles", stdout=StringIO())
    users = []
    for name in ("owner", "other", "participant", "admin"):
        user = User.objects.create_user(f"{name}@events.example", "Event-test-password-123!")
        if name in ("owner", "other"):
            user.groups.add(Group.objects.get(name="Organizer"))
        if name == "admin":
            user.groups.add(Group.objects.get(name="Platform Admin"))
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        users.append(user)
    EventType.objects.get_or_create(code="SEMINAR", defaults={"name": "Seminar"})
    return users


def event_data(**overrides):
    now = timezone.now()
    return {
        "title": "Seminar SIMEVENT",
        "description": "Diskusi formal pengembangan perangkat lunak.",
        "event_type": EventType.objects.get(code="SEMINAR").pk,
        "delivery_mode": "OFFLINE",
        "start_datetime": now + timedelta(days=10),
        "end_datetime": now + timedelta(days=10, hours=2),
        "registration_open": now - timedelta(days=1),
        "registration_close": now + timedelta(days=9),
        "venue": "Auditorium kampus",
        "capacity": 100,
        "price": "0.00",
        **overrides,
    }


def published_event(owner, admin, **overrides):
    event = EventWorkflow(owner).create(data=event_data(**overrides))
    EventWorkflow(owner).transition(event.pk, action="submit")
    EventWorkflow(admin).transition(event.pk, action="approve")
    return EventWorkflow(admin).transition(event.pk, action="publish")


def banner_upload(format="PNG", size=(16, 16)):
    buffer = BytesIO()
    Image.new("RGB", size, "blue").save(buffer, format=format)
    return SimpleUploadedFile("untrusted-name.png", buffer.getvalue(), content_type="image/png")
