# Resource: Achievements

[Kembali ke API Reference](./SIMEVENT_API_Reference.md)

Resource Achievements menyediakan endpoint untuk membaca achievement pengguna, mengevaluasi ulang kelayakannya, mengelola kebijakan diskon event, dan menghitung preview diskon.

## Methods

| Method | HTTP Request | Deskripsi |
| --- | --- | --- |
| achievements.list | `GET /achievements/` | Mengambil achievement pengguna yang masih memenuhi syarat. |
| achievements.reconcile | `POST /achievements/reconcile/` | Mengevaluasi dan memperbarui achievement pengguna yang sedang login. |
| achievements.policy.get | `GET /achievements/events/{event_id}/policy/` | Membaca kebijakan diskon achievement pada event. |
| achievements.policy.update | `POST /achievements/events/{event_id}/policy/` | Membuat atau memperbarui kebijakan diskon event. |
| achievements.discount.get | `GET /achievements/events/{event_id}/discount/` | Menghitung preview diskon untuk pengguna yang sedang login. |

`{event_id}` adalah ID numerik event.

Endpoint GET juga mendukung HEAD dan OPTIONS. Endpoint reconcile mendukung POST dan OPTIONS.

Pengelolaan definisi Achievement dan Reward dilakukan melalui Django Admin. Resource API ini tidak menyediakan endpoint untuk membuat definisi achievement atau reward.

## Konsep

| Istilah | Deskripsi |
| --- | --- |
| Achievement | Definisi pencapaian, misalnya menghadiri sejumlah event tertentu. |
| User Achievement | Catatan pemberian achievement kepada pengguna. |
| Reward | Persentase diskon yang dikaitkan dengan satu achievement. |
| Event Reward Policy | Pengaturan apakah event menerima diskon achievement dan berapa batas maksimalnya. |
| Reconcile | Evaluasi ulang untuk memberikan, memperbarui, mencabut, atau mengaktifkan kembali achievement pengguna. |
| Discount Quote | Preview harga berdasarkan reward pengguna dan kebijakan event. |

Memiliki achievement tidak selalu berarti memiliki reward. Reward merupakan konfigurasi terpisah yang dapat diaktifkan atau dinonaktifkan.

## Autentikasi dan Akses

Seluruh endpoint memerlukan session login.

| Operasi | Persyaratan akses |
| --- | --- |
| Daftar achievement | Akun aktif; hanya achievement sendiri. |
| Reconcile | Akun aktif; hanya mengevaluasi pengguna yang sedang login. |
| Baca kebijakan event | Akun aktif, akses Organizer/Admin, `events.view_event`, dan event dalam cakupan pengelolaan. |
| Ubah kebijakan event | Seluruh syarat baca kebijakan, ditambah `events.change_event`. |
| Preview diskon | Akun aktif; event harus publik atau berada dalam cakupan pengelolaan pengguna. |

Cakupan pengelolaan event:

- Organizer melihat event miliknya sendiri.
- Admin dengan `accounts.manage_platform` dapat mengakses seluruh event.
- Permission `events.view_event` tetap diperlukan untuk cakupan pengelolaan.

Endpoint reconcile tidak menerima target pengguna lain. Mengirim `user_id` tidak mengubah pengguna yang dievaluasi, termasuk ketika pemanggil adalah Admin.

Preview diskon juga selalu menggunakan achievement milik pengguna yang sedang login.

## Format Request

Endpoint POST menggunakan form:

```http
Content-Type: application/x-www-form-urlencoded
```

Seluruh request POST memerlukan cookie dan token CSRF yang valid.

Kirim token melalui:

```http
X-CSRFToken: <token_csrf>
```

Alternatifnya, gunakan field form `csrfmiddlewaretoken`.

Pada endpoint update kebijakan, data dibaca dari `request.POST`. Raw JSON tidak digunakan sebagai input form.

## Pagination

Daftar achievement tidak menggunakan pagination.

Respons hanya memiliki field `results`. Tidak terdapat field `page` atau `pages`.

## Format Error

Error autentikasi:

```json
{
  "error": "Authentication required."
}
```

Error validasi kebijakan:

```json
{
  "errors": {
    "max_discount_percentage": [
      "Enter a positive discount cap."
    ]
  }
}
```

Error aturan proses:

```json
{
  "errors": {
    "__all__": [
      "Reward policy can only change in draft or revision."
    ]
  }
}
```

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Input kebijakan atau persyaratan preview diskon tidak valid. |
| 401 Unauthorized | Belum login. Pada daftar, reconcile, dan preview diskon, akun tidak aktif juga ditolak oleh pemeriksaan awal dengan status ini. |
| 403 Forbidden | Permission tidak mencukupi, pemeriksaan akses akun gagal, atau CSRF tidak valid. |
| 404 Not Found | Event tidak ditemukan atau di luar cakupan akses. |
| 405 Method Not Allowed | Method tidak didukung setelah pemeriksaan akses dan middleware yang berlaku. |

Endpoint kebijakan memakai pemeriksaan akses pengelolaan Events. Akun tidak aktif yang masih terbaca sebagai pengguna terautentikasi ditolak oleh pemeriksaan tersebut dengan 403.

Respons 403, 404, dan 405 tidak dijamin berbentuk JSON.

Pemeriksaan CSRF dilakukan sebelum view. Request POST tanpa CSRF yang valid dapat menghasilkan 403 sebelum pemeriksaan login.

---

# Representasi Data

## User Achievement

| Field | Tipe JSON | Deskripsi |
| --- | --- | --- |
| id | integer | ID definisi Achievement, bukan ID record pemberian kepada pengguna. |
| code | string | Kode unik achievement. |
| name | string | Nama achievement. |
| description | string | Deskripsi; dapat kosong. |
| scope | string | Nama jenis event yang dihitung, atau `"All event types"` jika berlaku untuk semua jenis. |
| required_count | integer | Jumlah event yang harus dipenuhi. |
| qualifying_count | integer | Jumlah event pengguna yang saat ini memenuhi syarat dalam scope tersebut. |
| awarded_at | string | Waktu pertama pemberian achievement, dalam format ISO 8601. |

Contoh dengan data ilustrasi:

```json
{
  "id": 3,
  "code": "seminar-hero",
  "name": "Seminar Hero",
  "description": "Mengikuti minimal dua seminar hingga selesai.",
  "scope": "Seminar",
  "required_count": 2,
  "qualifying_count": 3,
  "awarded_at": "2027-01-20T04:00:00Z"
}
```

`qualifying_count` pada respons dihitung dari kondisi registrasi dan kehadiran saat ini. Nilainya bukan sekadar menampilkan hitungan yang terakhir disimpan saat reconcile.

Persentase reward tidak disertakan pada objek ini.

## Reward Policy

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| accept_achievement_discount | boolean | Apakah event menerima diskon dari achievement. |
| max_discount_percentage | string decimal | Batas maksimal persentase diskon event. |

Contoh:

```json
{
  "accept_achievement_discount": true,
  "max_discount_percentage": "20.00"
}
```

Jika belum ada record kebijakan, respons menggunakan nilai default:

```json
{
  "accept_achievement_discount": false,
  "max_discount_percentage": "0.00"
}
```

Membaca nilai default tidak membuat record kebijakan baru.

## Discount Quote

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| original_price | string decimal | Harga event sebelum diskon. |
| discount_percentage | string decimal | Persentase reward setelah dibatasi oleh kebijakan event. |
| discount_amount | string decimal | Besaran potongan harga. |
| final_price | string decimal | Harga setelah potongan. |
| reward_id | integer atau null | ID reward yang dipilih; null jika tidak ada reward yang digunakan. |
| preview_only | boolean | Selalu true. Hasil hanya merupakan preview. |

Contoh ilustrasi untuk event draft berbayar yang diakses pengelolanya sendiri, dengan reward pengguna sebesar 15%:

```json
{
  "original_price": "199.99",
  "discount_percentage": "15.00",
  "discount_amount": "30.00",
  "final_price": "169.99",
  "reward_id": 5,
  "preview_only": true
}
```

Nilai harga tidak disertai field mata uang pada respons ini.

---

# Aturan Achievement dan Reward

## Kehadiran yang Dihitung

Event dihitung untuk achievement jika:

- Registrasi pengguna berstatus REGISTERED.
- Kehadiran berstatus PRESENT.
- Event berstatus COMPLETED.

Setiap event dihitung satu kali untuk pengguna tersebut.

Jika achievement memiliki jenis event tertentu, hanya event dengan jenis tersebut yang dihitung. Jika tidak, seluruh jenis event dihitung.

Registrasi tanpa kehadiran, kehadiran VOIDED, registrasi CANCELLED, dan event yang belum COMPLETED tidak memenuhi syarat.

## Kelayakan Achievement

Achievement dapat muncul dalam daftar jika:

- Record pemberian kepada pengguna sudah ada.
- Record pemberian tersebut aktif.
- Definisi achievement aktif.
- Jumlah event yang saat ini memenuhi syarat mencapai `required_count`.

GET daftar achievement tidak membuat record pemberian baru.

Pengguna yang sudah mencapai syarat tetapi belum memiliki record pemberian perlu menjalankan reconcile.

Jika kelayakan hilang, GET akan menyembunyikan achievement tersebut tanpa mengubah record tersimpan. Reconcile memperbarui status record agar sesuai dengan kondisi terbaru.

## Perilaku Reconcile

| Kondisi | Hasil |
| --- | --- |
| Memenuhi syarat dan belum memiliki record | Membuat pemberian achievement baru. |
| Memenuhi syarat dan record sudah aktif | Memperbarui hitungan tersimpan jika berubah. |
| Memenuhi syarat kembali dan record tidak aktif | Mengaktifkan kembali record yang sama dan mengosongkan waktu pencabutan. |
| Tidak lagi memenuhi syarat tetapi record masih aktif | Menonaktifkan record dan mencatat waktu pencabutan. |

Pengaktifan kembali mempertahankan waktu `awarded_at` pertama.

Reconcile berulang tidak membuat duplikasi pemberian untuk achievement yang sama.

## Pemilihan Reward

Preview diskon menggunakan aturan berikut:

1. Event harus memiliki kebijakan yang menerima diskon achievement.
2. Achievement pengguna harus sudah diberikan, aktif, dan masih memenuhi syarat saat request.
3. Definisi achievement dan reward harus aktif.
4. Pilih reward dengan persentase terbesar.
5. Jika persentase sama, pilih reward dengan ID terkecil.
6. Batasi persentasenya dengan `max_discount_percentage` event.

Reward tidak ditumpuk.

Scope jenis event pada achievement mengatur cara memperoleh achievement. Kode preview tidak mensyaratkan jenis event tujuan diskon sama dengan jenis event pada achievement.

GET preview tidak membuat atau mengaktifkan achievement. Jalankan reconcile jika record pemberian belum ada atau masih tidak aktif.

## Perhitungan Diskon

```text
discount_percentage = min(persentase_reward, batas_diskon_event)

discount_amount = original_price × discount_percentage / 100

final_price = original_price − discount_amount
```

`discount_amount` dibulatkan ke dua angka desimal menggunakan ROUND_HALF_UP.

Jika tidak ada kebijakan, diskon dinonaktifkan, atau tidak ada reward yang memenuhi syarat:

- `discount_percentage` bernilai `"0.00"`.
- `discount_amount` bernilai `"0.00"`.
- `final_price` sama dengan `original_price`.
- `reward_id` bernilai null.

Pada event gratis, reward tetap dapat terpilih dan memiliki persentase positif, tetapi potongan nominal serta harga akhir tetap nol.

## Batas Fitur Pembayaran

Preview diskon tidak:

- Melakukan pembayaran.
- Membuat registrasi.
- Memesan kursi.
- Mengubah harga event.
- Menghabiskan atau menandai reward sebagai sudah digunakan.

Hasil dihitung dari kondisi saat request dan dapat berubah jika achievement, reward, harga, atau kebijakan berubah.

Pada alur Events saat ini, event berbayar belum dapat diajukan dan dipublikasikan melalui workflow normal. Pendaftaran juga hanya menerima event gratis.

Preview untuk draft berbayar tetap dapat dihitung oleh pengguna yang memiliki akses pengelolaan event tersebut.

---

# Methods

## Method: achievements.list

Mengambil achievement pengguna yang sudah diberikan dan masih memenuhi syarat.

### HTTP Request

```http
GET /achievements/
```

### Authentication

Memerlukan session login dan akun aktif.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang digunakan.

Endpoint tidak menyediakan pagination, filter jenis event, atau pilihan target pengguna.

### Request Body

Tidak ada.

### Response Body

Status `200 OK`:

```json
{
  "results": [
    {
      "id": 3,
      "code": "seminar-hero",
      "name": "Seminar Hero",
      "description": "Mengikuti minimal dua seminar hingga selesai.",
      "scope": "Seminar",
      "required_count": 2,
      "qualifying_count": 3,
      "awarded_at": "2027-01-20T04:00:00Z"
    }
  ]
}
```

Data di atas merupakan ilustrasi.

| Field | Tipe | Deskripsi |
| --- | --- | --- |
| results | array of User Achievement | Achievement aktif yang masih memenuhi syarat. |

Daftar diurutkan berdasarkan waktu pemberian, lalu ID record pemberian, secara menurun.

Jika tidak ada hasil:

```json
{
  "results": []
}
```

Respons kosong dapat berarti belum memenuhi syarat, belum pernah reconcile, record pemberian tidak aktif, atau definisi achievement dinonaktifkan.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Belum login atau akun tidak aktif. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: achievements.reconcile

Mengevaluasi seluruh definisi achievement untuk pengguna yang sedang login dan memperbarui record pemberiannya.

### HTTP Request

```http
POST /achievements/reconcile/
```

### Authentication

Memerlukan session login, akun aktif, serta cookie dan token CSRF.

Tidak memerlukan akses Organizer atau Admin.

### Path Parameters

Tidak ada.

### Query Parameters

Tidak ada parameter yang digunakan.

### Request Body

Tidak memerlukan field bisnis atau field `confirm`.

Jika CSRF dikirim melalui header, body boleh kosong.

Target pengguna selalu berasal dari session. Field seperti `user_id`, `achievement_id`, dan `qualifying_count` tidak digunakan untuk mengatur evaluasi.

### Request Example

```http
POST /achievements/reconcile/
X-CSRFToken: <token_csrf>
```

Cookie session dan CSRF harus ikut dikirim.

### Response Body

Status `200 OK`, dengan struktur yang sama seperti `achievements.list`:

```json
{
  "results": []
}
```

Array berisi achievement yang masih memenuhi syarat setelah proses selesai. Contoh di atas menunjukkan tidak ada achievement yang memenuhi syarat.

Respons bukan daftar perubahan. Tidak ada field terpisah yang menghitung achievement baru, dicabut, atau diaktifkan kembali.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Belum login atau akun tidak aktif pada pemeriksaan awal. |
| 403 Forbidden | CSRF gagal atau akses akun tidak lagi valid saat evaluasi berlangsung. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: achievements.policy.get

Membaca kebijakan diskon achievement untuk satu event.

### HTTP Request

```http
GET /achievements/events/{event_id}/policy/
```

### Authentication

Memerlukan session login, akun aktif, akses Organizer/Admin, permission `events.view_event`, dan akses pengelolaan event tersebut.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| event_id | integer | Ya | ID event yang dapat dikelola. |

### Query Parameters

Tidak ada parameter yang digunakan.

### Request Body

Tidak ada.

### Response Body

Status `200 OK`, berupa objek Reward Policy.

Contoh:

```json
{
  "accept_achievement_discount": true,
  "max_discount_percentage": "20.00"
}
```

Jika event ditemukan tetapi belum memiliki kebijakan, endpoint tetap menghasilkan 200 dengan nilai default false dan `"0.00"`.

Pembacaan kebijakan tidak dibatasi hanya pada status DRAFT atau NEEDS_REVISION. Batas tersebut berlaku untuk perubahan kebijakan.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Akun atau akses Organizer/Admin tidak memenuhi persyaratan. |
| 404 Not Found | Event tidak ditemukan atau di luar cakupan pengelolaan. |
| 405 Method Not Allowed | Method tidak didukung. |

---

## Method: achievements.policy.update

Membuat kebijakan jika belum ada, atau memperbarui kebijakan yang sudah tersedia pada event.

### HTTP Request

```http
POST /achievements/events/{event_id}/policy/
```

### Authentication

Memerlukan session login, akun aktif, akses Organizer/Admin, permission `events.view_event` dan `events.change_event`, akses terhadap event, serta cookie dan token CSRF.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| event_id | integer | Ya | ID event yang akan diubah kebijakannya. |

### Query Parameters

Tidak ada parameter yang digunakan.

### Request Body

| Field | Tipe input | Wajib | Deskripsi |
| --- | --- | --- | --- |
| accept_achievement_discount | boolean | Tidak | True untuk mengaktifkan diskon. Jika dihilangkan, diproses sebagai false. |
| max_discount_percentage | decimal | Ya | Batas diskon, 0 sampai 100, dengan maksimal 2 angka desimal. |

Gunakan `true` atau `false` untuk field boolean.

Form diproses secara lengkap. Tidak mengirim `accept_achievement_discount` tidak mempertahankan nilai lama; nilainya menjadi false.

Field event, pemilik event, dan status event tidak dapat diubah melalui form ini.

### Validation Rules

- Event harus berstatus DRAFT atau NEEDS_REVISION.
- Jika diskon diaktifkan, batas harus lebih besar dari 0 dan maksimal 100.
- Jika diskon dinonaktifkan, batas harus 0.
- Batas diskon menerima maksimal 2 angka desimal.

### Request Example: Mengaktifkan

```http
POST /achievements/events/12/policy/
Content-Type: application/x-www-form-urlencoded
X-CSRFToken: <token_csrf>

accept_achievement_discount=true&max_discount_percentage=20.00
```

### Request Example: Menonaktifkan

```http
POST /achievements/events/12/policy/
Content-Type: application/x-www-form-urlencoded
X-CSRFToken: <token_csrf>

accept_achievement_discount=false&max_discount_percentage=0.00
```

Cookie session dan CSRF harus ikut dikirim.

### Response Body

Status `200 OK`, berupa objek Reward Policy.

Status 200 digunakan baik ketika membuat record kebijakan pertama maupun memperbarui record yang sudah ada.

Contoh:

```json
{
  "accept_achievement_discount": true,
  "max_discount_percentage": "20.00"
}
```

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Nilai form tidak valid atau status event tidak mengizinkan perubahan kebijakan. |
| 401 Unauthorized | Belum login. |
| 403 Forbidden | Permission tidak mencukupi, akun tidak memenuhi persyaratan, atau CSRF gagal. |
| 404 Not Found | Event tidak ditemukan atau di luar cakupan pengelolaan. |
| 405 Method Not Allowed | Method tidak didukung. |

Contoh diskon dinonaktifkan tetapi batas masih positif:

```json
{
  "errors": {
    "max_discount_percentage": [
      "Disabled policies must have a zero cap."
    ]
  }
}
```

Contoh status event tidak dapat diedit:

```json
{
  "errors": {
    "__all__": [
      "Reward policy can only change in draft or revision."
    ]
  }
}
```

---

## Method: achievements.discount.get

Menghitung preview diskon berdasarkan harga event, achievement pengguna, reward aktif, dan batas kebijakan event.

### HTTP Request

```http
GET /achievements/events/{event_id}/discount/
```

### Authentication

Memerlukan session login dan akun aktif.

Event harus termasuk salah satu cakupan:

- Event publik.
- Event yang dapat dikelola oleh pengguna.

Reward yang digunakan selalu milik pengguna yang sedang login. Pengelola tidak dapat meminta preview atas nama peserta lain melalui parameter request.

### Path Parameters

| Parameter | Tipe | Wajib | Deskripsi |
| --- | --- | --- | --- |
| event_id | integer | Ya | ID event tujuan preview. |

### Query Parameters

Tidak ada parameter yang digunakan.

Parameter seperti `price`, `percentage`, `reward_id`, atau `user_id` tidak mengubah perhitungan.

### Request Body

Tidak ada.

### Validation Rules

- Event harus berada dalam cakupan akses pengguna.
- Status COMPLETED, CANCELLED, dan REJECTED tidak menerima preview.
- Waktu mulai event harus berada di masa depan.

Status DRAFT, NEEDS_REVISION, SUBMITTED, dan APPROVED dapat dipreview oleh pengguna yang memiliki akses pengelolaan event tersebut.

Pengguna biasa tidak dapat mengakses draft melalui endpoint ini.

Preview tidak mensyaratkan pengguna sudah mendaftar atau periode pendaftaran sedang dibuka.

### Request Example

```http
GET /achievements/events/12/discount/
```

Kirim cookie session pengguna.

### Response Body

Status `200 OK`, berupa objek Discount Quote.

Contoh event gratis tanpa reward yang digunakan:

```json
{
  "original_price": "0.00",
  "discount_percentage": "0.00",
  "discount_amount": "0.00",
  "final_price": "0.00",
  "reward_id": null,
  "preview_only": true
}
```

Tidak memiliki reward bukan error. Server tetap mengembalikan preview dengan diskon nol.

### Error Responses

| Status | Deskripsi |
| --- | --- |
| 400 Bad Request | Event sudah dimulai atau statusnya tidak menerima preview. |
| 401 Unauthorized | Belum login atau akun tidak aktif pada pemeriksaan awal. |
| 403 Forbidden | Akun tidak lagi aktif saat pemeriksaan di service. |
| 404 Not Found | Event tidak ditemukan atau di luar cakupan akses. |
| 405 Method Not Allowed | Method tidak didukung. |

Pencarian dalam cakupan akses dilakukan sebelum pemeriksaan status.

Karena itu, event CANCELLED atau REJECTED dapat menghasilkan 404 bagi pengguna biasa, tetapi 400 bagi pengelola yang dapat mengakses event tersebut.

Contoh waktu mulai telah lewat:

```json
{
  "errors": {
    "__all__": [
      "Discount previews require an upcoming event."
    ]
  }
}
```
