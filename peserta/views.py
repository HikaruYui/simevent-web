from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from events.models import EventRegistration, Certificate, Payment
from django.utils import timezone


@login_required
def dashboard(request):
    """Peserta dashboard."""
    # Hanya untuk peserta
    if hasattr(request.user, 'profile') and request.user.profile.role == 'panitia':
        return redirect('panitia_dashboard')
        
    registrations = EventRegistration.objects.filter(user=request.user).order_by('-registration_date')
    certificates = Certificate.objects.filter(user=request.user)
    payments = Payment.objects.filter(user=request.user).order_by('-payment_date')
    
    # Stats
    total_events = registrations.filter(payment_status__in=['paid', 'free']).count()
    total_certs = certificates.filter(claimed=True).count()
    upcoming_events = registrations.filter(
        payment_status__in=['paid', 'free'],
        event__status='upcoming'
    ).count()
    
    context = {
        'registrations': registrations[:5],
        'upcoming_registrations': registrations.filter(event__status='upcoming')[:3],
        'recent_certificates': certificates[:3],
        'recent_payments': payments[:3],
        'stats': {
            'total_events': total_events,
            'total_certs': total_certs,
            'upcoming_events': upcoming_events,
        }
    }
    return render(request, 'peserta/dashboard.html', context)


@login_required
def my_events(request):
    """List of all events user registered for."""
    registrations = EventRegistration.objects.filter(user=request.user).order_by('-registration_date')
    return render(request, 'peserta/my_events.html', {'registrations': registrations})


@login_required
def certificates(request):
    """List of all certificates."""
    certificates = Certificate.objects.filter(user=request.user).order_by('-issued_date')
    return render(request, 'peserta/certificates.html', {'certificates': certificates})


@login_required
def claim_certificate(request, cert_id):
    """Logic to claim a certificate after attending event."""
    cert = get_object_or_404(Certificate, id=cert_id, user=request.user)
    
    # Check if eligible to claim (must have attended)
    if not cert.registration.attended:
        messages.error(request, 'Anda harus dikonfirmasi hadir oleh panitia untuk klaim sertifikat ini.')
        return redirect('peserta_certificates')
        
    if not cert.claimed:
        cert.claimed = True
        cert.claimed_date = timezone.now()
        cert.save()
        messages.success(request, f'Berhasil mengklaim sertifikat untuk {cert.event.title}!')
    
    return redirect('peserta_certificates')


@login_required
def payments(request):
    """Payment history."""
    payments = Payment.objects.filter(user=request.user).order_by('-payment_date')
    return render(request, 'peserta/payments.html', {'payments': payments})


@login_required
def profile(request):
    """Peserta profile page."""
    if request.method == 'POST':
        # Simple profile update logic
        user = request.user
        profile = user.profile
        
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        profile.phone = request.POST.get('phone', profile.phone)
        profile.institution = request.POST.get('institution', profile.institution)
        profile.bio = request.POST.get('bio', profile.bio)
        
        user.save()
        profile.save()
        messages.success(request, 'Profil berhasil diperbarui.')
        return redirect('peserta_profile')
        
    return render(request, 'peserta/profile.html')
