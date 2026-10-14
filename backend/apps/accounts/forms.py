# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk akun, autentikasi, dan hak akses.

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)

from .models import User


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
        )

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


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        max_length=254,
    )


class AccountChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


# Kalau udah butuh fitur edit profil
# class ProfileForm(forms.ModelForm):
#     class Meta:
#         model = User
#         fields = (
#             "first_name",
#             "last_name",
#             "email",
#         )
