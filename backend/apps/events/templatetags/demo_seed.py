from django import template

from apps.events.seeds.presentation import demo_ui_data
from apps.events.seeds import load_demo_catalog

register = template.Library()


# OOP — Decorator registrasi: mengekspos callable sebagai tag template Django.
@register.simple_tag
def demo_seed(section=None):
    """Baca data seed untuk halaman yang belum dihubungkan ke database."""
    return demo_ui_data(section)


@register.simple_tag
def runtime_ui():
    """Hanya label UI; data operasional berasal dari view sesuai hak akses."""
    data = load_demo_catalog()["ui"]
    return {
        "admin_name": "Administrator", "organizer_name": "",
        "admin_notifications": data["admin_notifications"],
        "organizer_notifications": data["organizer_notifications"],
        "proposal_summaries": {},
        "admin_events": [], "admin_users": [], "proposals": [],
        "extra_tickets": [], "audit": [],
        "eo": {"events": [], "participants": [], "tickets": [], "activity": [],
               "monthly": {"labels": [], "pendapatan": [], "tiket": []}, "attendance_series": {}},
        "committee": {"participants": []},
    }
