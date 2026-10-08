from django.contrib import admin
from .models import Event, EventRegistration, Certificate, Payment


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'date', 'price', 'capacity', 'registered_count']
    list_filter = ['category', 'status', 'format']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'event', 'registration_date', 'payment_status', 'attended']
    list_filter = ['payment_status', 'attended']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_number', 'user', 'event', 'claimed', 'issued_date']
    list_filter = ['claimed']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'method', 'status', 'payment_date']
    list_filter = ['status', 'method']
