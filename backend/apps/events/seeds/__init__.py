"""Satu katalog data demo untuk seed database dan tampilan demo sementara."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_demo_catalog():
    with Path(__file__).with_name("demo.json").open(encoding="utf-8") as source:
        return json.load(source)


_catalog = load_demo_catalog()
KATEGORI = _catalog["kategori"]
VENUES = _catalog["venues"]
HARGA = _catalog["harga"]
EMAIL_PANITIA = _catalog["email_panitia"]
DEMO_ACCOUNTS = _catalog["demo_accounts"]
EVENTS_KP = _catalog["events_kp"]
EVENTS_ADMIN = _catalog["events_admin"]
PROPOSALS = _catalog["proposals"]
FIRST_NAMES = _catalog["first_names"]
LAST_NAMES = _catalog["last_names"]


class DemoRNG:
    """Generator deterministik yang mempertahankan identitas peserta demo lama."""

    def __init__(self, seed=2026):
        self.state = seed

    def random(self):
        self.state = (self.state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.state / 4294967296


def demo_participants():
    """Baris peserta yang sama untuk perintah seed dan UI yang belum memakai DB."""
    rng = DemoRNG()
    number = 0
    for event_id, event in enumerate(EVENTS_KP, start=1):
        _, _, _, _, _, sold, _, status = event
        ratio = 0.6 if status == "berlangsung" else 0.85 if status == "selesai" else 0
        present_count = int(sold * ratio + 0.5)
        for index in range(sold):
            first = FIRST_NAMES[int(rng.random() * len(FIRST_NAMES))]
            last = LAST_NAMES[int(rng.random() * len(LAST_NAMES))]
            suffix = int(rng.random() * 90) + 10
            day = int(rng.random() * 20) + 1
            month = 9 if status == "selesai" else 10
            number += 1
            yield {
                "no": number,
                "nama": f"{first} {last}",
                "email": f"{first}.{last}{suffix}@mail.com".lower(),
                "eventId": event_id,
                "terdaftar": f"2026-{month:02d}-{day:02d}",
                "status": "hadir" if index < present_count else "terdaftar",
            }
