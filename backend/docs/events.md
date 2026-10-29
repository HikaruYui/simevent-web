# Resource: Events

[Kembali ke API Reference](./SIMEVENT_API_Reference.md)

Resource Events menyediakan endpoint untuk melihat katalog event, membuat dan mengubah event, mengelola status, serta menghapus draft.

## Methods

| Method | HTTP Request | Deskripsi |
| --- | --- | --- |
| events.list | `GET /events/` | Mengambil daftar event publik. |
| events.get | `GET /events/{slug}/` | Mengambil detail event publik. |
| events.manage.list | `GET /events/manage/` | Mengambil daftar event yang dapat dikelola pengguna. |
| events.create | `POST /events/manage/` | Membuat event baru sebagai draft. |
| events.manage.get | `GET /events/manage/{pk}/` | Mengambil detail pengelolaan event, termasuk akses meeting dan riwayat status. |
| events.update | `POST /events/manage/{pk}/` | Mengubah isi event. |
| events.transition | `POST /events/manage/{pk}/{action}/` | Menjalankan perubahan status event. |
| events.delete | `POST /events/manage/{pk}/delete/` | Menghapus event yang masih berstatus DRAFT. |

`{pk}` adalah ID numerik event. `{slug}` adalah slug event yang dibuat oleh server.

Endpoint GET di atas juga mendukung HEAD dan OPTIONS. Endpoint khusus transisi dan penghapusan mendukung POST dan OPTIONS.

## Autentikasi dan Akses

Endpoint publik dapat diakses tanpa login:

- `GET /events/`
- `GET /events/{slug}/`

Endpoint pengelolaan memerlukan:

- Session login yang valid.
- Akun aktif.
- Permission `accounts.access_organizer` atau `accounts.manage_platform`.
- Permission tambahan sesuai operasi yang dijalankan.

Untuk membaca dan mengakses event yang sudah ada, pengguna juga memerlukan permission `events.view_event`.

Cakupan event yang dapat dikelola:

| Pengguna | Cakupan |
| --- | --- |
| Organizer | Event dengan `organizer` yang menunjuk ke pengguna tersebut. |
| Admin dengan `accounts.manage_platform` | Seluruh event, selama memiliki permission yang diperlukan. |

Jika pengguna lolos pemeriksaan akses Organizer/Admin tetapi tidak memiliki `events.view_event`, daftar pengelolaan dapat kosong dan akses terhadap event tertentu menghasilkan `404 Not Found`.

Event milik Organizer lain tidak dapat diakses oleh Organizer biasa melalui endpoint pengelolaan.

## Format Request

Endpoint POST membaca data form.

Tanpa unggahan file:

```http
Content-Type: application/x-www-form-urlencoded
```

Dengan unggahan banner:

```http
Content-Type: multipart/form-data; boundary=<boundary>
```

Saat memakai FormData atau fitur form-data pada klien HTTP, biarkan klien mengatur boundary.

Raw JSON tidak digunakan sebagai input form pada endpoint ini.

Seluruh request POST memerlukan cookie dan token CSRF yang valid. Token dapat dikirim melalui header:

```http
X-CSRFToken: <token_csrf>
```

Alternatifnya, kirim token melalui field form `csrfmiddlewaretoken`.

## Format Waktu

Contoh input waktu yang menyertakan zona waktu:

```text
2027-01-20T09:00:00+08:00
```

Konfigurasi aplikasi menggunakan zona waktu `Asia/Makassar`. Jika waktu dikirim tanpa zona waktu, form Django menafsirkannya berdasarkan zona waktu aktif aplikasi.

Respons waktu menggunakan string ISO 8601. Contoh:

```text
2027-01-20T01:00:00Z
```

Kedua contoh tersebut menunjukkan waktu yang sama.

Saat memakai URL encoded form, karakter `+` pada offset harus di-encode menjadi `%2B`. Klien form biasanya menangani encoding ini secara otomatis.

## Format Error

Error validasi pada resource Events menggunakan daftar pesan per field:

```json
{
  "errors": {
    "end_datetime": [
      "End must be after start."
    ]
  }
}
```

Error umum yang tidak terkait satu field menggunakan key `__all__`:

```json
{
  "errors": {
    "__all__": [
      "Only draft or revision events can be edited."
    ]
  }
}
```

Struktur error validasi Events berbeda dari Accounts: setiap item di dalam array merupakan string pesan.

Error autentikasi menggunakan:

```json
{
  "error": "Authentication required."
}
```

Ringkasan status error:

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Data atau perubahan status tidak memenuhi validasi. |
| 401 Unauthorized | Pengguna belum terautentikasi pada endpoint pengelolaan. |
| 403 Forbidden | Permission tidak mencukupi, akun tidak memenuhi persyaratan akses, atau pemeriksaan CSRF gagal. |
| 404 Not Found | Event tidak ditemukan, tidak termasuk cakupan akses, atau halaman pagination tidak valid. |
| 405 Method Not Allowed | Method HTTP tidak didukung setelah pemeriksaan akses dan middleware yang berlaku. |

Respons 403, 404, dan 405 tidak dijamin berbentuk JSON.

Pemeriksaan CSRF dilakukan oleh middleware. Request POST tanpa CSRF yang valid dapat menghasilkan 403 sebelum pemeriksaan login pada view.

---

# Representasi Data

## Event

Objek Event digunakan pada respons publik dan sebagian besar respons pengelolaan.

| Field | Tipe JSON | Deskripsi |
| --- | --- | --- |
| id | integer | ID event. |
| slug | string | Identitas URL event yang dibuat server. |
| title | string | Judul event. |
| description | string | Deskripsi event. |
| event_type | object | Jenis event, berisi `code` dan `name`. |
| delivery_mode | string | `OFFLINE`, `ONLINE`, atau `HYBRID`. |
| start_datetime | string | Waktu mulai dalam format ISO 8601. |
| end_datetime | string | Waktu selesai dalam format ISO 8601. |
| venue | string | Lokasi fisik event; dapat kosong. |
| capacity | integer | Kapasitas peserta. |
| price | string | Nilai desimal harga, misalnya `"0.00"`. |
| registration_open | string | Waktu pembukaan pendaftaran. |
| registration_close | string | Waktu penutupan pendaftaran. |
| banner_url | string atau null | URL/path banner dari storage; null jika tidak ada banner. |
| status | string | Status event. |
| is_ongoing | boolean | True jika status PUBLISHED dan waktu sekarang berada dalam rentang pelaksanaan event. |

`price` diserialisasi sebagai string agar nilai desimal tetap terjaga. Kode tidak menyertakan field mata uang pada respons ini.

`banner_url` tidak selalu berupa URL absolut; bentuknya mengikuti konfigurasi storage.

### Event Type

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| code | string | Kode jenis event. |
| name | string | Nama jenis event. |

Pada request pembuatan/perubahan, `event_type` menggunakan ID numerik. Pada respons, field ini menjadi objek berisi `code` dan `name`.

### Contoh Event

Data berikut merupakan ilustrasi:

```json
{
  "id": 12,
  "slug": "seminar-teknologi-0123456789abcdef0123456789abcdef",
  "title": "Seminar Teknologi",
  "description": "Seminar pengembangan aplikasi web.",
  "event_type": {
    "code": "SEMINAR",
    "name": "Seminar"
  },
  "delivery_mode": "OFFLINE",
  "start_datetime": "2027-01-20T01:00:00Z",
  "end_datetime": "2027-01-20T03:00:00Z",
  "venue": "Auditorium Kampus",
  "capacity": 100,
  "price": "0.00",
  "registration_open": "2027-01-01T00:00:00Z",
  "registration_close": "2027-01-19T09:00:00Z",
  "banner_url": null,
  "status": "PUBLISHED",
  "is_ongoing": false
}
```

Nilai `is_ongoing` bergantung pada waktu request.

## Managed Event

Respons detail pengelolaan memuat seluruh field Event dan tambahan berikut:

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| meeting_url | string | URL meeting privat; kosong jika tidak tersedia. |
| access_instructions | string | Petunjuk akses privat; kosong jika tidak tersedia. |
| transitions | array of object | Riwayat perubahan status, diurutkan berdasarkan waktu pencatatan lalu ID riwayat. |

Objek dalam `transitions`:

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| from_status | string | Status sebelum perubahan. |
| to_status | string | Status setelah perubahan. |
| reason | string | Alasan perubahan; dapat kosong. |
| created_at | string | Waktu perubahan dalam format ISO 8601. |

Field privat dan riwayat ini hanya ditambahkan pada respons `events.manage.get`.

Respons daftar pengelolaan, pembuatan, perubahan isi, dan perubahan status menggunakan objek Event biasa.

## Event List

Respons daftar menggunakan struktur:

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| results | array of Event | Event pada halaman saat ini. |
| page | integer | Nomor halaman saat ini. |
| pages | integer | Jumlah seluruh halaman. |

Ukuran halaman tetap: maksimal 20 event.

Contoh ketika tidak ada event:

```json
{
  "results": [],
  "page": 1,
  "pages": 1
}
```

## Event Status

| Nilai | Deskripsi |
| --- | --- |
| DRAFT | Draft awal yang dapat diedit. |
| SUBMITTED | Diajukan untuk peninjauan. |
| NEEDS_REVISION | Memerlukan perbaikan dan dapat diedit. |
| APPROVED | Disetujui dan belum dipublikasikan, atau dikembalikan dari publikasi melalui unpublish. |
| PUBLISHED | Dipublikasikan. |
| COMPLETED | Selesai. |
| REJECTED | Ditolak. |
| CANCELLED | Dibatalkan. |

Event publik mencakup status PUBLISHED dan COMPLETED.

Status tidak berubah otomatis hanya karena waktu event sudah lewat. Misalnya, perubahan menjadi COMPLETED dilakukan melalui action `complete`.

---

# Methods

## Method: events.list

Mengambil daftar event dengan status PUBLISHED atau COMPLETED.

Daftar diurutkan berdasarkan `start_datetime`, lalu ID event, secara menaik.

### HTTP Request

```http
GET /events/
```

### Authentication

Tidak memerlukan login.

### Path Parameters

Tidak ada.

### Query Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| page | integer atau `"last"` | Tidak | Nomor halaman, mulai dari 1. Default 1. Nilai `last` mengambil halaman terakhir. |

View ini tidak menerapkan filter pencarian, status, jenis event, ataupun ukuran halaman melalui query parameter.

### Request Body

Tidak ada.

### Request Example

```http
GET /events/?page=2
```

### Response Body

Status `200 OK`, berupa objek Event List.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 404 Not Found | Nilai halaman tidak valid atau halaman tidak tersedia. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: events.get

Mengambil detail event publik berdasarkan slug.

Event hanya dapat diakses jika berstatus PUBLISHED atau COMPLETED.

### HTTP Request

```http
GET /events/{slug}/
```

### Authentication

Tidak memerlukan login.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| slug | string | Ya | Slug event dari respons API. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Tidak ada.

### Response Body

Status `200 OK`, berupa objek Event.

Respons tidak memuat `meeting_url`, `access_instructions`, atau riwayat perubahan status.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 404 Not Found | Slug tidak ditemukan atau event bukan event publik. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: events.manage.list

Mengambil daftar event dalam cakupan pengelolaan pengguna.

Daftar mencakup seluruh status yang dapat diakses pengguna dan diurutkan berdasarkan `start_datetime`, lalu ID event, secara menaik.

### HTTP Request

```http
GET /events/manage/
```

### Authentication

Memerlukan session login, akses Organizer/Admin, dan permission `events.view_event` agar event dapat muncul dalam daftar.

Organizer melihat event miliknya sendiri. Admin dengan permission yang sesuai dapat melihat seluruh event.

### Path Parameters

Tidak ada.

### Query Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| page | integer atau `"last"` | Tidak | Nomor halaman. Default 1. Maksimal 20 event per halaman. |

View ini tidak menerapkan filter status atau pencarian melalui query parameter.

### Request Body

Tidak ada.

### Response Body

Status `200 OK`, berupa objek Event List.

Daftar ini tidak menyertakan informasi meeting privat.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Tidak memenuhi persyaratan akses Organizer/Admin. |
| 404 Not Found | Halaman tidak valid atau tidak tersedia. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: events.create

Membuat event baru dengan status DRAFT.

Slug dibuat oleh server dari judul dan UUID.

### HTTP Request

```http
POST /events/manage/
```

### Authentication

Memerlukan session login, akses Organizer/Admin, permission `events.add_event`, serta cookie dan token CSRF.

Jika dibuat oleh Organizer, pemilik event otomatis adalah pengguna tersebut.

Jika dibuat oleh Admin dengan `accounts.manage_platform`, field `organizer` wajib dikirim untuk memilih pemilik event.

Pemilik yang dipilih harus aktif dan memiliki permission `accounts.access_organizer`.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe input | Wajib | Deskripsi |
| --- | --- | --- | --- |
| title | string | Ya | Judul, maksimal 200 karakter. |
| description | string | Ya | Deskripsi, maksimal 20.000 karakter. |
| event_type | integer | Ya | ID jenis event yang aktif. |
| delivery_mode | string | Ya | OFFLINE, ONLINE, atau HYBRID. |
| start_datetime | datetime | Ya | Waktu mulai event. |
| end_datetime | datetime | Ya | Waktu selesai event. |
| venue | string | Tidak saat menyimpan draft | Lokasi fisik, maksimal 500 karakter. |
| capacity | integer | Ya | Kapasitas peserta, harus lebih besar dari 0. |
| price | decimal | Ya | Harga tidak negatif, maksimal 12 digit total dan 2 angka desimal. Kirim `0.00` untuk event gratis. |
| registration_open | datetime | Ya | Waktu pembukaan pendaftaran. |
| registration_close | datetime | Ya | Waktu penutupan pendaftaran. |
| banner | file | Tidak | Gambar JPEG, PNG, atau WebP. |
| remove_banner | boolean | Tidak | Mengosongkan banner; terutama digunakan saat update. |
| meeting_url | string | Tidak saat menyimpan draft | URL meeting HTTPS, maksimal 1.000 karakter. |
| access_instructions | string | Tidak | Petunjuk akses privat, maksimal 5.000 karakter. |
| organizer | integer | Ya, khusus pembuatan oleh Admin | ID pemilik event yang aktif dan memiliki akses Organizer. |

Nilai boolean dapat dikirim sebagai `true` atau `false`. Untuk nilai false pada field opsional, field juga dapat dihilangkan.

`event_type` harus menggunakan ID yang sudah tersedia di database. Resource Events ini tidak menyediakan endpoint daftar EventType.

Field `id`, `slug`, `status`, dan `is_ongoing` ditentukan server.

### Validation Rules

- `end_datetime` harus setelah `start_datetime`.
- `registration_open` harus sebelum `registration_close`.
- `registration_close` tidak boleh setelah `start_datetime`.
- `capacity` harus lebih besar dari 0.
- `price` tidak boleh negatif.
- Jenis event harus aktif.
- Banner maksimal 5 MiB atau 5.242.880 byte.
- Lebar dan tinggi banner masing-masing tidak boleh melebihi 4.096 piksel.
- Tidak boleh mengirim banner baru sekaligus `remove_banner=true`.
- Jika diisi, `meeting_url` harus menggunakan HTTPS.

Draft dapat disimpan sebelum seluruh syarat pengajuan terpenuhi. Syarat tambahan diperiksa saat submit, approve, dan publish.

### Request Example

Contoh pasangan key-value pada form untuk pembuatan oleh Organizer:

| Key | Value |
| --- | --- |
| title | Seminar Teknologi |
| description | Seminar pengembangan aplikasi web. |
| event_type | 1 |
| delivery_mode | OFFLINE |
| start_datetime | 2027-01-20T09:00:00+08:00 |
| end_datetime | 2027-01-20T11:00:00+08:00 |
| venue | Auditorium Kampus |
| capacity | 100 |
| price | 0.00 |
| registration_open | 2027-01-01T08:00:00+08:00 |
| registration_close | 2027-01-19T17:00:00+08:00 |

ID jenis event dan tanggal di atas merupakan ilustrasi. Sesuaikan dengan data yang tersedia.

### Response Body

Status `201 Created`, berupa objek Event dengan:

```json
{
  "status": "DRAFT"
}
```

Potongan di atas hanya menyorot field status. Respons sebenarnya memuat seluruh field Event.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Form tidak valid atau pemilik event tidak memenuhi persyaratan. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Permission tidak mencukupi atau pemeriksaan CSRF gagal. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: events.manage.get

Mengambil detail event untuk pengelolaan, termasuk informasi meeting privat dan riwayat perubahan status.

### HTTP Request

```http
GET /events/manage/{pk}/
```

### Authentication

Memerlukan session login, akses Organizer/Admin, permission `events.view_event`, dan akses terhadap event tersebut.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID event. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Tidak ada.

### Response Body

Status `200 OK`, berupa objek Managed Event.

Selain seluruh field Event, respons menyertakan field tambahan seperti contoh berikut:

```json
{
  "meeting_url": "https://meeting.example.com/ruang-seminar",
  "access_instructions": "Masuk 10 menit sebelum acara.",
  "transitions": [
    {
      "from_status": "DRAFT",
      "to_status": "SUBMITTED",
      "reason": "",
      "created_at": "2027-01-02T02:00:00Z"
    }
  ]
}
```

Contoh di atas hanya menampilkan field tambahan. Data dan URL merupakan ilustrasi.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Tidak memenuhi persyaratan akses Organizer/Admin. |
| 404 Not Found | Event tidak ditemukan atau tidak termasuk cakupan pengelolaan pengguna. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: events.update

Mengubah isi event yang berstatus DRAFT atau NEEDS_REVISION.

### HTTP Request

```http
POST /events/manage/{pk}/
```

### Authentication

Memerlukan session login, akses Organizer/Admin, permission `events.view_event` dan `events.change_event`, akses terhadap event, serta cookie dan token CSRF.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID event yang akan diubah. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Menggunakan field Event Form yang dijelaskan pada `events.create`, kecuali `organizer`.

Kirim seluruh field wajib, meskipun hanya ingin mengubah satu nilai. Endpoint ini memproses form lengkap.

Perilaku field opsional:

| Field | Perilaku |
| --- | --- |
| venue | Jika dihilangkan atau dikosongkan, nilainya menjadi kosong. |
| meeting_url | Jika dihilangkan atau dikosongkan, URL meeting menjadi kosong. |
| access_instructions | Jika dihilangkan atau dikosongkan, petunjuk akses menjadi kosong. |
| banner | Banner lama dipertahankan jika tidak ada unggahan baru dan `remove_banner` tidak aktif. |
| remove_banner | Kirim `true` untuk menghapus banner dari event. |

Pemilik, slug, dan status tidak dapat diubah melalui form ini. Mengubah judul tidak membuat ulang slug.

### Validation Rules

Seluruh validasi field pada pembuatan event tetap berlaku.

Tambahan:

- Event hanya dapat diedit saat DRAFT atau NEEDS_REVISION.
- Kapasitas baru tidak boleh lebih kecil dari jumlah registrasi aktif.
- Banner baru dan `remove_banner=true` tidak boleh dikirim bersamaan.

### Response Body

Status `200 OK`, berupa objek Event setelah diperbarui.

Respons update tidak menyertakan `meeting_url`, `access_instructions`, atau `transitions`. Gunakan `events.manage.get` untuk membaca informasi tersebut.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Form tidak valid, status tidak dapat diedit, atau kapasitas lebih kecil dari jumlah registrasi aktif. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Permission tidak mencukupi atau pemeriksaan CSRF gagal. |
| 404 Not Found | Event tidak ditemukan atau di luar cakupan akses. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: events.transition

Menjalankan perubahan status berdasarkan action.

Setiap perubahan yang berhasil dicatat dalam riwayat event.

### HTTP Request

```http
POST /events/manage/{pk}/{action}/
```

### Authentication

Memerlukan session login, akses Organizer/Admin, permission `events.view_event`, akses terhadap event, permission action terkait, serta cookie dan token CSRF.

Action review dan publikasi juga memerlukan permission `accounts.manage_platform`.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID event. |
| action | string | Ya | Action dari tabel berikut; gunakan huruf kecil persis seperti yang tercantum. |

### Actions

| Action | Status awal yang diizinkan | Status tujuan | Permission action | Khusus Admin platform | Alasan wajib |
| --- | --- | --- | --- | --- | --- |
| submit | DRAFT, NEEDS_REVISION | SUBMITTED | `events.submit_event` | Tidak | Tidak |
| request_revision | SUBMITTED, APPROVED | NEEDS_REVISION | `events.review_event` | Ya | Ya |
| approve | SUBMITTED | APPROVED | Admin: `events.review_event`; ketua pemilik event: `events.submit_event` | Admin atau ketua pemilik event | Tidak |
| publish | APPROVED | PUBLISHED | `events.publish_event` | Ya | Tidak |
| unpublish | PUBLISHED | APPROVED | `events.publish_event` | Ya | Tidak |
| reject | SUBMITTED | REJECTED | `events.review_event` | Ya | Ya |
| complete | PUBLISHED | COMPLETED | `events.complete_event` | Tidak | Tidak |
| cancel | DRAFT, SUBMITTED, NEEDS_REVISION, APPROVED, PUBLISHED | CANCELLED | `events.cancel_event` | Tidak | Ya |

Kolom “Khusus Admin platform: Tidak” berarti Organizer dapat menjalankan action jika memiliki permission yang sesuai dan event berada dalam cakupan aksesnya.

Tidak ada action yang disediakan untuk keluar dari status COMPLETED, REJECTED, atau CANCELLED.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| reason | string | Kondisional | Alasan perubahan, maksimal 2.000 karakter. Wajib untuk request_revision, reject, dan cancel. |

Spasi di awal dan akhir alasan dibersihkan. Alasan yang hanya berisi spasi dianggap kosong.

### Validation Rules

Untuk `submit`, `approve`, dan `publish`:

- Data event harus valid.
- Pemilik event harus aktif dan memiliki permission `accounts.access_organizer`.
- Jenis event harus aktif.
- Waktu mulai event harus berada di masa depan.
- Harga harus `0.00`; event berbayar belum dapat diajukan karena pembayaran belum didukung.
- Event OFFLINE dan HYBRID harus memiliki venue.
- Event ONLINE dan HYBRID harus memiliki URL meeting HTTPS yang valid.

Aturan waktu untuk action lain:

| Action | Syarat |
| --- | --- |
| unpublish | Hanya sebelum waktu mulai event. |
| complete | Hanya pada atau setelah waktu selesai event. |
| cancel | Hanya sebelum waktu selesai event. |

### Request Examples

Mengajukan event:

```http
POST /events/manage/12/submit/
```

Body boleh kosong karena alasan tidak diwajibkan. Cookie dan token CSRF tetap harus dikirim.

Meminta revisi:

```http
POST /events/manage/12/request_revision/
Content-Type: application/x-www-form-urlencoded

reason=Lengkapi+lokasi+dan+deskripsi+acara.
```

Mempublikasikan event:

```http
POST /events/manage/12/publish/
```

### Response Body

Status `200 OK`, berupa objek Event dengan status terbaru.

Riwayat perubahan dapat dibaca melalui `events.manage.get`.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Action tidak dikenal, transisi tidak diizinkan dari status saat ini, alasan wajib tidak diisi, atau syarat event/waktu belum terpenuhi. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Permission action atau akses Admin platform tidak mencukupi, atau pemeriksaan CSRF gagal. |
| 404 Not Found | Event tidak ditemukan atau di luar cakupan akses. |
| 405 Method Not Allowed | Method tidak didukung. |

Contoh error transisi:

```json
{
  "errors": {
    "__all__": [
      "This transition is not allowed from the current state."
    ]
  }
}
```

Contoh error ketika harga belum memenuhi syarat pengajuan:

```json
{
  "errors": {
    "__all__": [
      "Paid events remain drafts until payment is supported."
    ]
  }
}
```

---

## Method: events.delete

Menghapus event yang masih berstatus DRAFT.

### HTTP Request

```http
POST /events/manage/{pk}/delete/
```

### Authentication

Memerlukan session login, akses Organizer/Admin, permission `events.view_event` dan `events.delete_event`, akses terhadap event, serta cookie dan token CSRF.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID event yang akan dihapus. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| confirm | boolean | Ya | Harus bernilai true untuk mengonfirmasi penghapusan. |

### Request Example

```http
POST /events/manage/12/delete/
Content-Type: application/x-www-form-urlencoded

confirm=true
```

### Validation Rules

- Event harus berstatus DRAFT.
- `confirm` harus bernilai true.
- Event dengan status NEEDS_REVISION maupun status lain tidak dapat dihapus melalui endpoint ini.

### Response Body

Jika berhasil, server mengembalikan status `200 OK`:

```json
{
  "deleted": true
}
```

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| deleted | boolean | Bernilai true ketika event berhasil dihapus. |

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Konfirmasi tidak valid atau event bukan DRAFT. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Permission tidak mencukupi atau pemeriksaan CSRF gagal. |
| 404 Not Found | Event tidak ditemukan atau di luar cakupan akses. |
| 405 Method Not Allowed | Method tidak didukung. |

Contoh error status:

```json
{
  "errors": {
    "__all__": [
      "Only an unsubmitted draft can be deleted."
    ]
  }
}
```
