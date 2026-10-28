from django import template

from apps.events.seeds.presentation import demo_ui_data

register = template.Library()


@register.simple_tag
def demo_seed(section=None):
    """Baca data seed untuk halaman yang belum dihubungkan ke database."""
    return demo_ui_data(section)
