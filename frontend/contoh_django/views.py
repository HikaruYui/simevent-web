# Salin ke app Anda (mis. event/views.py). Data di bawah masih contoh; ganti dengan model Anda.
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render


def beranda(request):
    return render(request, "index.html", {
        "halaman_aktif": "beranda",
        "events": [],        # ganti: Event.objects.all()[:4]
        "testimoni": [],     # ganti: Testimoni.objects.all()[:3]
    })


def masuk(request):
    ctx = {"next": request.GET.get("next", "")}
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        user = authenticate(request, username=email, password=request.POST.get("password", ""))
        if user:
            login(request, user)
            return redirect(request.POST.get("next") or "beranda")
        ctx.update(error="Email atau kata sandi salah.", email=email)
    return render(request, "masuk.html", ctx)


# Halaman sementara supaya semua link navbar tidak error sebelum halamannya dibuat.
def _placeholder(nama):
    def view(request, *args, **kwargs):
        return render(request, "index.html", {"halaman_aktif": nama})
    return view

jelajah = _placeholder("jelajah")
tentang = _placeholder("tentang")
bantuan = _placeholder("bantuan")
daftar = _placeholder("daftar")
lupa_password = _placeholder("lupa_password")
buat_event = _placeholder("buat_event")
detail_event = _placeholder("detail_event")
