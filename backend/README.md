# Cara pakai docker

### 1. Install docker dengan mengikuti panduan dari situs resmi

https://docs.docker.com/desktop/

### 2. pull repository ini dan buka powershell/bash shell

```bash
git clone <repo-url>
cd simevent-web
```

### 3. pastikan docker terinstall dengan mengetik command

```bash
docker --version
docker compose version
```

### 4. compose docker dengan kode ini

```bash
docker compose up -d --build
```

note: untuk pertama kali akan memakan waktu lama karena harus mengunduh image dan menginstall depedensi. pastikan punya internet stabil dan kuota

### 5. Buat tabel dan akun admin

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

### 6. Buka browser dan akses link

- http://localhost:8000

untuk admin cukup tambahkan "/admin/" di belakang untuk akses admin

### Email undangan panitia

Undangan dari **Ketua Panitia → Pengaturan** dikirim otomatis lewat SMTP Gmail.
Isi `EMAIL_HOST_USER` dengan alamat pengirim dan `EMAIL_HOST_PASSWORD` dengan
app password Gmail di lingkungan backend, lalu restart backend. Jalankan migrasi
untuk menambahkan waktu pengiriman email terakhir:

```bash
docker compose exec backend python manage.py migrate
```

Email berisi pesan, akses event, dan tautan penerimaan yang berlaku tujuh hari.
Gunakan alamat web yang bisa diakses penerima; tautan mengikuti alamat saat
membuka aplikasi. Jika SMTP gagal, undangan tetap tersimpan dan bisa **Kirim ulang**
atau **Salin tautan**. Seed tidak mengirim email saat dijalankan.

### PERINTAH LAIN

| Perintah | Fungsi |
|---|---|
| `docker compose up -d` | Menyalakan semua service di latar belakang |
| `docker compose ps` | Melihat status service (`db` harus `healthy`) |
| `docker compose logs -f backend` | Melihat log backend secara langsung |
| `docker compose exec backend python manage.py <perintah>` | Menjalankan perintah Django (`migrate`, `makemigrations`, `shell`, dll.) |
| `docker compose exec backend bash` | Masuk ke dalam container backend |
| `docker compose down` | Mematikan container. **Data database tetap aman.** |
| `docker compose down -v` | Mematikan container **dan menghapus data database** |
| `docker compose up -d --build` | Membangun ulang image setelah kode atau dependency berubah |
| `docker compose up -d --force-recreate backend` | Membuat ulang container backend (wajib setelah mengubah `.env`) |

### Setelah mengubah kode backend

Kode backend disalin ke image saat build, jadi perubahan di laptop belum terlihat di container sampai image dibangun ulang:

```bash
docker compose up -d --build
```

Perubahan di folder `frontend/` langsung terlihat karena folder itu dipasang sebagai volume.

### Setelah mengubah `.env`

Container hanya membaca `.env` saat dibuat. `docker compose restart` tidak cukup, gunakan:

```bash
docker compose up -d --force-recreate backend
```

### Setelah menambah dependency Python

Tambahkan ke `backend/requirements.txt`, lalu jalankan `docker compose up -d --build`.

## Data yang tersimpan

Data contoh untuk demo dipusatkan di
[`backend/apps/events/seeds/demo.json`](backend/apps/events/seeds/demo.json).
Setelah migrasi, isi data demo dengan:

```bash
docker compose exec backend python manage.py seed_simevent_initial
```

Perintah ini memerlukan `DEBUG=True`. Panduan isi katalog, perilaku seed, dan
bagian yang masih memakai alur demo tersedia di
[`backend/apps/events/seeds/README.md`](backend/apps/events/seeds/README.md).

Docker Compose membuat dua volume bernama:

- `pgdata`: data PostgreSQL. Tetap ada selama kamu tidak memakai `down -v`.
- `media`: file upload dan QR code (`/app/media`).

Data ini hanya ada di laptop masing-masing. Yang dibagikan lewat git adalah struktur database lewat file migrasi Django, sehingga `migrate` menghasilkan tabel yang sama di mana pun. Setiap anggota tim memiliki akun admin dan datanya sendiri.
