# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk proposal kerja sama dan approval Organizer.

from django import forms

from .models import OrganizerProposal


class ProposalForm(forms.ModelForm):
    class Meta:
        model = OrganizerProposal
        fields = ("organization_name", "contact_information", "proposal_text")


class ConfirmationForm(forms.Form):
    confirm = forms.BooleanField(required=True)
