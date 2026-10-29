import json
import re
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.events.models import Event, EventTransition, EventType
from apps.events.seeds import EVENTS_KP, demo_participants
from apps.events.seeds.presentation import demo_ui_data
from apps.partnerships.models import OrganizerProposal
from apps.registrations.models import Attendance, Payment, Registration, Ticket


# OOP — Single inheritance: DemoCatalogTests mewarisi SimpleTestCase dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: SimpleTestCase juga menjadi induk class saudara lain di proyek.
class DemoCatalogTests(SimpleTestCase):
    def test_ui_keeps_participants_and_event_totals_consistent(self):
        data = demo_ui_data()
        participants = data["eo"]["participants"]
        self.assertEqual(len(participants), sum(row[5] for row in EVENTS_KP))
        self.assertEqual(participants, list(demo_participants()))
        for event in data["eo"]["events"]:
            registrations = [p for p in participants if p["eventId"] == event["id"]]
            self.assertEqual(len(registrations), event["terjual"])
            self.assertEqual(sum(p["status"] == "hadir" for p in registrations), event["hadir"])
            series = data["eo"]["attendance_series"][str(event["id"])]
            self.assertEqual(sum(series["daftar"]), event["terjual"])
            self.assertEqual(sum(series["onsite"]) + sum(series["online"]), event["hadir"])
        event_ids = {e["id"] for e in data["eo"]["events"] + data["admin_events"]}
        for ticket in data["eo"]["tickets"] + data["extra_tickets"]:
            self.assertIn(ticket["eventId"], event_ids)

    def test_presentation_mutations_do_not_change_seed_source(self):
        data = demo_ui_data()
        data["team"].clear()
        data["shared_defaults"]["settings"]["feePct"] = 99
        data["catalogue"]["categories"]["conference"]["titles"].clear()
        next_data = demo_ui_data()
        self.assertEqual(len(next_data["team"]), 4)
        self.assertEqual(next_data["shared_defaults"]["settings"]["feePct"], 5)
        self.assertEqual(len(next_data["catalogue"]["categories"]["conference"]["titles"]), 10)

    def test_template_can_load_seed_without_database_queries(self):
        rendered = Template(
            '{% load demo_seed %}{% demo_seed "committee" as demo %}'
            '{{ demo|json_script:"demo" }}'
        ).render(Context())
        data = json.loads(re.search(r">(.*)</script>", rendered)[1])
        self.assertEqual(len(data["participants"]), 5)
        self.assertEqual(data["participants"][0]["code"], "SIM-001")


# OOP — Single inheritance: DemoSeedTests mewarisi TestCase dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: TestCase juga menjadi induk class saudara lain di proyek.
# OOP — Decorator Python (override_settings): mengganti settings selama konteks pengujian lalu memulihkannya; tidak menambah pewarisan class.
@override_settings(DEBUG=True)
class DemoSeedTests(TestCase):
    # OOP — Method overriding: framework pengujian memanggil hook setUpTestData milik subclass untuk menyiapkan/membersihkan fixture.
    # OOP — Class method: menerima cls sehingga operasi terikat pada class dan tetap mengikuti subclass.
    @classmethod
    def setUpTestData(cls):
        call_command("seed_simevent_initial", stdout=StringIO())

    def test_seed_matches_catalog_and_is_repeatable_without_overwriting_edits(self):
        User = get_user_model()
        models = (User, EventType, Event, EventTransition, Registration,
                  Ticket, Payment, Attendance, OrganizerProposal)
        counts = [model.objects.count() for model in models]
        event = Event.objects.get(title=EVENTS_KP[0][0])
        self.assertEqual(event.registrations.count(), EVENTS_KP[0][5])
        person = next(demo_participants())
        reg = Registration.objects.get(event=event, participant__email=person["email"])
        self.assertEqual(reg.participant.get_full_name(), person["nama"])
        self.assertEqual(reg.registered_at.date().isoformat(), person["terdaftar"])
        self.assertEqual(reg.attendance.status, Attendance.Status.PRESENT)
        self.assertEqual(reg.payment.status, Payment.Status.APPROVED)
        event.title = "Judul yang diedit saat demo"
        event.save(update_fields=["title"])
        owner = event.organizer
        owner.set_password("Password-demo-yang-sudah-diatur-123!")
        owner.save(update_fields=["password"])
        call_command("seed_simevent_initial", stdout=StringIO())
        self.assertEqual([model.objects.count() for model in models], counts)
        event.refresh_from_db()
        owner.refresh_from_db()
        self.assertEqual(event.title, "Judul yang diedit saat demo")
        self.assertTrue(owner.check_password("Password-demo-yang-sudah-diatur-123!"))

    # OOP — Decorator Python (override_settings): mengganti settings selama konteks pengujian lalu memulihkannya; tidak menambah pewarisan class.
    @override_settings(DEBUG=False)
    def test_seed_still_refuses_to_run_outside_development(self):
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            call_command("seed_simevent_initial", stdout=StringIO())

    def test_pages_load_runtime_labels_without_demo_records(self):
        User = get_user_model()
        for email, pages in (
            ("admin@simevent.id", ("admin_dashboard", "admin_users", "admin_events",
                                  "admin_finance", "admin_audit", "admin_settings", "admin_support")),
            ("budi@simevent.id", ("eo_dashboard", "eo_event", "eo_peserta",
                                 "eo_pendapatan", "eo_log", "eo_pengaturan", "eo_support")),
            ("siti.rahma@mail.com", ("panitia_biasa",)),
        ):
            self.client.force_login(User.objects.get(email=email))
            for page in pages:
                # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
                with self.subTest(page=page):
                    response = self.client.get(reverse(page))
                    self.assertEqual(response.status_code, 200)
                    html = response.content.decode()
                    self.assertEqual(html.count('id="simevent-ui-config"'), 1)
                    self.assertNotIn('id="simevent-demo-seed"', html)
                    marker = html.index("window.SIMEVENT_DEMO =")
                    script = ("js/admin_control.js" if page.startswith("admin_") else "js/ketua_panitia.js") if page != "panitia_biasa" else "let participants"
                    self.assertLess(marker, html.index(script))
        response = self.client.get(reverse("jelajah"))
        self.assertContains(response, 'id="backend-events"')
        self.assertNotContains(response, 'id="demo-catalogue"')
        self.assertNotContains(response, "const titles =")

    def test_public_demo_records_are_rendered_from_catalog(self):
        data = demo_ui_data()
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.content.decode().count('class="event-card"'), 4)
        for event in response.context["recommended_events"]:
            self.assertContains(response, event.title)
            self.assertContains(response, reverse("detail_event", args=[event.slug]))
        for testimonial in data["landing"]["testimonials"]:
            self.assertContains(response, testimonial["quote"])
        response = self.client.get(reverse("tentang"))
        for member in data["about"]["team"]:
            self.assertContains(response, member["name"])
        self.assertContains(response, data["about"]["chart_points"])
