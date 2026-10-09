# Fungsi file: Pengujian app events: validasi banner, penggantian/penghapusan file, dan penanganan kegagalan.

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.events.models import Event
from apps.events.workflow import EventWorkflow

from .support import banner_upload, event_data, setup_users


class EventUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other, cls.participant, cls.admin = setup_users()

    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory())
        self.enterContext(self.settings(MEDIA_ROOT=self.directory))

    def test_valid_banner_is_saved_with_generated_name(self):
        event = EventWorkflow(self.owner).create(data=event_data(), files={"banner": banner_upload()})
        self.assertTrue(event.banner.storage.exists(event.banner.name))
        self.assertTrue(event.banner.name.startswith("event-banners/"))
        self.assertNotIn("untrusted-name", event.banner.name)

    def test_rejects_non_image_unsupported_format_dimensions_and_size(self):
        uploads = [
            SimpleUploadedFile("fake.png", b"<svg><script>alert(1)</script></svg>"),
            banner_upload(format="GIF"),
            banner_upload(size=(4097, 1)),
            SimpleUploadedFile("huge.png", b"x" * (5 * 1024 * 1024 + 1)),
        ]
        for upload in uploads:
            with self.subTest(upload=upload.name), self.assertRaises(ValidationError):
                EventWorkflow(self.owner).create(data=event_data(), files={"banner": upload})
        self.assertFalse(Event.objects.exists())

    def test_banner_can_be_replaced_and_removed_after_commit(self):
        event = EventWorkflow(self.owner).create(data=event_data(), files={"banner": banner_upload()})
        old = event.banner.name
        with self.captureOnCommitCallbacks(execute=True):
            event = EventWorkflow(self.owner).update(event.pk, data=event_data(), files={"banner": banner_upload()})
        self.assertFalse(event.banner.storage.exists(old))
        self.assertTrue(event.banner.storage.exists(event.banner.name))
        previous = event.banner.name
        with self.captureOnCommitCallbacks(execute=True):
            event = EventWorkflow(self.owner).update(event.pk, data=event_data(remove_banner=True))
        self.assertFalse(event.banner)
        self.assertFalse(event.banner.storage.exists(previous))

    def test_failed_content_save_cleans_new_upload(self):
        with patch("apps.events.workflow.EventAccess.objects.update_or_create", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                EventWorkflow(self.owner).create(data=event_data(), files={"banner": banner_upload()})
        self.assertFalse(Event.objects.exists())
        self.assertFalse(any(path.is_file() for path in Path(self.directory).rglob("*")))

    def test_failed_replacement_preserves_original_banner(self):
        event = EventWorkflow(self.owner).create(data=event_data(), files={"banner": banner_upload()})
        previous = event.banner.name
        with patch("apps.events.workflow.EventAccess.objects.update_or_create", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                EventWorkflow(self.owner).update(event.pk, data=event_data(), files={"banner": banner_upload()})
        event.refresh_from_db()
        self.assertEqual(event.banner.name, previous)
        self.assertTrue(event.banner.storage.exists(previous))
        self.assertEqual(len([path for path in Path(self.directory).rglob("*") if path.is_file()]), 1)

    def test_rejects_ambiguous_banner_removal_and_upload(self):
        with self.assertRaises(ValidationError):
            EventWorkflow(self.owner).create(data=event_data(remove_banner=True), files={"banner": banner_upload()})

    def test_meeting_url_must_use_https(self):
        for url in ("http://meeting.example/room", "javascript:alert(1)", "ftp://meeting.example/room"):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                EventWorkflow(self.owner).create(data=event_data(meeting_url=url))

    def test_delete_draft_removes_banner_after_commit(self):
        event = EventWorkflow(self.owner).create(data=event_data(), files={"banner": banner_upload()})
        name, storage = event.banner.name, event.banner.storage
        with self.captureOnCommitCallbacks(execute=True):
            EventWorkflow(self.owner).delete_draft(event.pk)
        self.assertFalse(storage.exists(name))
