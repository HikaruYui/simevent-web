# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk proposal kerja sama dan approval Organizer.

from django import forms

from .models import OrganizerProposal


# Inheritance: ProposalForm mewarisi pembuatan form, validasi, dan penyimpanan berbasis model.
class ProposalForm(forms.ModelForm):
    class Meta:
        model = OrganizerProposal
        fields = ("organization_name", "contact_information", "proposal_text")


# Inheritance: ConfirmationForm mewarisi pengelolaan field dan validasi input Django.
class ConfirmationForm(forms.Form):
    confirm = forms.BooleanField(required=True)
