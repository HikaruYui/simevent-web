# Fungsi file: Penanganan request HTTP, scope akses, dan respons untuk akun, autentikasi, dan hak akses.

from django.contrib.auth import login, logout
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST
from .forms import EmailAuthenticationForm, RegistrationForm
from .models import User


@never_cache
@require_GET
def csrf_token(request):
    return JsonResponse({
        "csrf_token": get_token(request)
    })

@never_cache
@sensitive_post_parameters("password1", "password2")
@require_POST
def register(request):
    form = RegistrationForm(request.POST)

    if form.is_valid():
        try:
            with transaction.atomic():
                form.save()

        except IntegrityError:
            email = form.cleaned_data["email"]

            if not User.objects.filter(
                email__iexact=email
            ).exists():
                raise

            form.add_error(
                "email",
                "Email ini sudah terdaftar.",
            )

        else:
            return JsonResponse(
                {"registered": True},
                status=201,
            )

    return JsonResponse(
        {"errors": form.errors.get_json_data()},
        status=400,
    )


@never_cache
@sensitive_post_parameters("password")
@require_POST
def sign_in(request):
    form = EmailAuthenticationForm(
        request,
        data={
            "username": request.POST.get("email", ""),
            "password": request.POST.get("password", ""),
        },
    )

    if not form.is_valid():
        return JsonResponse(
            {"errors": form.errors.get_json_data()},
            status=400,
        )

    login(request, form.get_user())

    return JsonResponse({
        "authenticated": True
    })


@never_cache
@require_POST
def sign_out(request):
    logout(request)

    return JsonResponse({
        "authenticated": False
    })


@never_cache
@require_GET
def profile(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Anda harus login terlebih dahulu."},
            status=401,
        )

    user = request.user

    return JsonResponse({
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
    })
