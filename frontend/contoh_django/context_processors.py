from apps.events.seeds import KATEGORI


def kategori(request):
    return {"kategori_list": [
        {"slug": "konferensi" if code == "CONFERENCE" else code.lower(),
         "nama": name, "jumlah": len(titles)}
        for code, (name, titles) in KATEGORI.items()
    ]}  # Contoh tampilan; integrasi jumlah dari DB dilakukan terpisah.
