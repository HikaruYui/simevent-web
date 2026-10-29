# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk proposal kerja sama dan approval Organizer.

from django import forms

from .models import OrganizerProposal


# Inheritance: ProposalForm mewarisi pembuatan form, validasi, dan penyimpanan berbasis model.
# OOP — Hierarchical inheritance: forms.ModelForm juga menjadi induk class saudara lain di proyek.
class ProposalForm(forms.ModelForm):
    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        model = OrganizerProposal
        fields = ("organization_name", "contact_information", "proposal_text")


# Inheritance: ConfirmationForm mewarisi pengelolaan field dan validasi input Django.
# OOP — Hierarchical inheritance: forms.Form juga menjadi induk class saudara lain di proyek.
# OOP — Object composition: objek field disusun sebagai bagian form; validasi didelegasikan ke masing-masing field.
class ConfirmationForm(forms.Form):
    confirm = forms.BooleanField(required=True)
