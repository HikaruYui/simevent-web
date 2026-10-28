/* Adapter tampilan demo. Sumber data: backend/apps/events/seeds/demo.json.
   Aksi lokal tetap memakai SIM sampai masing-masing fitur dihubungkan ke DB. */
(function () {
  "use strict";
  var data = window.SIMEVENT_DEMO.eo;
  var METRIK = {
    onsite: { nama: "Kehadiran On Site", labels: ["08.00","09.00","10.00","11.00","12.00","13.00","14.00"] },
    online: { nama: "Kehadiran Online", labels: ["08.00","09.00","10.00","11.00","12.00","13.00","14.00"] },
    daftar: { nama: "Pendaftaran", labels: ["H-6","H-5","H-4","H-3","H-2","H-1","Hari H"] }
  };
  window.EO = {
    events: data.events,
    participants: data.participants,
    tickets: data.tickets,
    activity: data.activity,
    monthly: data.monthly,
    metrik: METRIK,
    series: function (eventId, metric) {
      var event = data.attendance_series[String(eventId)];
      return event && event[metric] ? event[metric] : [0, 0, 0, 0, 0, 0, 0];
    },
    statusEvent: { berlangsung: "Sedang Berlangsung", mendatang: "Mendatang", selesai: "Selesai" },
    statusTiket: { diaudit: "Sedang Diaudit", selesai: "Selesai" }
  };
  if (window.SIM) { window.SIM.applyToEO(window.EO); }
})();
