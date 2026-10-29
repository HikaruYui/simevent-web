# SIMEVENT — Alur Website dan Panduan Presentasi Demo

SIMEVENT menghubungkan peserta, panitia biasa, ketua panitia, dan admin dalam satu proses pengelolaan event: menyiapkan acara, memublikasikannya, menerima pendaftaran, mencatat kehadiran, lalu menyediakan hasil kegiatan bagi peserta.

Dokumen ini menjelaskan alur demo berdasarkan implementasi kode saat ini. Bagian **OOP di fitur ini** dapat dipakai saat presentasi untuk menghubungkan perilaku website dengan class, method, dan relasi yang menjalankannya.

## 1. Gambaran cara kerja website

**Alur utama:** Ketua panitia membuat event → event diajukan dan ditinjau → admin memublikasikan event → peserta mendaftar → panitia memverifikasi kehadiran → event diselesaikan → peserta mengisi feedback dan mengakses hasil kegiatan.

| Peran | Tanggung jawab | Halaman awal |
| --- | --- | --- |
| Peserta | Menemukan event, mendaftar, menggunakan tiket, memberi feedback, dan melihat sertifikat/pencapaian. | `/peserta/` |
| Panitia biasa | Membantu operasional event yang ditugaskan: daftar peserta, absensi, dokumentasi, dan unggahan sertifikat. | `/panitia_biasa/` |
| Ketua panitia | Menyiapkan event, mengelola tim, memantau peserta dan pendapatan, serta mengakhiri kegiatan. | `/ketua-panitia/` |
| Admin | Mengelola pengguna, meninjau dan memublikasikan event, serta mengawasi aktivitas platform. | `/admin-panel/` |

Pengunjung dapat membuka beranda dan Jelajah tanpa login. Setelah login, sistem mengarahkan pengguna berdasarkan hak aksesnya. Role bukan empat class pengguna yang berbeda: semuanya memakai model `User`, sedangkan perannya ditentukan melalui permission dan grup. Akun panitia biasa juga memiliki akses mode peserta.

**Narasi pembuka:** “Kami mendemokan satu perjalanan event dari dibuat penyelenggara sampai diikuti peserta. Setiap peran memiliki halaman dan kewenangan yang berbeda, tetapi bekerja pada data event dan pendaftaran yang saling terhubung.”

## 2. Alur peserta

### A. Membuat akun dan melengkapi profil

1. Buka beranda atau Jelajah, kemudian masuk atau daftar akun.
2. Buka **Profil Saya** dan lengkapi biodata yang diminta.
3. Setelah profil memenuhi persyaratan, peserta dapat melanjutkan pendaftaran event.

**OOP di fitur ini:**

- **Inheritance:** `User` mewarisi `AbstractUser`, sehingga autentikasi Django digunakan kembali dengan identitas login berupa email. `RegistrationForm` mewarisi `UserCreationForm`, sedangkan `ProfileForm` mewarisi `ModelForm`.
- **Polymorphism melalui hook:** `clean_email()` menambahkan validasi email dalam siklus validasi form Django. `User.save()` menyesuaikan penyimpanan dengan normalisasi email, lalu meneruskan ke induknya menggunakan `super()`.
- **Encapsulation dan property:** `User.role` dan `User.profile_complete` menyajikan hasil perhitungan melalui atribut baca. Pemanggil tidak perlu mengulang aturan pengecekan permission atau kelengkapan biodata.

Kode: [model akun](backend/apps/accounts/models.py), [form akun](backend/apps/accounts/forms.py).

### B. Memilih event dan mendaftar

1. Buka **Daftar Event** atau Jelajah, lalu lihat detail acara: jadwal, lokasi/mode, kuota, dan biaya.
2. Pilih event yang sudah dipublikasikan dan masih membuka pendaftaran.
3. Klik daftar. Sistem memeriksa profil, waktu pendaftaran, status event, dan sisa kuota.
4. Untuk event gratis yang memenuhi syarat, sistem menyimpan pendaftaran dan membuat tiket. Peserta dapat melihat event yang diikuti dari area peserta.

**OOP di fitur ini:**

- **Abstraction:** `RegistrationService.register()` menyediakan satu operasi pendaftaran. View tidak perlu mengerjakan sendiri validasi, penguncian kuota, dan penerbitan tiket.
- **Encapsulation:** service menyimpan identitas pelaku dalam `_actor_id` dan mengelompokkan aturan pendaftaran. Awalan `_` adalah konvensi internal Python, bukan private yang dipaksakan bahasa.
- **Association:** objek `Registration` menghubungkan `User` dan `Event`; `Ticket` terhubung ke pendaftaran. Ini relasi antarobjek, bukan pewarisan peserta menjadi event.
- **Decorator:** `@transaction.atomic` membungkus operasi database dalam transaksi agar perubahan terkait diproses sebagai satu kesatuan.

Kode: [service registrasi](backend/apps/registrations/services.py), [model registrasi dan tiket](backend/apps/registrations/models.py).

### C. Menggunakan tiket dan mencatat kehadiran

Peserta membuka QR tiket, lalu menunjukkan tiket tersebut kepada panitia saat acara berlangsung. Panitia memindai QR atau memasukkan identifier tiket melalui fasilitas input absensi. Kehadiran baru tercatat jika tiket, pendaftaran, akses petugas, dan waktu event valid.

**OOP di fitur ini:** `TicketQRView` memakai `TicketAccessMixin` untuk pemeriksaan akses yang digunakan kembali. Rantai `ParticipantAccessMixin → TicketAccessMixin → TicketQRView` menunjukkan **multilevel inheritance**, sedangkan penggabungan `TicketAccessMixin` dan `View` menunjukkan **multiple inheritance**. Pembuatan QR menggunakan buffer `BytesIO`; operasi penyimpanan gambar menerima objek file-like melalui **duck typing**.

Kode: [view tiket](backend/apps/registrations/views.py), [pembuatan QR](backend/apps/registrations/tickets.py).

### D. Feedback, dokumentasi, sertifikat, dan pencapaian

1. Setelah event berstatus selesai, peserta yang memiliki kehadiran sah dapat mengirim feedback satu kali.
2. Dokumentasi tersedia melalui pemeriksaan akses pendaftaran dan kesiapan dokumentasi event.
3. Peserta membuka **Sertifikat Saya** untuk melihat sertifikat yang tersedia.
4. Buka **Pencapaian** untuk melihat progres berdasarkan kehadiran pada event yang selesai.

Ada dua jalur sertifikat yang perlu dibedakan saat demo:

- **Sertifikat PDF berbasis template:** membutuhkan template aktif, event selesai dan sudah melewati waktu berakhir, kehadiran sah, feedback, serta pembayaran disetujui jika terdapat pembayaran.
- **Sertifikat unggahan panitia:** panitia mengunggah berkas untuk pendaftaran aktif dengan kehadiran sah. Unduhannya diperiksa berdasarkan kepemilikan pendaftaran dan keberadaan berkas; jalur ini tidak memakai seluruh prasyarat generator PDF.

**OOP di fitur ini:** `FeedbackService.submit()` mengabstraksikan validasi dan penyimpanan feedback. `RegistrationQuerySet.owned_by()` dan `with_documentation()` mengemas aturan pemilihan data. `AchievementService.evaluate()` mengemas evaluasi pemberian/pencabutan achievement, sedangkan static method `_counts_for()` membantu menghitung kehadiran. Halaman Pencapaian sendiri menghitung progres dari database; membuka halaman tidak sama dengan menjalankan rekonsiliasi assignment achievement.

Kode: [feedback](backend/apps/registrations/feedback.py), [queryset registrasi](backend/apps/registrations/models.py), [service achievement](backend/apps/achievements/services.py), [halaman peserta dan unduhan](backend/config/views.py).

## 3. Alur panitia biasa

1. Masuk ke **Mode Panitia**, lalu pilih event yang ditugaskan oleh pengelola.
2. Buka **Daftar Peserta** untuk melihat pendaftar pada event terpilih.
3. Buka **Scan & Input Absen**, lalu proses tiket peserta. Pemindaian ulang tiket yang sudah tercatat tidak menambah kehadiran kedua.
4. Buka **Dokumentasi Event** untuk menyimpan tautan dokumentasi sesuai akses event.
5. Buka **Sertifikat Peserta** untuk mengunggah atau mengganti berkas sertifikat peserta yang hadir. Tersedia pula tindakan menghapus unggahan.

**Narasi demo:** “Panitia biasa berfokus pada pelaksanaan acara. Penugasan menentukan event yang dapat dikerjakan, jadi panitia tidak otomatis memperoleh akses ke seluruh event.”

**OOP di fitur ini:**

- **Association:** `EventCommitteeAssignment` menghubungkan anggota panitia dengan event; `CommitteePreference` menyimpan pilihan event panitia.
- **Abstraction dan encapsulation:** `AttendanceService.scan()` mengelompokkan pemeriksaan tiket, lingkup event, jadwal, dan pencatatan kehadiran. Helper internal memisahkan aturan akses dari operasi publik service.
- **Multiple inheritance:** `TicketScanView(ParticipantAccessMixin, View)` menggabungkan pemeriksaan akses dengan mekanisme HTTP Django.
- **Duck typing:** unggahan sertifikat dibaca melalui `read()` dan posisi bacanya dikembalikan melalui `seek()`. Kode memakai kemampuan objek file, tanpa mensyaratkan satu class penyimpanan tertentu.

Kode: [model penugasan](backend/apps/events/models.py), [service absensi](backend/apps/registrations/attendance.py), [view scanner](backend/apps/registrations/attendance_views.py), [dashboard dan unggahan panitia](backend/config/views.py).

## 4. Alur ketua panitia

### A. Menyiapkan dan mengajukan event

1. Buka **Kelola Event** dan pilih **Event baru**.
2. Isi informasi acara, kategori, jadwal, periode pendaftaran, kuota, lokasi/mode, dan berkas pendukung.
3. Simpan sebagai draft, periksa isinya, lalu ajukan event.
4. Jika diminta revisi, perbaiki event dan ajukan kembali. Dalam skenario demo, admin menangani persetujuan dan publikasi.

Alur status utama: **DRAFT → SUBMITTED → APPROVED → PUBLISHED → COMPLETED**. Cabang lain mencakup **NEEDS_REVISION**, **REJECTED**, dan **CANCELLED**. Event yang disetujui belum otomatis tampil sebagai event publik; persetujuan dan publikasi merupakan tindakan berbeda.

**OOP di fitur ini:**

- **Abstraction:** `EventWorkflow.create()`, `update()`, dan `transition()` menjadi pintu masuk operasi event. Pemeriksaan izin, perpindahan status, dan pencatatan riwayat ditangani di dalam workflow.
- **Composition:** `EventForm` menyusun objek field, termasuk `BannerField` dan `ProposalField`, untuk menangani input.
- **Inheritance dan overriding:** `BannerField(ImageField)` dan `ProposalField(FileField)` menyediakan implementasi `to_python()` khusus; keduanya tetap memanggil perilaku induk melalui `super()`.
- **Multilevel inheritance:** `ModelForm → EventForm → AdminEventForm` memungkinkan form admin menggunakan kembali aturan form event sambil menambahkan pilihan organizer.
- **Polymorphism:** workflow memilih `EventForm` atau `AdminEventForm`, lalu memakai antarmuka yang sama: `is_valid()` dan `save()`.

Kode: [workflow event](backend/apps/events/workflow.py), [form event](backend/apps/events/forms.py).

### B. Mengelola tim dan memantau kegiatan

Ketua panitia memakai **Pengaturan** untuk pengelolaan tim/undangan, **Peserta** untuk memantau pendaftaran, **Pendapatan** untuk melihat ringkasan keuangan, serta **Log Aktivitas** dan **Bantuan** untuk pemantauan operasional. Setelah waktu acara berakhir, event dapat ditandai selesai sesuai hak aksesnya.

**OOP di fitur ini:** `EventQuerySet.managed_by()` mengemas lingkup event yang dapat dikelola. `EventManagementMixin` digunakan oleh beberapa view, sehingga membentuk **hierarchical inheritance**. `ManagedEventListView(EventManagementMixin, EventListView)` menggabungkan mixin dengan view daftar yang sudah memiliki induk: kombinasi **multiple dan multilevel inheritance**. Pencarian method mengikuti **MRO**, dan `super()` melanjutkan ke implementasi berikutnya dalam urutan tersebut.

Kode: [queryset dan model event](backend/apps/events/models.py), [view pengelolaan event](backend/apps/events/views.py), [pengaturan tim dan halaman ketua](backend/config/views.py).

## 5. Alur admin

1. Buka **Kelola Pengguna** untuk melihat akun, mengatur peran, serta mengaktifkan atau menangguhkan akun sesuai kewenangan.
2. Tinjau pengajuan penyelenggara dan event. Untuk event, admin dapat meminta revisi, menolak, menyetujui, atau memublikasikan sesuai statusnya.
3. Setelah publikasi, buka Jelajah untuk menunjukkan bahwa event dapat ditemukan peserta.
4. Gunakan **Keuangan**, **Bantuan**, **Log Audit**, dan **Pengaturan** untuk pengawasan platform.

Panel aplikasi `/admin-panel/` berbeda dari Django Admin `/admin/`. Konfigurasi model seperti definisi achievement, reward, atau template sertifikat memiliki registrasi admin tersendiri; jangan menganggap seluruh konfigurasi tersebut berada pada menu panel aplikasi yang sama.

**OOP di fitur ini:**

- **Multiple inheritance dan mixin:** misalnya `EventAdmin(ReadOnlyAuditAdmin, admin.ModelAdmin)` memakai aturan akses audit bersama sekaligus kemampuan administrasi model Django.
- **Hierarchical inheritance:** `AchievementAdmin` dan `RewardAdmin` sama-sama mewarisi `PlatformDefinitionAdmin`.
- **Polymorphism:** method `has_view_permission()`, `has_change_permission()`, dan hook admin lainnya menyediakan perilaku khusus melalui antarmuka Django admin.
- **Decorator:** `@admin.register` mendaftarkan class admin; `@admin.action` memberi metadata tindakan. Keduanya decorator Python, bukan otomatis pola desain Decorator berbasis pembungkusan objek.
- **Duck typing dan callable:** `run_single_action()` menerima objek admin yang menyediakan `message_user()`/`log_change()` serta operasi yang dapat dipanggil sebagai `operation(pk, reason)`.

Kode: [admin event](backend/apps/events/admin.py), [admin achievement/reward](backend/apps/achievements/admin.py), [mixin dan action bersama](backend/apps/accounts/admin_support.py), [pengelolaan akses akun](backend/apps/accounts/role_service.py).

## 6. Urutan demo yang disarankan

Untuk menjelaskan sistem, kenalkan peran dengan urutan peserta → panitia biasa → ketua panitia → admin. Untuk memperagakan transaksi dari awal, gunakan urutan berikut agar data yang dibutuhkan sudah tersedia.

| Tahap | Peragaan | Hasil yang ditunjukkan | OOP yang dijelaskan |
| --- | --- | --- | --- |
| 1 | Ketua membuat dan mengajukan event gratis. | Draft menjadi pengajuan. | `EventWorkflow`, form inheritance, abstraction. |
| 2 | Admin meninjau, menyetujui, lalu memublikasikan. | Event muncul di Jelajah. | Workflow status, model `EventTransition`, permission hook. |
| 3 | Peserta melengkapi profil dan mendaftar. | Registrasi dan tiket tersedia. | Property, `RegistrationService`, association. |
| 4 | Panitia memilih event berjalan dan memproses tiket. | Kehadiran tercatat satu kali. | `AttendanceService`, mixin, multiple inheritance. |
| 5 | Tunjukkan event yang sudah selesai. | Peserta dapat mengisi feedback. | `FeedbackService`, validasi melalui form. |
| 6 | Panitia menyiapkan dokumentasi/sertifikat; peserta membuka hasilnya. | Hasil kegiatan tersedia bagi peserta yang berhak. | QuerySet abstraction, relasi model, duck typing file. |
| 7 | Peserta membuka Pencapaian; admin membuka audit. | Progres peserta dan riwayat operasional terlihat. | Model/QuerySet, service achievement, reusable admin. |

**Narasi penutup:** “Satu tindakan pada satu peran menghasilkan data yang dipakai peran lain. Pendaftaran menghasilkan tiket, tiket digunakan untuk absensi, dan kehadiran menjadi dasar feedback serta pencapaian. OOP membantu memusatkan aturan tersebut agar dapat dipakai kembali tanpa menyalin logika di setiap halaman.”

## 7. Persiapan dan batasan demo sesuai kode saat ini

- Siapkan akun untuk empat peran dan penugasan panitia pada event yang akan diperagakan.
- Gunakan event gratis untuk alur membuat → mengajukan → memublikasikan. Walaupun model, form, dan service pembayaran sudah tersedia, `EventWorkflow._validate_ready()` saat ini masih menolak event berharga bukan nol. Jangan menjanjikan publikasi event berbayar baru pada demo ini.
- Siapkan contoh event mendatang, sedang berlangsung, dan sudah selesai. Check-in hanya diterima ketika event berstatus `PUBLISHED` dan waktu saat ini berada dalam jadwal acara; penyelesaian event hanya diterima setelah waktu berakhir. Satu event baru tidak bisa melewati seluruh tahap waktu secara instan.
- Untuk demo review, gunakan admin. Kode saat ini juga memiliki pengecualian yang mengizinkan pemilik event melakukan aksi `approve` dengan permission pengajuan; publikasi tetap memerlukan kewenangan platform. Jadi jangan menyebut seluruh persetujuan eksklusif admin.
- Siapkan template aktif jika ingin memperagakan PDF otomatis, atau siapkan berkas sertifikat untuk jalur unggahan panitia. Periksa juga tautan dokumentasi dan definisi achievement yang aktif.
- Seed awal belum menyiapkan seluruh data pendukung fitur peserta. Periksa data akun demo sebelum presentasi; jangan menganggap sertifikat, feedback, atau achievement sudah tersedia hanya karena seed pernah dijalankan.
- Ringkasan pendapatan/pencairan di aplikasi bukan bukti integrasi transfer bank atau payment gateway otomatis.

## 8. Cara menjawab pertanyaan OOP saat presentasi

| Konsep | Contoh konkret | Penjelasan singkat |
| --- | --- | --- |
| Encapsulation | `_actor_id` dan helper internal pada service | Identitas pelaku dan aturan operasi dikelompokkan dalam objek. |
| Abstraction | `RegistrationService.register()` | Pemanggil meminta pendaftaran tanpa mengurus seluruh langkah internal. |
| Inheritance | `User(AbstractUser)` | Kemampuan induk digunakan kembali dan disesuaikan. |
| Polymorphism | `to_python()`, `save()`, hook permission | Antarmuka yang sama memiliki perilaku khusus sesuai class objek. |
| Multiple inheritance | `TicketScanView(ParticipantAccessMixin, View)` | Satu class menggabungkan perilaku beberapa induk. |
| Multilevel inheritance | `ModelForm → EventForm → AdminEventForm` | Pewarisan berlangsung melalui lebih dari satu tingkat. |
| Hierarchical inheritance | `PlatformDefinitionAdmin → AchievementAdmin / RewardAdmin` | Beberapa class berbagi induk yang sama. |
| Duck typing | `read()`/`seek()` pada unggahan | Kode bergantung pada kemampuan objek, bukan satu tipe konkret. |
| Property / descriptor | `User.profile_complete` | Getter dipakai seperti atribut untuk menyajikan hasil perhitungan. |
| Class method | `UserManager.normalize_email()` | Method menerima class melalui `cls`, bukan instance melalui `self`. |
| Static method | `AchievementService._counts_for()` | Utilitas dikelompokkan dalam class tanpa parameter `self`/`cls` otomatis. |
| Association dan composition | Relasi registrasi; field pada form | Objek dihubungkan atau disusun untuk bekerja bersama. |
| Operator overloading | `Q(...) & Q(...)` atau `Q(...) | Q(...)` | Operator membentuk kondisi query, bukan operasi angka biasa. |
| Decorator Python | `@transaction.atomic`, `@admin.register` | Callable/class dibungkus atau diberi metadata sesuai kebutuhan. |

**Batas istilah:** Django template `{% extends %}` adalah pewarisan template, bukan class inheritance Python. `AbstractUser` adalah model abstrak Django, bukan bukti penggunaan `abc.ABC`. Tidak semua fungsi pada proyek merupakan method OOP, dan decorator Python tidak selalu merupakan pola desain Decorator.
