# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk registrasi, tiket, attendance, feedback, dan statistik.

from django import forms
from django.core.validators import FileExtensionValidator

from .models import (
    Feedback,
    RATING_FIELDS,
    validate_payment_proof_size,
)


# Inheritance: ConfirmationForm mewarisi pengelolaan field dan validasi input Django.
class ConfirmationForm(forms.Form):
    confirm = forms.BooleanField(required=True)


# Inheritance: TicketScanForm mewarisi pengelolaan field dan validasi input Django.
class TicketScanForm(forms.Form):
    token = forms.UUIDField()


# Inheritance: FeedbackForm mewarisi pembuatan form, validasi, dan penyimpanan berbasis model.
class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = (*RATING_FIELDS, "comment", "suggestion")


# Inheritance: PaymentProofForm mewarisi pengelolaan field dan validasi input Django.
class PaymentProofForm(forms.Form):
    proof = forms.FileField(
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "pdf"]),
            validate_payment_proof_size,
        ],
    )
    note = forms.CharField(max_length=500, required=False)

    # Abstraction: Django memanggil hook ini saat is_valid() untuk memvalidasi field proof.
    def clean_proof(self):
        proof = self.cleaned_data["proof"]
        header = proof.read(8)
        proof.seek(0)
        if not (
            header.startswith(b"%PDF-")
            or header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith(b"\xff\xd8\xff")
        ):
            raise forms.ValidationError("Unggah bukti berupa PDF, JPEG, atau PNG yang valid.")
        return proof
