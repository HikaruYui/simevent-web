def kategori(request):
    data = [("konferensi", "Konferensi"), ("workshop", "Workshop"), ("seminar", "Seminar"),
            ("webinar", "Webinar"), ("sosialisasi", "Sosialisasi")]
    return {"kategori_list": [{"slug": s, "nama": n, "jumlah": 10} for s, n in data]}  # jumlah: ganti dari DB
