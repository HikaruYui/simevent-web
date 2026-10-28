(function () {
  "use strict";

  var E = window.EO, S = window.SIM, st = S.state;
  var ADMIN = (document.querySelector(".eo-user b") || {}).textContent || window.SIMEVENT_DEMO.admin_name;
  var ORG = window.SIMEVENT_DEMO.organizer_name;   /* pemilik 12 event contoh Ketua Panitia */
  // Data database hanya tersedia di halaman Kelola Event Admin.
  var adminRowsElement = document.getElementById("admin-event-rows");

  var backendAdminEvents = adminRowsElement
    ? JSON.parse(adminRowsElement.textContent)
    : null;

  /* ---------- Helper ---------- */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function num(n) { return Number(n).toLocaleString("id-ID"); }
  function rp(n) { return n === 0 ? "Gratis" : "Rp " + num(n); }
  function rp0(n) { return "Rp " + num(n); }
  function fmtDate(s) { return new Date(s + "T00:00:00Z").toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }); }
  function chip(status, label) { return '<span class="chip chip--' + status + '"><i></i>' + esc(label) + "</span>"; }
  function sum(a, f) { return a.reduce(function (t, x) { return t + f(x); }, 0); }
  var toastTimer;
  function toast(msg) {
    var t = $("#toast"); if (!t) { return; }
    t.textContent = msg; t.hidden = false; clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 4200);
  }
  function setText(id, v) { var n = document.getElementById(id); if (n) { n.textContent = v; } }

  /* Dialog konfirmasi (dengan alasan wajib bila perlu) */
  var dlg = $("#admDlg"), cur = null;
  function ask(o) {
    cur = o;
    $("#admDlgTitle").textContent = o.title; $("#admDlgText").textContent = o.text || "";
    var w = $("#admDlgReasonWrap"); w.hidden = !o.reason;
    $("#admDlgReasonLabel").textContent = o.reason || ""; $("#admDlgReason").value = "";
    $$("small.err", dlg).forEach(function (x) { x.remove(); });
    var ok = $("#admDlgOk"); ok.textContent = o.ok || "Lanjutkan"; ok.className = "btn" + (o.danger ? " btn--danger" : "");
    dlg.showModal(); if (o.reason) { $("#admDlgReason").focus(); }
  }
  if (dlg) {
    $$("[data-close]", dlg).forEach(function (b) { b.addEventListener("click", function () { dlg.close(); }); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) { dlg.close(); } });
    $("#admDlgForm").addEventListener("submit", function (ev) {
      ev.preventDefault(); var r = "";
      if (cur.reason) {
        r = $("#admDlgReason").value.trim();
        if (r.length < 5) {
          $$("small.err", dlg).forEach(function (x) { x.remove(); });
          var m = document.createElement("small"); m.className = "err"; m.textContent = "Alasan wajib diisi (minimal 5 karakter).";
          $("#admDlgReasonWrap").appendChild(m); $("#admDlgReason").focus(); return;
        }
      }
      dlg.close(); cur.onOk(r);
    });
  }

  /* ---------- Data: event ---------- */
  var OTHERS = window.SIMEVENT_DEMO.admin_events;
  OTHERS.forEach(function (o) {
    if (st.eventStatus[o.id]) { o.status = st.eventStatus[o.id]; }
    if (st.eventReason[o.id]) { o.alasan = st.eventReason[o.id]; }
    o.pendapatan = o.terjual * o.harga;
  });
  function events() {
    // Halaman Kelola Event menggunakan PostgreSQL.
    if (backendAdminEvents !== null) {
      return backendAdminEvents;
    }

    // Halaman Admin lain tetap menggunakan sumber
    // sebelumnya sampai integrasinya dilakukan.
    E.events.forEach(function (e) {
      e.organizer = ORG;
      e.pendapatan = e.terjual * e.harga;
    });

    return E.events.concat(OTHERS);
  }

  async function adminEventTransition(e, action, reason) {
    if (!e) {
      toast("Event tidak ditemukan.");
      return false;
    }

    if (backendAdminEvents === null) {
      toast("Data backend belum tersedia.");
      return false;
    }

    var csrfInput = document.querySelector(
      '#adminEventCsrf [name="csrfmiddlewaretoken"]'
    );

    if (!csrfInput) {
      toast("Token keamanan tidak ditemukan. Refresh halaman.");
      return false;
    }

    var body = new URLSearchParams();
    body.set("reason", reason || "");

    try {
      var response = await fetch(
        "/events/manage/" +
          encodeURIComponent(e.id) +
          "/" +
          action +
          "/",
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": csrfInput.value,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
          },
          body: body.toString()
        }
      );

      var data = await response.json().catch(function () {
        return null;
      });

      if (!response.ok) {
        if (response.redirected) {
          throw new Error(
            "Sesi login berakhir. Silakan login kembali."
          );
        }

        if (data && data.errors) {
          var errors = Object.entries(data.errors)
            .map(function (entry) {
              return (
                entry[0] + ": " +
                (Array.isArray(entry[1])
                  ? entry[1].join(", ")
                  : String(entry[1]))
              );
            })
            .join(" | ");

          throw new Error(errors);
        }

        if (response.status === 403) {
          throw new Error(
            "Akses ditolak. Periksa permission Admin atau CSRF."
          );
        }

        throw new Error(
          (data && (data.error || data.detail)) ||
          "Gagal memproses event (HTTP " +
            response.status + ")."
        );
      }

      if (!data || !data.id || !data.status) {
        throw new Error(
          "Respons backend tidak sesuai."
        );
      }

      var labels = {
        approve: "disetujui",
        reject: "ditolak",
        request_revision: "diminta revisi",
        publish: "dipublikasikan"
      };

      toast(
        'Event "' + e.nama + '" berhasil ' +
        (labels[action] || "diproses") + "."
      );

      // Reload agar Admin mengambil status yang
      // benar-benar tersimpan di PostgreSQL.
      window.setTimeout(function () {
        window.location.reload();
      }, 800);

      return true;

    } catch (error) {
      console.error("Admin event transition:", error);

      toast(
        error.message ||
        "Terjadi kesalahan saat memproses event."
      );

      return false;
    }
  }

  function eventById(id) { return events().filter(function (e) { return e.id === id; })[0]; }
  var STATUS_EVENT = E.statusEvent;
  Object.assign(STATUS_EVENT, {
  draft: "Draft",
  diajukan: "Menunggu Persetujuan",
  revisi: "Perlu Revisi",
  disetujui: "Disetujui",
  ditolak: "Ditolak",
  dibatalkan: "Dibatalkan"
});
  function setStatus(e, status, reason) {
    if (status === "ditangguhkan") { st.eventPrev[e.id] = e.status; }
    st.eventStatus[e.id] = status;
    if (reason) { st.eventReason[e.id] = reason; } else { delete st.eventReason[e.id]; }
    e.status = status; e.alasan = reason || "";
  }

  function logEvent(e, teks) { S.log("event", teks, ADMIN, "Admin Platform", { eo: e.organizer === ORG }); }
  function approveEvent(e) {
  if (backendAdminEvents !== null) {
    return adminEventTransition(e, "approve", "");
  }

  setStatus(e, "mendatang");
  logEvent(e, 'Event "' + e.nama + '" disetujui admin');
  toast('Event "' + e.nama + '" disetujui.');
}

function rejectEvent(e, why) {
  if (backendAdminEvents !== null) {
    return adminEventTransition(e, "reject", why);
  }

  setStatus(e, "ditolak", why);
  logEvent(e, 'Event "' + e.nama + '" ditolak admin: ' + why);
  toast('Event "' + e.nama + '" ditolak.');
}
  function suspendEvent(e, why) { setStatus(e, "ditangguhkan", why); logEvent(e, 'Event "' + e.nama + '" ditangguhkan admin: ' + why); toast('Event "' + e.nama + '" ditangguhkan.'); }
  function restoreEvent(e) { var prev = st.eventPrev[e.id] || "mendatang"; setStatus(e, prev); logEvent(e, 'Event "' + e.nama + '" dipulihkan admin'); toast('Event "' + e.nama + '" dipulihkan.'); }
  function askReject(e, after) { ask({ title: "Tolak event?", text: '"' + e.nama + '" oleh ' + e.organizer + ".", reason: "Alasan penolakan (dikirim ke penyelenggara)", ok: "Tolak event", danger: true, onOk: function (r) { rejectEvent(e, r); after(); } }); }
  function askSuspend(e, after) { ask({ title: "Tangguhkan event?", text: 'Event "' + e.nama + '" tidak lagi tampil untuk peserta sampai dipulihkan.', reason: "Alasan penangguhan", ok: "Tangguhkan", danger: true, onOk: function (r) { suspendEvent(e, r); after(); } }); }

  /* ---------- Proposal & detail event (dialog bersama) ---------- */
  var RINGKAS = window.SIMEVENT_DEMO.proposal_summaries;
  
  function proposalOf(e) {
    // Halaman Kelola Event Admin membaca PostgreSQL.
    if (backendAdminEvents !== null) {
      return {
        file: e.has_proposal
          ? "Proposal event (PDF)"
          : "Belum ada proposal",
        size: "",
        uploaded: null,
        ringkasan: e.deskripsi || "Belum ada deskripsi event.",
        asli: Boolean(e.has_proposal),
        backend: true
      };
    }

    // Fallback untuk halaman Admin yang masih dummy.
    var n = st.newEvents.filter(function (x) {
      return x.id === e.id;
    })[0];

    if (n && n.proposal) {
      return {
        file: n.proposal.file,
        size: n.proposal.size,
        uploaded: n.proposal.uploaded,
        ringkasan: n.proposal.ringkasan ||
          RINGKAS[e.jenis] || RINGKAS.Seminar,
        asli: true,
        backend: false
      };
    }

    return {
      file: "Proposal contoh",
      size: "Data contoh",
      uploaded: e.tanggal,
      ringkasan: RINGKAS[e.jenis] || RINGKAS.Seminar,
      asli: false,
      backend: false
    };
  }

var detailCtx = null;
function openDetail(e, after) {
  if (!e) {
    toast("Event tidak ditemukan.");
    return;
  }

  var dlgD = $("#propDlg");
  if (!dlgD) {
    console.error("Modal #propDlg tidak ditemukan");
    return;
  }

  var p = proposalOf(e);

  var anggaran = Math.round(
    e.kuota * Math.max(e.harga, 25000) * 0.6 / 100000
  ) * 100000;

  detailCtx = {
    id: e.id,
    after: after
  };

  $("#propDlgTitle").textContent = e.nama;

  var proposalMeta = p.backend
    ? ""
    : p.size + " · diunggah " + fmtDate(p.uploaded);

  var proposalButton = (!p.backend || p.asli)
    ? '<button type="button" class="btn btn--ghost sm" data-open-doc>Buka proposal</button>'
    : "";

  var proposalNote = p.backend
    ? (
        p.asli
          ? ""
          : '<p class="pdoc__note">Belum ada proposal PDF yang diunggah.</p>'
      )
    : (
        p.asli
          ? ""
          : '<p class="pdoc__note">Proposal ini masih data contoh.</p>'
      );

  $("#propDlgBody").innerHTML =
    '<dl class="dl">' +
      '<dt>Penyelenggara</dt><dd>' + esc(e.organizer) + '</dd>' +
      '<dt>Jenis</dt><dd>' + esc(e.jenis) + '</dd>' +
      '<dt>Tanggal</dt><dd>' + fmtDate(e.tanggal) + '</dd>' +
      '<dt>Lokasi</dt><dd>' + esc(e.lokasi) + '</dd>' +
      '<dt>Status</dt><dd>' +
        chip(e.status, STATUS_EVENT[e.status]) + '</dd>' +
      '<dt>Kuota &amp; harga</dt><dd>' +
        e.kuota + ' peserta &middot; ' + rp(e.harga) + '</dd>' +

      (
        e.status === "diajukan"
          ? ""
          : '<dt>Tiket terjual</dt><dd>' +
            e.terjual + ' dari ' + e.kuota +
            ' &middot; ' + rp0(e.terjual * e.harga) + '</dd>'
      ) +

      (
        e.alasan
          ? '<dt>Catatan admin</dt><dd>' +
            esc(e.alasan) + '</dd>'
          : ""
      ) +
    '</dl>' +

    '<h3 class="prop-h">Proposal</h3>' +

    '<div class="pdoc">' +
      '<span class="pdoc__ico" aria-hidden="true">PDF</span>' +
      '<div>' +
        '<b>' + esc(p.file) + '</b>' +
        '<small>' + esc(proposalMeta) + '</small>' +
      '</div>' +
      proposalButton +
    '</div>' +

    '<dl class="dl dl--prop">' +
      '<dt>Tujuan &amp; ringkasan</dt>' +
      '<dd>' + esc(p.ringkasan) + '</dd>' +
      '<dt>Target peserta</dt>' +
      '<dd>' + e.kuota + ' peserta, mahasiswa dan umum</dd>' +
      '<dt>Estimasi anggaran</dt>' +
      '<dd>' + rp0(anggaran) + '</dd>' +
    '</dl>' +

    proposalNote;

  // TOMBOL APPROVAL
  var f =
    '<button type="button" class="btn btn--ghost" data-close>Tutup</button>';

  if (e.status === "diajukan") {
    f +=
      '<button type="button" class="btn btn--ghost" data-act="rev">Minta Revisi</button>' +
      '<button type="button" class="btn btn--ghost" data-act="no">Tolak</button>' +
      '<button type="button" class="btn" data-act="ok">Setujui</button>';

  } else if (
    backendAdminEvents !== null &&
    e.status === "disetujui"
  ) {
    f +=
      '<button type="button" class="btn" data-act="pub">Publikasikan</button>';

  } else if (
    backendAdminEvents === null &&
    (e.status === "mendatang" || e.status === "berlangsung")
  ) {
    f +=
      '<button type="button" class="btn btn--ghost" data-act="sus">Tangguhkan</button>';

  } else if (
    backendAdminEvents === null &&
    e.status === "ditangguhkan"
  ) {
    f +=
      '<button type="button" class="btn" data-act="res">Pulihkan</button>';
  }

  $("#propDlgFoot").innerHTML = f;

  dlgD.showModal();
}

  (function () {
    var d = $("#propDlg");
    if (!d) return;

    d.addEventListener("click", function (ev) {

      // Tutup modal
      if (
        ev.target === d ||
        ev.target.closest("[data-close]")
      ) {
        d.close();
        return;
      }

      // Buka proposal
      // Buka proposal PDF asli dari PostgreSQL
    if (ev.target.closest("[data-open-doc]")) {
      if (backendAdminEvents === null) {
        toast("Proposal ini masih data contoh.");
        return;
      }

      var eventData = detailCtx && eventById(detailCtx.id);

      if (!eventData || !eventData.has_proposal) {
        toast("Proposal belum diunggah.");
        return;
      }

      window.open(
        "/events/manage/" + eventData.id + "/proposal/",
        "_blank",
        "noopener,noreferrer"
      );

      return;
    }

      // Ambil tombol aksi terlebih dahulu
      var b = ev.target.closest("[data-act]");

      if (!b || !detailCtx) return;

      var e = eventById(detailCtx.id);
      var after = detailCtx.after;

      if (!e) {
        toast("Event tidak ditemukan.");
        return;
      }

      var action = b.dataset.act;

      d.close();

      // SETUJUI EVENT
      if (action === "ok") {
        if (backendAdminEvents !== null) {
          adminEventTransition(e, "approve", "");
        } else {
          approveEvent(e);
          if (after) after();
        }
      }

      // TOLAK EVENT
      else if (action === "no") {
        if (backendAdminEvents !== null) {
          ask({
            title: "Tolak event?",
            text: 'Event "' + e.nama +
              '" akan ditolak dan alasannya dicatat.',
            reason: "Alasan penolakan",
            ok: "Tolak Event",
            danger: true,
            onOk: function (reason) {
              adminEventTransition(e, "reject", reason);
            }
          });
        } else {
          askReject(e, after);
        }
      }

      // MINTA REVISI
      else if (action === "rev") {
        ask({
          title: "Minta revisi event?",
          text: 'Event "' + e.nama +
            '" akan dikembalikan kepada Ketua Panitia.',
          reason: "Bagian yang harus diperbaiki",
          ok: "Kirim Revisi",
          onOk: function (reason) {
            adminEventTransition(
              e,
              "request_revision",
              reason
            );
          }
        });
      }

      // PUBLIKASIKAN
      else if (action === "pub") {
        ask({
          title: "Publikasikan event?",
          text: 'Event "' + e.nama +
            '" akan ditampilkan di Jelajah Event.',
          ok: "Publikasikan",
          onOk: function () {
            adminEventTransition(e, "publish", "");
          }
        });
      }

    // TANGGUHKAN (HANYA MODE DUMMY LAMA)
    else if (action === "sus") {
      if (backendAdminEvents === null) {
        askSuspend(e, after);
      }
    }

    // PULIHKAN (HANYA MODE DUMMY LAMA)
    else if (action === "res") {
      if (backendAdminEvents === null) {
        restoreEvent(e);
        if (after) after();
      }
    }
  });
})();


  /* ---------- Data: pengguna ---------- */
  var PERAN = { admin: "Admin Platform", penyelenggara: "Ketua Panitia", panitia: "Panitia", peserta: "Peserta" };
  var BASE_USERS = window.SIMEVENT_DEMO.admin_users;
  var PESERTA = (function () {
    var seen = {}, out = [];
    E.participants.forEach(function (p) {
      if (!seen[p.email]) { seen[p.email] = { email: p.email, nama: p.nama, peran: "peserta", org: "-", daftar: 0 }; out.push(seen[p.email]); }
      seen[p.email].daftar++;
    });
    return out.slice(0, 48);
  })();
  function users() {
    var all = BASE_USERS.concat(PESERTA).concat(st.customUsers).map(function (u) {
      var o = st.users[u.email] || {};
      return { email: u.email, nama: u.nama, org: u.org, daftar: u.daftar || 0, peranAsli: u.peran, peran: o.peran || u.peran, status: o.status || u.status || "aktif" };
    });
    return all;
  }
  function userByEmail(em) { return users().filter(function (u) { return u.email === em; })[0]; }
  var PROPOSALS = window.SIMEVENT_DEMO.proposals;
  function proposals() {
    return PROPOSALS.map(function (p) { var o = st.proposals[p.id] || {}; return Object.assign({}, p, { status: o.status || "diajukan", alasan: o.alasan || "" }); });
  }
  var PROP_LABEL = { diajukan: "Menunggu Tinjauan", disetujui: "Disetujui", revisi: "Perlu Revisi", ditolak: "Ditolak" };
  function decideProposal(p, status, why) {
    st.proposals[p.id] = { status: status, alasan: why || "" };
    if (status === "disetujui") { st.users[p.email] = Object.assign(st.users[p.email] || {}, { peran: "penyelenggara", status: "aktif" }); }
    S.log("pengguna", "Pengajuan penyelenggara " + p.org + " (" + p.nama + ") " + PROP_LABEL[status].toLowerCase() + (why ? ": " + why : ""), ADMIN, "Admin Platform");
  }

  /* ---------- Data: tiket support ---------- */
  var EXTRA_TICKETS = window.SIMEVENT_DEMO.extra_tickets;
  function tickets() {
    var mine = E.tickets.map(function (t) { return { id: t.id, judul: t.judul, pelapor: t.pelapor, org: ORG, eventId: t.eventId, tanggal: t.tanggal, status: t.status, isi: t.isi, balasan: t.balasan || "" }; });
    var more = EXTRA_TICKETS.map(function (t) { var o = st.tickets[t.id] || {}; return Object.assign({}, t, { status: o.status || t.status, balasan: o.balasan || t.balasan || "" }); });
    return mine.concat(more).sort(function (a, b) { return a.tanggal < b.tanggal ? 1 : -1; });
  }
  var STATUS_TIKET = { diaudit: "Sedang Diaudit", selesai: "Selesai" };

  /* ---------- Data: keuangan ---------- */
  function finance() {
    var fee = st.settings.feePct, orgs = {};
    events().forEach(function (e) {
      if (e.status === "diajukan" || e.status === "ditolak") { return; }
      var o = orgs[e.organizer] || (orgs[e.organizer] = { nama: e.organizer, event: 0, tiket: 0, kotor: 0, selesai: 0 });
      var g = e.terjual * e.harga; o.event++; o.tiket += e.terjual; o.kotor += g; if (e.status === "selesai") { o.selesai += g; }
    });
    var rows = Object.keys(orgs).map(function (k) {
      var o = orgs[k]; o.fee = Math.round(o.kotor * fee / 100); o.bersih = o.kotor - o.fee;
      var netSel = o.selesai - Math.round(o.selesai * fee / 100);
      o.cair = st.payouts[o.nama] || 0; o.tersedia = Math.max(0, netSel - o.cair);
      return o;
    }).sort(function (a, b) { return b.kotor - a.kotor; });
    return { rows: rows, fee: fee, kotor: sum(rows, function (o) { return o.kotor; }), feeTotal: sum(rows, function (o) { return o.fee; }), cair: sum(rows, function (o) { return o.cair; }), tersedia: sum(rows, function (o) { return o.tersedia; }) };
  }

  /* ---------- Data: audit ---------- */
  var AUDIT_SEED = window.SIMEVENT_DEMO.audit.map(function (item) { return Object.assign({}, item, { aktor: item.aktor === "{admin}" ? ADMIN : item.aktor }); });
  var CAT = { daftar: "peserta", hadir: "peserta", bayar: "keuangan", support: "support", event: "event", pengguna: "pengguna", keuangan: "keuangan", pengaturan: "pengaturan" };
  function audit() {
    var nEo = st.activity.filter(function (a) { return a.eo; }).length;
    var rows = st.activity.map(function (a) { return { tipe: CAT[a.tipe] || a.tipe, teks: a.teks, aktor: a.aktor, peran: a.peran, waktu: S.ago(a.ts) }; });
    E.activity.slice(nEo).forEach(function (a) { rows.push({ tipe: CAT[a.tipe] || a.tipe, teks: a.teks, aktor: a.tipe === "support" || a.tipe === "event" ? ORG : "Sistem", peran: a.tipe === "support" || a.tipe === "event" ? "Ketua Panitia" : "Sistem", waktu: a.waktu }); });
    AUDIT_SEED.forEach(function (a) { rows.push({ tipe: a.tipe, teks: a.teks, aktor: a.aktor, peran: a.peran, waktu: a.waktu }); });
    return rows;
  }

  /* ---------- Grafik batang sederhana ---------- */
  var NS = "http://www.w3.org/2000/svg";
  function barChart(host, labels, values, name) {
    function draw() {
      host.innerHTML = "";
      var W = Math.max(host.clientWidth, 300), H = Math.max(host.clientHeight, 240), m = { l: 56, r: 12, t: 22, b: 30 };
      var max = Math.max.apply(null, values.concat([1])), p = Math.pow(10, Math.floor(Math.log10(max))), yMax = Math.ceil(max / p * 2) / 2 * p;
      var inW = W - m.l - m.r, inH = H - m.t - m.b, slot = inW / values.length, bw = Math.min(54, slot * 0.56);
      var svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", name + ": " + labels.map(function (l, i) { return l + " " + rp0(values[i]); }).join(", "));
      function add(tag, a, par) { var n = document.createElementNS(NS, tag); Object.keys(a).forEach(function (k) { n.setAttribute(k, a[k]); }); (par || svg).appendChild(n); return n; }
      for (var i = 0; i <= 3; i++) {
        var y = m.t + inH - inH * i / 3;
        add("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: i === 0 ? "#9F886F" : "#E8DCC4", "stroke-width": 1 });
        var t = add("text", { x: m.l - 8, y: y + 4, "text-anchor": "end", style: "font:500 12px var(--font-body);fill:var(--muted)" });
        t.textContent = i === 0 ? "0" : (yMax * i / 3 >= 1e6 ? (yMax * i / 3 / 1e6).toFixed(1).replace(".0", "").replace(".", ",") + " jt" : Math.round(yMax * i / 3 / 1e3) + " rb");
      }
      values.forEach(function (v, i) {
        var h = Math.max(2, inH * v / yMax), x = m.l + slot * (i + .5) - bw / 2, y = m.t + inH - h, last = i === values.length - 1;
        var r = add("rect", { x: x, y: y, width: bw, height: h, rx: 4, fill: last ? "#D78B30" : "#3F422E" });
        add("title", {}, r).textContent = labels[i] + ": " + rp0(v);
        var lt = add("text", { x: m.l + slot * (i + .5), y: H - 8, "text-anchor": "middle", style: "font:500 12px var(--font-body);fill:var(--muted)" }); lt.textContent = labels[i];
        if (last) { var vt = add("text", { x: m.l + slot * (i + .5), y: y - 6, "text-anchor": "middle", style: "font:800 12px var(--font-head);fill:var(--olive)" }); vt.textContent = rp0(v); }
      });
      host.appendChild(svg);
    }
    host.__draw = draw; draw();
    if (!host.__ro && window.ResizeObserver) { host.__ro = new ResizeObserver(function () { host.__draw(); }); host.__ro.observe(host); }
  }

  /* ---------- Grafik garis ---------- */
  function lineChart(host, labels, values, name) {
    function draw() {
      host.innerHTML = "";
      var W = Math.max(host.clientWidth, 300), H = Math.max(host.clientHeight, 240), m = { l: 56, r: 28, t: 30, b: 30 };
      var max = Math.max.apply(null, values.concat([1])), p = Math.pow(10, Math.floor(Math.log10(max))), yMax = Math.ceil(max / p * 2) / 2 * p;
      var inW = W - m.l - m.r, inH = H - m.t - m.b, slot = inW / values.length;
      var svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", name + ": " + labels.map(function (l, i) { return l + " " + rp0(values[i]); }).join(", "));
      function add(tag, a, par) { var n = document.createElementNS(NS, tag); Object.keys(a).forEach(function (k) { n.setAttribute(k, a[k]); }); (par || svg).appendChild(n); return n; }
      for (var i = 0; i <= 3; i++) {
        var y = m.t + inH - inH * i / 3;
        add("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: i === 0 ? "#9F886F" : "#E8DCC4", "stroke-width": 1 });
        var t = add("text", { x: m.l - 8, y: y + 4, "text-anchor": "end", style: "font:500 12px var(--font-body);fill:var(--muted)" });
        t.textContent = i === 0 ? "0" : (yMax * i / 3 >= 1e6 ? (yMax * i / 3 / 1e6).toFixed(1).replace(".0", "").replace(".", ",") + " jt" : Math.round(yMax * i / 3 / 1e3) + " rb");
      }
      var pts = values.map(function (v, i) { return [m.l + slot * (i + .5), m.t + inH - inH * v / yMax]; });
      add("path", { d: "M" + pts.map(function (q) { return q[0].toFixed(1) + "," + q[1].toFixed(1); }).join(" L"), fill: "none", stroke: "#3F422E", "stroke-width": 3, "stroke-linejoin": "round", "stroke-linecap": "round" });
      pts.forEach(function (q, i) {
        var last = i === pts.length - 1;
        var c = add("circle", { cx: q[0], cy: q[1], r: last ? 6 : 5, fill: last ? "#D78B30" : "#3F422E", stroke: "#fff", "stroke-width": 2 });
        add("title", {}, c).textContent = labels[i] + ": " + rp0(values[i]);
        add("text", { x: q[0], y: H - 8, "text-anchor": "middle", style: "font:500 12px var(--font-body);fill:var(--muted)" }).textContent = labels[i];
        if (last) { add("text", { x: q[0], y: q[1] - 12, "text-anchor": "middle", style: "font:800 12px var(--font-head);fill:var(--olive)" }).textContent = rp0(values[i]); }
      });
      host.appendChild(svg);
    }
    host.__draw = draw; draw();
    if (!host.__ro && window.ResizeObserver) { host.__ro = new ResizeObserver(function () { host.__draw(); }); host.__ro.observe(host); }
  }

  function download(name, text) {
    var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }));
    a.download = name; document.body.appendChild(a); a.click(); a.remove();
  }
  function csvCell(v) { v = String(v == null ? "" : v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function pager(host, info, total, page, per, go) {
    var pc = Math.max(1, Math.ceil(total / per));
    info.textContent = total ? "Menampilkan " + ((page - 1) * per + 1) + "-" + Math.min(page * per, total) + " dari " + total : "Tidak ada data";
    host.innerHTML = '<button type="button" data-p="' + (page - 1) + '"' + (page <= 1 ? " disabled" : "") + ">Sebelumnya</button><button type=\"button\" data-p=\"" + (page + 1) + '"' + (page >= pc ? " disabled" : "") + ">Berikutnya</button>";
    host.onclick = function (ev) { var b = ev.target.closest("button[data-p]"); if (b && !b.disabled) { go(parseInt(b.dataset.p, 10)); } };
  }

  /* =========================================================
     BERANDA
     ========================================================= */
  function pageDashboard() {
    function render() {
      var evs = events(), us = users(), tk = tickets(), props = proposals();
      var pend = evs.filter(function (e) { return e.status === "diajukan"; });
      var disetujui = evs.filter(function (e) { return ["mendatang", "berlangsung", "selesai"].indexOf(e.status) !== -1; });
      var open = tk.filter(function (t) { return t.status === "diaudit"; });
      var pProp = props.filter(function (p) { return p.status === "diajukan"; });
      setText("kUsers", num(us.filter(function (u) { return u.status !== "dibekukan"; }).length));
      setText("kProp", pProp.length);
      setText("kEvents", num(evs.length));
      setText("kLiveEv", evs.filter(function (e) { return e.status === "berlangsung"; }).length);
      setText("kPend", pend.length); setText("kOk", disetujui.length);
      setText("kTkOpen", open.length); setText("kTkDone", tk.length - open.length);
      $("#apvBody").innerHTML = pend.length ? pend.map(function (e) {
        return '<tr><td><span class="cell-title">' + esc(e.nama) + '</span><span class="cell-sub">' + esc(e.jenis) + " &middot; " + esc(e.lokasi) + "</span></td><td>" + esc(e.organizer) + "</td><td>" + fmtDate(e.tanggal) + "</td>" +
          '<td class="act"><button type="button" class="btn btn--ghost sm" data-d="' + e.id + '">Detail</button> <button type="button" class="btn sm" data-ok="' + e.id + '">Setujui</button> <button type="button" class="btn btn--ghost sm" data-no="' + e.id + '">Tolak</button></td></tr>';
      }).join("") : '<tr><td colspan="4"><p class="tbl-empty">Tidak ada event yang menunggu persetujuan.</p></td></tr>';
      $("#tkMini").innerHTML = open.length ? open.slice(0, 4).map(function (t) {
        return '<li class="mini"><div><b>' + esc(t.judul) + "</b><small>" + esc(t.id) + " &middot; " + esc(t.pelapor) + " &middot; " + fmtDate(t.tanggal) + "</small></div></li>";
      }).join("") : '<li><p class="tbl-empty">Semua tiket sudah selesai.</p></li>';
      $("#propMini").innerHTML = pProp.length ? pProp.map(function (p) {
        return '<li class="mini"><div><b>' + esc(p.org) + "</b><small>" + esc(p.nama) + " &middot; " + fmtDate(p.tanggal) + '</small></div><a class="btn btn--ghost sm" href="' + $("#propMini").dataset.href + '">Tinjau</a></li>';
      }).join("") : '<li><p class="tbl-empty">Tidak ada pengajuan baru.</p></li>';
      $("#actMini").innerHTML = audit().slice(0, 6).map(function (a) {
        return '<li class="mini"><div><b>' + esc(a.teks) + "</b><small>" + esc(a.aktor) + " &middot; " + esc(a.waktu) + "</small></div></li>";
      }).join("");
    }
    $("#apvBody").addEventListener("click", function (ev) {
      var ok = ev.target.closest("[data-ok]"), no = ev.target.closest("[data-no]"), dt = ev.target.closest("[data-d]");
      if (dt) { openDetail(eventById(parseInt(dt.dataset.d, 10)), render); }
      if (ok) { approveEvent(eventById(parseInt(ok.dataset.ok, 10))); render(); }
      if (no) { askReject(eventById(parseInt(no.dataset.no, 10)), render); }
    });
    render();
  }

  /* =========================================================
     KELOLA EVENT
     ========================================================= */
  function pageEvents() {
    var tab = "semua", q = $("#evSearch"), body = $("#evBody"), tabs = $("#evTabs");
    var TABS = [
      ["semua", "Semua"],
      ["diajukan", "Menunggu Persetujuan"],
      ["revisi", "Perlu Revisi"],
      ["disetujui", "Disetujui"],
      ["aktif", "Aktif"],
      ["selesai", "Selesai"],
      ["tidak", "Ditolak / Dibatalkan"],
      ["draft", "Draft"]
    ];
    function inTab(e, t) {
      if (t === "semua") return true;

      if (t === "aktif") {
        return (
          e.status === "mendatang" ||
          e.status === "berlangsung"
        );
      }

      if (t === "tidak") {
        return (
          e.status === "ditolak" ||
          e.status === "dibatalkan" ||
          e.status === "ditangguhkan"
        );
      }

      return e.status === t;
    }
    function render() {
      var evs = events();
      tabs.innerHTML = TABS.map(function (t) {
        var c = evs.filter(function (e) { return inTab(e, t[0]); }).length;
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === tab ? "is-active" : "") + '" aria-pressed="' + (t[0] === tab) + '">' + t[1] + "<span>" + c + "</span></button>";
      }).join("");
      var term = q.value.trim().toLowerCase();
      var rows = evs.filter(function (e) {
        return inTab(e, tab) && (!term || (e.nama + " " + e.organizer + " " + e.lokasi + " " + e.jenis).toLowerCase().indexOf(term) !== -1);
      });
      body.innerHTML = rows.length ? rows.map(function (e) {
        var pct = e.kuota ? Math.round(e.terjual / e.kuota * 100) : 0;
        return '<tr><td><span class="cell-title">' + esc(e.nama) + '</span><span class="cell-sub">' + esc(e.jenis) + " &middot; " + esc(e.lokasi) + "</span></td><td>" + esc(e.organizer) + "</td><td>" + fmtDate(e.tanggal) + "</td>" +
          '<td><div class="tk"><div class="tk__bar" aria-hidden="true"><i style="width:' + pct + '%"></i></div><span>' + e.terjual + "/" + e.kuota + '</span></div></td><td class="num">' + rp(e.harga) + "</td><td>" + chip(e.status, STATUS_EVENT[e.status]) + '</td><td class="act"><button type="button" class="btn btn--ghost sm" data-d="' + e.id + '">Detail</button></td></tr>';
      }).join("") : '<tr><td colspan="7"><p class="tbl-empty">Tidak ada event yang cocok.</p></td></tr>';
    }
    tabs.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { tab = b.dataset.f; render(); } });
    q.addEventListener("input", render);
    body.addEventListener("click", function (ev) {
      var b = ev.target.closest("button[data-d]"); if (b) { openDetail(eventById(parseInt(b.dataset.d, 10)), render); }
    });
    render();
  }

  /* =========================================================
     KELOLA PENGGUNA
     ========================================================= */
  function pageUsers() {
    var tab = (location.hash || "#semua").slice(1), page = 1, PER = 10;
    var q = $("#userSearch"), body = $("#userBody"), tabs = $("#userTabs"), propBox = $("#propBox"), tableBox = $("#userTable"), info = $("#userInfo"), pg = $("#userPager");
    var TABS = [["semua", "Semua"], ["penyelenggara", "Ketua Panitia"], ["panitia", "Panitia"], ["peserta", "Peserta"], ["pengajuan", "Pengajuan Penyelenggara"]];
    if (!TABS.some(function (t) { return t[0] === tab; })) { tab = "semua"; }
    function inTab(u, t) {
      if (t === "semua") { return true; }
      return u.peran === t;
    }
    function render() {
      var us = users(), props = proposals();
      tabs.innerHTML = TABS.map(function (t) {
        var c = t[0] === "pengajuan" ? props.filter(function (p) { return p.status === "diajukan"; }).length : us.filter(function (u) { return inTab(u, t[0]); }).length;
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === tab ? "is-active" : "") + '" aria-pressed="' + (t[0] === tab) + '">' + t[1] + "<span>" + c + "</span></button>";
      }).join("");
      var isProp = tab === "pengajuan";
      propBox.hidden = !isProp; tableBox.hidden = isProp; $("#userTools").hidden = isProp;
      if (isProp) {
        $("#propList").innerHTML = props.map(function (p) {
          var act = p.status === "diajukan" || p.status === "revisi"
            ? '<button type="button" class="btn sm" data-pok="' + p.id + '">Setujui</button> <button type="button" class="btn btn--ghost sm" data-prev="' + p.id + '">Minta revisi</button> <button type="button" class="btn btn--ghost sm" data-pno="' + p.id + '">Tolak</button>' : "";
          return '<li class="prop"><div><b>' + esc(p.org) + "</b><small>Pemohon: " + esc(p.nama) + " &middot; " + esc(p.email) + " &middot; " + fmtDate(p.tanggal) + "</small><p>" + esc(p.rencana) + "</p>" + (p.alasan ? '<p class="muted">Catatan: ' + esc(p.alasan) + "</p>" : "") + '</div><div class="prop__act">' + chip(p.status, PROP_LABEL[p.status]) + act + "</div></li>";
        }).join("");
        return;
      }
      var term = q.value.trim().toLowerCase();
      var rows = us.filter(function (u) { return inTab(u, tab) && (!term || (u.nama + " " + u.email + " " + PERAN[u.peran] + " " + u.org).toLowerCase().indexOf(term) !== -1); });
      var pc = Math.max(1, Math.ceil(rows.length / PER)); if (page > pc) { page = pc; }
      body.innerHTML = rows.slice((page - 1) * PER, page * PER).map(function (u) {
        var self = u.peran === "admin";
        var act = '<button type="button" class="btn btn--ghost sm" data-edit="' + esc(u.email) + '">Edit</button> <button type="button" class="btn btn--ghost sm" data-reset="' + esc(u.email) + '">Reset sandi</button>';
        if (!self) { act += u.status === "aktif" ? ' <button type="button" class="btn btn--ghost sm" data-freeze="' + esc(u.email) + '">Bekukan</button>' : ' <button type="button" class="btn sm" data-unfreeze="' + esc(u.email) + '">Aktifkan</button>'; }
        return '<tr><td><span class="cell-title">' + esc(u.nama) + '</span><span class="cell-sub">' + esc(u.email) + '</span></td><td><span class="role-badge role-badge--' + u.peran + '">' + esc(PERAN[u.peran]) + "</span></td><td>" + esc(u.org) + "</td><td>" +
          (u.peran === "peserta" ? u.daftar + " event" : "-") + "</td><td>" + chip(u.status, { aktif: "Aktif", ditangguhkan: "Ditangguhkan ketua", dibekukan: "Dibekukan admin" }[u.status]) + '</td><td class="act">' + act + "</td></tr>";
      }).join("") || '<tr><td colspan="6"><p class="tbl-empty">Tidak ada pengguna yang cocok.</p></td></tr>';
      pager(pg, info, rows.length, page, PER, function (p) { page = p; render(); });
    }
    tabs.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { tab = b.dataset.f; page = 1; history.replaceState(null, "", "#" + tab); render(); } });
    window.addEventListener("hashchange", function () { var t = (location.hash || "#semua").slice(1); if (TABS.some(function (x) { return x[0] === t; })) { tab = t; page = 1; render(); } });
    q.addEventListener("input", function () { page = 1; render(); });
    body.addEventListener("click", function (ev) {
      var b = ev.target.closest("button"); if (!b) { return; }
      var em = b.dataset.edit || b.dataset.reset || b.dataset.freeze || b.dataset.unfreeze, u = userByEmail(em);
      if (b.dataset.freeze) {
        ask({ title: "Bekukan akun " + u.nama + "?", text: "Akun tidak bisa masuk sampai diaktifkan lagi. Datanya tetap tersimpan.", reason: "Alasan pembekuan", ok: "Bekukan", danger: true, onOk: function (r) {
          st.users[em] = Object.assign(st.users[em] || {}, { status: "dibekukan" });
          S.log("pengguna", "Akun " + u.nama + " (" + PERAN[u.peran] + ") dibekukan: " + r, ADMIN, "Admin Platform", { eo: u.peran === "panitia" || u.nama === ORG });
          toast("Akun " + u.nama + " dibekukan."); render();
        } });
      } else if (b.dataset.unfreeze) {
        st.users[em] = Object.assign(st.users[em] || {}, { status: "aktif" });
        S.log("pengguna", "Akun " + u.nama + " diaktifkan kembali", ADMIN, "Admin Platform", { eo: u.peran === "panitia" });
        toast("Akun " + u.nama + " diaktifkan."); render();
      } else if (b.dataset.reset) {
        S.log("pengguna", "Tautan atur ulang kata sandi dikirim ke " + u.email, ADMIN, "Admin Platform");
        toast("Tautan atur ulang kata sandi dikirim ke " + u.email + " (contoh, belum ada email terkirim).");
      } else if (b.dataset.edit) { openForm(u); }
    });
    $("#propList").addEventListener("click", function (ev) {
      var b = ev.target.closest("button"); if (!b) { return; }
      var id = parseInt(b.dataset.pok || b.dataset.prev || b.dataset.pno, 10), p = proposals().filter(function (x) { return x.id === id; })[0];
      if (b.dataset.pok) { decideProposal(p, "disetujui"); toast(p.nama + " kini menjadi Ketua Panitia untuk " + p.org + "."); render(); }
      if (b.dataset.prev) { ask({ title: "Minta revisi pengajuan?", text: p.org, reason: "Catatan revisi untuk pemohon", ok: "Kirim permintaan", onOk: function (r) { decideProposal(p, "revisi", r); render(); toast("Permintaan revisi dikirim."); } }); }
      if (b.dataset.pno) { ask({ title: "Tolak pengajuan?", text: p.org, reason: "Alasan penolakan", ok: "Tolak", danger: true, onOk: function (r) { decideProposal(p, "ditolak", r); render(); toast("Pengajuan ditolak."); } }); }
    });

    /* Tambah / edit pengguna */
    var uf = $("#userDlg"), ufForm = $("#userForm"), editing = null;
    function openForm(u) {
      editing = u || null; ufForm.reset(); $$("small.err", ufForm).forEach(function (x) { x.remove(); });
      $("#userDlgTitle").textContent = u ? "Edit pengguna" : "Tambah pengguna";
      ufForm.nama.value = u ? u.nama : ""; ufForm.email.value = u ? u.email : ""; ufForm.email.readOnly = !!u;
      ufForm.peran.value = u ? u.peran : "peserta"; ufForm.org.value = u && u.org !== "-" ? u.org : "";
      uf.showModal(); ufForm.nama.focus();
    }
    $("#addUserBtn").addEventListener("click", function () { openForm(null); });
    $$("[data-close]", uf).forEach(function (b) { b.addEventListener("click", function () { uf.close(); }); });
    uf.addEventListener("click", function (ev) { if (ev.target === uf) { uf.close(); } });
    ufForm.addEventListener("submit", function (ev) {
      ev.preventDefault(); $$("small.err", ufForm).forEach(function (x) { x.remove(); });
      var nama = ufForm.nama.value.trim(), email = ufForm.email.value.trim().toLowerCase(), err = null;
      if (nama.length < 3) { err = ["nama", "Nama minimal 3 karakter."]; }
      else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { err = ["email", "Format email tidak valid."]; }
      else if (!editing && userByEmail(email)) { err = ["email", "Email sudah terdaftar."]; }
      if (err) { var m = document.createElement("small"); m.className = "err"; m.textContent = err[1]; ufForm[err[0]].closest(".field").appendChild(m); ufForm[err[0]].focus(); return; }
      if (editing) {
        st.users[email] = Object.assign(st.users[email] || {}, { peran: ufForm.peran.value });
        S.log("pengguna", "Data " + nama + " diperbarui (peran: " + PERAN[ufForm.peran.value] + ")", ADMIN, "Admin Platform");
        toast("Data " + nama + " diperbarui.");
      } else {
        st.customUsers.push({ email: email, nama: nama, peran: ufForm.peran.value, org: ufForm.org.value.trim() || "-" });
        S.log("pengguna", "Akun baru " + nama + " (" + PERAN[ufForm.peran.value] + ") dibuat admin", ADMIN, "Admin Platform");
        toast("Akun " + nama + " dibuat. Tautan buat kata sandi dikirim (contoh).");
      }
      S.save(); uf.close(); render();
    });
    render();
  }

  /* =========================================================
     SUPPORT
     ========================================================= */
  function pageSupport() {
    var tab = "semua", q = $("#tkSearch"), list = $("#tkList"), tabs = $("#tkTabs"), open = {};
    var TABS = [["semua", "Semua"], ["diaudit", "Sedang Diaudit"], ["selesai", "Selesai"]];
    function save(t, status, balasan) {
      st.tickets[t.id] = { status: status, balasan: balasan };
      S.log("support", "Tiket " + t.id + (status === "selesai" ? " ditandai selesai" : " dibalas") + " oleh admin", ADMIN, "Admin Platform", { eo: t.org === ORG });
    }
    function render() {
      var all = tickets();
      tabs.innerHTML = TABS.map(function (t) {
        var c = t[0] === "semua" ? all.length : all.filter(function (x) { return x.status === t[0]; }).length;
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === tab ? "is-active" : "") + '" aria-pressed="' + (t[0] === tab) + '">' + t[1] + "<span>" + c + "</span></button>";
      }).join("");
      var term = q.value.trim().toLowerCase();
      var rows = all.filter(function (t) { return (tab === "semua" || t.status === tab) && (!term || (t.judul + " " + t.id + " " + t.pelapor + " " + t.org).toLowerCase().indexOf(term) !== -1); });
      list.innerHTML = rows.length ? rows.map(function (t) {
        var e = eventById(t.eventId);
        return '<li><details class="ticket" data-id="' + esc(t.id) + '"' + (open[t.id] ? " open" : "") + '><summary><div><span class="ticket__title">' + esc(t.judul) + '</span><span class="ticket__meta">' + esc(t.id) + " &middot; " + esc(t.org) + " &middot; " + (e ? esc(e.nama) : "-") + " &middot; " + fmtDate(t.tanggal) + "</span></div>" +
          chip(t.status === "selesai" ? "selesai" : "diaudit", STATUS_TIKET[t.status]) + '<span class="ticket__chev" aria-hidden="true"><svg class="icon"><use href="#i-chev"/></svg></span></summary><div class="ticket__body"><p>' + esc(t.isi) + '</p><p class="ticket__meta">Dilaporkan oleh ' + esc(t.pelapor) + "</p>" +
          (t.status === "selesai" ? (t.balasan ? '<p class="ticket__reply"><b>Balasan admin:</b> ' + esc(t.balasan) + "</p>" : "")
            : '<div class="field"><label for="rp-' + esc(t.id) + '">Balasan untuk penyelenggara</label><textarea id="rp-' + esc(t.id) + '" rows="3" maxlength="500" placeholder="Tulis tindak lanjut atau solusi...">' + esc(t.balasan) + '</textarea></div><div class="ticket__actions"><button type="button" class="btn btn--ghost" data-save="' + esc(t.id) + '">Simpan balasan</button><button type="button" class="btn" data-done="' + esc(t.id) + '">Kirim &amp; tandai selesai</button></div>') +
          "</div></details></li>";
      }).join("") : '<li><p class="tbl-empty">Tidak ada tiket yang cocok.</p></li>';
    }
    tabs.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { tab = b.dataset.f; render(); } });
    q.addEventListener("input", render);
    list.addEventListener("toggle", function (ev) { var d = ev.target; if (d.dataset && d.dataset.id) { open[d.dataset.id] = d.open; } }, true);
    list.addEventListener("click", function (ev) {
      var b = ev.target.closest("button[data-save],button[data-done]"); if (!b) { return; }
      var id = b.dataset.save || b.dataset.done, t = tickets().filter(function (x) { return x.id === id; })[0], ta = document.getElementById("rp-" + id), txt = ta.value.trim();
      $$("small.err", ta.parentNode).forEach(function (x) { x.remove(); });
      if (b.dataset.done && txt.length < 5) { var m = document.createElement("small"); m.className = "err"; m.textContent = "Tulis balasan (minimal 5 karakter) sebelum menyelesaikan tiket."; ta.parentNode.appendChild(m); ta.focus(); return; }
      if (b.dataset.done) { save(t, "selesai", txt); toast("Tiket " + id + " selesai. Balasan tampil di dashboard " + t.org + "."); }
      else { save(t, "diaudit", txt); toast("Balasan tiket " + id + " disimpan."); }
      render();
    });
    render();
  }

  /* =========================================================
     KEUANGAN
     ========================================================= */
  function pageFinance() {
    var body = $("#finBody");
    function render() {
      var f = finance();
      setText("fGross", rp0(f.kotor)); setText("fFee", rp0(f.feeTotal)); setText("fFeeNote", "Biaya platform " + f.fee + "% dari tiket terjual");
      setText("fCair", rp0(f.cair)); setText("fAvail", rp0(f.tersedia));
      var scale = f.rows.length ? f.kotor / (f.rows.filter(function (o) { return o.nama === ORG; })[0] || { kotor: f.kotor }).kotor : 1;
      lineChart($("#finChart"), E.monthly.labels, E.monthly.pendapatan.map(function (v) { return Math.round(v * scale * f.fee / 100); }), "Biaya platform");
      body.innerHTML = f.rows.map(function (o) {
        var status = o.tersedia > 0 ? chip("menunggu", "Siap dicairkan") : (o.cair > 0 ? chip("dicairkan", "Sudah dicairkan") : chip("belum", "Belum ada dana"));
        return '<tr><td><span class="cell-title">' + esc(o.nama) + '</span><span class="cell-sub">' + o.event + " event &middot; " + num(o.tiket) + ' tiket</span></td><td class="num">' + rp0(o.kotor) + '</td><td class="num">' + rp0(o.fee) + '</td><td class="num">' + rp0(o.bersih) + '</td><td class="num">' + rp0(o.tersedia) + "</td><td>" + status + '</td><td class="act">' +
          (o.tersedia > 0 ? '<button type="button" class="btn sm" data-pay="' + esc(o.nama) + '">Cairkan</button>' : "") + "</td></tr>";
      }).join("");
      body.parentNode.querySelector("tfoot").innerHTML = '<tr><td>Total</td><td class="num">' + rp0(f.kotor) + '</td><td class="num">' + rp0(f.feeTotal) + '</td><td class="num">' + rp0(f.kotor - f.feeTotal) + '</td><td class="num">' + rp0(f.tersedia) + "</td><td></td><td></td></tr>";
    }
    body.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-pay]"); if (!b) { return; }
      var o = finance().rows.filter(function (x) { return x.nama === b.dataset.pay; })[0];
      ask({ title: "Cairkan dana " + o.nama + "?", text: rp0(o.tersedia) + " akan ditransfer ke rekening penyelenggara (contoh, belum ada transfer sungguhan).", ok: "Cairkan dana", onOk: function () {
        st.payouts[o.nama] = (st.payouts[o.nama] || 0) + o.tersedia;
        S.log("keuangan", "Dana " + rp0(o.tersedia) + " dicairkan ke " + o.nama, ADMIN, "Admin Platform", { eo: o.nama === ORG });
        toast("Dana " + rp0(o.tersedia) + " dicairkan ke " + o.nama + "."); render();
      } });
    });
    $("#finExport").addEventListener("click", function () {
      var f = finance();
      download("keuangan-simevent.csv", ["Penyelenggara,Event,Tiket,Pendapatan Kotor,Biaya Platform,Bersih,Tersedia,Sudah Dicairkan"].concat(f.rows.map(function (o) {
        return [o.nama, o.event, o.tiket, o.kotor, o.fee, o.bersih, o.tersedia, o.cair].map(csvCell).join(",");
      })).join("\r\n"));
    });
    render();
  }

  /* =========================================================
     AUDIT LOG
     ========================================================= */
  function pageAudit() {
    var tab = "semua", page = 1, PER = 12, q = $("#auSearch"), tabs = $("#auTabs"), list = $("#auList"), info = $("#auInfo"), pg = $("#auPager");
    var TABS = [["semua", "Semua"], ["event", "Event"], ["pengguna", "Pengguna"], ["support", "Bantuan"], ["keuangan", "Keuangan"], ["pengaturan", "Pengaturan"], ["peserta", "Aktivitas Peserta"]];
    var ICON = { event: "i-calendar", pengguna: "i-users", support: "i-help", keuangan: "i-wallet", pengaturan: "i-gear", peserta: "i-user" };
    function filtered() {
      var term = q.value.trim().toLowerCase();
      return audit().filter(function (a) { return (tab === "semua" || a.tipe === tab) && (!term || (a.teks + " " + a.aktor).toLowerCase().indexOf(term) !== -1); });
    }
    function render() {
      var all = audit();
      tabs.innerHTML = TABS.map(function (t) {
        var c = t[0] === "semua" ? all.length : all.filter(function (a) { return a.tipe === t[0]; }).length;
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === tab ? "is-active" : "") + '" aria-pressed="' + (t[0] === tab) + '">' + t[1] + "<span>" + c + "</span></button>";
      }).join("");
      var rows = filtered(), pc = Math.max(1, Math.ceil(rows.length / PER)); if (page > pc) { page = pc; }
      list.innerHTML = rows.slice((page - 1) * PER, page * PER).map(function (a) {
        return '<li class="log-item"><span class="log-item__ico"><svg class="icon" aria-hidden="true"><use href="#' + (ICON[a.tipe] || "i-log") + '"/></svg></span><div><p>' + esc(a.teks) + "</p><small>" + esc(a.aktor) + " &middot; " + esc(a.peran) + " &middot; " + esc(a.waktu) + "</small></div></li>";
      }).join("") || '<li><p class="tbl-empty">Tidak ada catatan yang cocok.</p></li>';
      pager(pg, info, rows.length, page, PER, function (p) { page = p; render(); });
    }
    tabs.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { tab = b.dataset.f; page = 1; render(); } });
    q.addEventListener("input", function () { page = 1; render(); });
    $("#auExport").addEventListener("click", function () {
      download("audit-log-simevent.csv", ["Waktu,Jenis,Aktor,Peran,Kegiatan"].concat(filtered().map(function (a) { return [a.waktu, a.tipe, a.aktor, a.peran, a.teks].map(csvCell).join(","); })).join("\r\n"));
    });
    render();
  }

  /* =========================================================
     PENGATURAN
     ========================================================= */
  function pageSettings() {
    var tabs = $$("#setNav a"), panels = $$("[data-panel]");
    function showTab() {
      var name = (location.hash || "#platform").slice(1);
      if (!$("#panel-" + name)) { name = "platform"; }
      panels.forEach(function (p) { p.hidden = p.dataset.panel !== name; });
      tabs.forEach(function (a) { var on = a.dataset.tab === name; a.classList.toggle("is-active", on); if (on) { a.setAttribute("aria-current", "page"); } else { a.removeAttribute("aria-current"); } });
    }
    window.addEventListener("hashchange", showTab); showTab();

    var cats = st.settings.categories;
    function stats() {
      if (!$("#setStats")) { return; }
      var names = Object.keys(cats), on = names.filter(function (k) { return cats[k]; }).length;
      $("#setStats").innerHTML = [["Biaya platform", st.settings.feePct + "%", "dari tiket berbayar"], ["Kategori aktif", on, "dari " + names.length + " kategori"], ["Akun dibekukan", users().filter(function (u) { return u.status === "dibekukan"; }).length, "tidak bisa masuk"]].map(function (s) {
        return '<article class="card stat"><p class="stat__label">' + s[0] + '</p><p class="stat__value">' + s[1] + '</p><p class="stat__note stat__note--muted">' + s[2] + "</p></article>";
      }).join("");
    }

    /* Platform */
    var pf = $("#platformForm");
    pf.fee.value = st.settings.feePct; pf.approval.setAttribute("aria-checked", String(!!st.settings.approvalRequired));
    pf.approval.addEventListener("click", function () { this.setAttribute("aria-checked", this.getAttribute("aria-checked") === "true" ? "false" : "true"); });
    var pfBtn = $("#pfSave"), pfState = $("#pfState");
    function pfDirty() {
      var d = parseFloat(pf.fee.value) !== st.settings.feePct || (pf.approval.getAttribute("aria-checked") === "true") !== !!st.settings.approvalRequired;
      pfBtn.disabled = !d; pfState.textContent = d ? "Ada perubahan belum disimpan" : "Belum ada perubahan";
    }
    function pfLast() {
      var a = st.activity.filter(function (x) { return x.tipe === "pengaturan" && /^Pengaturan platform diubah/.test(x.teks); })[0];
      $("#pfLastTxt").textContent = a ? "Terakhir diubah oleh " + a.aktor + " · " + S.ago(a.ts) : "Belum ada perubahan tercatat";
    }
    pf.fee.addEventListener("input", pfDirty); pf.approval.addEventListener("click", pfDirty); pfDirty(); pfLast();
    pf.addEventListener("submit", function (ev) {
      ev.preventDefault(); $$("small.err", pf).forEach(function (x) { x.remove(); });
      var fee = parseFloat(pf.fee.value);
      if (!(fee >= 0 && fee <= 20)) { var m = document.createElement("small"); m.className = "err"; m.textContent = "Biaya platform harus antara 0 dan 20 persen."; pf.fee.closest(".sp-row").appendChild(m); pf.fee.focus(); return; }
      var need = pf.approval.getAttribute("aria-checked") === "true", changes = [];
      if (fee !== st.settings.feePct) { changes.push("biaya platform " + fee + "%"); }
      if (need !== st.settings.approvalRequired) { changes.push("persetujuan event " + (need ? "wajib" : "tidak wajib")); }
      st.settings.feePct = fee; st.settings.approvalRequired = need; S.save();
      if (changes.length) { S.log("pengaturan", "Pengaturan platform diubah: " + changes.join(", "), ADMIN, "Admin Platform"); }
      toast("Pengaturan platform disimpan. Dashboard ketua panitia memakai aturan baru."); stats(); pfDirty(); pfLast();
    });

    /* Kategori */
    function renderCats() {
      $("#catList").innerHTML = Object.keys(cats).map(function (k, i) {
        return '<li class="tog"><div><b id="ct-' + i + '">' + esc(k) + '</b><small>' + (cats[k] ? "Tampil sebagai pilihan jenis saat ketua panitia membuat event." : "Disembunyikan dari pilihan ketua panitia.") + '</small></div><button type="button" class="switch" role="switch" aria-labelledby="ct-' + i + '" aria-checked="' + !!cats[k] + '" data-cat="' + esc(k) + '"><i></i></button></li>';
      }).join("");
      stats();
    }
    $("#catList").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-cat]"); if (!b) { return; }
      var k = b.dataset.cat, on = !cats[k];
      if (!on && Object.keys(cats).filter(function (x) { return cats[x]; }).length <= 1) { toast("Minimal satu kategori harus aktif."); return; }
      cats[k] = on; S.save(); S.log("pengaturan", 'Kategori "' + k + '" ' + (on ? "diaktifkan" : "dinonaktifkan"), ADMIN, "Admin Platform"); renderCats();
    });
    $("#catForm").addEventListener("submit", function (ev) {
      ev.preventDefault(); var f = ev.target, nama = f.nama.value.trim(); $$("small.err", f).forEach(function (x) { x.remove(); });
      var msg = nama.length < 3 ? "Nama kategori minimal 3 karakter." : Object.keys(cats).some(function (k) { return k.toLowerCase() === nama.toLowerCase(); }) ? "Kategori sudah ada." : "";
      if (msg) { var m = document.createElement("small"); m.className = "err"; m.textContent = msg; f.nama.closest(".field").appendChild(m); f.nama.focus(); return; }
      cats[nama] = true; S.save(); S.log("pengaturan", 'Kategori "' + nama + '" ditambahkan', ADMIN, "Admin Platform"); f.reset(); renderCats(); toast("Kategori ditambahkan.");
    });
    renderCats();

    /* Notifikasi */
    var NOTIF = window.SIMEVENT_DEMO.admin_notifications;
    $("#togList").innerHTML = NOTIF.map(function (n) {
      return '<li class="tog"><div><b id="tg-' + n[0] + '">' + n[1] + "</b><small>" + n[2] + '</small></div><button type="button" class="switch" role="switch" aria-labelledby="tg-' + n[0] + '" aria-checked="' + !!st.settings.notif[n[0]] + '" data-k="' + n[0] + '"><i></i></button></li>';
    }).join("");
    $("#togList").addEventListener("click", function (ev) {
      var b = ev.target.closest(".switch"); if (!b) { return; }
      var on = b.getAttribute("aria-checked") !== "true"; b.setAttribute("aria-checked", String(on)); st.settings.notif[b.dataset.k] = on; S.save(); toast("Pengaturan notifikasi disimpan.");
    });

    /* Profil & kata sandi */
    var pw = { lama: $("#pwLama"), baru: $("#pwBaru"), ulang: $("#pwUlang") };
    function pwState() {
      var b = pw.baru.value, r = { len: b.length >= 12, mix: /[a-z]/.test(b) && /[A-Z]/.test(b) && /\d/.test(b), old: b.length > 0 && b !== pw.lama.value, same: b.length > 0 && b === pw.ulang.value };
      $$("#pwRules li").forEach(function (li) { var ok = r[li.dataset.rule]; li.classList.toggle("is-ok", ok); li.querySelector("i").textContent = ok ? "✓" : "•"; });
      return r;
    }
    ["lama", "baru", "ulang"].forEach(function (k) { pw[k].addEventListener("input", pwState); }); pwState();
    $$("[data-eye]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var inp = btn.parentNode.querySelector("input"), show = inp.type === "password"; inp.type = show ? "text" : "password";
        btn.setAttribute("aria-pressed", String(show)); btn.setAttribute("aria-label", show ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"); btn.classList.toggle("is-on", show);
      });
    });
    $("#pwForm").addEventListener("submit", function (ev) {
      ev.preventDefault(); $$("small.err", ev.target).forEach(function (x) { x.remove(); });
      var r = pwState(), msg = !pw.lama.value ? "Isi kata sandi saat ini." : !(r.len && r.mix && r.old && r.same) ? "Kata sandi baru belum memenuhi semua syarat." : "";
      if (msg) { var s = document.createElement("small"); s.className = "err"; s.textContent = msg; $("#pwRules").after(s); return; }
      ev.target.reset(); pwState(); S.log("pengaturan", "Admin mengganti kata sandi", ADMIN, "Admin Platform"); toast("Kata sandi diubah. Ini data contoh, belum tersimpan ke database.");
    });
  }

  /* ---------- Profil admin: foto (dengan crop), nama, email. Data contoh di localStorage ---------- */
  var PKEY = "simevent_admin_profile_v1";
  function getProfile() { try { return JSON.parse(localStorage.getItem(PKEY)) || {}; } catch (e) { return {}; } }
  function setProfile(p) { try { localStorage.setItem(PKEY, JSON.stringify(p)); return true; } catch (e) { return false; } }
  function adminInitials(n) { return (n || "A").trim().split(/\s+/).slice(0, 2).map(function (w) { return w.charAt(0).toUpperCase(); }).join(""); }
  function curName() { return getProfile().nama || ADMIN; }
  function applyProfile() {
    var pr = getProfile();
    $$(".js-adm-ava").forEach(function (el) {
      el.style.backgroundImage = pr.foto ? 'url("' + pr.foto + '")' : "";
      el.textContent = pr.foto ? "" : adminInitials(curName());
    });
    if (pr.nama) { $$(".js-adm-name").forEach(function (el) { el.textContent = pr.nama; }); }
  }
  function initAccount() {
    var msg = $("#profMsg"), fIn = $("#profFoto"), em = $("#emailForm"), emIn = $("#pfEmailAdm");
    var modal = $("#profileCropModal"), vp = $("#profileCropViewport"), img = $("#profileCropImage"), zoom = $("#profileCropZoom"), okBtn = $("#profileCropSave"), noBtn = $("#profileCropCancel");
    var src = null, url = null, scale = 1, left = 0, top = 0, drag = null;
    function say(t) { msg.innerHTML = t ? '<small class="err">' + t + "</small>" : ""; }
    function fieldErr(input, text) {
      var m = document.createElement("small"); m.className = "err"; m.textContent = text;
      input.closest(".field").appendChild(m); input.focus();
    }
    emIn.value = getProfile().email || emIn.defaultValue;
    var nm = $("#nameForm"), nmIn = $("#pfNamaAdm");
    nmIn.value = getProfile().nama || nmIn.defaultValue;
    nm.addEventListener("submit", function (ev) {
      ev.preventDefault(); $$("small.err", nm).forEach(function (x) { x.remove(); });
      var v = nmIn.value.trim().replace(/\s+/g, " "), p = getProfile();
      if (v.length < 3) { fieldErr(nmIn, "Nama minimal 3 karakter."); return; }
      if (v === (p.nama || nmIn.defaultValue)) { toast("Nama tidak berubah."); return; }
      p.nama = v; setProfile(p); applyProfile(); S.log("pengaturan", "Admin mengganti nama akun", ADMIN, "Admin Platform"); toast("Nama admin diperbarui.");
    });

    function layout(keep) {
      if (!img.naturalWidth) { return; }
      var size = vp.clientWidth; if (!size) { return; }
      var cx = keep && scale ? (size / 2 - left) / scale : null, cy = keep && scale ? (size / 2 - top) / scale : null;
      scale = Math.max(size / img.naturalWidth, size / img.naturalHeight) * Number(zoom.value);
      var w = img.naturalWidth * scale, h = img.naturalHeight * scale;
      img.style.width = w + "px"; img.style.height = h + "px";
      left = cx === null ? (size - w) / 2 : size / 2 - cx * scale; top = cy === null ? (size - h) / 2 : size / 2 - cy * scale;
      left = Math.min(0, Math.max(size - w, left)); top = Math.min(0, Math.max(size - h, top));
      img.style.left = left + "px"; img.style.top = top + "px";
    }
    function closeCrop() {
      modal.hidden = true; modal.setAttribute("aria-hidden", "true"); drag = null; src = null; fIn.value = "";
      if (url) { URL.revokeObjectURL(url); url = null; }
      img.removeAttribute("src"); fIn.focus();
    }
    fIn.addEventListener("change", function () {
      var f = fIn.files[0]; say(""); if (!f) { return; }
      if (!/^image\/(png|jpe?g|webp)$/.test(f.type)) { say("Pilih foto JPG, PNG, atau WebP."); fIn.value = ""; return; }
      if (f.size > 5 * 1024 * 1024) { say("Ukuran foto maksimal 5 MB."); fIn.value = ""; return; }
      src = f; zoom.value = "1"; url = URL.createObjectURL(f);
      modal.hidden = false; modal.setAttribute("aria-hidden", "false");
      img.onload = function () { requestAnimationFrame(function () { layout(false); okBtn.focus(); }); };
      img.onerror = function () { say("Foto tidak dapat dibuka. Coba file gambar lain."); closeCrop(); };
      img.src = url;
    });
    zoom.addEventListener("input", function () { layout(true); });
    window.addEventListener("resize", function () { if (!modal.hidden) { layout(true); } });
    vp.addEventListener("pointerdown", function (e) { if (!src) { return; } e.preventDefault(); vp.setPointerCapture(e.pointerId); drag = { x: e.clientX, y: e.clientY, l: left, t: top }; });
    vp.addEventListener("pointermove", function (e) {
      if (!drag) { return; }
      var size = vp.clientWidth;
      left = Math.min(0, Math.max(size - img.clientWidth, drag.l + e.clientX - drag.x)); top = Math.min(0, Math.max(size - img.clientHeight, drag.t + e.clientY - drag.y));
      img.style.left = left + "px"; img.style.top = top + "px";
    });
    vp.addEventListener("pointerup", function () { drag = null; });
    vp.addEventListener("pointercancel", function () { drag = null; });
    noBtn.addEventListener("click", closeCrop);
    modal.addEventListener("click", function (e) { if (e.target === modal) { closeCrop(); } });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !modal.hidden) { closeCrop(); } });
    okBtn.addEventListener("click", function () {
      if (!src || !img.naturalWidth) { return; }
      var size = vp.clientWidth, c = document.createElement("canvas"); c.width = c.height = 384;
      c.getContext("2d").drawImage(img, -left / scale, -top / scale, size / scale, size / scale, 0, 0, 384, 384);
      var p = getProfile(); p.foto = c.toDataURL("image/jpeg", .85);
      if (!setProfile(p)) { say("Foto gagal disimpan di browser."); closeCrop(); return; }
      closeCrop(); applyProfile(); S.log("pengaturan", "Admin mengganti foto profil", ADMIN, "Admin Platform"); toast("Foto profil diperbarui.");
    });

    $("#profFotoDel").addEventListener("click", function () {
      var p = getProfile(); if (!p.foto) { say("Belum ada foto yang bisa dihapus."); return; }
      delete p.foto; setProfile(p); say(""); applyProfile(); S.log("pengaturan", "Admin menghapus foto profil", ADMIN, "Admin Platform"); toast("Foto profil dihapus.");
    });
    em.addEventListener("submit", function (ev) {
      ev.preventDefault(); $$("small.err", em).forEach(function (x) { x.remove(); });
      var v = emIn.value.trim(), p = getProfile();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) { fieldErr(emIn, "Format email belum benar."); return; }
      if (v === (p.email || emIn.defaultValue)) { toast("Email tidak berubah."); return; }
      p.email = v; setProfile(p); S.log("pengaturan", "Admin mengganti email akun", ADMIN, "Admin Platform"); toast("Email diubah. Ini data contoh, belum tersimpan ke database.");
    });
  }

  var pages = { admin_dashboard: pageDashboard, admin_users: pageUsers, admin_events: pageEvents, admin_support: pageSupport, admin_finance: pageFinance, admin_audit: pageAudit, admin_settings: pageSettings };
  applyProfile();
  var fn = pages[document.body.dataset.page];
  if (fn) { fn(); }
  if (document.body.dataset.page === "admin_settings") { initAccount(); }
})();
