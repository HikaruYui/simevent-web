from datetime import date

from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render


def beranda(request):
    return render(request, "index.html", {
        "halaman_aktif": "beranda",
        "events": [],        # ganti: Event.objects.all()[:4]
        "testimoni": [],     # ganti: Testimoni.objects.all()[:3]
        "kategori_list": [],
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


# ---------------------------------------------------------------- Jelajah
STATUS_CHOICES = [
    ("berlangsung", "Sedang Berlangsung"),
    ("akan_datang", "Akan Datang"),
    ("selesai", "Selesai"),
]
BIAYA_CHOICES = [("semua", "Semua"), ("gratis", "Gratis"), ("berbayar", "Berbayar")]

KATEGORI = {
    "webinar": "Webinar",
    "sosialisasi": "Sosialisasi",
    "seminar": "Seminar",
    "workshop": "Workshop",
    "konferensi": "Konferensi",
}

# Data contoh. Ganti dengan Event.objects.all() dari model kamu.
CONTOH_EVENTS = [
    {"pk": 1, "judul": "Webinar Karier di Era AI", "kategori_slug": "webinar",
     "tanggal": date(2026, 10, 11), "status": "berlangsung", "lokasi": "Live via Zoom",
     "penyelenggara": "Contoh Penyelenggara A", "harga": 0},
    {"pk": 2, "judul": "Sosialisasi Beasiswa", "kategori_slug": "sosialisasi",
     "tanggal": date(2026, 10, 15), "status": "akan_datang", "lokasi": "Aula Rektorat",
     "penyelenggara": "Contoh Penyelenggara B", "harga": 0},
    {"pk": 3, "judul": "Seminar Nasional Teknologi", "kategori_slug": "seminar",
     "tanggal": date(2026, 10, 18), "status": "berlangsung", "lokasi": "Auditorium Unmul, Samarinda",
     "penyelenggara": "Contoh Penyelenggara C", "harga": 50000},
    {"pk": 4, "judul": "Workshop Desain UI", "kategori_slug": "workshop",
     "tanggal": date(2026, 10, 25), "status": "akan_datang", "lokasi": "Lab Komputer",
     "penyelenggara": "Contoh Penyelenggara D", "harga": 75000},
]
for _e in CONTOH_EVENTS:
    _e["kategori"] = KATEGORI[_e["kategori_slug"]]


def jelajah(request):
    q = request.GET.get("q", "").strip()
    kategori = request.GET.get("kategori", "")
    biaya = request.GET.get("biaya", "semua")
    urut = request.GET.get("urut", "tanggal")
    status_aktif = request.GET.getlist("status") or ["berlangsung", "akan_datang"]

    kategori_list = [
        {"slug": s, "nama": n,
         "jumlah": sum(1 for e in CONTOH_EVENTS if e["kategori_slug"] == s)}
        for s, n in KATEGORI.items()
    ]

    events = [e for e in CONTOH_EVENTS if e["status"] in status_aktif]
    if kategori:
        events = [e for e in events if e["kategori_slug"] == kategori]
    if biaya == "gratis":
        events = [e for e in events if e["harga"] == 0]
    elif biaya == "berbayar":
        events = [e for e in events if e["harga"] > 0]
    if q:
        ql = q.lower()
        events = [e for e in events
                  if ql in (e["judul"] + e["lokasi"] + e["penyelenggara"]).lower()]
    events.sort(key=lambda e: e["harga"] if urut == "harga" else e["tanggal"])

    return render(request, "jelajah.html", {
        "halaman_aktif": "jelajah",
        "events": events, "q": q, "kategori": kategori, "kategori_list": kategori_list,
        "biaya": biaya, "biaya_choices": BIAYA_CHOICES,
        "urut": urut, "status_choices": STATUS_CHOICES, "status_aktif": status_aktif,
        "terdaftar_ids": [],
    })


# ---------------------------------------------------------------- Tentang
def tentang(request):
    return render(request, "tentang.html", {"halaman_aktif": "tentang"})


# Halaman sementara supaya semua link tidak error sebelum halamannya dibuat.
def _placeholder(nama):
    def view(request, *args, **kwargs):
        return render(request, "index.html", {"halaman_aktif": nama})
    return view


bantuan = _placeholder("bantuan")
daftar = _placeholder("daftar")
lupa_password = _placeholder("lupa_password")
buat_event = _placeholder("buat_event")
detail_event = _placeholder("detail_event")
peserta_event = _placeholder("peserta_event")