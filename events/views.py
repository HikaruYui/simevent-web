from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Event


def event_list(request):
    """Browse/Jelajah events page with filters."""
    events = Event.objects.filter(status__in=['active', 'upcoming'])
    
    # Filter by category
    category = request.GET.get('category', '')
    if category:
        events = events.filter(category=category)
    
    # Filter by status
    status = request.GET.get('status', '')
    if status:
        events = events.filter(status=status)
    
    # Filter by format
    format_filter = request.GET.get('format', '')
    if format_filter:
        events = events.filter(format=format_filter)
    
    # Filter by price (free/paid)
    price_filter = request.GET.get('price', '')
    if price_filter == 'free':
        events = events.filter(price=0)
    elif price_filter == 'paid':
        events = events.filter(price__gt=0)
    
    # Search
    q = request.GET.get('q', '')
    if q:
        events = events.filter(title__icontains=q)
    
    # Sort
    sort = request.GET.get('sort', '-date')
    events = events.order_by(sort)
    
    # Pagination
    paginator = Paginator(events, 6)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # View mode (grid/list)
    view_mode = request.GET.get('view', 'grid')
    
    context = {
        'page_obj': page_obj,
        'category': category,
        'status': status,
        'format_filter': format_filter,
        'price_filter': price_filter,
        'q': q,
        'view_mode': view_mode,
        'total_events': events.count(),
        'categories': Event.CATEGORY_CHOICES,
    }
    return render(request, 'events/event_list.html', context)


def event_detail(request, slug):
    """Event detail page."""
    event = get_object_or_404(Event, slug=slug)
    is_registered = False
    
    if request.user.is_authenticated:
        is_registered = event.registrations.filter(user=request.user).exists()
    
    context = {
        'event': event,
        'is_registered': is_registered,
    }
    return render(request, 'events/event_detail.html', context)
