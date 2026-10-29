# Fungsi file: Penanganan request HTTP, scope akses, dan respons untuk akun, autentikasi, dan hak akses.

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from .forms import EmailAuthenticationForm, ProfileForm, RegistrationForm
from .models import User


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (login_required): memeriksa autentikasi sebelum menjalankan view; tidak menambah pewarisan class.
@login_required(login_url="login_page")
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
def ktp_document(request):
    document = request.user.ktp_document
    if not document:
        raise Http404("Dokumen KTP tidak ditemukan.")

    try:
        file_handle = document.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("Dokumen KTP tidak ditemukan.")

    response = FileResponse(
        file_handle,
        as_attachment=False,
        filename=document.name.rsplit("/", 1)[-1],
        content_type="application/pdf",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_GET): membatasi pemanggilan view ke HTTP GET; tidak menambah pewarisan class.
@require_GET
def csrf_token(request):
    return JsonResponse({
        "csrf_token": get_token(request)
    })

# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (sensitive_post_parameters): menandai parameter POST sensitif agar disamarkan dalam laporan error; tidak menambah pewarisan class.
@sensitive_post_parameters("password1", "password2")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def register(request):
    form = RegistrationForm(request.POST)

    if form.is_valid():
        try:
            # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
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


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (sensitive_post_parameters): menandai parameter POST sensitif agar disamarkan dalam laporan error; tidak menambah pewarisan class.
@sensitive_post_parameters("password")
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
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


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_POST): membatasi pemanggilan view ke HTTP POST; tidak menambah pewarisan class.
@require_POST
def sign_out(request):
    logout(request)

    return JsonResponse({
        "authenticated": False
    })


# OOP — Decorator Python (never_cache): membungkus view agar respons tidak disimpan cache browser/proxy; tidak menambah pewarisan class.
@never_cache
# OOP — Decorator Python (require_http_methods): membatasi view ke daftar metode HTTP yang diberikan; tidak menambah pewarisan class.
@require_http_methods(["GET", "POST"])
def profile(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Anda harus login terlebih dahulu."},
            status=401,
        )

    user = request.user

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if not form.is_valid():
            return JsonResponse(
                {"errors": form.errors.get_json_data()},
                status=400,
            )
        user = form.save()

    return JsonResponse({
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.get_full_name(),
        "nim": user.nim,
        "prodi": user.prodi,
        "ktp_number": user.ktp_number,
        "gender": user.gender,
        "birth_place": user.birth_place,
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "address": user.address,
        "phone_number": user.phone_number,
        "profile_complete": user.profile_complete,
        "role": user.role,
    })
