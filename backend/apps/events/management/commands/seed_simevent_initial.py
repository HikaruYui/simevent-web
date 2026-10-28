
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
from apps.events.seeds import (
    DEMO_ACCOUNTS,
    EVENTS_ADMIN,
    EVENTS_KP,
    HARGA,
    KATEGORI,
    PROPOSALS,
    VENUES,
    demo_participants,
    load_demo_catalog,
)


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
                        "reason": load_demo_catalog()["ui"]["event_rejection_reason"],
                    },
                )

        # 300 PESERTA & REGISTRASI KETUA PANITIA

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

        for participant in demo_participants():
            event, _, _ = kp_events[participant["eventId"] - 1]
            user = ensure_user(participant["email"], participant["nama"])
            pool.append(user)
            add_registration(
                user=user,
                event=event,
                registered_at=tanggal(participant["terdaftar"]),
                hadir=participant["status"] == "hadir",
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
