# SIMEVENT API Reference

Dokumentasi endpoint SIMEVENT untuk pengelolaan akun, kerja sama, event, registrasi peserta, tiket, presensi, feedback, statistik, dan achievement.

## Base URL

Contoh alamat server untuk pengembangan lokal:

```text
http://127.0.0.1:8000
```

Seluruh path endpoint pada dokumentasi ini ditambahkan setelah base URL.

Contoh:

```text
http://127.0.0.1:8000/accounts/profile/
```

Sesuaikan base URL dengan alamat server yang digunakan. Gunakan garis miring `/` pada akhir endpoint sesuai dokumentasi.

## Status Dokumentasi

Dokumentasi disusun berdasarkan kode backend yang diberikan.

Contoh respons berhasil mengikuti struktur respons pada kode. Data akun dan nilai token dalam contoh merupakan ilustrasi. Endpoint belum diuji langsung ke server aplikasi.

## Resource

| Resource | Deskripsi |
| --- | --- |
| Accounts | Pendaftaran akun, autentikasi, dan profil pengguna. |
| Partnerships | Proposal kerja sama. |
| Events | Informasi dan pengelolaan event. |
| Registrations | Pendaftaran peserta, tiket, akses meeting, presensi, feedback, dan statistik. |
| Achievements | Achievement, kebijakan reward, dan diskon. |

## Autentikasi dan CSRF

API akun menggunakan session Django.

Setelah login berhasil, server menyimpan status autentikasi melalui session. Klien perlu menyimpan cookie session dari server dan mengirimkannya pada request berikutnya.

Untuk request POST, klien perlu mengirim:

- Cookie CSRF yang diberikan server.
- Token CSRF melalui header `X-CSRFToken`, atau field form `csrfmiddlewaretoken`.

Urutan penggunaan:

1. Panggil `GET /accounts/csrf/`.
2. Simpan cookie dari server dan nilai `csrf_token` dari respons.
3. Kirim request login dengan cookie dan token tersebut.
4. Simpan cookie terbaru setelah login.
5. Gunakan cookie session untuk mengakses endpoint yang memerlukan login.
6. Ambil token CSRF kembali sebelum request POST berikutnya karena login merotasi token CSRF.

Gunakan host yang konsisten. Cookie untuk `localhost` dan `127.0.0.1` dianggap berbeda.

Pada konfigurasi backend yang diberikan, cookie session dan CSRF memakai atribut Secure ketika `DEBUG` bernilai false. Contoh HTTP lokal memerlukan konfigurasi pengembangan yang sesuai; gunakan HTTPS pada lingkungan dengan cookie Secure.

## Format Request

Endpoint POST pada resource Accounts membaca data form.

Gunakan:

```http
Content-Type: application/x-www-form-urlencoded
```

Mengirim raw JSON tidak mengisi field `request.POST` yang digunakan oleh endpoint ini.

## Format Error

Error validasi pada register dan login menggunakan struktur:

```json
{
  "errors": {
    "nama_field": [
      {
        "message": "Pesan kesalahan",
        "code": "kode_kesalahan"
      }
    ]
  }
}
```

Kesalahan yang tidak terkait dengan satu field dapat menggunakan key `__all__`.

Respons dari middleware atau pembatasan method tidak selalu berupa JSON. Contohnya, kegagalan CSRF dapat menghasilkan halaman HTML.

---

# Resource: Accounts

Resource Accounts menyediakan endpoint pendaftaran akun, login, logout, pengambilan profil, dan pengambilan token CSRF.

## Methods

| Method | HTTP Request | Deskripsi |
| --- | --- | --- |
| accounts.csrf | `GET /accounts/csrf/` | Mengambil token CSRF. |
| accounts.register | `POST /accounts/register/` | Membuat akun pengguna. |
| accounts.login | `POST /accounts/login/` | Melakukan autentikasi dan membuat session login. |
| accounts.logout | `POST /accounts/logout/` | Mengakhiri session login. |
| accounts.profile | `GET /accounts/profile/` | Mengambil profil pengguna yang sedang login. |

---

## Method: accounts.csrf

Mengambil token CSRF untuk digunakan pada request POST.

Server juga menetapkan atau memperbarui cookie CSRF.

### HTTP Request

```http
GET /accounts/csrf/
```

### Authentication

Tidak memerlukan login.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Tidak ada.

### Response Body

Jika berhasil, server mengembalikan status `200 OK` dengan struktur:

```json
{
  "csrf_token": "<token_dari_server>"
}
```

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| csrf_token | string | Token yang dapat dikirim melalui header `X-CSRFToken` atau field form `csrfmiddlewaretoken`. |

Nilai `<token_dari_server>` merupakan placeholder. Gunakan nilai sebenarnya dari respons.

Token pada respons dan cookie CSRF dapat memiliki bentuk yang berbeda. Simpan cookie yang diberikan server dan gunakan token dari body respons sesuai fungsinya.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 405 Method Not Allowed | Request menggunakan method selain GET, setelah melewati pemeriksaan middleware yang berlaku. |

---

## Method: accounts.register

Membuat akun pengguna dengan email dan password.

Endpoint ini tidak menerima pengaturan role dari pengguna dan tidak otomatis melakukan login setelah pendaftaran berhasil.

### HTTP Request

```http
POST /accounts/register/
```

### Authentication

Tidak memerlukan login.

Memerlukan cookie dan token CSRF yang valid.

### Request Headers

| Header | Nilai | Deskripsi |
| --- | --- | --- |
| Content-Type | `application/x-www-form-urlencoded` | Format body request. |
| X-CSRFToken | Token CSRF | Wajib jika token tidak dikirim melalui field form `csrfmiddlewaretoken`. |

Cookie CSRF dari server harus ikut dikirim.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| email | string | Ya | Alamat email yang valid dan belum terdaftar. |
| first_name | string | Tidak | Nama depan pengguna. |
| last_name | string | Tidak | Nama belakang pengguna. |
| password1 | string | Ya | Password akun baru. |
| password2 | string | Ya | Konfirmasi password; harus sama dengan `password1`. |

Email dinormalisasi menjadi huruf kecil dan dibersihkan dari spasi di awal serta akhir sebelum disimpan.

Validasi password mengikuti konfigurasi backend:

- Minimal 12 karakter.
- Tidak seluruhnya berupa angka.
- Tidak termasuk password yang terlalu umum.
- Tidak terlalu mirip dengan informasi pengguna.

### Request Example

Contoh body dengan nilai ilustrasi:

```text
email=peserta%40example.com&first_name=Budi&last_name=Santoso&password1=Contoh%21SandiAcara2026&password2=Contoh%21SandiAcara2026
```

### Response Body

Jika berhasil, server mengembalikan status `201 Created`:

```json
{
  "registered": true
}
```

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| registered | boolean | Bernilai `true` ketika akun berhasil dibuat. |

Respons tidak memuat profil pengguna atau status login. Pengguna perlu melakukan login melalui endpoint `accounts.login`.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Validasi gagal, misalnya email sudah terdaftar, password tidak memenuhi persyaratan, atau konfirmasi password berbeda. |
| 403 Forbidden | Pemeriksaan CSRF gagal. |
| 405 Method Not Allowed | Request menggunakan method selain POST, setelah melewati pemeriksaan middleware yang berlaku. |

Contoh error ketika email terdeteksi sudah terdaftar pada validasi form:

```json
{
  "errors": {
    "email": [
      {
        "message": "Email ini sudah terdaftar.",
        "code": "duplicate_email"
      }
    ]
  }
}
```

Error lain mengikuti field dan jenis validasi yang gagal.

---

## Method: accounts.login

Melakukan autentikasi menggunakan email dan password.

Jika berhasil, server membuat session pengguna.

### HTTP Request

```http
POST /accounts/login/
```

### Authentication

Tidak memerlukan login sebelumnya.

Memerlukan cookie dan token CSRF yang valid.

### Request Headers

| Header | Nilai | Deskripsi |
| --- | --- | --- |
| Content-Type | `application/x-www-form-urlencoded` | Format body request. |
| X-CSRFToken | Token CSRF | Wajib jika token tidak dikirim melalui field form `csrfmiddlewaretoken`. |

Cookie CSRF dari server harus ikut dikirim.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| email | string | Ya | Email valid milik akun terdaftar; maksimal 254 karakter pada form login. |
| password | string | Ya | Password akun pengguna. |

### Request Example

```text
email=peserta%40example.com&password=Contoh%21SandiAcara2026
```

### Response Body

Jika berhasil, server mengembalikan status `200 OK`:

```json
{
  "authenticated": true
}
```

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| authenticated | boolean | Bernilai `true` ketika autentikasi berhasil. |

Server juga menetapkan cookie session. Simpan cookie tersebut untuk request berikutnya.

Login merotasi token CSRF. Ambil token kembali melalui `accounts.csrf` sebelum mengirim request POST berikutnya.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Input tidak valid atau autentikasi ditolak. |
| 403 Forbidden | Pemeriksaan CSRF gagal. |
| 405 Method Not Allowed | Request menggunakan method selain POST, setelah melewati pemeriksaan middleware yang berlaku. |

Contoh ilustrasi struktur error autentikasi:

```json
{
  "errors": {
    "__all__": [
      {
        "message": "<pesan_penolakan_autentikasi>",
        "code": "invalid_login"
      }
    ]
  }
}
```

Teks pesan aktual mengikuti form autentikasi dan bahasa aplikasi.

Form internal menggunakan nama field `username` untuk menampung email. Karena itu, sebagian error validasi email dapat muncul di key `username`, meskipun nama field pada request tetap `email`.

---

## Method: accounts.logout

Mengakhiri session login pengguna.

### HTTP Request

```http
POST /accounts/logout/
```

### Authentication

Kirim cookie session untuk mengakhiri session yang sedang digunakan.

Endpoint tidak mewajibkan pengguna sudah login. Request tanpa session login juga dapat menghasilkan respons berhasil, selama pemeriksaan CSRF terpenuhi.

### Request Headers

| Header | Nilai | Deskripsi |
| --- | --- | --- |
| X-CSRFToken | Token CSRF | Wajib jika token tidak dikirim melalui field form `csrfmiddlewaretoken`. |

Kirim cookie yang diperlukan, termasuk cookie CSRF dan cookie session jika pengguna sedang login.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Tidak memerlukan field bisnis.

Jika menggunakan header `X-CSRFToken`, body boleh kosong.

### Response Body

Jika berhasil, server mengembalikan status `200 OK`:

```json
{
  "authenticated": false
}
```

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| authenticated | boolean | Bernilai `false` setelah proses logout. |

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 403 Forbidden | Pemeriksaan CSRF gagal. |
| 405 Method Not Allowed | Request menggunakan method selain POST, setelah melewati pemeriksaan middleware yang berlaku. |

---

## Method: accounts.profile

Mengambil informasi profil pengguna berdasarkan session login yang dikirim.

### HTTP Request

```http
GET /accounts/profile/
```

### Authentication

Memerlukan session login yang valid.

Kirim cookie session dari server. Header CSRF tidak diperlukan untuk request GET ini.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Tidak ada.

### Response Body

Jika berhasil, server mengembalikan status `200 OK`.

Contoh respons dengan data ilustrasi:

```json
{
  "email": "peserta@example.com",
  "first_name": "Budi",
  "last_name": "Santoso",
  "role": "PARTICIPANT"
}
```

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| email | string | Email pengguna. |
| first_name | string | Nama depan; dapat berupa string kosong. |
| last_name | string | Nama belakang; dapat berupa string kosong. |
| role | string | Peran pengguna berdasarkan permission. |

Nilai `role`:

| Nilai | Deskripsi |
| --- | --- |
| ADMIN | Pengguna memiliki permission `accounts.manage_platform`. |
| ORGANIZER | Pengguna memiliki permission `accounts.access_organizer`, tanpa memenuhi kondisi ADMIN. |
| PARTICIPANT | Pengguna tidak memenuhi kondisi ADMIN atau ORGANIZER. |

Role ditentukan oleh backend dan tidak dikirim sebagai parameter request.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Pengguna belum login atau session tidak lagi valid. |
| 405 Method Not Allowed | Request menggunakan method selain GET, setelah melewati pemeriksaan middleware yang berlaku. |

Respons ketika pengguna belum login:

```json
{
  "error": "Anda harus login terlebih dahulu."
}
```
