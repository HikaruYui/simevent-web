/* =========================================================
   SIMEVENT - Data contoh untuk Dashboard Ketua Panitia (EO)
   Semua angka di sini hanya DATA CONTOH. Nanti ganti dengan
   data dari backend (lihat bagian "Menghubungkan ke backend" di README).
   Total sengaja dibuat sama dengan desain:
   pendapatan 27.600.000 | tiket 300 | event aktif 4+4 | support 4+4
   ========================================================= */
(function () {
  "use strict";

  /* ---------- Event (12) ---------- */
  var events = [
    { id: 1,  nama: "Konferensi Meja Bundar",           jenis: "Konferensi", tanggal: "2026-10-16", lokasi: "Aula Utama Universitas Mulawarman",  kuota: 60,  terjual: 42, harga: 150000, status: "berlangsung" },
    { id: 2,  nama: "Workshop UI/UX Dasar",             jenis: "Workshop",   tanggal: "2026-10-16", lokasi: "Lab Komputer Gedung Informatika",    kuota: 40,  terjual: 35, harga: 100000, status: "berlangsung" },
    { id: 3,  nama: "Seminar Kewirausahaan Digital",    jenis: "Seminar",    tanggal: "2026-10-17", lokasi: "Ruang Seminar Fakultas Ekonomi",     kuota: 50,  terjual: 28, harga: 75000,  status: "berlangsung" },
    { id: 4,  nama: "Webinar Karier Teknologi",         jenis: "Webinar",    tanggal: "2026-10-17", lokasi: "Online (Zoom)",                      kuota: 100, terjual: 31, harga: 0,      status: "berlangsung" },
    { id: 5,  nama: "Konferensi Pendidikan Kaltim",     jenis: "Konferensi", tanggal: "2026-10-24", lokasi: "Hotel Mercure Samarinda",            kuota: 80,  terjual: 24, harga: 150000, status: "mendatang" },
    { id: 6,  nama: "Workshop Data Science",            jenis: "Workshop",   tanggal: "2026-10-28", lokasi: "Lab Komputer Gedung Informatika",    kuota: 30,  terjual: 20, harga: 130000, status: "mendatang" },
    { id: 7,  nama: "Seminar Kesehatan Mental",         jenis: "Seminar",    tanggal: "2026-11-02", lokasi: "Aula Fakultas Kedokteran",           kuota: 70,  terjual: 18, harga: 50000,  status: "mendatang" },
    { id: 8,  nama: "Webinar Literasi Keuangan",        jenis: "Webinar",    tanggal: "2026-11-08", lokasi: "Online (Zoom)",                      kuota: 150, terjual: 22, harga: 0,      status: "mendatang" },
    { id: 9,  nama: "Kuliah Umum Kecerdasan Buatan",    jenis: "Kuliah Umum",tanggal: "2026-09-18", lokasi: "Auditorium Universitas Mulawarman",  kuota: 120, terjual: 30, harga: 100000, status: "selesai" },
    { id: 10, nama: "Workshop Fotografi Jurnalistik",   jenis: "Workshop",   tanggal: "2026-09-27", lokasi: "Gedung Kesenian Samarinda",          kuota: 25,  terjual: 16, harga: 150000, status: "selesai" },
    { id: 11, nama: "Seminar Lingkungan Hidup",         jenis: "Seminar",    tanggal: "2026-09-30", lokasi: "Ruang Rapat Dinas Lingkungan Hidup", kuota: 60,  terjual: 19, harga: 50000,  status: "selesai" },
    { id: 12, nama: "Konferensi Pariwisata Kaltim",     jenis: "Konferensi", tanggal: "2026-10-05", lokasi: "Hotel Aston Samarinda",              kuota: 40,  terjual: 15, harga: 150000, status: "selesai" }
  ];

  var STATUS_EVENT = {
    berlangsung: "Sedang Berlangsung",
    mendatang:   "Mendatang",
    selesai:     "Selesai"
  };

  /* Rasio kehadiran per status event (dipakai peserta & grafik) */
  var HADIR_RATIO = { berlangsung: 0.6, mendatang: 0, selesai: 0.85 };
  events.forEach(function (e) {
    e.hadir = Math.round(e.terjual * HADIR_RATIO[e.status]);
    e.pendapatan = e.terjual * e.harga;
  });

  /* ---------- Pendapatan & tiket per bulan (Mei - Okt) ---------- */
  var monthly = {
    labels:     ["Mei", "Jun", "Jul", "Agu", "Sep", "Okt"],
    pendapatan: [2900000, 3600000, 4200000, 5062500, 5837500, 6000000],
    tiket:      [22, 34, 45, 53, 72, 74]
  };

  /* ---------- Generator acak yang selalu sama (seeded) ---------- */
  function rng(seed) {
    var s = seed >>> 0;
    return function () {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }

  /* ---------- Peserta (300 baris, sesuai total tiket terjual) ---------- */
  var depan = ["Ahmad","Aisyah","Alya","Andi","Annisa","Bagas","Bayu","Cahya","Citra","Dewi","Dimas","Eka","Farhan","Fitri","Gita","Hafiz","Indah","Irfan","Jihan","Kevin","Lestari","Maulana","Nabila","Nanda","Putri","Rafi","Rizky","Salsabila","Syarafina","Tegar","Vina","Wahyu","Yusuf","Zahra"];
  var belakang = ["Pratama","Saputra","Ramadhani","Wijaya","Nugraha","Amalia","Hidayat","Lestari","Kurniawan","Permata","Firmansyah","Maharani","Setiawan","Anggraini","Syahputra","Utami","Prasetyo","Rahmawati","Hakim","Safitri"];

  var participants = [];
  (function () {
    var r = rng(2026);
    var no = 0;
    events.forEach(function (e) {
      for (var i = 0; i < e.terjual; i++) {
        no++;
        var n = depan[Math.floor(r() * depan.length)];
        var b = belakang[Math.floor(r() * belakang.length)];
        var email = (n + "." + b + (Math.floor(r() * 90) + 10)).toLowerCase() + "@mail.com";
        var hari = Math.floor(r() * 20) + 1;
        var bulan = e.status === "selesai" ? 8 : 9; /* indeks 0-based: 8 = September, 9 = Oktober */
        var tgl = new Date(2026, bulan, Math.min(hari, 28));
        participants.push({
          no: no,
          nama: n + " " + b,
          email: email,
          eventId: e.id,
          terdaftar: tgl.getFullYear() + "-" + ("0" + (tgl.getMonth() + 1)).slice(-2) + "-" + ("0" + tgl.getDate()).slice(-2),
          status: i < e.hadir ? "hadir" : "terdaftar"
        });
      }
    });
  })();

  /* ---------- Ticket support (4 diaudit + 4 selesai) ---------- */
  var tickets = [
    { id: "SUP-0108", judul: "Kode QR peserta tidak terbaca di pintu masuk", pelapor: "Budi Santoso",  eventId: 1,  tanggal: "2026-10-16", status: "diaudit", isi: "Beberapa peserta gagal check-in karena QR tidak terbaca pada perangkat scan. Mohon dicek apakah format QR berubah." },
    { id: "SUP-0107", judul: "Permintaan perubahan jadwal sesi workshop",   pelapor: "Budi Santoso",  eventId: 6,  tanggal: "2026-10-15", status: "diaudit", isi: "Sesi dimajukan 1 jam karena narasumber ada keperluan. Mohon persetujuan perubahan jadwal." },
    { id: "SUP-0106", judul: "Peserta ganda terdaftar dengan email sama",   pelapor: "Siti Rahma",    eventId: 2,  tanggal: "2026-10-14", status: "diaudit", isi: "Ditemukan dua pendaftaran dengan email yang sama pada event ini. Mohon pengecekan data." },
    { id: "SUP-0105", judul: "Verifikasi ulang data penyelenggara",         pelapor: "Siti Rahma",    eventId: 5,  tanggal: "2026-10-12", status: "diaudit", isi: "Dokumen legalitas komunitas diperbarui dan perlu diverifikasi ulang oleh admin." },
    { id: "SUP-0104", judul: "Sertifikat peserta belum terbit",             pelapor: "Budi Santoso",  eventId: 9,  tanggal: "2026-09-25", status: "selesai", isi: "Sertifikat belum muncul untuk peserta yang hadir. Sudah diperbaiki dan diterbitkan ulang oleh admin." },
    { id: "SUP-0103", judul: "Pengembalian dana peserta yang batal hadir",  pelapor: "Budi Santoso",  eventId: 10, tanggal: "2026-09-22", status: "selesai", isi: "Dua peserta meminta pengembalian dana sebelum event. Sudah diproses sesuai kebijakan penyelenggara." },
    { id: "SUP-0102", judul: "Tautan Zoom tidak dapat diakses peserta",     pelapor: "Siti Rahma",    eventId: 4,  tanggal: "2026-10-03", status: "selesai", isi: "Tautan rapat kedaluwarsa. Tautan baru sudah dikirim ke semua peserta terdaftar." },
    { id: "SUP-0101", judul: "Kuota event perlu ditambah",                  pelapor: "Budi Santoso",  eventId: 12, tanggal: "2026-09-29", status: "selesai", isi: "Permintaan penambahan kuota 10 kursi telah disetujui admin." }
  ];
  var STATUS_TIKET = { diaudit: "Sedang Diaudit", selesai: "Selesai" };

  /* ---------- Log aktivitas ---------- */
  var activity = [
    { tipe: "daftar",  teks: "Nabila Amalia mendaftar ke Konferensi Meja Bundar", waktu: "5 menit lalu" },
    { tipe: "hadir",   teks: "18 peserta check-in di Workshop UI/UX Dasar",       waktu: "22 menit lalu" },
    { tipe: "bayar",   teks: "Pembayaran 3 tiket Seminar Kewirausahaan Digital diterima", waktu: "1 jam lalu" },
    { tipe: "support", teks: "Tiket SUP-0108 masuk tahap audit",                  waktu: "2 jam lalu" },
    { tipe: "event",   teks: "Workshop Data Science dijadwalkan 28 Oktober",      waktu: "Kemarin" },
    { tipe: "daftar",  teks: "Rafi Hidayat mendaftar ke Webinar Literasi Keuangan", waktu: "Kemarin" },
    { tipe: "bayar",   teks: "Pembayaran 5 tiket Konferensi Pendidikan Kaltim diterima", waktu: "2 hari lalu" },
    { tipe: "support", teks: "Tiket SUP-0104 ditandai selesai",                   waktu: "3 hari lalu" }
  ];

  /* ---------- Grafik kehadiran: 7 titik per event & metrik ---------- */
  var METRIK = {
    onsite:  { nama: "Kehadiran On Site", labels: ["08.00","09.00","10.00","11.00","12.00","13.00","14.00"] },
    online:  { nama: "Kehadiran Online",  labels: ["08.00","09.00","10.00","11.00","12.00","13.00","14.00"] },
    daftar:  { nama: "Pendaftaran",       labels: ["H-6","H-5","H-4","H-3","H-2","H-1","Hari H"] }
  };

  function series(eventId, metrik) {
    var e = events.filter(function (x) { return x.id === eventId; })[0];
    var total = metrik === "onsite" ? Math.round(e.hadir * 0.7)
              : metrik === "online" ? e.hadir - Math.round(e.hadir * 0.7)
              : e.terjual;
    var r = rng(eventId * 31 + metrik.length * 7);
    var w = [];
    var sum = 0;
    for (var i = 0; i < 7; i++) {
      var base = metrik === "daftar" ? 1 + i * 0.35 : 1 + i * 0.25;
      var v = base * (0.45 + r() * 1.1);
      w.push(v); sum += v;
    }
    var out = w.map(function (v) { return Math.round(v / sum * total); });
    var diff = total - out.reduce(function (a, b) { return a + b; }, 0);
    out[6] += diff;
    return out;
  }

  window.EO = {
    events: events,
    participants: participants,
    tickets: tickets,
    activity: activity,
    monthly: monthly,
    metrik: METRIK,
    series: series,
    statusEvent: STATUS_EVENT,
    statusTiket: STATUS_TIKET
  };
  /* Terapkan tindakan Admin (persetujuan event, balasan support, dst) bila ada */
  if (window.SIM) { window.SIM.applyToEO(window.EO); }
})();
