# Fungsi file: Pengujian app events: action, pembatasan edit, konfirmasi, serta rendering Django Admin.

from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.events.models import EventStatus, EventType
from apps.events.workflow import EventWorkflow

from .support import event_data, setup_users


# OOP — Single inheritance: EventAdminTests mewarisi TestCase dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: TestCase juga menjadi induk class saudara lain di proyek.
class EventAdminTests(TestCase):
    # OOP — Method overriding: framework pengujian memanggil hook setUpTestData milik subclass untuk menyiapkan/membersihkan fixture.
    # OOP — Class method: menerima cls sehingga operasi terikat pada class dan tetap mengikuti subclass.
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()
        cls.event = EventWorkflow(cls.owner).create(data=event_data())
        EventWorkflow(cls.owner).transition(cls.event.pk, action="submit")

    # OOP — Method overriding: framework pengujian memanggil hook setUp milik subclass untuk menyiapkan/membersihkan fixture.
    def setUp(self):
        self.client.force_login(self.admin)

    # OOP — Encapsulation: method action mengelompokkan operasi terkait objek EventAdminTests.
    def action(self, action, **overrides):
        return self.client.post(reverse("admin:events_event_changelist"), {
            "action": action, "_selected_action": self.event.pk,
            "reason": "Review admin selesai", "confirm": "on", **overrides,
        })

    def test_native_admin_approval_and_publication_use_workflow(self):
        self.assertEqual(self.action("approve").status_code, 302)
        self.assertEqual(self.action("publish").status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.PUBLISHED)
        self.assertEqual(self.event.transitions.count(), 3)

    def test_admin_confirmation_and_reason_are_required(self):
        self.action("approve", confirm="")
        self.action("approve", reason="")
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.SUBMITTED)

    def test_even_superuser_cannot_bypass_workflow_using_normal_edit(self):
        root = User.objects.create_superuser("root@events.example", "password")
        self.client.force_login(root)
        for operation in ("change", "delete"):
            # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
            with self.subTest(operation=operation):
                response = self.client.post(reverse(f"admin:events_event_{operation}", args=[self.event.pk]), {
                    "status": "PUBLISHED",
                })
                self.assertEqual(response.status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.SUBMITTED)

    def test_staff_organizer_cannot_access_global_admin_events(self):
        self.owner.is_staff = True
        self.owner.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("admin:events_event_changelist")).status_code, 403)
        self.assertEqual(self.action("approve").status_code, 403)

    def test_admin_actions_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse("admin:events_event_changelist"), {
            "action": "approve", "_selected_action": self.event.pk, "reason": "Reason", "confirm": "on",
        }).status_code, 403)

    def test_admin_can_add_and_deactivate_event_types_but_not_change_code(self):
        response = self.client.post(reverse("admin:events_eventtype_add"), {
            "code": "SUMMIT", "name": "Summit", "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        event_type = EventType.objects.get(code="SUMMIT")
        self.client.post(reverse("admin:events_eventtype_change", args=[event_type.pk]), {
            "code": "FORGED", "name": "Summit updated",
        })
        event_type.refresh_from_db()
        self.assertEqual(event_type.code, "SUMMIT")
        self.assertFalse(event_type.is_active)

    def test_view_permission_without_platform_role_does_not_expose_private_access(self):
        self.participant.is_staff = True
        self.participant.save()
        self.participant.user_permissions.add(Permission.objects.get(codename="view_eventaccess"))
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get(reverse("admin:events_eventaccess_changelist")).status_code, 403)

    def test_admin_pages_render_readonly_and_escape_user_content(self):
        self.event.title = "<script>alert(1)</script>"
        self.event.save()
        response = self.client.get(reverse("admin:events_event_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Konfirmasi tindakan")
        self.assertNotContains(response, "<script>alert(1)</script>")
        response = self.client.get(reverse("admin:events_event_change", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="status"')
