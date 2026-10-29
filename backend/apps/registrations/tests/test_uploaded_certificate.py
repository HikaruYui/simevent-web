# Fungsi file: Pengujian unggah sertifikat peserta oleh panitia dan unduhan oleh peserta.

import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import Permission
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.events.models import EventCommitteeAssignment
from apps.events.tests.support import published_event, setup_users
from apps.registrations.models import Attendance, Registration, UploadedCertificate

PDF = b"%PDF-1.4\n%test\n"


def make_committee(email):
    user = User.objects.create_user(
        email, "Event-test-password-123!", first_name="Panitia", last_name="Uji",
        nim=email[:5], prodi="Informatika",
    )
    user.user_permissions.add(Permission.objects.get(codename="access_organizer"))
    return User.objects.get(pk=user.pk)


# OOP — Single inheritance: UploadedCertificateTests mewarisi TestCase dan menyesuaikan kontrak framework melalui atribut/method class.
# OOP — Hierarchical inheritance: TestCase juga menjadi induk class saudara lain di proyek.
class UploadedCertificateTests(TestCase):
    # OOP — Method overriding: framework pengujian memanggil hook setUpClass milik subclass untuk menyiapkan/membersihkan fixture.
    # OOP — Class method: menerima cls sehingga operasi terikat pada class dan tetap mengikuti subclass.
    @classmethod
    def setUpClass(cls):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        cls.override = override_settings(BASE_DIR=Path(cls.tmp))
        cls.override.enable()
        # FileField mengevaluasi factory storage saat impor; arahkan fixture ke folder sementara.
        cls.file_field = UploadedCertificate._meta.get_field("file")
        cls.original_storage = cls.file_field.storage
        cls.file_field.storage = FileSystemStorage(location=Path(cls.tmp) / "private_media")

    # OOP — Method overriding: framework pengujian memanggil hook tearDownClass milik subclass untuk menyiapkan/membersihkan fixture.
    # OOP — Class method: menerima cls sehingga operasi terikat pada class dan tetap mengikuti subclass.
    @classmethod
    def tearDownClass(cls):
        cls.file_field.storage = cls.original_storage
        cls.override.disable()
        shutil.rmtree(cls.tmp, ignore_errors=True)
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        super().tearDownClass()

    # OOP — Method overriding: framework pengujian memanggil hook setUp milik subclass untuk menyiapkan/membersihkan fixture.
    def setUp(self):
        owner, other, self.participant, admin = setup_users()
        self.event = published_event(owner, admin)
        for person in (self.participant, other):
          for field, value in (
              ("ktp_number", "1234567890123456"), ("gender", "L"), ("birth_place", "Samarinda"),
              ("birth_date", "2000-01-01"), ("address", "Jl. Contoh 1"), ("phone_number", "081234567890"),
          ):
            setattr(person, field, value)
          person.save()
        self.committee = make_committee("panitia@x.example")
        self.stranger = make_committee("lain@x.example")
        EventCommitteeAssignment.objects.create(event=self.event, member=self.committee)
        self.registration = Registration.objects.create(event=self.event, participant=self.participant)
        self.absent = Registration.objects.create(event=self.event, participant=other)
        Attendance.objects.create(
            registration=self.registration, verified_by=self.committee,
            status=Attendance.Status.PRESENT,
        )
        self.url = reverse("panitia_upload_sertifikat")

    # OOP — Encapsulation: method upload mengelompokkan operasi terkait objek UploadedCertificateTests.
    def upload(self, registration, name="s.pdf", content=PDF):
        return self.client.post(self.url, {
            "registration_id": registration.pk,
            "certificate_file": SimpleUploadedFile(name, content),
        })

    def test_assigned_committee_uploads_replaces_and_deletes(self):
        self.client.force_login(self.committee)
        self.assertEqual(self.upload(self.registration).status_code, 200)
        first = UploadedCertificate.objects.get(registration=self.registration).file.name
        self.assertEqual(self.upload(self.registration).status_code, 200)
        cert = UploadedCertificate.objects.get(registration=self.registration)
        self.assertNotEqual(cert.file.name, first)
        response = self.client.post(reverse("panitia_hapus_sertifikat"), {"registration_id": self.registration.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UploadedCertificate.objects.exists())

    def test_rejects_bad_type_and_fake_content(self):
        self.client.force_login(self.committee)
        self.assertEqual(self.upload(self.registration, "s.exe", PDF).status_code, 400)
        self.assertEqual(self.upload(self.registration, "s.pdf", b"bukan pdf").status_code, 400)
        self.assertFalse(UploadedCertificate.objects.exists())

    def test_unassigned_committee_and_absent_participant_are_rejected(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.upload(self.registration).status_code, 404)
        self.client.force_login(self.committee)
        self.assertEqual(self.upload(self.absent).status_code, 404)

    def test_participant_downloads_only_own_certificate(self):
        self.client.force_login(self.committee)
        self.upload(self.registration)
        url = reverse("peserta_sertifikat_unggahan", args=[self.registration.pk])
        self.client.force_login(self.participant)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), PDF)
        self.client.force_login(self.absent.participant)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_committee_page_renders_certificate_tab(self):
        self.client.force_login(self.committee)
        self.upload(self.registration)
        html = self.client.get(reverse("panitia_biasa")).content.decode()
        self.assertIn("tab-sertifikat", html)
        self.assertIn("cert-row", html)
