from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Masukkan Email Anda',
            'id': 'email',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Masukkan Kata Sandi Anda',
            'id': 'password',
            'autocomplete': 'current-password',
        })
    )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True, label='Nama Depan')
    last_name = forms.CharField(max_length=100, required=False, label='Nama Belakang')
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label='Daftar Sebagai')
    institution = forms.CharField(max_length=200, required=False, label='Institusi')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                institution=self.cleaned_data.get('institution', ''),
            )
        return user
