# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk akun, autentikasi, dan hak akses.

import re

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)

from .models import User


# Inheritance: RegistrationForm mewarisi perilaku UserCreationForm untuk diperluas sesuai kebutuhan class ini.
class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
        )

    # Abstraction: Django memanggil hook ini saat is_valid() untuk memvalidasi field email.
    def clean_email(self):
        email = User.objects.normalize_email(
            self.cleaned_data["email"]
        )

        if User.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(
                "Email ini sudah terdaftar.",
                code="duplicate_email",
            )

        return email


# Inheritance: ProfileForm mewarisi pembuatan form, validasi, dan penyimpanan berbasis model.
class ProfileForm(forms.ModelForm):
    full_name = forms.CharField(
        label="Nama lengkap",
        max_length=300,
        required=False,
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "ktp_number",
            "ktp_document",
            "profile_photo",
            "gender",
            "birth_place",
            "birth_date",
            "address",
            "phone_number",
        )
        widgets = {
            "birth_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "address": forms.Textarea(attrs={"rows": 1}),
            "ktp_number": forms.TextInput(attrs={"inputmode": "numeric", "pattern": "[0-9]{16}", "maxlength": "16", "autocomplete": "off"}),
            "ktp_document": forms.FileInput(attrs={"accept": "application/pdf,.pdf"}),
            "profile_photo": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "phone_number": forms.TelInput(attrs={"inputmode": "numeric", "pattern": "08[0-9]{8,11}", "maxlength": "13", "autocomplete": "tel"}),
        }

    # OOP inisialisasi: super().__init__() menyiapkan objek induk sebelum field form disesuaikan.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["full_name"].initial = self.instance.get_full_name().strip()
        for field in self.fields.values():
            field.required = True
        self.fields["full_name"].required = False
        self.fields["ktp_document"].required = False
        self.fields["profile_photo"].required = False
        self.fields["first_name"].required = False
        self.fields["last_name"].required = False
        self.fields["first_name"].widget = forms.HiddenInput()
        self.fields["last_name"].widget = forms.HiddenInput()

    # Polymorphism: menambahkan validasi khusus pada hook clean() milik Django.
    def clean(self):
        cleaned_data = super().clean()
        full_name = (cleaned_data.get("full_name") or "").strip()
        if full_name:
            name_parts = full_name.split()
            cleaned_data["first_name"] = name_parts[0]
            cleaned_data["last_name"] = " ".join(name_parts[1:])
        else:
            cleaned_data["first_name"] = (cleaned_data.get("first_name") or "").strip()
            cleaned_data["last_name"] = (cleaned_data.get("last_name") or "").strip()
            if not cleaned_data["first_name"] and "first_name" not in self.errors:
                self.add_error("first_name", "Masukkan nama lengkap.")

        for field in self.Meta.fields:
            if field in ("first_name", "last_name", "ktp_document", "profile_photo"):
                continue
            value = cleaned_data.get(field)
            if isinstance(value, str):
                value = value.strip()
                cleaned_data[field] = value
            if not value and field not in self.errors:
                self.add_error(field, "Lengkapi biodata ini.")
        return cleaned_data

    # Abstraction: Django memanggil hook ini saat is_valid() untuk memvalidasi field ktp_document.
    def clean_ktp_document(self):
        document = self.cleaned_data.get("ktp_document")
        if not document or getattr(document, "_committed", False):
            return document
        if document.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Ukuran PDF KTP maksimal 5 MB.")
        if not document.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Dokumen KTP harus berformat PDF.")
        signature = document.read(5)
        document.seek(0)
        if signature != b"%PDF-":
            raise forms.ValidationError("File yang diunggah bukan PDF yang valid.")
        return document

    # Abstraction: Django memanggil hook ini saat is_valid() untuk memvalidasi field profile_photo.
    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if photo and not getattr(photo, "_committed", False) and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Ukuran foto profil maksimal 5 MB.")
        return photo

    # Abstraction: Django memanggil hook ini saat is_valid() untuk memvalidasi field phone_number.
    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        if phone and not re.fullmatch(r"08\d{8,11}", phone):
            raise forms.ValidationError("Nomor HP harus diawali 08 dan terdiri dari 10 sampai 13 digit angka.")
        return phone


# Inheritance: EmailAuthenticationForm mewarisi perilaku AuthenticationForm untuk diperluas sesuai kebutuhan class ini.
class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        max_length=254,
    )


# Inheritance: AccountChangeForm mewarisi perilaku UserChangeForm untuk diperluas sesuai kebutuhan class ini.
class AccountChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
