/* =========================================================
   SIMEVENT - Penyimpanan bersama antar-peran (data contoh)
   Dipakai Dashboard Admin dan Dashboard Ketua Panitia supaya
   tindakan di satu peran langsung terlihat di peran lain
   (persetujuan event, tiket support, pembekuan akun, dst).
   Disimpan di localStorage browser. Nanti ganti dengan database.
   ========================================================= */
(function () {
  "use strict";
  var KEY = "simevent_shared_v1";

  function defaults() {
    return JSON.parse(JSON.stringify(window.SIMEVENT_DEMO.shared_defaults));
  }

  function load() {
    var d = defaults(), s = null;
    try { s = JSON.parse(localStorage.getItem(KEY)); } catch (e) { s = null; }
    if (s && typeof s === "object") {
      Object.keys(d).forEach(function (k) { if (s[k] !== undefined) { d[k] = s[k]; } });
      d.settings = Object.assign(defaults().settings, s.settings || {});
    }
    return d;
  }

  var state = load();
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* mode privat: abaikan */ } }

  function ago(ts) {
    var m = Math.round((Date.now() - ts) / 60000);
    if (m < 1) { return "Baru saja"; }
    if (m < 60) { return m + " menit lalu"; }
    var h = Math.round(m / 60);
    if (h < 24) { return h + " jam lalu"; }
    var d = Math.round(h / 24);
    return d === 1 ? "Kemarin" : d + " hari lalu";
  }

  /* opsi.eo = true -> juga tampil di Log Aktivitas Ketua Panitia */
  function log(tipe, teks, aktor, peran, opsi) {
    state.activity.unshift({ tipe: tipe, teks: teks, aktor: aktor || "Admin", peran: peran || "Admin Platform", ts: Date.now(), eo: !!(opsi && opsi.eo) });
    if (state.activity.length > 300) { state.activity.length = 300; }
    save();
  }

  /* Terapkan perubahan bersama ke data contoh Ketua Panitia (window.EO) */
  function applyToEO(EO) {
    if (!EO) { return; }
    EO.statusEvent.diajukan = "Menunggu Persetujuan";
    EO.statusEvent.ditolak = "Ditolak";
    EO.statusEvent.ditangguhkan = "Ditangguhkan";

    state.newEvents.forEach(function (n) {
      if (!EO.events.some(function (e) { return e.id === n.id; })) {
        EO.events.push({ id: n.id, nama: n.nama, jenis: n.jenis, tanggal: n.tanggal, lokasi: n.lokasi, kuota: n.kuota, terjual: 0, harga: n.harga, status: n.status, hadir: 0, pendapatan: 0 });
      }
    });
    EO.events.forEach(function (e) {
      if (state.eventStatus[e.id]) { e.status = state.eventStatus[e.id]; }
      if (state.eventReason[e.id]) { e.alasan = state.eventReason[e.id]; }
    });
    EO.tickets.forEach(function (t) {
      var o = state.tickets[t.id];
      if (o) { t.status = o.status; if (o.balasan) { t.balasan = o.balasan; } }
    });
    state.activity.filter(function (a) { return a.eo; }).slice().reverse().forEach(function (a) {
      EO.activity.unshift({ tipe: a.tipe === "keuangan" ? "bayar" : a.tipe, teks: a.teks, waktu: ago(a.ts) });
    });
  }

  window.SIM = {
    state: state,
    save: save,
    log: log,
    ago: ago,
    applyToEO: applyToEO,
    reset: function () { try { localStorage.removeItem(KEY); } catch (e) { /* abaikan */ } location.reload(); }
  };
})();
