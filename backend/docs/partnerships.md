# Resource: Partnerships

[Kembali ke API Reference](./SIMEVENT_API_Reference.md)

Resource Partnerships menyediakan endpoint untuk membuat, membaca, mengubah, mengajukan, dan menghapus draft proposal kerja sama.

Proposal digunakan oleh pengguna yang ingin memperoleh akses Organizer.

## Methods

| Method | HTTP Request | Deskripsi |
| --- | --- | --- |
| partnerships.proposals.list | `GET /partnerships/proposals/` | Mengambil daftar proposal milik pengguna. |
| partnerships.proposals.create | `POST /partnerships/proposals/` | Membuat draft proposal baru. |
| partnerships.proposals.get | `GET /partnerships/proposals/{pk}/` | Mengambil detail proposal beserta riwayat perubahan status. |
| partnerships.proposals.update | `POST /partnerships/proposals/{pk}/` | Mengubah isi proposal. |
| partnerships.proposals.submit | `POST /partnerships/proposals/{pk}/submit/` | Mengajukan proposal untuk ditinjau. |
| partnerships.proposals.delete | `POST /partnerships/proposals/{pk}/delete/` | Menghapus proposal yang masih berstatus DRAFT. |

`{pk}` adalah ID numerik proposal.

Endpoint daftar dan detail juga mendukung HEAD dan OPTIONS. Endpoint submit dan delete mendukung POST dan OPTIONS.

Keputusan APPROVED, NEEDS_REVISION, dan REJECTED dijalankan melalui action Django Admin. Resource API ini tidak menyediakan endpoint review.

## Autentikasi dan Akses

Seluruh endpoint memerlukan session login.

Cakupan akses selalu dibatasi pada proposal milik pengguna yang sedang login. Endpoint ini tidak memberikan akses lintas pengguna kepada Admin.

| Operasi | Persyaratan |
| --- | --- |
| Melihat daftar dan detail | Login; hanya proposal sendiri. |
| Membuat proposal | Akun aktif dan belum memiliki akses Organizer atau Admin platform. |
| Mengubah proposal | Akun aktif, pemilik proposal, dan belum memiliki akses Organizer atau Admin platform. |
| Mengajukan proposal | Akun aktif, pemilik proposal, dan belum memiliki akses Organizer atau Admin platform. |
| Menghapus draft | Akun aktif dan pemilik proposal. |

Pemeriksaan akses Organizer/Admin pada pembuatan, perubahan, dan pengajuan menggunakan permission:

- `accounts.access_organizer`
- `accounts.manage_platform`

Jika pengguna sudah memiliki salah satu permission tersebut, operasi create, update, dan submit ditolak dengan `400 Bad Request`.

Pengguna yang sudah menjadi Organizer tetap dapat membaca riwayat proposalnya sendiri. Penghapusan draft tidak menerapkan larangan berdasarkan permission Organizer/Admin, tetapi tetap memeriksa kepemilikan dan status DRAFT.

## Format Request

Endpoint POST membaca data form:

```http
Content-Type: application/x-www-form-urlencoded
```

Seluruh request POST memerlukan cookie dan token CSRF yang valid.

Token dapat dikirim melalui header:

```http
X-CSRFToken: <token_csrf>
```

Alternatifnya, kirim token melalui field form `csrfmiddlewaretoken`.

Endpoint proposal menerima informasi teks. Tidak ada field unggahan dokumen proposal pada form yang tersedia.

## Aturan Umum

- Satu pengguna hanya boleh memiliki satu proposal terbuka.
- Proposal terbuka adalah proposal berstatus DRAFT, SUBMITTED, atau NEEDS_REVISION.
- Proposal hanya dapat diedit saat DRAFT atau NEEDS_REVISION.
- Proposal hanya dapat diajukan saat DRAFT atau NEEDS_REVISION.
- Proposal hanya dapat dihapus saat DRAFT.
- Pemilik, status, dan timestamp ditentukan oleh server.
- Pengguna tidak dapat memilih pemilik proposal atau menetapkan status melalui body create/update.
- Proposal REJECTED tidak dapat diedit atau diajukan ulang melalui endpoint ini. Pengguna dapat membuat proposal baru jika masih memenuhi syarat.
- Persetujuan proposal memberikan akses Organizer kepada pemohon.

## Format Error

Error validasi dari proses proposal umumnya berbentuk:

```json
{
  "errors": {
    "proposal_text": [
      "<pesan_validasi>"
    ]
  }
}
```

Error aturan proses menggunakan key `__all__`:

```json
{
  "errors": {
    "__all__": [
      "You already have an open proposal."
    ]
  }
}
```

Khusus validasi field `confirm` pada penghapusan, formatnya menggunakan objek pesan dan kode:

```json
{
  "errors": {
    "confirm": [
      {
        "message": "<pesan_validasi>",
        "code": "required"
      }
    ]
  }
}
```

Teks dalam tanda `<...>` merupakan placeholder. Pesan aktual mengikuti validasi dan bahasa aplikasi.

Error ketika belum login:

```json
{
  "error": "Authentication required."
}
```

Ringkasan status:

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Input, status proposal, konfirmasi, atau persyaratan pemohon tidak valid. |
| 401 Unauthorized | Pengguna belum terautentikasi. |
| 403 Forbidden | Pemeriksaan CSRF atau persyaratan akses akun gagal. |
| 404 Not Found | Proposal tidak ditemukan atau bukan milik pengguna. |
| 405 Method Not Allowed | Method HTTP tidak didukung setelah pemeriksaan akses dan middleware yang berlaku. |

Respons 403, 404, dan 405 tidak dijamin berbentuk JSON.

CSRF diperiksa sebelum view dijalankan. Request POST tanpa CSRF yang valid dapat menghasilkan 403 sebelum pemeriksaan login.

---

# Representasi Data

## Proposal

| Field | Tipe JSON | Deskripsi |
| --- | --- | --- |
| id | integer | ID proposal. |
| organization_name | string | Nama organisasi atau komunitas. |
| contact_information | string | Informasi kontak pemohon atau organisasi. |
| proposal_text | string | Isi proposal kerja sama. |
| status | string | Status proposal. |
| submitted_at | string atau null | Waktu pengajuan terakhir dalam format ISO 8601; null pada draft yang belum diajukan. |
| created_at | string | Waktu pembuatan dalam format ISO 8601. |
| updated_at | string | Waktu perubahan terakhir dalam format ISO 8601. |

Respons Proposal tidak menyertakan identitas pemohon sebagai field tersendiri.

### Contoh Proposal

Data berikut merupakan ilustrasi:

```json
{
  "id": 7,
  "organization_name": "Komunitas Teknologi Kampus",
  "contact_information": "panitia@example.com",
  "proposal_text": "Kami mengajukan kerja sama penyelenggaraan seminar teknologi untuk mahasiswa.",
  "status": "DRAFT",
  "submitted_at": null,
  "created_at": "2027-01-05T02:00:00Z",
  "updated_at": "2027-01-05T02:00:00Z"
}
```

## Proposal Detail

Detail proposal memuat seluruh field Proposal dan field tambahan:

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| reviews | array of object | Riwayat pengajuan dan keputusan review. |

Objek dalam `reviews`:

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| from_status | string | Status sebelum perubahan. |
| to_status | string | Status setelah perubahan. |
| reason | string | Alasan keputusan; dapat kosong. |
| created_at | string | Waktu pencatatan dalam format ISO 8601. |

Riwayat diurutkan berdasarkan waktu pencatatan, lalu ID riwayat, secara menaik.

Identitas reviewer dan catatan administrasi perubahan akses tidak disertakan dalam respons ini.

## Proposal List

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| results | array of Proposal | Proposal pada halaman saat ini. |
| page | integer | Nomor halaman yang dikembalikan. |
| pages | integer | Jumlah seluruh halaman. |

Maksimal 20 proposal per halaman.

Contoh daftar kosong:

```json
{
  "results": [],
  "page": 1,
  "pages": 1
}
```

## Proposal Status

| Status | Deskripsi | Termasuk proposal terbuka |
| --- | --- | --- |
| DRAFT | Draft yang belum diajukan. | Ya |
| SUBMITTED | Sudah diajukan dan menunggu peninjauan. | Ya |
| NEEDS_REVISION | Memerlukan perbaikan sebelum diajukan kembali. | Ya |
| APPROVED | Disetujui; akses Organizer diberikan melalui proses persetujuan. | Tidak |
| REJECTED | Ditolak. | Tidak |

## Perubahan Status

| Tindakan | Status awal | Status tujuan | Pelaksana |
| --- | --- | --- | --- |
| Membuat proposal | Belum ada | DRAFT | Pemohon melalui API create. |
| Mengajukan proposal | DRAFT | SUBMITTED | Pemohon melalui API submit. |
| Meminta revisi | SUBMITTED | NEEDS_REVISION | Admin melalui Django Admin. |
| Mengajukan ulang | NEEDS_REVISION | SUBMITTED | Pemohon melalui API submit. |
| Menyetujui | SUBMITTED | APPROVED | Admin melalui Django Admin. |
| Menolak | SUBMITTED | REJECTED | Admin melalui Django Admin. |

Mengedit isi proposal tidak mengubah status.

Setiap pengajuan, termasuk pengajuan ulang, memperbarui `submitted_at` dan menambahkan riwayat dengan status tujuan SUBMITTED.

Keputusan revisi dan penolakan memerlukan alasan. Pemohon dapat membaca alasan tersebut melalui detail proposal.

---

# Methods

## Method: partnerships.proposals.list

Mengambil daftar seluruh proposal milik pengguna yang sedang login.

Daftar diurutkan berdasarkan `created_at`, lalu ID proposal, secara menurun. Proposal terbaru berada di awal.

### HTTP Request

```http
GET /partnerships/proposals/
```

### Authentication

Memerlukan session login.

### Path Parameters

Tidak ada.

### Query Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| page | integer | Tidak | Nomor halaman. Default 1. Maksimal 20 proposal per halaman. |

Perilaku pagination:

- Jika `page` tidak dikirim, server mengembalikan halaman pertama.
- Nilai yang tidak dapat dibaca sebagai integer mengembalikan halaman pertama.
- Nilai lebih besar dari jumlah halaman mengembalikan halaman terakhir.
- Nilai 0 atau negatif juga mengembalikan halaman terakhir.
- Nilai teks `last` diperlakukan sebagai nilai non-integer dan mengembalikan halaman pertama.

Perilaku ini mengikuti penggunaan `Paginator.get_page()` pada endpoint.

Endpoint tidak menerapkan filter status, pencarian, atau ukuran halaman melalui query parameter.

### Request Body

Tidak ada.

### Request Example

```http
GET /partnerships/proposals/?page=2
```

### Response Body

Status `200 OK`, berupa objek Proposal List.

Field `reviews` tidak disertakan pada setiap item daftar.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Belum login. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: partnerships.proposals.create

Membuat proposal baru dengan status DRAFT.

Pemilik proposal otomatis diambil dari pengguna yang sedang login.

### HTTP Request

```http
POST /partnerships/proposals/
```

### Authentication

Memerlukan session login, akun aktif, serta cookie dan token CSRF.

Pengguna belum boleh memiliki permission `accounts.access_organizer` atau `accounts.manage_platform`.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| organization_name | string | Ya | Nama organisasi, maksimal 200 karakter. |
| contact_information | string | Ya | Informasi kontak, maksimal 500 karakter. |
| proposal_text | string | Ya | Isi proposal, maksimal 10.000 karakter. |

`contact_information` merupakan teks bebas. Backend tidak membatasinya sebagai satu alamat email atau satu nomor telepon.

Ketiga field tidak boleh kosong atau hanya berisi spasi.

Field pemilik, status, ID, dan timestamp tidak dapat ditetapkan melalui form ini.

### Validation Rules

- Pengguna harus memenuhi persyaratan pemohon.
- Pengguna tidak boleh memiliki proposal berstatus DRAFT, SUBMITTED, atau NEEDS_REVISION.
- Seluruh field wajib harus valid.

### Request Example

```http
POST /partnerships/proposals/
Content-Type: application/x-www-form-urlencoded
X-CSRFToken: <token_csrf>

organization_name=Komunitas+Teknologi+Kampus&contact_information=panitia%40example.com&proposal_text=Pengajuan+kerja+sama+seminar+teknologi.
```

Cookie session dan CSRF yang sesuai tetap harus dikirim.

### Response Body

Status `201 Created`, berupa objek Proposal.

Pada proposal baru:

- `status` bernilai `DRAFT`.
- `submitted_at` bernilai null.
- `created_at` dan `updated_at` diisi oleh server.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Field tidak valid, sudah memiliki proposal terbuka, atau sudah memiliki akses Organizer/Admin. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Pemeriksaan CSRF gagal atau akun tidak memenuhi persyaratan aktif pada proses perubahan. |
| 405 Method Not Allowed | Method tidak didukung. |

Contoh error proposal terbuka:

```json
{
  "errors": {
    "__all__": [
      "You already have an open proposal."
    ]
  }
}
```

Contoh error akses Organizer/Admin:

```json
{
  "errors": {
    "__all__": [
      "This account already has organizer or administrator access."
    ]
  }
}
```

---

## Method: partnerships.proposals.get

Mengambil detail proposal milik pengguna beserta riwayat pengajuan dan keputusan review.

### HTTP Request

```http
GET /partnerships/proposals/{pk}/
```

### Authentication

Memerlukan session login dan kepemilikan proposal.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID proposal. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Tidak ada.

### Response Body

Status `200 OK`, berupa objek Proposal Detail.

Contoh dengan data ilustrasi:

```json
{
  "id": 7,
  "organization_name": "Komunitas Teknologi Kampus",
  "contact_information": "panitia@example.com",
  "proposal_text": "Kami mengajukan kerja sama penyelenggaraan seminar teknologi untuk mahasiswa.",
  "status": "NEEDS_REVISION",
  "submitted_at": "2027-01-05T03:00:00Z",
  "created_at": "2027-01-05T02:00:00Z",
  "updated_at": "2027-01-06T01:00:00Z",
  "reviews": [
    {
      "from_status": "DRAFT",
      "to_status": "SUBMITTED",
      "reason": "",
      "created_at": "2027-01-05T03:00:00Z"
    },
    {
      "from_status": "SUBMITTED",
      "to_status": "NEEDS_REVISION",
      "reason": "Lengkapi susunan acara.",
      "created_at": "2027-01-06T01:00:00Z"
    }
  ]
}
```

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Belum login. |
| 404 Not Found | Proposal tidak ditemukan atau bukan milik pengguna. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: partnerships.proposals.update

Mengubah isi proposal yang berstatus DRAFT atau NEEDS_REVISION.

### HTTP Request

```http
POST /partnerships/proposals/{pk}/
```

### Authentication

Memerlukan session login, akun aktif, kepemilikan proposal, serta cookie dan token CSRF.

Pengguna belum boleh memiliki akses Organizer atau Admin platform.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID proposal yang akan diubah. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| organization_name | string | Ya | Nama organisasi, maksimal 200 karakter. |
| contact_information | string | Ya | Informasi kontak, maksimal 500 karakter. |
| proposal_text | string | Ya | Isi proposal, maksimal 10.000 karakter. |

Kirim ketiga field secara lengkap, termasuk nilai lama yang ingin dipertahankan.

Endpoint memproses form lengkap. Mengirim hanya satu field akan menyebabkan field wajib lainnya gagal validasi.

### Validation Rules

- Proposal harus milik pengguna.
- Status harus DRAFT atau NEEDS_REVISION.
- Pengguna harus memenuhi persyaratan pemohon.
- Ketiga field wajib harus valid.
- Pemilik dan status tidak dapat diubah melalui request ini.

### Response Body

Status `200 OK`, berupa objek Proposal setelah diperbarui.

Status tetap seperti sebelum perubahan. Untuk mengajukan hasil revisi, panggil endpoint submit.

Respons update tidak menyertakan `reviews`.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Field tidak valid, status tidak dapat diedit, atau pengguna sudah memiliki akses Organizer/Admin. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Pemeriksaan CSRF atau persyaratan akses akun gagal. |
| 404 Not Found | Proposal tidak ditemukan atau bukan milik pengguna. |
| 405 Method Not Allowed | Method tidak didukung. |

Contoh error status:

```json
{
  "errors": {
    "__all__": [
      "Only drafts and proposals needing revision can be edited."
    ]
  }
}
```

---

## Method: partnerships.proposals.submit

Mengajukan proposal untuk ditinjau Admin.

Endpoint ini juga digunakan untuk mengajukan ulang proposal yang berstatus NEEDS_REVISION.

### HTTP Request

```http
POST /partnerships/proposals/{pk}/submit/
```

### Authentication

Memerlukan session login, akun aktif, kepemilikan proposal, serta cookie dan token CSRF.

Pengguna belum boleh memiliki akses Organizer atau Admin platform.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID proposal yang akan diajukan. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

Tidak memerlukan field bisnis. Field `confirm` tidak diperlukan.

Jika CSRF dikirim melalui header, body boleh kosong.

Isi proposal yang diajukan berasal dari data yang sudah tersimpan. Untuk mengubah isi, panggil endpoint update terlebih dahulu.

### Validation Rules

- Proposal harus milik pengguna.
- Status harus DRAFT atau NEEDS_REVISION.
- Pengguna harus memenuhi persyaratan pemohon.
- Data proposal yang tersimpan harus valid.

### Request Example

```http
POST /partnerships/proposals/7/submit/
X-CSRFToken: <token_csrf>
```

Kirim cookie session dan CSRF yang sesuai.

### Response Body

Status `200 OK`, berupa objek Proposal dengan perubahan berikut:

- `status` menjadi `SUBMITTED`.
- `submitted_at` menjadi waktu pengajuan saat ini.
- `updated_at` diperbarui.
- Riwayat pengajuan ditambahkan.

Respons tidak menyertakan `reviews`. Gunakan endpoint detail untuk membaca riwayat.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Status tidak dapat diajukan, data tersimpan tidak valid, atau pengguna sudah memiliki akses Organizer/Admin. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Pemeriksaan CSRF atau persyaratan akses akun gagal. |
| 404 Not Found | Proposal tidak ditemukan atau bukan milik pengguna. |
| 405 Method Not Allowed | Method tidak didukung. |

Contoh ketika proposal sudah berstatus SUBMITTED:

```json
{
  "errors": {
    "__all__": [
      "This proposal cannot be submitted from its current state."
    ]
  }
}
```

---

## Method: partnerships.proposals.delete

Menghapus proposal yang masih berstatus DRAFT.

### HTTP Request

```http
POST /partnerships/proposals/{pk}/delete/
```

### Authentication

Memerlukan session login, akun aktif, kepemilikan proposal, serta cookie dan token CSRF.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| pk | integer | Ya | ID draft yang akan dihapus. |

### Query Parameters

Tidak ada parameter yang diperlukan.

### Request Body

| Field | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| confirm | boolean | Ya | Harus bernilai true untuk mengonfirmasi penghapusan. |

### Validation Rules

- Proposal harus milik pengguna.
- Status harus DRAFT.
- Konfirmasi harus bernilai true.
- Proposal NEEDS_REVISION dan status lain tidak dapat dihapus melalui endpoint ini.

### Request Example

```http
POST /partnerships/proposals/7/delete/
Content-Type: application/x-www-form-urlencoded
X-CSRFToken: <token_csrf>

confirm=true
```

Kirim cookie session dan CSRF yang sesuai.

### Response Body

Status `200 OK`:

```json
{
  "deleted": true
}
```

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| deleted | boolean | Bernilai true jika draft berhasil dihapus. |

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Konfirmasi tidak valid atau proposal bukan DRAFT. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Pemeriksaan CSRF atau persyaratan akses akun gagal. |
| 404 Not Found | Proposal tidak ditemukan atau bukan milik pengguna. |
| 405 Method Not Allowed | Method tidak didukung. |

Kepemilikan proposal diperiksa sebelum validasi konfirmasi. ID proposal milik pengguna lain menghasilkan 404, termasuk jika field `confirm` tidak dikirim.

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
