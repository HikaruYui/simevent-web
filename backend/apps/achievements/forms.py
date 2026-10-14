# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk achievement, reward, dan kebijakan diskon.

from django import forms

from .models import EventRewardPolicy


class EventRewardPolicyForm(forms.ModelForm):
    class Meta:
        model = EventRewardPolicy
        fields = ("accept_achievement_discount", "max_discount_percentage")

    def clean(self):
        data = super().clean()
        maximum = data.get("max_discount_percentage")
        if maximum is not None:
            if data.get("accept_achievement_discount") and maximum <= 0:
                self.add_error("max_discount_percentage", "Enter a positive discount cap.")
            elif not data.get("accept_achievement_discount") and maximum != 0:
                self.add_error("max_discount_percentage", "Disabled policies must have a zero cap.")
        return data
