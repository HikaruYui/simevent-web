# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk registrasi, tiket, attendance, feedback, dan statistik.

from django import forms

from .models import Feedback, RATING_FIELDS


class ConfirmationForm(forms.Form):
    confirm = forms.BooleanField(required=True)


class TicketScanForm(forms.Form):
    token = forms.UUIDField()


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = (*RATING_FIELDS, "comment", "suggestion")
