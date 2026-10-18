# SIMEVENT API Reference

Dokumentasi API backend SIMEVENT untuk pengelolaan akun, proposal kerja sama, event, pendaftaran peserta, tiket, presensi, feedback, statistik, achievement, dan reward.

## Daftar Resource

| Resource | Deskripsi | Dokumentasi |
| --- | --- | --- |
| Accounts | Pendaftaran akun, login, logout, profil pengguna, dan token CSRF. | [Accounts](./accounts.md) |
| Events | Katalog event, pembuatan dan perubahan event, serta alur pengajuan dan publikasi. | [Events](./events.md) |
| Partnerships | Proposal kerja sama untuk memperoleh akses Organizer. | [Partnerships](./partnerships.md) |
| Registrations | Pendaftaran peserta, pembatalan, tiket, meeting, presensi, feedback, dan statistik. | [Registrations](./registrations.md) |
| Achievements | Achievement pengguna, evaluasi ulang, kebijakan reward, dan preview diskon. | [Achievements](./achievements.md) |

## Status Dokumentasi

Dokumentasi disusun berdasarkan kode sumber dalam arsip `backend.zip` yang ditinjau.

Endpoint, field, validasi, dan aturan akses dijelaskan berdasarkan implementasi tersebut. Endpoint belum diuji langsung ke server.

Data pengguna, ID, tanggal, URL meeting, token, dan nilai respons pada contoh merupakan ilustrasi.

Jika implementasi backend berubah, dokumentasi perlu diperbarui agar tetap sesuai.

## Base URL

Contoh server pengembangan lokal:

```text
http://127.0.0.1:8000
```

Gabungkan base URL dengan path endpoint.

Contoh:

```text
http://127.0.0.1:8000/accounts/profile/
```

Sesuaikan alamat dengan server yang digunakan.

Pada konfigurasi routing yang didokumentasikan, endpoint langsung menggunakan prefix resource, seperti `/accounts/` dan `/events/`, tanpa prefix `/api/` atau nomor versi.

Gunakan garis miring `/` pada akhir endpoint sesuai dokumentasi.

## Autentikasi

Backend menggunakan session Django.

Setelah login berhasil, server menetapkan cookie session. Klien harus menyimpan dan mengirimkan cookie tersebut pada request berikutnya yang memerlukan autentikasi.

Respons login:

```json
{
  "authenticated": true
}
```

Cookie session dikirim melalui mekanisme HTTP cookie dan tidak berada di dalam body JSON tersebut.

Detail endpoint autentikasi tersedia pada [Accounts](./accounts.md).

## CSRF

Request yang mengubah data menggunakan POST dan memerlukan perlindungan CSRF.

Ambil token melalui:

```http
GET /accounts/csrf/
```

Contoh bentuk respons:

```json
{
  "csrf_token": "<token_dari_server>"
}
```

Simpan cookie CSRF dari server, lalu kirim token melalui header:

```http
X-CSRFToken: <token_dari_server>
```

Alternatifnya, kirim melalui field form `csrfmiddlewaretoken`.

Token dan cookie CSRF yang sesuai harus dikirim bersama.

### Urutan Login

1. Panggil `GET /accounts/csrf/`.
2. Simpan cookie dan nilai `csrf_token`.
3. Kirim `POST /accounts/login/` dengan email, password, cookie, dan token CSRF.
4. Simpan cookie terbaru dari respons login.
5. Ambil token CSRF kembali sebelum request POST berikutnya karena login merotasi token.
6. Gunakan cookie session untuk mengakses endpoint yang memerlukan login.

Gunakan host yang konsisten. Cookie untuk `localhost` dan `127.0.0.1` dianggap berbeda.

Pada konfigurasi yang ditinjau, cookie session dan CSRF memiliki atribut Secure ketika `DEBUG` bernilai false. Gunakan HTTPS pada lingkungan tersebut; contoh HTTP lokal memerlukan konfigurasi pengembangan yang sesuai.

## Hak Akses

Hak akses ditentukan oleh permission, kepemilikan data, status akun, dan aturan masing-masing operasi.

| Peran | Gambaran akses |
| --- | --- |
| PARTICIPANT | Mengelola data milik sendiri, seperti registrasi, tiket, feedback, dan achievement. |
| ORGANIZER | Mengelola event milik sendiri sesuai permission yang diberikan. |
| ADMIN | Mengelola platform dan event sesuai permission yang diberikan. |

Nama role saja tidak menjamin seluruh operasi dapat dijalankan. Beberapa endpoint memerlukan permission tambahan.

Akses Admin juga tidak otomatis membuka endpoint pribadi milik pengguna lain. Contohnya, endpoint tiket sendiri tetap memeriksa kepemilikan registrasi.

Persyaratan lengkap dicantumkan pada dokumentasi setiap endpoint.

## Format Request

### Data Form

Sebagian besar endpoint POST membaca data dari form:

```http
Content-Type: application/x-www-form-urlencoded
```

Contoh body:

```text
email=peserta%40example.com&password=contoh-password
```

Raw JSON tidak digunakan sebagai input pada form endpoint yang didokumentasikan.

### Unggahan File

Pembuatan dan perubahan event dapat menerima banner melalui:

```http
Content-Type: multipart/form-data; boundary=<boundary>
```

Saat menggunakan FormData atau fitur form-data pada klien HTTP, biarkan klien mengatur boundary.

### Method untuk Perubahan Data

Implementasi menggunakan POST untuk sejumlah operasi yang mengubah data, termasuk:

- Mengubah isi event atau proposal.
- Membatalkan registrasi.
- Menghapus draft.
- Mengubah status event.
- Mengubah kebijakan reward.

Gunakan method yang tercantum pada setiap endpoint.

## Format Response

Sebagian besar respons berhasil menggunakan JSON.

Pengecualian utama adalah QR tiket:

```http
GET /registrations/{pk}/ticket/qr/
```

Endpoint tersebut mengembalikan gambar dengan:

```http
Content-Type: image/png
```

Format respons, field, dan status keberhasilan dijelaskan pada masing-masing resource.

### Nilai Desimal

Harga, besaran diskon, dan beberapa hasil perhitungan dikembalikan sebagai string desimal.

Contoh:

```json
{
  "price": "0.00"
}
```

Rata-rata rating dikembalikan sebagai number atau null. Periksa tipe field pada dokumentasi endpoint.

### Nilai Waktu

Respons waktu menggunakan format ISO 8601.

Contoh:

```text
2027-01-20T01:00:00Z
```

Konfigurasi aplikasi menggunakan zona waktu `Asia/Makassar`.

Untuk input waktu, sertakan zona waktu agar jelas:

```text
2027-01-20T09:00:00+08:00
```

Kedua contoh menunjukkan waktu yang sama.

Saat menggunakan URL encoded form, karakter `+` pada offset perlu di-encode menjadi `%2B`. Klien form umumnya menangani encoding secara otomatis.

## Parameter Identitas

Perhatikan objek yang dirujuk oleh setiap ID.

| Lokasi parameter | Identitas yang digunakan |
| --- | --- |
| `/events/{slug}/` | Slug event. |
| `/events/manage/{pk}/` | ID event. |
| `/partnerships/proposals/{pk}/` | ID proposal. |
| `/registrations/{pk}/...` | ID registrasi. |
| `/registrations/events/{event_id}/...` | ID event. |
| `/achievements/events/{event_id}/...` | ID event. |

Pada endpoint tiket, attendance, dan feedback di bawah `/registrations/{pk}/`, gunakan ID registrasi.

Jangan menggantinya dengan ID feedback, identifier tiket, atau ID attendance.

## Pagination

Beberapa endpoint daftar menggunakan struktur:

```json
{
  "results": [],
  "page": 1,
  "pages": 1
}
```

| Field | Deskripsi |
| --- | --- |
| results | Data pada halaman yang diminta. |
| page | Nomor halaman yang dikembalikan. |
| pages | Jumlah seluruh halaman. |

Ukuran halaman pada endpoint berpaginasi adalah maksimal 20 item.

Contoh:

```http
GET /events/?page=2
```

Perilaku nilai halaman tidak valid berbeda antarresource:

- Events dan daftar berpaginasi pada Registrations dapat menghasilkan 404.
- Daftar Partnerships menggunakan fallback ke halaman pertama atau terakhir.
- Daftar Achievements tidak menggunakan pagination.

Lihat aturan pagination pada dokumentasi resource terkait.

## Status HTTP

| Status | Penggunaan umum |
| --- | --- |
| 200 OK | Pembacaan atau perubahan berhasil. |
| 201 Created | Pembuatan data berhasil, seperti registrasi, event, atau feedback. |
| 400 Bad Request | Input atau aturan proses tidak terpenuhi. |
| 401 Unauthorized | Belum terautentikasi; beberapa endpoint juga menggunakannya untuk akun tidak aktif. |
| 403 Forbidden | Permission, akses akun, atau pemeriksaan CSRF gagal. |
| 404 Not Found | Objek tidak ditemukan, di luar cakupan akses, atau halaman tidak valid. |
| 405 Method Not Allowed | Method HTTP tidak didukung. |

Status keberhasilan tidak selalu dapat disimpulkan dari jenis operasi. Misalnya, pembuatan kebijakan reward pertama menghasilkan 200, sedangkan aktivasi ulang registrasi menghasilkan 201.

Pemeriksaan middleware dan akses dapat terjadi sebelum pemeriksaan method atau input.

## Struktur Error

Struktur error tidak sepenuhnya seragam antarresource.

Contoh error umum:

```json
{
  "error": "Authentication required."
}
```

Contoh validasi dengan daftar pesan:

```json
{
  "errors": {
    "__all__": [
      "You are already registered."
    ]
  }
}
```

Contoh validasi dengan pesan dan kode:

```json
{
  "errors": {
    "nama_field": [
      {
        "message": "<pesan_validasi>",
        "code": "<kode_validasi>"
      }
    ]
  }
}
```

Format setiap endpoint dijelaskan dalam resource masing-masing.

Respons dari middleware atau penanganan error Django dapat berupa HTML atau body kosong. Jangan mengasumsikan seluruh respons gagal adalah JSON.

## Alur Penggunaan

### Peserta

1. Membuat akun dan login melalui [Accounts](./accounts.md).
2. Melihat event publik melalui [Events](./events.md).
3. Mendaftar, mengambil tiket, dan mengakses meeting melalui [Registrations](./registrations.md).
4. Melihat status presensi setelah tiket dipindai pengelola.
5. Mengirim feedback setelah memenuhi syarat dan event berstatus COMPLETED.
6. Menjalankan reconcile dan membaca achievement melalui [Achievements](./achievements.md).

### Calon Organizer

1. Membuat draft proposal melalui [Partnerships](./partnerships.md).
2. Mengajukan proposal untuk ditinjau.
3. Membaca hasil review dan memperbaiki proposal jika diminta.
4. Memperoleh akses Organizer setelah proposal disetujui melalui proses administrasi.

### Pengelola Event

1. Membuat draft event melalui [Events](./events.md).
2. Melengkapi informasi event dan kebijakan reward jika digunakan.
3. Menjalankan alur submit, review, dan publikasi sesuai permission.
4. Membaca daftar peserta dan melakukan scan tiket melalui [Registrations](./registrations.md).
5. Menandai event selesai setelah waktu pelaksanaan berakhir.
6. Membaca feedback dan statistik event.

## Batas Fitur Saat Ini

- Pendaftaran hanya menerima event gratis.
- Workflow normal belum mengizinkan pengajuan dan publikasi event berbayar.
- Perhitungan diskon masih berupa preview dan tidak melakukan pembayaran.
- Review proposal dilakukan melalui Django Admin.
- Pengelolaan definisi Achievement dan Reward dilakukan melalui Django Admin.
- Daftar endpoint pada setiap resource menjadi acuan operasi API yang tersedia.
