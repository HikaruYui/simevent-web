# Fungsi file: Form input dan validasi field yang boleh dikirim pengguna untuk achievement, reward, dan kebijakan diskon.

from django import forms

from .models import EventRewardPolicy


# Inheritance: EventRewardPolicyForm mewarisi pembuatan form, validasi, dan penyimpanan berbasis model.
# OOP — Hierarchical inheritance: forms.ModelForm juga menjadi induk class saudara lain di proyek.
class EventRewardPolicyForm(forms.ModelForm):
    # OOP — Nested class: Meta mengelompokkan konfigurasi deklaratif untuk class Django yang menaunginya.
    class Meta:
        model = EventRewardPolicy
        fields = ("accept_achievement_discount", "max_discount_percentage")

    # Polymorphism: menambahkan validasi khusus pada hook clean() milik Django.
    def clean(self):
        # OOP — Cooperative inheritance: super() meneruskan pemanggilan ke implementasi berikutnya dalam MRO, bukan selalu induk pertama.
        data = super().clean()
        maximum = data.get("max_discount_percentage")
        if maximum is not None:
            if data.get("accept_achievement_discount") and maximum <= 0:
                self.add_error("max_discount_percentage", "Enter a positive discount cap.")
            elif not data.get("accept_achievement_discount") and maximum != 0:
                self.add_error("max_discount_percentage", "Disabled policies must have a zero cap.")
        return data
