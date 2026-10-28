"""Adapter katalog seed ke bentuk data UI lama, tanpa query atau penulisan DB."""

from copy import deepcopy

from . import (
    DEMO_ACCOUNTS,
    EVENTS_ADMIN,
    EVENTS_KP,
    DemoRNG,
    HARGA,
    KATEGORI,
    PROPOSALS,
    VENUES,
    demo_participants,
    load_demo_catalog,
)


def demo_ui_data(section=None):
    data = deepcopy(load_demo_catalog()["ui"])
    if section in data:
        return data[section]
    accounts = {email: name for email, name, _ in DEMO_ACCOUNTS}
    organizer = accounts["budi@simevent.id"]

    def event_row(row, event_id):
        title, code, day, venue, capacity, sold, price, status = row[:8]
        return {
            "id": event_id,
            "nama": title,
            "jenis": KATEGORI[code][0],
            "tanggal": day,
            "lokasi": venue,
            "kuota": capacity,
            "terjual": sold,
            "harga": price,
            "status": status,
        }

    events = []
    participants = list(demo_participants())
    for event_id, row in enumerate(EVENTS_KP, start=1):
        event = event_row(row, event_id)
        event["jenis"] = data["eo"]["event_labels"].get(str(event_id), event["jenis"])
        event["hadir"] = sum(
            p["eventId"] == event_id and p["status"] == "hadir" for p in participants
        )
        event["pendapatan"] = event["terjual"] * event["harga"]
        events.append(event)
    data["eo"]["events"] = events
    data["eo"]["participants"] = participants
    data["eo"]["attendance_series"] = {
        str(event["id"]): {
            metric: _attendance_series(event, metric)
            for metric in ("onsite", "online", "daftar")
        }
        for event in events
    }
    data["organizer_name"] = organizer
    data["admin_name"] = accounts["admin@simevent.id"]
    data["admin_events"] = []
    for event_id, row in enumerate(EVENTS_ADMIN, start=101):
        event = event_row(row, event_id)
        event["organizer"] = data["admin_event_organizers"].get(str(event_id), accounts[row[8]])
        if event["status"] == "ditolak":
            event["alasan"] = data["event_rejection_reason"]
        data["admin_events"].append(event)
    data["proposals"] = [
        {"id": index, "nama": accounts[email], "email": email,
         "org": org, "rencana": text, "tanggal": submitted}
        for index, (email, org, text, submitted) in enumerate(PROPOSALS, start=1)
    ]
    data["catalogue"] = {
        "categories": {
            code.lower(): {"name": name, "titles": list(titles)}
            for code, (name, titles) in KATEGORI.items()
        },
        "venues": list(VENUES),
        "prices": list(HARGA),
        "organizers": data.pop("catalogue_organizers"),
    }
    return data[section] if section else data


def _attendance_series(event, metric):
    onsite = int(event["hadir"] * 0.7 + 0.5)
    total = {
        "onsite": onsite,
        "online": event["hadir"] - onsite,
        "daftar": event["terjual"],
    }[metric]
    rng = DemoRNG(event["id"] * 31 + len(metric) * 7)
    weights = [
        (1 + index * (0.35 if metric == "daftar" else 0.25))
        * (0.45 + rng.random() * 1.1)
        for index in range(7)
    ]
    values = [int(weight / sum(weights) * total + 0.5) for weight in weights]
    values[-1] += total - sum(values)
    return values
