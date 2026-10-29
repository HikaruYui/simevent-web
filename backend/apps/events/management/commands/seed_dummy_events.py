# Fungsi file: Mengisi database dengan event contoh (5 kategori x 10 event) agar Landing, Jelajah, dan akun peserta membaca data yang sama.

from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.events.models import DeliveryMode, Event, EventStatus, EventType

from apps.events.seeds import EMAIL_PANITIA, HARGA, KATEGORI, VENUES


# Inheritance: Command mewarisi kerangka perintah manage.py.
# OOP — Hierarchical inheritance: BaseCommand juga menjadi induk class saudara lain di proyek.
class Command(BaseCommand):
    help = "Isi database dengan 50 event contoh (idempotent: aman dijalankan berulang)."

    # Polymorphism: menyediakan implementasi perintah yang dipanggil oleh BaseCommand.
    # OOP — Decorator transaksi: membungkus eksekusi dalam transaksi atomik; decorator Python bukan otomatis pola Decorator berbasis class.
    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        organizer = User.objects.filter(email__iexact=EMAIL_PANITIA).first()
        if organizer is None:
            organizer = User.objects.create_user(
                EMAIL_PANITIA, password=None, first_name="Panitia", last_name="SIMEVENT",
            )
        now = timezone.now()
        dibuat = diperbarui = 0
        for ci, (kode, (nama, judul_list)) in enumerate(KATEGORI.items()):
            jenis, _ = EventType.objects.update_or_create(
                code=kode, defaults={"name": nama, "is_active": True}
            )
            for i, judul in enumerate(judul_list):
                offset = 0 if i == 0 else ((i * 9 + ci * 4) % 60) - 14   # hari dari sekarang
                if offset == 0:                      # sedang berlangsung
                    mulai = now - timedelta(hours=1)
                    status = EventStatus.PUBLISHED
                else:
                    mulai = (now + timedelta(days=offset)).replace(minute=0, second=0, microsecond=0)
                    status = EventStatus.COMPLETED if offset < 0 else EventStatus.PUBLISHED
                online = kode == "WEBINAR"
                defaults = dict(
                    organizer=organizer,
                    event_type=jenis,
                    title=judul,
                    description=f"{judul}. Acara contoh SIMEVENT untuk keperluan pengembangan dan uji tampilan.",
                    delivery_mode=DeliveryMode.ONLINE if online else DeliveryMode.OFFLINE,
                    start_datetime=mulai,
                    end_datetime=mulai + timedelta(hours=3),
                    venue="Online (Zoom)" if online else VENUES[(i + ci) % len(VENUES)],
                    capacity=60 + 20 * ((i + ci) % 6),
                    price=Decimal(0 if i % 3 == 0 else HARGA[(i + ci) % 4]),
                    registration_open=mulai - timedelta(days=30),
                    registration_close=mulai - timedelta(minutes=30),
                    status=status,
                )
                _, created = Event.objects.update_or_create(
                    slug=f"demo-{kode.lower()}-{i + 1}", defaults=defaults
                )
                dibuat += created
                diperbarui += not created
        self.stdout.write(self.style.SUCCESS(
            f"Selesai: {dibuat} event dibuat, {diperbarui} diperbarui. Penyelenggara: {EMAIL_PANITIA}"
        ))
