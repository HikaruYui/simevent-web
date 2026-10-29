# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk registrasi, tiket, attendance, feedback, dan statistik.

from django import forms
from django.core.validators import FileExtensionValidator

from .models import (
    Feedback,
    RATING_FIELDS,
    validate_payment_proof_size,
)


# Inheritance: ConfirmationForm mewarisi pengelolaan field dan validasi input Django.
# OOP — Hierarchical inheritance: forms.Form juga menjadi induk class saudara lain di proyek.
# OOP — Object composition: objek field disusun sebagai bagian form; validasi didelegasikan ke masing-masing field.
class ConfirmationForm(forms.Form):
    confirm = forms.BooleanField(required=True)


# Inheritance: TicketScanForm mewarisi pengelolaan field dan validasi input Django.
# OOP — Hierarchical inheritance: forms.Form juga menjadi induk class saudara lain di proyek.
# OOP — Object composition: objek field disusun sebagai bagian form; validasi didelegasikan ke masing-masing field.
class TicketScanForm(forms.Form):
    token = forms.UUIDField()


# Inheritance: FeedbackForm mewarisi pembuatan form, validasi, dan penyimpanan berbasis model.
# OOP — Hierarchical inheritance: forms.ModelForm juga menjadi induk class saudara lain di proyek.
class FeedbackForm(forms.ModelForm):
    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        model = Feedback
        fields = (*RATING_FIELDS, "comment", "suggestion")


# Inheritance: PaymentProofForm mewarisi pengelolaan field dan validasi input Django.
# OOP — Hierarchical inheritance: forms.Form juga menjadi induk class saudara lain di proyek.
# OOP — Object composition: objek field disusun sebagai bagian form; validasi didelegasikan ke masing-masing field.
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
        # OOP — Duck typing: objek unggahan dipakai melalui read()/seek(); implementasi file di memori atau disk dapat memenuhi protokol yang sama.
        header = proof.read(8)
        proof.seek(0)
        if not (
            header.startswith(b"%PDF-")
            or header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith(b"\xff\xd8\xff")
        ):
            raise forms.ValidationError("Unggah bukti berupa PDF, JPEG, atau PNG yang valid.")
        return proof
