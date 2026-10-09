# Fungsi file: Pengujian app events: endpoint event, CSRF, ownership, data privat, dan pagination.

from django.test import Client, TestCase
from django.urls import reverse

from apps.events.models import EventStatus
from apps.events.workflow import EventWorkflow

from .support import event_data, published_event, setup_users


class EventHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()

    def test_public_only_sees_published_and_completed(self):
        draft = EventWorkflow(self.owner).create(data=event_data())
        published = published_event(self.owner, self.admin)
        response = self.client.get(reverse("events:list"))
        self.assertEqual([item["id"] for item in response.json()["results"]], [published.pk])
        self.assertEqual(self.client.get(reverse("events:detail", args=[draft.slug])).status_code, 404)

    def test_public_and_participant_do_not_receive_private_meeting_information(self):
        event = published_event(
            self.owner, self.admin, delivery_mode="ONLINE", venue="",
            meeting_url="https://meeting.example/secret-token", access_instructions="private passcode 789",
        )
        for authenticated in (False, True):
            if authenticated:
                self.client.force_login(self.participant)
            for url in (reverse("events:list"), reverse("events:detail", args=[event.slug])):
                with self.subTest(authenticated=authenticated, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    for secret in ("meeting_url", "secret-token", "private passcode", self.owner.email):
                        self.assertNotContains(response, secret)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("events:manage-detail", args=[event.pk]))
        self.assertEqual(response.json()["meeting_url"], "https://meeting.example/secret-token")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_manager_lists_are_scoped_and_admin_can_see_all(self):
        first = EventWorkflow(self.owner).create(data=event_data())
        second = EventWorkflow(self.other).create(data=event_data())
        self.client.force_login(self.owner)
        self.assertEqual([item["id"] for item in self.client.get(reverse("events:manage-list")).json()["results"]], [first.pk])
        self.client.force_login(self.admin)
        self.assertCountEqual([item["id"] for item in self.client.get(reverse("events:manage-list")).json()["results"]], [first.pk, second.pk])

    def test_cross_owner_get_edit_delete_and_all_transitions_fail(self):
        event = EventWorkflow(self.owner).create(data=event_data())
        self.client.force_login(self.other)
        detail = reverse("events:manage-detail", args=[event.pk])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.post(detail, event_data()).status_code, 404)
        self.assertEqual(self.client.post(reverse("events:delete", args=[event.pk]), {"confirm": "on"}).status_code, 404)
        for action in EventWorkflow.action_targets:
            with self.subTest(action=action):
                response = self.client.post(reverse("events:transition", args=[event.pk, action]), {"reason": "Attempt"})
                self.assertEqual(response.status_code, 404)

    def test_authentication_and_csrf_are_required(self):
        url = reverse("events:manage-list")
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get(url).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url, event_data()).status_code, 403)

    def test_create_and_edit_cannot_set_owner_slug_or_status(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("events:manage-list"), event_data(
            organizer=self.other.pk, status="PUBLISHED", slug="forged"
        ))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], EventStatus.DRAFT)
        pk = response.json()["id"]
        response = self.client.post(reverse("events:manage-detail", args=[pk]), event_data(
            title="Edited", organizer=self.other.pk, status="PUBLISHED"
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], EventStatus.DRAFT)

    def test_invalid_transition_and_delete_confirmation(self):
        event = EventWorkflow(self.owner).create(data=event_data())
        self.client.force_login(self.owner)
        url = reverse("events:transition", args=[event.pk, "submit"])
        self.assertEqual(self.client.get(url).status_code, 405)
        bad = reverse("events:transition", args=[event.pk, "UNKNOWN"])
        self.assertEqual(self.client.post(bad).status_code, 400)
        delete = reverse("events:delete", args=[event.pk])
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertEqual(self.client.post(delete).status_code, 400)
        self.assertEqual(self.client.post(delete, {"confirm": "on"}).status_code, 200)

    def test_organizer_cannot_publish_with_crafted_post(self):
        event = EventWorkflow(self.owner).create(data=event_data())
        self.client.force_login(self.owner)
        response = self.client.post(reverse("events:transition", args=[event.pk, "publish"]))
        self.assertEqual(response.status_code, 403)

    def test_public_list_query_count_does_not_grow_per_event(self):
        for _ in range(5):
            published_event(self.owner, self.admin)
        # Count + one joined page query; event type must not produce N+1 queries.
        with self.assertNumQueries(2):
            response = self.client.get(reverse("events:list"))
            self.assertEqual(len(response.json()["results"]), 5)

    def test_public_catalog_is_paginated(self):
        for _ in range(21):
            published_event(self.owner, self.admin)
        first = self.client.get(reverse("events:list")).json()
        second = self.client.get(reverse("events:list"), {"page": 2}).json()
        self.assertEqual(len(first["results"]), 20)
        self.assertEqual(len(second["results"]), 1)
