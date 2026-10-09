# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk event, ownership, dan alur approval/publikasi.

from django import forms
from django.core.validators import URLValidator
from django.db.models import Q

from apps.accounts.models import User

from .models import Event, EventType


class BannerField(forms.ImageField):
    max_bytes = 5 * 1024 * 1024
    max_dimension = 4096
    extensions = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

    # Polymorphism: hook ImageField yang sama diberi perilaku khusus untuk validasi banner.
    def to_python(self, data):
        if data and data.size > self.max_bytes:
            raise forms.ValidationError("Banner must be at most 5 MiB.")
        upload = super().to_python(data)
        if upload is None:
            return None
        image = upload.image
        if image.format not in self.extensions:
            raise forms.ValidationError("Use a JPEG, PNG or WebP banner.")
        if max(image.size) > self.max_dimension:
            raise forms.ValidationError("Banner dimensions must not exceed 4096 pixels.")
        upload.name = "banner" + self.extensions[image.format]
        return upload


# Inheritance: memakai validasi dan penyimpanan ModelForm, lalu menambahkan aturan event.
class EventForm(forms.ModelForm):
    banner = BannerField(required=False)
    remove_banner = forms.BooleanField(required=False)
    meeting_url = forms.URLField(
        required=False, max_length=1000, validators=[URLValidator(schemes=["https"])]
    )
    access_instructions = forms.CharField(required=False, max_length=5000)

    class Meta:
        model = Event
        fields = (
            "title", "description", "event_type", "delivery_mode",
            "start_datetime", "end_datetime", "venue", "capacity", "price",
            "registration_open", "registration_close", "banner",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event_type"].queryset = EventType.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("remove_banner") and self.files.get("banner"):
            self.add_error("banner", "Choose either a new banner or removal.")
        return cleaned


# Inheritance: memperluas EventForm dengan pemilihan organizer tanpa menyalin validasi event.
class AdminEventForm(EventForm):
    class Meta(EventForm.Meta):
        fields = (*EventForm.Meta.fields, "organizer")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        permission = Q(
            groups__permissions__codename="access_organizer",
            groups__permissions__content_type__app_label="accounts",
        ) | Q(
            user_permissions__codename="access_organizer",
            user_permissions__content_type__app_label="accounts",
        )
        self.fields["organizer"].queryset = User.objects.filter(
            Q(is_superuser=True) | permission, is_active=True
        ).distinct()


class TransitionForm(forms.Form):
    reason = forms.CharField(required=False, max_length=2000)


class DeleteDraftForm(forms.Form):
    confirm = forms.BooleanField(required=True)
