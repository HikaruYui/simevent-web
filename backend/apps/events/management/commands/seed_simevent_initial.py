
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.events.models import (
    Event,
    EventStatus,
    EventType,
    EventTransition,
    DeliveryMode,
)
from apps.registrations.models import (
    Registration,
    Ticket,
    Payment,
    Attendance,
)
from apps.partnerships.models import OrganizerProposal, ProposalStatus
from .seed_dummy_events import KATEGORI, VENUES, HARGA



# SIMEVENT INITIAL DATA
# Berdasarkan dummy frontend dan seed event sebelumnya.
# Khusus DEVELOPMENT, bukan production.


DEMO_ACCOUNTS = [
    ("admin@simevent.id", "Super Administrator", "ADMIN"),
    ("budi@simevent.id", "Budi Santoso", "ORGANIZER"),
    ("ahmad.fauzi@simevent.id", "Prof. Ahmad Fauzi", "ORGANIZER"),
    ("rina.kartika@simevent.id", "Dr. Rina Kartika", "ORGANIZER"),
    ("sari.wulandari@simevent.id", "Sari Wulandari", "ORGANIZER"),
    ("andi.pratama@simevent.id", "Andi Pratama", "ORGANIZER"),
    ("lina.marlina@simevent.id", "Dr. Lina Marlina", "ORGANIZER"),
    ("biro.kemahasiswaan@simevent.id", "Biro Kemahasiswaan", "ORGANIZER"),
    ("seni.rupa@simevent.id", "Himpunan Seni Rupa", "ORGANIZER"),

    ("siti.rahma@mail.com", "Siti Rahma", "COMMITTEE"),
    ("rafi.hidayat@mail.com", "Rafi Hidayat", "COMMITTEE"),
    ("nabila.a@mail.com", "Nabila Amalia", "COMMITTEE"),
    ("dimas.p@mail.com", "Dimas Prakoso", "COMMITTEE"),

    ("rizky.ananda@mail.com", "Rizky Ananda", "PARTICIPANT"),
    ("salsa.putri@mail.com", "Salsa Putri", "PARTICIPANT"),
    ("fajar.nugroho@mail.com", "Fajar Nugroho", "PARTICIPANT"),
]



# 12 EVENT KETUA PANITIA
#
# Format:
# (judul, jenis, tanggal, lokasi, kuota, terjual,
#  harga, status)


EVENTS_KP = [
    ("Konferensi Meja Bundar", "CONFERENCE", "2026-10-16",
     "Aula Utama Universitas Mulawarman", 60, 42, 150000, "berlangsung"),

    ("Workshop UI/UX Dasar", "WORKSHOP", "2026-10-16",
     "Lab Komputer Gedung Informatika", 40, 35, 100000, "berlangsung"),

    ("Seminar Kewirausahaan Digital", "SEMINAR", "2026-10-17",
     "Ruang Seminar Fakultas Ekonomi", 50, 28, 75000, "berlangsung"),

    ("Webinar Karier Teknologi", "WEBINAR", "2026-10-17",
     "Online (Zoom)", 100, 31, 0, "berlangsung"),

    ("Konferensi Pendidikan Kaltim", "CONFERENCE", "2026-10-24",
     "Hotel Mercure Samarinda", 80, 24, 150000, "mendatang"),

    ("Workshop Data Science", "WORKSHOP", "2026-10-28",
     "Lab Komputer Gedung Informatika", 30, 20, 130000, "mendatang"),

    ("Seminar Kesehatan Mental", "SEMINAR", "2026-11-02",
     "Aula Fakultas Kedokteran", 70, 18, 50000, "mendatang"),

    ("Webinar Literasi Keuangan", "WEBINAR", "2026-11-08",
     "Online (Zoom)", 150, 22, 0, "mendatang"),

    ("Kuliah Umum Kecerdasan Buatan", "SEMINAR", "2026-09-18",
     "Auditorium Universitas Mulawarman", 120, 30, 100000, "selesai"),

    ("Workshop Fotografi Jurnalistik", "WORKSHOP", "2026-09-27",
     "Gedung Kesenian Samarinda", 25, 16, 150000, "selesai"),

    ("Seminar Lingkungan Hidup", "SEMINAR", "2026-09-30",
     "Ruang Rapat Dinas Lingkungan Hidup", 60, 19, 50000, "selesai"),

    ("Konferensi Pariwisata Kaltim", "CONFERENCE", "2026-10-05",
     "Hotel Aston Samarinda", 40, 15, 150000, "selesai"),
]



# 9 EVENT TAMBAHAN ADMIN
#
# Format:
# (judul, jenis, tanggal, lokasi, kuota, terjual,
#  harga, status, email organizer)


EVENTS_ADMIN = [
    ("Hackathon PTIK 2026", "CONFERENCE", "2026-11-12",
     "Gedung Serbaguna Samarinda", 120, 0, 50000, "diajukan",
     "ahmad.fauzi@simevent.id"),

    ("Workshop AI & Machine Learning", "WORKSHOP", "2026-12-05",
     "Lab Komputer FKTI", 60, 0, 85000, "diajukan",
     "sari.wulandari@simevent.id"),

    ("Sosialisasi Beasiswa dan Program Magang Nasional",
     "SOSIALISASI", "2026-11-15",
     "Aula Rektorat", 200, 0, 0, "diajukan",
     "biro.kemahasiswaan@simevent.id"),

    ("Seminar Nasional Teknologi Informasi 2026",
     "SEMINAR", "2026-10-18",
     "Auditorium Unmul, Samarinda", 300, 248, 0, "berlangsung",
     "rina.kartika@simevent.id"),

    ("Workshop UI/UX untuk Pemula", "WORKSHOP", "2026-10-24",
     "Lab Komputer FKTI", 30, 22, 25000, "mendatang",
     "andi.pratama@simevent.id"),

    ("Konferensi Pendidikan & Riset Kalimantan",
     "CONFERENCE", "2026-11-05",
     "Aula Utama, Samarinda", 180, 96, 50000, "mendatang",
     "ahmad.fauzi@simevent.id"),

    ("Webinar Metodologi Penelitian Modern",
     "WEBINAR", "2026-10-02",
     "Online (Zoom)", 150, 131, 0, "selesai",
     "lina.marlina@simevent.id"),

    ("Workshop Analisis Data dengan Python",
     "WORKSHOP", "2026-11-12",
     "Online (Zoom)", 75, 41, 35000, "mendatang",
     "sari.wulandari@simevent.id"),

    ("Konser Amal Kampus", "CONFERENCE", "2026-11-21",
     "Lapangan Utama", 500, 0, 30000, "ditolak",
     "seni.rupa@simevent.id"),
]


PROPOSALS = [
    (
        "rizky.ananda@mail.com",
        "Komunitas Pecinta Alam Mahakam",
        "Kegiatan edukasi lingkungan dan susur sungai untuk pelajar, tiga kali setahun.",
        "2026-10-19",
    ),
    (
        "salsa.putri@mail.com",
        "BEM Fakultas Hukum",
        "Seminar hukum dan kuliah umum dengan praktisi, sekitar 200 peserta per acara.",
        "2026-10-17",
    ),
    (
        "fajar.nugroho@mail.com",
        "Himpunan Mahasiswa Sistem Informasi",
        "Workshop pemrograman dan pelatihan karier bagi mahasiswa tingkat awal.",
        "2026-10-14",
    ),
]


FIRST_NAMES = [
    "Ahmad", "Aisyah", "Alya", "Andi", "Annisa", "Bagas",
    "Bayu", "Cahya", "Citra", "Dewi", "Dimas", "Eka",
    "Farhan", "Fitri", "Gita", "Hafiz", "Indah", "Irfan",
    "Jihan", "Kevin", "Lestari", "Maulana", "Nabila",
    "Nanda", "Putri", "Rafi", "Rizky", "Salsabila",
    "Syarafina", "Tegar", "Vina", "Wahyu", "Yusuf", "Zahra",
]

LAST_NAMES = [
    "Pratama", "Saputra", "Ramadhani", "Wijaya",
    "Nugraha", "Amalia", "Hidayat", "Lestari",
    "Kurniawan", "Permata", "Firmansyah", "Maharani",
    "Setiawan", "Anggraini", "Syahputra", "Utami",
    "Prasetyo", "Rahmawati", "Hakim", "Safitri",
]


STATUS_MAP = {
    "berlangsung": EventStatus.PUBLISHED,
    "mendatang": EventStatus.PUBLISHED,
    "selesai": EventStatus.COMPLETED,
    "diajukan": EventStatus.SUBMITTED,
    "ditolak": EventStatus.REJECTED,
}


def tanggal(value, hour=9):
    dt = datetime.strptime(value, "%Y-%m-%d")
    dt = dt.replace(hour=hour)
    return timezone.make_aware(dt, timezone.get_current_timezone())


class DemoRNG:
    """Generator deterministik yang sama dengan dummy JS."""

    def __init__(self, seed=2026):
        self.state = seed

    def random(self):
        self.state = (
            self.state * 1664525 + 1013904223
        ) & 0xFFFFFFFF
        return self.state / 4294967296


class Command(BaseCommand):
    help = "Initial data lengkap SIMEVENT untuk development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Perbarui data event dengan slug demo yang sudah ada.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Seed demo hanya boleh dijalankan saat DEBUG=True."
            )

        refresh = options["refresh"]

        # Siapkan role dan permission dahulu
        call_command("bootstrap_roles", verbosity=0)

        User = get_user_model()
        organizer_group = Group.objects.get(name="Organizer")
        admin_group = Group.objects.get(name="Platform Admin")

        def perm(codename):
            return Permission.objects.get(
                content_type__app_label="accounts",
                codename=codename,
            )

        committee_perm = perm("access_organizer")
        head_perm = perm("access_head_organizer")

        user_cache = {}
        created_users = 0

        def ensure_user(email, name, role="PARTICIPANT", active=True):
            nonlocal created_users

            email = email.lower().strip()

            if email in user_cache:
                return user_cache[email]

            user = User.objects.filter(email__iexact=email).first()
            created = user is None

            if created:
                parts = name.split(" ", 1)

                user = User.objects.create_user(
                    email=email,
                    password=None,
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else "",
                    is_active=active,
                    is_staff=(role == "ADMIN"),
                )

                # Akun demo dibuat tanpa password login.
                if role == "ADMIN":
                    user.groups.add(admin_group)

                elif role == "ORGANIZER":
                    user.groups.add(organizer_group)
                    user.user_permissions.add(
                        committee_perm, head_perm
                    )

                elif role == "COMMITTEE":
                    user.groups.add(organizer_group)
                    user.user_permissions.add(committee_perm)

                created_users += 1

            # Akun yang sudah ada tidak diubah permission,
            # password, status aktif, atau identitasnya.
            user_cache[email] = user
            return user

        accounts = {}
        for email, name, role in DEMO_ACCOUNTS:
            accounts[email] = ensure_user(
                email, name, role,
                active=(email != "dimas.p@mail.com"),
            )

        admin = accounts["admin@simevent.id"]
        budi = accounts["budi@simevent.id"]

        # EVENT TYPES

        types = {}
        for code, (name, titles) in KATEGORI.items():
            obj, created = EventType.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_active": True},
            )
            if refresh and not created:
                obj.name = name
                obj.is_active = True
                obj.save(update_fields=["name", "is_active"])
            types[code] = obj

        # Judul -> slug dari katalog seed lama
        title_slugs = {}
        for code, (name, titles) in KATEGORI.items():
            for index, title in enumerate(titles, start=1):
                title_slugs[title] = (
                    f"demo-{code.lower()}-{index}"
                )

        made_this_run = set()
        created_events = 0
        updated_events = 0

        def save_event(
            slug, title, code, owner, start,
            venue, capacity, price, status,
        ):
            nonlocal created_events, updated_events

            online = (
                code == "WEBINAR"
                or "Online" in venue
            )

            data = {
                "organizer": owner,
                "event_type": types[code],
                "title": title,
                "description": (
                    f"{title}. Event contoh SIMEVENT "
                    "untuk pengembangan dan demonstrasi."
                ),
                "delivery_mode": (
                    DeliveryMode.ONLINE
                    if online else DeliveryMode.OFFLINE
                ),
                "start_datetime": start,
                "end_datetime": start + timedelta(hours=3),
                "venue": venue,
                "capacity": capacity,
                "price": Decimal(price),
                "registration_open": start - timedelta(days=40),
                "registration_close": start - timedelta(minutes=30),
                "status": status,
            }

            event, created = Event.objects.get_or_create(
                slug=slug,
                defaults=data,
            )

            if created:
                made_this_run.add(slug)
                created_events += 1

            elif refresh or slug in made_this_run:
                for key, value in data.items():
                    setattr(event, key, value)

                event.save(
                    update_fields=list(data.keys()) + ["updated_at"]
                )
                updated_events += 1

            return event

        # 50 EVENT KATALOG JELAJAH

        now = timezone.now()
        main_organizers = [
            accounts["budi@simevent.id"],
            accounts["ahmad.fauzi@simevent.id"],
            accounts["rina.kartika@simevent.id"],
            accounts["sari.wulandari@simevent.id"],
            accounts["andi.pratama@simevent.id"],
        ]

        for ci, (code, (name, titles)) in enumerate(
            KATEGORI.items()
        ):
            for i, title in enumerate(titles):
                offset = (
                    0 if i == 0
                    else ((i * 9 + ci * 4) % 60) - 14
                )

                if offset == 0:
                    start = now - timedelta(hours=1)
                    status = EventStatus.PUBLISHED
                else:
                    start = (
                        now + timedelta(days=offset)
                    ).replace(
                        minute=0, second=0, microsecond=0
                    )

                    status = (
                        EventStatus.COMPLETED
                        if offset < 0
                        else EventStatus.PUBLISHED
                    )

                price = (
                    0 if i % 3 == 0
                    else HARGA[(i + ci) % len(HARGA)]
                )

                venue = (
                    "Online (Zoom)"
                    if code == "WEBINAR"
                    else VENUES[(i + ci) % len(VENUES)]
                )

                save_event(
                    slug=f"demo-{code.lower()}-{i + 1}",
                    title=title,
                    code=code,
                    owner=main_organizers[
                        (i + ci) % len(main_organizers)
                    ],
                    start=start,
                    venue=venue,
                    capacity=60 + 20 * ((i + ci) % 6),
                    price=price,
                    status=status,
                )

        # EVENT KETUA PANITIA

        kp_events = []

        for row in EVENTS_KP:
            (
                title, code, day, venue,
                capacity, sold, price, status
            ) = row

            slug = title_slugs.get(
                title,
                "demo-eo-uiux-dasar",
            )

            event = save_event(
                slug=slug,
                title=title,
                code=code,
                owner=budi,
                start=tanggal(day),
                venue=venue,
                capacity=capacity,
                price=price,
                status=STATUS_MAP[status],
            )

            kp_events.append((event, sold, status))

        # EVENT TAMBAHAN ADMIN

        admin_events = []

        for idx, row in enumerate(EVENTS_ADMIN, start=101):
            (
                title, code, day, venue,
                capacity, sold, price, status, email
            ) = row

            event = save_event(
                slug=title_slugs.get(
                    title,
                    f"demo-admin-{idx}",
                ),
                title=title,
                code=code,
                owner=accounts[email],
                start=tanggal(day),
                venue=venue,
                capacity=capacity,
                price=price,
                status=STATUS_MAP[status],
            )

            admin_events.append((event, sold, status))

            if status == "ditolak":
                EventTransition.objects.get_or_create(
                    event=event,
                    to_status=EventStatus.REJECTED,
                    defaults={
                        "actor": admin,
                        "from_status": EventStatus.SUBMITTED,
                        "reason": (
                            "Dokumen izin kegiatan dari kampus "
                            "belum dilampirkan."
                        ),
                    },
                )

        # 300 PESERTA & REGISTRASI KETUA PANITIA

        rng = DemoRNG(2026)
        pool = []
        total_reg = 0
        total_ticket = 0
        total_payment = 0
        total_attendance = 0

        def add_registration(
            user, event, registered_at,
            hadir=False, verifier=None,
        ):
            nonlocal total_reg
            nonlocal total_ticket
            nonlocal total_payment
            nonlocal total_attendance

            reg, created = Registration.objects.get_or_create(
                participant=user,
                event=event,
                defaults={
                    "registered_at": registered_at,
                    "status": "REGISTERED",
                },
            )

            if created:
                total_reg += 1

            ticket, made = Ticket.objects.get_or_create(
                registration=reg,
            )

            if made:
                total_ticket += 1

            # Pembayaran simulasi untuk event berbayar.
            # Tidak membuat bukti transfer palsu.
            if event.price > 0:
                payment, made = Payment.objects.get_or_create(
                    registration=reg,
                    defaults={
                        "amount": event.price,
                        "status": Payment.Status.APPROVED,
                        "reviewed_by": admin,
                        "reviewed_at": (
                            registered_at + timedelta(minutes=10)
                        ),
                    },
                )

                if made:
                    total_payment += 1

            if hadir:
                attendance, made = Attendance.objects.get_or_create(
                    registration=reg,
                    defaults={
                        "checked_in_at": (
                            event.start_datetime
                            + timedelta(minutes=10)
                        ),
                        "verified_by": verifier or budi,
                        "status": Attendance.Status.PRESENT,
                    },
                )

                if made:
                    total_attendance += 1

        for event, sold, status in kp_events:
            ratio = (
                0.60 if status == "berlangsung"
                else 0.85 if status == "selesai"
                else 0
            )

            present_count = int(sold * ratio + 0.5)

            for i in range(sold):
                first = FIRST_NAMES[
                    int(rng.random() * len(FIRST_NAMES))
                ]

                last = LAST_NAMES[
                    int(rng.random() * len(LAST_NAMES))
                ]

                number = int(rng.random() * 90) + 10
                day = int(rng.random() * 20) + 1

                email = (
                    f"{first}.{last}{number}@mail.com"
                ).lower()

                user = ensure_user(
                    email,
                    f"{first} {last}",
                    role="PARTICIPANT",
                )

                pool.append(user)

                month = (
                    9 if status == "selesai" else 10
                )

                registered_at = tanggal(
                    f"2026-{month:02d}-{day:02d}"
                )

                add_registration(
                    user=user,
                    event=event,
                    registered_at=registered_at,
                    hadir=i < present_count,
                    verifier=budi,
                )

        # REGISTRASI EVENT ADMIN

        if not pool:
            raise CommandError(
                "Pool peserta demo kosong."
            )

        for event_index, (event, sold, status) in enumerate(
            admin_events
        ):
            ratio = (
                0.60 if status == "berlangsung"
                else 0.85 if status == "selesai"
                else 0
            )
            present_count = int(sold * ratio + 0.5)

            for i in range(sold):
                user = pool[
                    (event_index * 17 + i) % len(pool)
                ]

                registered_at = (
                    event.start_datetime
                    - timedelta(days=4 + i % 10)
                )

                add_registration(
                    user=user,
                    event=event,
                    registered_at=registered_at,
                    hadir=i < present_count,
                    verifier=event.organizer,
                )

        # 3 PENGAJUAN ORGANIZER

        proposal_count = 0

        for email, org, text, submitted in PROPOSALS:
            user = accounts[email]

            # Jangan menimpa proposal yang sudah dibuat user.
            if OrganizerProposal.objects.filter(
                applicant=user
            ).exists():
                continue

            OrganizerProposal.objects.create(
                applicant=user,
                organization_name=org,
                contact_information=email,
                proposal_text=text,
                status=ProposalStatus.SUBMITTED,
                submitted_at=tanggal(submitted),
            )
            proposal_count += 1

        # RINGKASAN

        self.stdout.write(
            self.style.SUCCESS(
                "SEED SIMEVENT BERHASIL"
            )
        )
        self.stdout.write(
            f"Akun baru          : {created_users}"
        )
        self.stdout.write(
            f"Event baru         : {created_events}"
        )
        self.stdout.write(
            f"Event diperbarui   : {updated_events}"
        )
        self.stdout.write(
            f"Registrasi baru    : {total_reg}"
        )
        self.stdout.write(
            f"Tiket baru         : {total_ticket}"
        )
        self.stdout.write(
            f"Pembayaran baru    : {total_payment}"
        )
        self.stdout.write(
            f"Presensi baru      : {total_attendance}"
        )
        self.stdout.write(
            f"Proposal baru      : {proposal_count}"
        )
        self.stdout.write(
            "Selesai. Data yang sudah ada tidak dihapus."
        )
