# Pengujian integrasi halaman publik dengan data event dan session Django.
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.achievements.models import Achievement
from apps.accounts.models import User
from apps.events.models import Event, EventAccess, EventStatus
from apps.events.tests.support import event_data, setup_users
from apps.registrations.models import Attendance, Registration


class LandingIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()

    def event(self, status=EventStatus.PUBLISHED, **overrides):
        data = event_data(**overrides)
        data["event_type_id"] = data.pop("event_type")
        return Event.objects.create(
            organizer=self.owner, slug=f"event-{Event.objects.count()}", status=status, **data,
        )

    def test_landing_only_recommends_published_unended_events(self):
        event = self.event(title="Public seminar")
        self.event(status=EventStatus.DRAFT, title="Private draft")
        self.event(status=EventStatus.CANCELLED, title="Cancelled event")
        self.event(status=EventStatus.COMPLETED, title="Completed event")
        response = self.client.get(reverse("landing"))
        self.assertContains(response, "Public seminar")
        self.assertNotContains(response, "Private draft")
        self.assertNotContains(response, "Cancelled event")
        self.assertEqual(list(response.context["recommended_events"]), [event])
        self.assertEqual(response.context["completed_count"], 1)
        self.assertIn("no-store", response["Cache-Control"])

    def test_counts_come_from_public_participation(self):
        first = self.event()
        second = self.event()
        private = self.event(status=EventStatus.DRAFT)
        for event in (first, second):
            Registration.objects.create(event=event, participant=self.participant)
        Registration.objects.create(event=private, participant=self.other)
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.context["participant_count"], 1)
        self.assertEqual(response.context["organizer_count"], 1)
        seminar = next(c for c in response.context["categories"] if c.code == "SEMINAR")
        self.assertEqual(seminar.event_count, 2)

    def test_empty_landing_and_recommendation_limit(self):
        self.assertContains(self.client.get(reverse("landing")), "Belum ada event mendatang")
        for index in range(6):
            self.event(title=f"Event {index}")
        self.assertEqual(len(self.client.get(reverse("landing")).context["recommended_events"]), 4)

    def test_catalogue_uses_real_data_and_escapes_script_content(self):
        self.event(title='</script><script>alert("event")</script>')
        self.event(status=EventStatus.DRAFT, title="Hidden draft")
        response = self.client.get(reverse("jelajah"), {"q": "event", "kategori": "seminar"})
        self.assertEqual(len(response.context["event_data"]), 1)
        self.assertContains(response, 'id="public-events"')
        self.assertNotContains(response, '</script><script>alert("event")</script>')
        self.assertNotContains(response, "Hidden draft")
        self.assertNotContains(response, "conference-meja-bundar")

    def test_public_detail_has_no_meeting_data_and_hides_drafts(self):
        event = self.event(description='<img src=x onerror=alert(1)>')
        EventAccess.objects.create(event=event, meeting_url="https://private.example/secret")
        response = self.client.get(reverse("detail_event", args=[event.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "https://private.example/secret")
        self.assertContains(response, "&lt;img")
        draft = self.event(status=EventStatus.DRAFT)
        self.assertEqual(self.client.get(reverse("detail_event", args=[draft.slug])).status_code, 404)

    def test_nav_uses_session_and_logout_requires_csrf_post(self):
        client = Client(enforce_csrf_checks=True)
        self.assertContains(client.get(reverse("landing")), 'href="/masuk/#daftar"')
        client.force_login(self.participant)
        response = client.get(reverse("landing"))
        self.assertContains(response, 'action="/keluar/"')
        self.assertNotContains(response, 'href="/masuk/#daftar"')
        self.assertEqual(client.get(reverse("logout_page")).status_code, 405)
        self.assertEqual(client.post(reverse("logout_page")).status_code, 403)
        response = client.post(reverse("logout_page"), HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertRedirects(response, reverse("landing"))
        self.assertEqual(client.get(reverse("accounts:profile")).status_code, 401)

    def test_auth_page_uses_backend_and_registration_cannot_choose_role(self):
        response = self.client.get(reverse("login_page"))
        self.assertContains(response, 'action="/accounts/login/"')
        self.assertContains(response, 'action="/accounts/register/"')
        self.assertNotContains(response, "registerRole")
        self.assertNotContains(response, "localStorage")
        self.assertContains(response, '/static/js/auth.js')
        response = self.client.post(reverse("accounts:register"), {
            "email": "new@example.test", "first_name": "New participant",
            "password1": "Very-strong-demo-password-42!", "password2": "Very-strong-demo-password-42!",
            "role": "ADMIN", "is_staff": True,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(email="new@example.test").role, "PARTICIPANT")

    def test_login_redirect_uses_server_role(self):
        for user, destination in ((self.participant, "jelajah"), (self.owner, "panitia_dashboard")):
            self.client.force_login(user)
            response = self.client.get(reverse("after_login"))
            self.assertRedirects(response, reverse(destination), fetch_redirect_response=False)

    def test_participant_pages_render_for_authenticated_participant(self):
        self.client.force_login(self.participant)
        event = self.event(title="Participant page sample event")
        Registration.objects.create(event=event, participant=self.participant)
        Achievement.objects.create(
            code="five-events",
            name="Event Enthusiast",
            required_count=5,
        )
        paths = (
            "peserta_dashboard",
            "peserta_daftar_event",
            "peserta_sertifikat",
            "peserta_achievement",
        )
        for name in paths:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
        dashboard = self.client.get(reverse("peserta_dashboard"))
        self.assertEqual(dashboard.context["total_registrations"], 1)
        self.assertEqual(dashboard.context["attended_count"], 0)
        self.assertContains(dashboard, "Achievement Saya")
        self.assertContains(self.client.get(reverse("peserta_daftar_event")), event.title)
        self.assertContains(self.client.get(reverse("peserta_achievement")), "Event Enthusiast")

    def test_achievement_level_progress_uses_attended_event_thresholds(self):
        self.client.force_login(self.participant)
        now = timezone.now()
        for index in range(10):
            start = now - timedelta(days=index + 3)
            data = event_data(
                start_datetime=start,
                end_datetime=start + timedelta(hours=2),
                registration_open=start - timedelta(days=10),
                registration_close=start - timedelta(days=1),
            )
            data["event_type_id"] = data.pop("event_type")
            event = Event.objects.create(
                organizer=self.owner,
                slug=f"attended-{index}",
                status=EventStatus.COMPLETED,
                **data,
            )
            registration = Registration.objects.create(
                event=event,
                participant=self.participant,
            )
            Attendance.objects.create(
                registration=registration,
                verified_by=self.owner,
            )
            if index == 5:
                response = self.client.get(reverse("peserta_dashboard"))
                self.assertEqual(response.context["current_level"]["name"], "Perak")
                self.assertEqual(response.context["next_level"]["name"], "Emas")
                self.assertEqual(response.context["progress_remaining"], 4)

        response = self.client.get(reverse("peserta_dashboard"))
        self.assertEqual(response.context["current_level"]["name"], "Emas")
        self.assertEqual(response.context["next_level"]["name"], "Platinum")
        self.assertEqual(response.context["progress_remaining"], 15)
