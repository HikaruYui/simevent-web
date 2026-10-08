from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Event(models.Model):
    """Model for events."""
    CATEGORY_CHOICES = [
        ('konferensi', 'Konferensi'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('webinar', 'Webinar'),
        ('sosialisasi', 'Sosialisasi'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Sedang Berlangsung'),
        ('upcoming', 'Akan Datang'),
        ('finished', 'Selesai'),
    ]

    FORMAT_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
    ]

    title = models.CharField(max_length=300, verbose_name='Judul Event')
    slug = models.SlugField(max_length=300, unique=True)
    description = models.TextField(verbose_name='Deskripsi', blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='Kategori')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming', verbose_name='Status')
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='offline', verbose_name='Format')
    
    date = models.DateTimeField(verbose_name='Tanggal Event')
    end_date = models.DateTimeField(verbose_name='Tanggal Selesai', null=True, blank=True)
    
    location = models.CharField(max_length=300, verbose_name='Lokasi', blank=True)
    speaker = models.CharField(max_length=200, verbose_name='Pembicara', blank=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_events', verbose_name='Penyelenggara')
    organizer_name = models.CharField(max_length=200, verbose_name='Nama Penyelenggara', blank=True)
    
    price = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Harga')
    capacity = models.PositiveIntegerField(default=100, verbose_name='Kapasitas')
    
    image = models.ImageField(upload_to='events/', blank=True, null=True, verbose_name='Gambar')
    
    has_certificate = models.BooleanField(default=True, verbose_name='Sertifikat Digital')
    has_recording = models.BooleanField(default=False, verbose_name='Rekaman/Materi')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        ordering = ['-date']

    def __str__(self):
        return self.title
    
    @property
    def is_free(self):
        return self.price == 0
    
    @property
    def registered_count(self):
        return self.registrations.filter(payment_status='paid').count()
    
    @property
    def is_full(self):
        return self.registered_count >= self.capacity
    
    @property
    def spots_left(self):
        return max(0, self.capacity - self.registered_count)


class EventRegistration(models.Model):
    """Model for event registration by participants."""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Menunggu Pembayaran'),
        ('paid', 'Lunas'),
        ('free', 'Gratis'),
        ('refunded', 'Dikembalikan'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registrations')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    registration_date = models.DateTimeField(auto_now_add=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    attended = models.BooleanField(default=False, verbose_name='Hadir')
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    
    class Meta:
        verbose_name = 'Registrasi Event'
        verbose_name_plural = 'Registrasi Event'
        unique_together = ['user', 'event']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{timezone.now().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        if self.event.is_free:
            self.payment_status = 'free'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.event.title}"


class Certificate(models.Model):
    """Model for digital certificates."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='certificates')
    registration = models.OneToOneField(EventRegistration, on_delete=models.CASCADE, related_name='certificate')
    certificate_number = models.CharField(max_length=50, unique=True, blank=True)
    issued_date = models.DateTimeField(auto_now_add=True)
    claimed = models.BooleanField(default=False, verbose_name='Diklaim')
    claimed_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Sertifikat'
        verbose_name_plural = 'Sertifikat'
        unique_together = ['user', 'event']

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            self.certificate_number = f"CERT-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sertifikat {self.certificate_number} - {self.user.get_full_name()}"


class Payment(models.Model):
    """Model for payment records."""
    METHOD_CHOICES = [
        ('qris', 'QRIS'),
        ('transfer', 'Transfer Bank'),
        ('ewallet', 'E-Wallet'),
        ('free', 'Gratis'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Menunggu'),
        ('success', 'Berhasil'),
        ('failed', 'Gagal'),
        ('refunded', 'Dikembalikan'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    registration = models.ForeignKey(EventRegistration, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Jumlah')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, verbose_name='Metode')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pembayaran'
        verbose_name_plural = 'Pembayaran'
        ordering = ['-payment_date']

    def __str__(self):
        return f"Rp{self.amount:,.0f} - {self.user.get_full_name()} ({self.get_status_display()})"
