
from datetime import date, datetime, timedelta
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
    EventCommitteeAssignment,
    CommitteePreference,
    OrganizerInvitation,
    OrganizerPreference,
    OrganizerSupportTicket,
    PlatformSettings,
    PlatformAuditLog,
)
from apps.registrations.models import (
    Registration,
    Ticket,
    Payment,
    PaymentInstructions,
    Attendance,
    Feedback,
    RATING_FIELDS,
)
from apps.achievements.models import Achievement
from apps.achievements.services import AchievementService
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


# Inheritance: Command mewarisi kerangka perintah manage.py.
# OOP — Hierarchical inheritance: BaseCommand juga menjadi induk class saudara lain di proyek.
class Command(BaseCommand):
    help = "Initial data lengkap SIMEVENT untuk development."

    # Polymorphism: menentukan argumen khusus untuk perintah Django.
    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Perbarui data event dengan slug demo yang sudah ada.",
        )

    # Polymorphism: menyediakan implementasi perintah yang dipanggil oleh BaseCommand.
    # OOP — Decorator transaksi: membungkus eksekusi dalam transaksi atomik; decorator Python bukan otomatis pola Decorator berbasis class.
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
                    # Identitas sintetis untuk akun demo baru; akun yang sudah ada tetap utuh.
                    ktp_number=f"990000{created_users:010d}",
                    gender="L", birth_place="Kota Demo", birth_date=date(2000, 1, 1),
                    address="Alamat contoh untuk demonstrasi SIMEVENT", phone_number="081200000000",

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
        ui_seed = load_demo_catalog()["ui"]
        now = timezone.now()


        # REKENING PEMBAYARAN SIMEVENT (DEVELOPMENT)
        bank_data = {
            "bank_name": "BANK DEMO SIMEVENT",
            "account_number": "0000000000",
            "account_holder": "SIMEVENT DEMO",
            "instructions": (
                "Silakan ikuti instruksi pembayaran. "
                "Setelah mendaftar, unggah bukti pembayaran untuk diverifikasi."
            ),
        }

        rekening = PaymentInstructions.objects.filter(
            is_active=True
        ).order_by("pk").first()

        if rekening:
            for field, value in bank_data.items():
                setattr(rekening, field, value)

            rekening.save(update_fields=list(bank_data.keys()))
        else:
            rekening = PaymentInstructions.objects.create(
                **bank_data,
                is_active=True,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Rekening pembayaran diperbarui: {rekening.bank_name}"
            )
        )


        self.stdout.write(
            self.style.SUCCESS(
                "Instruksi pembayaran aktif tersedia."
            )
        )


        shared_settings = ui_seed["shared_defaults"]["settings"]
        PlatformSettings.objects.get_or_create(
            pk=1,
            defaults={
                "platform_fee_percent": shared_settings["feePct"],
                "event_approval_required": shared_settings["approvalRequired"],
                "notifications": shared_settings["notif"],
                "category_enabled": shared_settings["categories"],
            },
        )

        for category_name, enabled in shared_settings["categories"].items():
            if not EventType.objects.filter(name__iexact=category_name).exists():
                code = category_name.lower().replace(" ", "-")
                EventType.objects.get_or_create(
                    code=code,
                    defaults={"name": category_name, "is_active": enabled},
                )

        organizer_names = {
            item["email"].lower(): item.get("org", "")
            for item in ui_seed["admin_users"]
            if item["peran"] == "penyelenggara"
        }
        for email, organization in organizer_names.items():
            organizer = accounts.get(email)
            if not organizer or not organization:
                continue
            preference, _ = OrganizerPreference.objects.get_or_create(user=organizer)
            if not preference.organization_name:
                preference.organization_name = organization
                preference.save(update_fields=("organization_name", "updated_at"))

        seeded_proposals = 0
        for email, organization, proposal_text, submitted in PROPOSALS:
            applicant = accounts.get(email.lower())
            if not applicant or OrganizerProposal.objects.filter(applicant=applicant).exists():
                continue
            _, created = OrganizerProposal.objects.get_or_create(
                applicant=applicant,
                organization_name=organization,
                defaults={
                    "contact_information": applicant.email,
                    "proposal_text": proposal_text,
                    "status": ProposalStatus.SUBMITTED,
                    "submitted_at": tanggal(submitted),
                },
            )
            seeded_proposals += int(created)

        seeded_audit = 0
        for index, entry in enumerate(ui_seed["audit"], start=1):
            ago = entry["waktu"]
            days_ago = 0 if ago == "Hari ini" else int(ago.split()[0]) * (7 if "minggu" in ago else 30 if "bulan" in ago else 1)
            actor_name = entry["aktor"]
            actor = admin if actor_name == "{admin}" else None
            _, created = PlatformAuditLog.objects.get_or_create(
                seed_key=f"demo-audit-{index}",
                defaults={
                    "category": entry["tipe"],
                    "description": entry["teks"],
                    "actor": actor,
                    "actor_label": admin.get_full_name() if actor else actor_name,
                    "actor_role": entry["peran"],
                    "created_at": now - timedelta(days=days_ago),
                },
            )
            seeded_audit += int(created)

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

        # DATA DEMO KETUA PANITIA: preferensi, tim, undangan, dan tiket support.
        organizer_preferences = ui_seed["organizer_notifications"]
        OrganizerPreference.objects.get_or_create(
            user=budi,
            defaults={
                "notifications": {
                    item["k"]: item["on"]
                    for item in organizer_preferences
                },
            },
        )

        seeded_team = 0
        all_organizer_events = list(Event.objects.managed_by(budi))
        for member_data in ui_seed["team"]:
            member = accounts.get(member_data["email"].lower())
            if not member:
                continue
            if member_data["akses"] == "semua":
                member_events = all_organizer_events
            else:
                member_events = [
                    kp_events[int(event_id) - 1][0]
                    for event_id in member_data["akses"]
                    if 0 < int(event_id) <= len(kp_events)
                ]
            for event in member_events:
                _, created = EventCommitteeAssignment.objects.get_or_create(
                    event=event,
                    member=member,
                    defaults={"is_active": member_data["status"] == "aktif"},
                )
                seeded_team += int(created)
            selected_title = ui_seed["committee"]["event_name"]
            selected_event = next(
                (event for event in member_events if event.title == selected_title),
                member_events[0] if member_events else None,
            )
            CommitteePreference.objects.get_or_create(
                member=member,
                defaults={"selected_event": selected_event},
            )

        seeded_invites = 0
        for invite_data in ui_seed["invites"]:
            remaining_days = max(0, min(7, int(invite_data["sisa"])))
            sent_at = now - timedelta(days=7 - remaining_days)
            _, created = OrganizerInvitation.objects.get_or_create(
                organizer=budi,
                email=invite_data["email"].lower(),
                defaults={
                    "sent_at": sent_at,
                    "expires_at": sent_at + timedelta(days=7),
                },
            )
            seeded_invites += int(created)

        seeded_support = 0
        for ticket_data in ui_seed["eo"]["tickets"]:
            event_index = int(ticket_data["eventId"]) - 1
            if not 0 <= event_index < len(kp_events):
                continue
            event = kp_events[event_index][0]
            created_at = timezone.make_aware(
                datetime.strptime(ticket_data["tanggal"], "%Y-%m-%d"),
                timezone.get_current_timezone(),
            )
            ticket_status = (
                OrganizerSupportTicket.Status.RESOLVED
                if ticket_data["status"] == "selesai"
                else OrganizerSupportTicket.Status.IN_PROGRESS
            )
            _, created = OrganizerSupportTicket.objects.get_or_create(
                code=ticket_data["id"],
                defaults={
                    "organizer": budi,
                    "event": event,
                    "reporter": ticket_data["pelapor"],
                    "title": ticket_data["judul"],
                    "description": ticket_data["isi"],
                    "status": ticket_status,
                    "created_at": created_at,
                    "resolved_at": (
                        created_at
                        if ticket_status == OrganizerSupportTicket.Status.RESOLVED
                        else None
                    ),
                },
            )
            seeded_support += int(created)

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

        seeded_support = 0
        for ticket_data in ui_seed["extra_tickets"]:
            event_index = int(ticket_data["eventId"]) - 101
            if not 0 <= event_index < len(admin_events):
                continue
            event = admin_events[event_index][0]
            organizer = event.organizer
            created_at = timezone.make_aware(
                datetime.strptime(ticket_data["tanggal"], "%Y-%m-%d"),
                timezone.get_current_timezone(),
            )
            ticket_status = (
                OrganizerSupportTicket.Status.RESOLVED
                if ticket_data["status"] == "selesai"
                else OrganizerSupportTicket.Status.IN_PROGRESS
            )
            _, created = OrganizerSupportTicket.objects.get_or_create(
                code=ticket_data["id"],
                defaults={
                    "organizer": organizer,
                    "event": event,
                    "reporter": ticket_data["pelapor"],
                    "title": ticket_data["judul"],
                    "description": ticket_data["isi"],
                    "status": ticket_status,
                    "reply": ticket_data.get("balasan", ""),
                    "created_at": created_at,
                    "resolved_at": created_at if ticket_status == OrganizerSupportTicket.Status.RESOLVED else None,
                },
            )
            seeded_support += int(created)

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

        # Skenario lintas peran: identitas peserta yang sama dipakai pada event
        # mendatang, berjalan, dan selesai; seluruh panel membaca registrasi ini.
        demo_people = [accounts[email] for email, _, role in DEMO_ACCOUNTS if role == "PARTICIPANT"]
        demo_people += [
            ensure_user(item["email"], item["name"])
            for item in ui_seed["committee"]["participants"]
        ]
        demo_committee = [
            accounts[email] for email, _, role in DEMO_ACCOUNTS
            if role == "COMMITTEE" and accounts[email].is_active
        ]
        scenarios = (
            ("upcoming", "Demo Terpadu - Pendaftaran", now + timedelta(days=7), EventStatus.PUBLISHED),
            ("live", "Demo Terpadu - Absensi", now - timedelta(hours=1), EventStatus.PUBLISHED),
            ("completed", "Demo Terpadu - Hasil Kegiatan", now - timedelta(days=7), EventStatus.COMPLETED),
        )
        for stage, title, start, status in scenarios:
            event = save_event(
                slug=f"demo-integrated-{stage}", title=title, code="SEMINAR", owner=budi,
                start=start, venue="Ruang Demonstrasi SIMEVENT", capacity=100, price=0, status=status,
            )
            for member in demo_committee:
                EventCommitteeAssignment.objects.get_or_create(event=event, member=member)
            for index, user in enumerate(demo_people):
                add_registration(
                    user, event, min(now - timedelta(days=1), event.start_datetime - timedelta(days=2)),
                    hadir=stage == "completed", verifier=demo_committee[0] if demo_committee else budi,
                )
                registration = Registration.objects.get(participant=user, event=event)
                # Satu peserta dibiarkan belum feedback agar alurnya bisa didemokan.
                if (stage == "completed" and index > 0
                        and registration.status == "REGISTERED"
                        and Attendance.objects.filter(registration=registration, status="PRESENT").exists()):
                    Feedback.objects.get_or_create(registration=registration, defaults={
                        **{field: 4 for field in RATING_FIELDS},
                        "comment": "Feedback contoh untuk demonstrasi lintas peran.",
                    })
        Achievement.objects.get_or_create(code="demo-first-attendance", defaults={
            "name": "Langkah Pertama", "description": "Menghadiri satu event yang telah selesai.",
            "required_count": 1,
        })
        for user in demo_people:
            if user.is_active:
                AchievementService(user).evaluate()

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
            f"Penugasan tim baru  : {seeded_team}"
        )
        self.stdout.write(
            f"Undangan baru       : {seeded_invites}"
        )
        self.stdout.write(
            f"Tiket support baru  : {seeded_support}"
        )
        self.stdout.write(
            f"Pengajuan EO baru   : {seeded_proposals}"
        )
        self.stdout.write(
            f"Audit demo baru     : {seeded_audit}"
        )
        self.stdout.write(
            f"Proposal baru      : {proposal_count}"
        )
        self.stdout.write(
            "Selesai. Data yang sudah ada tidak dihapus."
        )
