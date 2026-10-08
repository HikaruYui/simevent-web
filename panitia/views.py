from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from events.models import Event, EventRegistration, Payment
from django.db.models import Sum
from django.utils.text import slugify


@login_required
def dashboard(request):
    """Panitia dashboard."""
    # Hanya untuk panitia
    if hasattr(request.user, 'profile') and request.user.profile.role != 'panitia':
        return redirect('peserta_dashboard')
        
    my_events = Event.objects.filter(organizer=request.user).order_by('-date')
    
    # Hitung total pendapatan (dari event milik panitia ini)
    total_income = Payment.objects.filter(
        registration__event__organizer=request.user,
        status='success'
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Hitung total peserta dari seluruh event panitia
    total_participants = EventRegistration.objects.filter(
        event__organizer=request.user,
        payment_status__in=['paid', 'free']
    ).count()
    
    context = {
        'my_events': my_events[:5],
        'total_events_count': my_events.count(),
        'total_income': total_income,
        'total_participants': total_participants,
    }
    return render(request, 'panitia/dashboard.html', context)


@login_required
def manage_events(request):
    """List of events managed by this panitia."""
    events = Event.objects.filter(organizer=request.user).order_by('-date')
    return render(request, 'panitia/manage_events.html', {'events': events})


@login_required
def create_event(request):
    """Create a new event."""
    if request.method == 'POST':
        title = request.POST.get('title')
        category = request.POST.get('category')
        date_str = request.POST.get('date')
        
        # Simple slug generation (in production, ensure uniqueness)
        slug = slugify(title)
        
        # Create draft event
        Event.objects.create(
            title=title,
            slug=slug,
            category=category,
            date=date_str,
            organizer=request.user,
            organizer_name=request.user.get_full_name() or request.user.username,
            status='draft'
        )
        messages.success(request, 'Event baru berhasil dibuat (Draft).')
        return redirect('panitia_manage_events')
        
    return redirect('panitia_dashboard') # Simple modal submit


@login_required
def event_participants(request, event_id):
    """Manage participants for a specific event."""
    event = get_object_or_404(Event, id=event_id, organizer=request.user)
    registrations = EventRegistration.objects.filter(event=event).order_by('-registration_date')
    
    context = {
        'event': event,
        'registrations': registrations,
    }
    return render(request, 'panitia/participants.html', context)
