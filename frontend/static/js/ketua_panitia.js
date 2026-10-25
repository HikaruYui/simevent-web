/* =========================================================
   SIMEVENT - Dashboard Ketua Panitia (EO)
   Perilaku halaman: grafik SVG, tabel, filter, dialog.
   Bergantung pada ketua_panitia_data.js (data contoh).
   ========================================================= */
(function () {
  "use strict";

  var E = window.EO;
  var NS = "http://www.w3.org/2000/svg";

  /* ---------- Helper umum ---------- */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function num(n) { return Number(n).toLocaleString("id-ID"); }
  function rp(n) { return n === 0 ? "Gratis" : "Rp " + num(n); }
  function rpShort(n) {
    if (n >= 1e6) { return (n / 1e6).toFixed(1).replace(".0", "").replace(".", ",") + " jt"; }
    if (n >= 1e3) { return Math.round(n / 1e3) + " rb"; }
    return String(n);
  }
  function fmtDate(s) {
    return new Date(s + "T00:00:00Z").toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  }
  function sum(arr, f) { return arr.reduce(function (t, x) { return t + f(x); }, 0); }
  function el(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (parent) { parent.appendChild(n); }
    return n;
  }
  function chip(status, label) { return '<span class="chip chip--' + status + '"><i></i>' + esc(label) + "</span>"; }
  function eventById(id) { return E.events.filter(function (e) { return e.id === id; })[0]; }

  var toastTimer;
  function toast(msg) {
    var t = $("#toast");
    if (!t) { return; }
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 4200);
  }

  /* ---------- Grafik ---------- */
  function niceMax(m) {
    if (m <= 0) { return 4; }
    var p = Math.pow(10, Math.floor(Math.log10(m)));
    var steps = [1, 1.2, 1.6, 2, 2.4, 3, 4, 5, 6, 8, 10];
    for (var i = 0; i < steps.length; i++) {
      var v = steps[i] * p;
      if (v >= m && (m >= 10 || v % 2 === 0)) { return v; }
    }
    return 10 * p;
  }

  function scaffold(host, W, H, m, yMax, labels, fmtY) {
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", tabindex: "0", preserveAspectRatio: "none" });
    var inW = W - m.l - m.r, inH = H - m.t - m.b;
    var grid = el("g", { "class": "ch-grid" }, svg), axis = el("g", { "class": "ch-axis" }, svg);
    [0, 0.5, 1].forEach(function (f) {
      var y = m.t + inH * (1 - f);
      if (f > 0) { el("line", { x1: m.l, x2: W - m.r, y1: y, y2: y }, grid); }
      var t = el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end" }, axis);
      t.textContent = fmtY(yMax * f);
    });
    var base = el("g", { "class": "ch-base" }, svg);
    el("line", { x1: m.l, x2: W - m.r, y1: m.t + inH, y2: m.t + inH }, base);
    return { svg: svg, axis: axis, inW: inW, inH: inH };
  }

  function srTable(host, name, labels, values, fmt) {
    var t = document.createElement("table");
    t.className = "sr-only";
    t.innerHTML = "<caption>" + esc(name) + "</caption><thead><tr><th>Titik</th><th>Nilai</th></tr></thead><tbody>" +
      labels.map(function (l, i) { return "<tr><td>" + esc(l) + "</td><td>" + esc(fmt(values[i])) + "</td></tr>"; }).join("") + "</tbody>";
    host.appendChild(t);
  }

  function attachHover(host, svg, W, count, xAt, show, hide) {
    var cur = -1;
    function idxFromEvent(ev) {
      var r = svg.getBoundingClientRect();
      var x = (ev.clientX - r.left) * (W / r.width);
      var best = 0, bd = 1e9;
      for (var i = 0; i < count; i++) {
        var d = Math.abs(xAt(i) - x);
        if (d < bd) { bd = d; best = i; }
      }
      return best;
    }
    svg.addEventListener("pointermove", function (ev) { cur = idxFromEvent(ev); show(cur); });
    svg.addEventListener("pointerleave", function () { hide(); });
    svg.addEventListener("focus", function () { cur = count - 1; show(cur); });
    svg.addEventListener("blur", hide);
    svg.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowRight") { cur = Math.min(count - 1, cur + 1); show(cur); ev.preventDefault(); }
      if (ev.key === "ArrowLeft") { cur = Math.max(0, cur - 1); show(cur); ev.preventDefault(); }
      if (ev.key === "Escape") { hide(); }
    });
  }

  function lineChart(host, o) {
    function draw() {
      host.innerHTML = "";
      var W = Math.max(host.clientWidth, 280), H = Math.max(host.clientHeight, 220);
      var m = { l: 44, r: 18, t: 18, b: 32 };
      var fmt = o.fmt || num, fmtY = o.fmtY || function (v) { return num(Math.round(v)); };
      var yMax = niceMax(Math.max.apply(null, o.values));
      var s = scaffold(host, W, H, m, yMax, o.labels, fmtY);
      var n = o.values.length;
      function xAt(i) { return m.l + (n === 1 ? s.inW / 2 : i * s.inW / (n - 1)); }
      function yAt(v) { return m.t + s.inH * (1 - v / yMax); }

      o.labels.forEach(function (l, i) {
        var t = el("text", { x: xAt(i), y: H - 8, "text-anchor": i === 0 ? "start" : i === n - 1 ? "end" : "middle" }, s.axis);
        t.textContent = l;
      });
      el("path", { "class": "ch-line", d: o.values.map(function (v, i) { return (i ? "L" : "M") + xAt(i).toFixed(1) + " " + yAt(v).toFixed(1); }).join(" ") }, s.svg);

      var cross = el("line", { "class": "ch-cross", y1: m.t, y2: m.t + s.inH, visibility: "hidden" }, s.svg);
      var dot = el("circle", { "class": "ch-dot", r: 5, visibility: "hidden" }, s.svg);
      var tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true;

      s.svg.setAttribute("aria-label", o.name + ": " + o.labels.map(function (l, i) { return l + " " + fmt(o.values[i]); }).join(", "));
      host.appendChild(s.svg); host.appendChild(tip);
      srTable(host, o.name, o.labels, o.values, fmt);

      attachHover(host, s.svg, W, n, xAt,
        function (i) {
          var x = xAt(i), y = yAt(o.values[i]);
          cross.setAttribute("x1", x); cross.setAttribute("x2", x); cross.setAttribute("visibility", "visible");
          dot.setAttribute("cx", x); dot.setAttribute("cy", y); dot.setAttribute("visibility", "visible");
          tip.innerHTML = "<b>" + esc(fmt(o.values[i])) + "</b>" + esc(o.labels[i]) + " &middot; " + esc(o.name);
          tip.hidden = false;
          var sx = x * (host.clientWidth / W), sy = y * (host.clientHeight / H);
          tip.style.left = Math.min(Math.max(sx, 70), host.clientWidth - 70) + "px";
          tip.style.top = (sy - 12) + "px";
        },
        function () { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); tip.hidden = true; });
    }
    host.__draw = draw; draw();
    if (!host.__ro && window.ResizeObserver) { host.__ro = new ResizeObserver(function () { host.__draw(); }); host.__ro.observe(host); }
  }

  function barChart(host, o) {
    function draw() {
      host.innerHTML = "";
      var W = Math.max(host.clientWidth, 280), H = Math.max(host.clientHeight, 220);
      var m = { l: 52, r: 12, t: 18, b: 32 };
      var fmt = o.fmt || num, fmtY = o.fmtY || num;
      var yMax = niceMax(Math.max.apply(null, o.values));
      var s = scaffold(host, W, H, m, yMax, o.labels, fmtY);
      var n = o.values.length, slot = s.inW / n, bw = Math.min(56, slot * 0.56);
      function xAt(i) { return m.l + slot * (i + 0.5); }
      var bars = o.values.map(function (v, i) {
        var h = Math.max(2, s.inH * v / yMax), x = xAt(i) - bw / 2, y = m.t + s.inH - h, r = Math.min(4, bw / 2, h);
        var p = el("path", { "class": "ch-bar", d: "M" + x + " " + (y + h) + "V" + (y + r) + "Q" + x + " " + y + " " + (x + r) + " " + y + "H" + (x + bw - r) + "Q" + (x + bw) + " " + y + " " + (x + bw) + " " + (y + r) + "V" + (y + h) + "Z" }, s.svg);
        var t = el("text", { x: xAt(i), y: H - 8, "text-anchor": "middle" }, s.axis); t.textContent = o.labels[i];
        return p;
      });
      /* label langsung hanya pada batang terakhir */
      var li = n - 1, lt = el("text", { x: xAt(li), y: m.t + s.inH * (1 - o.values[li] / yMax) - 8, "text-anchor": "middle", style: "font:800 13px var(--font-head);fill:var(--olive)" }, s.svg);
      lt.textContent = fmtY(o.values[li]);
      var tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true;
      s.svg.setAttribute("aria-label", o.name + ": " + o.labels.map(function (l, i) { return l + " " + fmt(o.values[i]); }).join(", "));
      host.appendChild(s.svg); host.appendChild(tip);
      srTable(host, o.name, o.labels, o.values, fmt);
      var prev = -1;
      attachHover(host, s.svg, W, n, xAt,
        function (i) {
          if (prev >= 0) { bars[prev].classList.remove("is-last"); }
          bars[i].classList.add("is-last"); prev = i;
          tip.innerHTML = "<b>" + esc(fmt(o.values[i])) + "</b>" + esc(o.labels[i]) + " &middot; " + esc(o.name);
          tip.hidden = false;
          var sx = xAt(i) * (host.clientWidth / W);
          tip.style.left = Math.min(Math.max(sx, 70), host.clientWidth - 70) + "px";
          tip.style.top = (m.t + s.inH * (1 - o.values[i] / yMax)) * (host.clientHeight / H) - 16 + "px";
        },
        function () { if (prev >= 0) { bars[prev].classList.remove("is-last"); prev = -1; } tip.hidden = true; });
    }
    host.__draw = draw; draw();
    if (!host.__ro && window.ResizeObserver) { host.__ro = new ResizeObserver(function () { host.__draw(); }); host.__ro.observe(host); }
  }

  function sparkline(host, values) {
    function draw() {
      host.innerHTML = "";
      var W = Math.max(host.clientWidth, 120), H = Math.max(host.clientHeight, 60), pad = 6;
      var min = Math.min.apply(null, values), max = Math.max.apply(null, values), n = values.length;
      function xAt(i) { return pad + i * (W - 2 * pad) / (n - 1); }
      function yAt(v) { return pad + (H - 2 * pad) * (1 - (v - min) / ((max - min) || 1)); }
      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, "aria-hidden": "true", preserveAspectRatio: "none" });
      el("path", { "class": "ch-spark", d: values.map(function (v, i) { return (i ? "L" : "M") + xAt(i).toFixed(1) + " " + yAt(v).toFixed(1); }).join(" ") }, svg);
      el("circle", { "class": "ch-spark-dot", cx: xAt(n - 1), cy: yAt(values[n - 1]), r: 4 }, svg);
      host.appendChild(svg);
    }
    host.__draw = draw; draw();
    if (!host.__ro && window.ResizeObserver) { host.__ro = new ResizeObserver(function () { host.__draw(); }); host.__ro.observe(host); }
  }

  function growth(arr) {
    var a = arr[arr.length - 1], b = arr[arr.length - 2];
    var p = (a / b - 1) * 100;
    return (p >= 0 ? "+" : "") + p.toFixed(2) + "%";
  }

  /* ---------- Dialog "Event baru" (dipakai semua halaman) ---------- */
  var onEventsChanged = function () {};
  function initNewEvent() {
    var dlg = $("#newEventDlg"); if (!dlg) { return; }
    var form = $("form", dlg);
    /* Jenis event mengikuti kategori aktif yang diatur Admin (Pengaturan > Kategori) */
    if (window.SIM && form.jenis) {
      var cats = Object.keys(SIM.state.settings.categories).filter(function (k) { return SIM.state.settings.categories[k]; });
      if (cats.length) { form.jenis.innerHTML = cats.map(function (c) { return "<option>" + esc(c) + "</option>"; }).join(""); }
    }
    $$("[data-open-new-event]").forEach(function (b) {
      b.addEventListener("click", function () { form.reset(); $$("small", form).forEach(function (s) { s.remove(); }); dlg.showModal(); $("#neNama").focus(); });
    });
    $$("[data-close]", dlg).forEach(function (b) { b.addEventListener("click", function () { dlg.close(); }); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) { dlg.close(); } });

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      $$("small", form).forEach(function (s) { s.remove(); });
      var v = {
        nama: form.nama.value.trim(), jenis: form.jenis.value, tanggal: form.tanggal.value,
        lokasi: form.lokasi.value.trim(), kuota: parseInt(form.kuota.value, 10), harga: parseInt(form.harga.value || "0", 10)
      };
      var errs = {};
      if (v.nama.length < 3) { errs.nama = "Nama event minimal 3 karakter."; }
      if (!v.tanggal) { errs.tanggal = "Pilih tanggal event."; }
      if (!v.lokasi) { errs.lokasi = "Isi lokasi event."; }
      if (!(v.kuota >= 1)) { errs.kuota = "Kuota minimal 1."; }
      if (!(v.harga >= 0)) { errs.harga = "Harga tidak boleh negatif."; }
      Object.keys(errs).forEach(function (k) {
        var s = document.createElement("small"); s.textContent = errs[k];
        form[k].closest(".field").appendChild(s);
      });
      if (Object.keys(errs).length) { var f = $("small", form); if (f) { f.closest(".field").querySelector("input,select").focus(); } return; }

      var S = window.SIM, needApproval = !S || S.state.settings.approvalRequired;
      var status = needApproval ? "diajukan" : "mendatang";
      var id = Math.max.apply(null, E.events.map(function (e) { return e.id; }).concat([200])) + 1;
      var imgInput = form.querySelector("#neGambar");
      var gambarUrl = imgInput && imgInput.files[0] ? URL.createObjectURL(imgInput.files[0]) : "/static/img/default-event.jpg";
      E.events.push({ id: id, nama: v.nama, gambarUrl: gambarUrl, jenis: v.jenis, tanggal: v.tanggal, lokasi: v.lokasi, kuota: v.kuota, terjual: 0, harga: v.harga, status: status, hadir: 0, pendapatan: 0 });
      var teks = needApproval ? "Event \"" + v.nama + "\" diajukan, menunggu persetujuan admin" : "Event baru \"" + v.nama + "\" dibuat";
      E.activity.unshift({ tipe: "event", teks: teks, waktu: "Baru saja" });
      if (S) {
        S.state.newEvents.push({ id: id, nama: v.nama, jenis: v.jenis, tanggal: v.tanggal, lokasi: v.lokasi, kuota: v.kuota, harga: v.harga, status: status });
        S.log("event", teks, "Budi Santoso", "Ketua Panitia", { eo: true });
      }
      dlg.close();
      onEventsChanged();
      toast(needApproval ? "Event \"" + v.nama + "\" dikirim ke admin untuk disetujui. Data contoh, belum tersimpan ke database." : "Event \"" + v.nama + "\" ditambahkan. Ini data contoh, belum tersimpan ke database.");
    });
  }

  /* ---------- Halaman: Dashboard ---------- */
  function pageDashboard() {
    function kpis() {
      $("#kpiPendapatan").textContent = num(sum(E.events, function (e) { return e.pendapatan; }));
      $("#kpiTiket").textContent = num(sum(E.events, function (e) { return e.terjual; }));
      $("#deltaPendapatan").textContent = growth(E.monthly.pendapatan);
      $("#deltaTiket").textContent = growth(E.monthly.tiket);
      $("#evBerlangsung").textContent = E.events.filter(function (e) { return e.status === "berlangsung"; }).length;
      $("#evMendatang").textContent = E.events.filter(function (e) { return e.status === "mendatang"; }).length;
      $("#tkDiaudit").textContent = E.tickets.filter(function (t) { return t.status === "diaudit"; }).length;
      $("#tkSelesai").textContent = E.tickets.filter(function (t) { return t.status === "selesai"; }).length;
    }
    kpis();
    sparkline($("#sparkPendapatan"), E.monthly.pendapatan);
    sparkline($("#sparkTiket"), E.monthly.tiket);

    /* grafik kehadiran */
    var selEvent = $("#selEvent"), selMetrik = $("#selMetrik"), plot = $("#attendancePlot");
    E.events.filter(function (e) { return e.status === "berlangsung" || e.status === "selesai"; }).forEach(function (e) {
      var o = document.createElement("option"); o.value = e.id; o.textContent = e.nama; selEvent.appendChild(o);
    });
    Object.keys(E.metrik).forEach(function (k) {
      var o = document.createElement("option"); o.value = k; o.textContent = E.metrik[k].nama; selMetrik.appendChild(o);
    });
    function drawChart() {
      var id = parseInt(selEvent.value, 10), k = selMetrik.value, m = E.metrik[k];
      lineChart(plot, { labels: m.labels, values: E.series(id, k), name: m.nama, fmt: function (v) { return num(v) + " orang"; } });
    }
    selEvent.addEventListener("change", drawChart);
    selMetrik.addEventListener("change", drawChart);
    drawChart();

    /* log aktivitas */
    var ICON = { daftar: "i-user", hadir: "i-check", bayar: "i-card", support: "i-help", event: "i-calendar" };
    var logCard = $("#logCard"), list = $("#logList"), toggle = $("#logToggle"), expanded = false;
    function renderLog() {
      var items = expanded ? E.activity : E.activity.slice(0, 4);
      list.innerHTML = items.map(function (a) {
        return '<li class="log-item"><span class="log-item__ico"><svg class="icon" aria-hidden="true"><use href="#' + (ICON[a.tipe] || "i-calendar") + '"/></svg></span><div><p>' + esc(a.teks) + "</p><small>" + esc(a.waktu) + "</small></div></li>";
      }).join("");
      if (toggle && toggle.tagName === "BUTTON") {
        toggle.textContent = expanded ? "Ringkas ←" : "Lihat semua →";
        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      }
      if (logCard) { logCard.classList.toggle("is-expanded", expanded); }
    }
    if (toggle && toggle.tagName === "BUTTON") {
      toggle.addEventListener("click", function () { expanded = !expanded; renderLog(); });
    }
    renderLog();

    onEventsChanged = function () { kpis(); renderLog(); };
  }

  /* ---------- Halaman: Event ---------- */
  function pageEvent() {
    var tbody = $("#evBody"), tabsEl = $("#evTabs"), q = $("#evSearch"), filter = "semua";
    var dlg = $("#detailDlg");
    var TABS = [["semua", "Semua"], ["berlangsung", "Sedang Berlangsung"], ["mendatang", "Mendatang"], ["selesai", "Selesai"]];
    var TABS_EXTRA = [["diajukan", "Menunggu Persetujuan"], ["ditolak", "Ditolak"], ["ditangguhkan", "Ditangguhkan"]];
    function counts() {
      return TABS.concat(TABS_EXTRA).map(function (t) { return [t[0], t[1], t[0] === "semua" ? E.events.length : E.events.filter(function (e) { return e.status === t[0]; }).length]; })
        .filter(function (t, i) { return i < TABS.length || t[2] > 0; });   /* tab tambahan hanya muncul bila ada isinya */
    }
    function render() {
      tabsEl.innerHTML = counts().map(function (t) {
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === filter ? "is-active" : "") + '" aria-pressed="' + (t[0] === filter) + '">' + esc(t[1]) + "<span>" + t[2] + "</span></button>";
      }).join("");
      var term = q.value.trim().toLowerCase();
      var rows = E.events.filter(function (e) {
        return (filter === "semua" || e.status === filter) && (!term || (e.nama + " " + e.jenis + " " + e.lokasi).toLowerCase().indexOf(term) !== -1);
      });
      if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6"><p class="tbl-empty">Tidak ada event yang cocok.</p></td></tr>'; return; }
      tbody.innerHTML = rows.map(function (e) {
        var pct = Math.min(100, Math.round(e.terjual / e.kuota * 100));
        return "<tr><td><span class=\"cell-title\">" + esc(e.nama) + '</span><span class="cell-sub">' + esc(e.jenis) + " &middot; " + esc(e.lokasi) + "</span></td>" +
          "<td>" + fmtDate(e.tanggal) + "</td>" +
          '<td><div class="meter"><div class="meter__bar" role="img" aria-label="' + e.terjual + " dari " + e.kuota + ' kuota"><i style="width:' + pct + '%"></i></div><small>' + e.terjual + "/" + e.kuota + "</small></div></td>" +
          '<td class="num">' + rp(e.harga) + "</td><td>" + chip(e.status, E.statusEvent[e.status]) + "</td>" +
          '<td><button type="button" class="btn btn--ghost" style="height:36px;padding:0 16px;font-size:13px" data-detail="' + e.id + '">Detail</button></td></tr>';
      }).join("");
    }
    tabsEl.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { filter = b.dataset.f; render(); } });
    q.addEventListener("input", render);
    tbody.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-detail]"); if (!b) { return; }
      var e = eventById(parseInt(b.dataset.detail, 10));
      $("#detailTitle").textContent = e.nama;
      $("#detailBody").innerHTML =
        "<dt>Jenis</dt><dd>" + esc(e.jenis) + "</dd><dt>Tanggal</dt><dd>" + fmtDate(e.tanggal) + "</dd><dt>Lokasi</dt><dd>" + esc(e.lokasi) + "</dd>" +
        "<dt>Status</dt><dd>" + chip(e.status, E.statusEvent[e.status]) + "</dd><dt>Tiket terjual</dt><dd>" + e.terjual + " dari " + e.kuota + " kuota</dd>" +
        "<dt>Hadir</dt><dd>" + e.hadir + " peserta</dd><dt>Harga tiket</dt><dd>" + rp(e.harga) + "</dd><dt>Pendapatan</dt><dd>" + (e.pendapatan ? "Rp " + num(e.pendapatan) : "Rp 0") + "</dd>" +
        (e.alasan ? "<dt>Catatan admin</dt><dd>" + esc(e.alasan) + "</dd>" : "");
      dlg.showModal();
    });
    $$("[data-close]", dlg).forEach(function (b) { b.addEventListener("click", function () { dlg.close(); }); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) { dlg.close(); } });
    onEventsChanged = render;
    render();
  }

  /* ---------- Halaman: Peserta ---------- */
  function pagePeserta() {
    var PER = 10, page = 1, rows = [];
    var q = $("#psSearch"), selE = $("#psEvent"), selS = $("#psStatus"), tbody = $("#psBody"), info = $("#psInfo"), prev = $("#psPrev"), next = $("#psNext"), pages = $("#psPage");
    E.events.forEach(function (e) { var o = document.createElement("option"); o.value = e.id; o.textContent = e.nama; selE.appendChild(o); });
    function filtered() {
      var term = q.value.trim().toLowerCase(), ev = selE.value, st = selS.value;
      return E.participants.filter(function (p) {
        return (!ev || String(p.eventId) === ev) && (!st || p.status === st) && (!term || (p.nama + " " + p.email).toLowerCase().indexOf(term) !== -1);
      });
    }
    function render() {
      rows = filtered();
      var pc = Math.max(1, Math.ceil(rows.length / PER)); if (page > pc) { page = pc; }
      var slice = rows.slice((page - 1) * PER, page * PER);
      tbody.innerHTML = slice.length ? slice.map(function (p) {
        var e = eventById(p.eventId);
        return "<tr><td>" + p.no + '</td><td><span class="cell-title">' + esc(p.nama) + '</span><span class="cell-sub">' + esc(p.email) + "</span></td><td>" + esc(e.nama) + "</td><td>" + fmtDate(p.terdaftar) + "</td><td>" + chip(p.status, p.status === "hadir" ? "Hadir" : "Terdaftar") + "</td></tr>";
      }).join("") : '<tr><td colspan="5"><p class="tbl-empty">Tidak ada peserta yang cocok.</p></td></tr>';
      var from = rows.length ? (page - 1) * PER + 1 : 0;
      info.textContent = "Menampilkan " + from + "–" + Math.min(page * PER, rows.length) + " dari " + num(rows.length) + " peserta";
      pages.textContent = "Hal. " + page + " / " + pc;
      prev.disabled = page <= 1; next.disabled = page >= pc;
    }
    [q, selE, selS].forEach(function (c) { c.addEventListener("input", function () { page = 1; render(); }); });
    prev.addEventListener("click", function () { page--; render(); });
    next.addEventListener("click", function () { page++; render(); });

    $("#psCsv").addEventListener("click", function () {
      function cell(v) {
        v = String(v);
        if (/^[=+\-@\t\r]/.test(v)) { v = "'" + v; }            /* cegah formula injection di Excel */
        return '"' + v.replace(/"/g, '""') + '"';
      }
      var head = ["No", "Nama", "Email", "Event", "Tanggal Daftar", "Status"];
      var lines = [head.map(cell).join(",")].concat(filtered().map(function (p) {
        return [p.no, p.nama, p.email, eventById(p.eventId).nama, p.terdaftar, p.status === "hadir" ? "Hadir" : "Terdaftar"].map(cell).join(",");
      }));
      var blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "peserta-simevent.csv";
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
      toast("CSV berisi " + num(filtered().length) + " peserta diunduh.");
    });
    render();
  }

  /* ---------- Halaman: Pendapatan ---------- */
  function pagePendapatan() {
    var total = sum(E.events, function (e) { return e.pendapatan; }), tiket = sum(E.events, function (e) { return e.terjual; });
    var top = E.events.slice().sort(function (a, b) { return b.pendapatan - a.pendapatan; });
    $("#pdTotal").textContent = "Rp " + num(total);
    $("#pdDelta").textContent = growth(E.monthly.pendapatan) + " dibanding bulan lalu";
    $("#pdAvg").textContent = "Rp " + num(Math.round(total / tiket));
    $("#pdTop").textContent = top[0].nama;
    $("#pdTopNote").textContent = "Rp " + num(top[0].pendapatan) + " (" + Math.round(top[0].pendapatan / total * 100) + "% dari total)";
    lineChart($("#pdChart"), { labels: E.monthly.labels, values: E.monthly.pendapatan, name: "Pendapatan", fmt: function (v) { return "Rp " + num(v); }, fmtY: rpShort });
    $("#pdBody").innerHTML = top.map(function (e) {
      var pct = Math.round(e.pendapatan / total * 100);
      return "<tr><td><span class=\"cell-title\">" + esc(e.nama) + '</span><span class="cell-sub">' + esc(e.jenis) + '</span></td><td class="num">' + e.terjual + '</td><td class="num">' + rp(e.harga) + '</td><td class="num"><b>Rp ' + num(e.pendapatan) + '</b></td><td><div class="meter"><div class="meter__bar" role="img" aria-label="' + pct + '% dari total"><i style="width:' + pct + '%"></i></div><small>' + pct + "%</small></div></td></tr>";
    }).join("");
    $("#pdFoot").innerHTML = '<tr><td><b>Total</b></td><td class="num"><b>' + tiket + '</b></td><td></td><td class="num"><b>Rp ' + num(total) + "</b></td><td></td></tr>";
  }

  /* ---------- Halaman: Support ---------- */
  function pageSupport() {
    var filter = "semua", tabsEl = $("#tkTabs"), list = $("#tkList");
    var TABS = [["semua", "Semua"], ["diaudit", "Sedang Diaudit"], ["selesai", "Selesai"]];
    function render() {
      tabsEl.innerHTML = TABS.map(function (t) {
        var c = t[0] === "semua" ? E.tickets.length : E.tickets.filter(function (x) { return x.status === t[0]; }).length;
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === filter ? "is-active" : "") + '" aria-pressed="' + (t[0] === filter) + '">' + t[1] + "<span>" + c + "</span></button>";
      }).join("");
      var rows = E.tickets.filter(function (t) { return filter === "semua" || t.status === filter; });
      list.innerHTML = rows.length ? rows.map(function (t) {
        var e = eventById(t.eventId);
        return '<li><details class="ticket"><summary><div><span class="ticket__title">' + esc(t.judul) + '</span><span class="ticket__meta">' + esc(t.id) + " &middot; " + esc(e.nama) + " &middot; " + fmtDate(t.tanggal) + "</span></div>" + chip(t.status, E.statusTiket[t.status]) +
          '<span class="ticket__chev" aria-hidden="true"><svg class="icon"><use href="#i-chev"/></svg></span></summary><div class="ticket__body"><p>' + esc(t.isi) + '</p><p class="ticket__meta">Dilaporkan oleh ' + esc(t.pelapor) + "</p>" + (t.balasan ? '<p class="ticket__reply"><b>Balasan admin:</b> ' + esc(t.balasan) + "</p>" : "") +
          (t.status === "diaudit" ? '<div class="ticket__actions"><button type="button" class="btn" data-done="' + esc(t.id) + '">Tandai selesai</button></div>' : "") + "</div></details></li>";
      }).join("") : '<li><p class="tbl-empty">Belum ada tiket.</p></li>';
    }
    tabsEl.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { filter = b.dataset.f; render(); } });
    list.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-done]"); if (!b) { return; }
      E.tickets.forEach(function (t) { if (t.id === b.dataset.done) { t.status = "selesai"; } });
      if (window.SIM) {
        var prev = SIM.state.tickets[b.dataset.done] || {};
        SIM.state.tickets[b.dataset.done] = { status: "selesai", balasan: prev.balasan || "" };
        SIM.log("support", "Tiket " + b.dataset.done + " ditandai selesai oleh Ketua Panitia", "Budi Santoso", "Ketua Panitia", { eo: true });
      }
      toast("Tiket " + b.dataset.done + " ditandai selesai. Ini data contoh, belum tersimpan ke database.");
      render();
    });
    render();
  }

/* ---------- Halaman: Log Aktivitas ---------- */
  function pageLog() {
    var ICON = { daftar: "i-user", hadir: "i-check", bayar: "i-card", support: "i-help", event: "i-calendar" };
    var TABS = [
      ["semua", "Semua"],
      ["daftar", "Pendaftaran"],
      ["hadir", "Kehadiran"],
      ["bayar", "Pembayaran"],
      ["event", "Event"],
      ["support", "Support"]
    ];
    var filter = "semua", tabsEl = $("#lgTabs"), listEl = $("#lgList"), q = $("#lgSearch");
    if (!tabsEl || !listEl) { return; }
    function render() {
      tabsEl.innerHTML = TABS.map(function (t) {
        var c = t[0] === "semua" ? E.activity.length : E.activity.filter(function (a) { return a.tipe === t[0]; }).length;
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === filter ? "is-active" : "") + '" aria-pressed="' + (t[0] === filter) + '">' + esc(t[1]) + "<span>" + c + "</span></button>";
      }).join("");
      var term = q ? q.value.trim().toLowerCase() : "";
      var rows = E.activity.filter(function (a) {
        return (filter === "semua" || a.tipe === filter) && (!term || (a.teks + " " + a.waktu).toLowerCase().indexOf(term) !== -1);
      });
      listEl.innerHTML = rows.length ? rows.map(function (a) {
        return '<li class="log-item"><span class="log-item__ico"><svg class="icon" aria-hidden="true"><use href="#' + (ICON[a.tipe] || "i-calendar") + '"/></svg></span><div><p>' + esc(a.teks) + "</p><small>" + esc(a.waktu) + "</small></div></li>";
      }).join("") : '<li><p class="tbl-empty">Tidak ada log aktivitas yang cocok.</p></li>';
    }
    tabsEl.addEventListener("click", function (ev) {
      var b = ev.target.closest("button[data-f]");
      if (b) { filter = b.dataset.f; render(); }
    });
    if (q) { q.addEventListener("input", render); }
    onEventsChanged = render;
    render();
  }

  /* ---------- Mulai ---------- */
  /* ---------- Halaman: Pengaturan ---------- */
  function pagePengaturan() {
    var PERAN = {
      lapangan:   { nama: "Panitia Lapangan", info: "Melihat daftar peserta dan melakukan check-in tiket saat acara. Bisa mengganti kata sandinya sendiri.",
                    poin: ["Melihat daftar peserta", "Check-in tiket", "Ganti kata sandi"] },
      dokumentasi:{ nama: "Tim Dokumentasi",  info: "Melihat event dan mengunggah foto kegiatan yang langsung muncul di akun peserta.",                      
                    poin: ["Melihat daftar event", "Unggah foto kegiatan ke peserta", "Ganti kata sandi"] }
    };
    var STATUS = { aktif: ["hadir", "Aktif"], tertunda: ["mendatang", "Menunggu"], ditangguhkan: ["selesai", "Ditangguhkan"] };
    var team = [
      { id: 1, nama: "Siti Rahma",       email: "siti.rahma@mail.com",   peran: "lapangan",    akses: "semua", status: "aktif",        terakhir: "Hari ini" },
      { id: 2, nama: "Rafi Hidayat",     email: "rafi.hidayat@mail.com", peran: "lapangan",    akses: [1, 2],  status: "aktif",        terakhir: "Kemarin" },
      { id: 3, nama: "Nabila Amalia",    email: "nabila.a@mail.com",     peran: "dokumentasi", akses: "semua", status: "aktif",        terakhir: "3 hari lalu" },
      { id: 4, nama: "Dimas Prakoso",    email: "dimas.p@mail.com",      peran: "dokumentasi", akses: [3],     status: "ditangguhkan", terakhir: "2 minggu lalu" }
    ];
    /* akun yang dibekukan Admin tidak bisa masuk: tampil sebagai ditangguhkan */
    if (window.SIM) { team.forEach(function (m) { var u = SIM.state.users[m.email]; if (u && u.status === "dibekukan") { m.status = "ditangguhkan"; } }); }
    var invites = [
      { id: 11, email: "putri.amelia@mail.com", peran: "lapangan",    kirim: "2 hari lalu", sisa: 5 },
      { id: 12, email: "agus.salim@mail.com",   peran: "dokumentasi", kirim: "6 hari lalu", sisa: 1 }
    ];
    var NOTIF = [
      { k: "daftar",  t: "Pendaftaran peserta baru",       d: "Setiap ada peserta yang mendaftar ke eventmu.", on: true },
      { k: "bayar",   t: "Pembayaran diterima",            d: "Ringkasan saat tiket berbayar terjual.",        on: true },
      { k: "support", t: "Balasan tiket support",          d: "Saat admin platform membalas atau menutup tiket.", on: true },
      { k: "h1",      t: "Pengingat H-1 event",            d: "Satu hari sebelum event dimulai.",              on: true },
      { k: "tim",     t: "Anggota tim bergabung atau keluar", d: "Saat undangan diterima atau akses dicabut.", on: false }
    ];

    /* ----- Tab (hash) ----- */
    var tabs = $$("#setNav a"), panels = $$("[data-panel]");
    function showTab() {
      var name = (location.hash || "#tim").slice(1);
      if (!$("#panel-" + name)) { name = "tim"; }
      panels.forEach(function (p) { p.hidden = p.dataset.panel !== name; });
      tabs.forEach(function (a) {
        var on = a.dataset.tab === name;
        a.classList.toggle("is-active", on);
        if (on) { a.setAttribute("aria-current", "page"); } else { a.removeAttribute("aria-current"); }
      });
    }
    window.addEventListener("hashchange", showTab);
    showTab();

    /* ----- Dialog konfirmasi ----- */
    var cf = $("#confirmDlg"), cfAction = null;
    function confirmBox(title, text, okLabel, action) {
      $("#cfTitle").textContent = title; $("#cfText").textContent = text;
      $("#cfOk").textContent = okLabel; cfAction = action; cf.showModal();
    }
    $$("[data-close]", cf).forEach(function (b) { b.addEventListener("click", function () { cf.close(); }); });
    $("form", cf).addEventListener("submit", function (ev) { ev.preventDefault(); cf.close(); if (cfAction) { cfAction(); } });

    /* ----- Profil ----- */
    function initials(n) { return n.trim().split(/\s+/).slice(0, 2).map(function (w) { return w[0] || ""; }).join("").toUpperCase() || "?"; }
    $("#avatarInit").textContent = initials($("#avatarName").textContent);
    $("#profilForm").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = ev.target, nama = f.nama.value.trim();
      $$("small.err", f).forEach(function (s) { s.remove(); });
      if (nama.length < 3) {
        var s = document.createElement("small"); s.className = "err"; s.textContent = "Nama minimal 3 karakter.";
        f.nama.closest(".field").appendChild(s); f.nama.focus(); return;
      }
      $("#avatarName").textContent = nama; $("#avatarInit").textContent = initials(nama);
      toast("Profil diperbarui. Ini data contoh, belum tersimpan ke database.");
    });

    /* ----- Kata sandi ----- */
    var pw = { lama: $("#pwLama"), baru: $("#pwBaru"), ulang: $("#pwUlang") };
    function pwState() {
      var b = pw.baru.value, r = {
        len: b.length >= 12,
        mix: /[a-z]/.test(b) && /[A-Z]/.test(b) && /\d/.test(b),
        old: b.length > 0 && b !== pw.lama.value,
        same: b.length > 0 && b === pw.ulang.value
      };
      $$("#pwRules li").forEach(function (li) {
        var ok = r[li.dataset.rule];
        li.classList.toggle("is-ok", ok);
        li.querySelector("i").textContent = ok ? "\u2713" : "\u2022";
        li.setAttribute("aria-label", li.textContent.replace(/^[\u2713\u2022]/, "") + (ok ? ": terpenuhi" : ": belum"));
      });
      return r;
    }
    ["lama", "baru", "ulang"].forEach(function (k) { pw[k].addEventListener("input", pwState); });
    pwState();
    $$("[data-eye]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var inp = btn.parentNode.querySelector("input"), show = inp.type === "password";
        inp.type = show ? "text" : "password";
        btn.setAttribute("aria-pressed", show ? "true" : "false");
        btn.setAttribute("aria-label", show ? "Sembunyikan kata sandi" : "Tampilkan kata sandi");
        btn.classList.toggle("is-on", show);
      });
    });
    $("#pwForm").addEventListener("submit", function (ev) {
      ev.preventDefault();
      $$("small.err", ev.target).forEach(function (s) { s.remove(); });
      var r = pwState(), msg = "";
      if (!pw.lama.value) { msg = "Isi kata sandi saat ini."; pw.lama.focus(); }
      else if (!(r.len && r.mix && r.old && r.same)) { msg = "Kata sandi baru belum memenuhi semua syarat."; pw.baru.focus(); }
      if (msg) {
        var s = document.createElement("small"); s.className = "err"; s.textContent = msg;
        $("#pwRules").after(s); return;
      }
      ev.target.reset(); pwState();
      toast("Kata sandi diubah. Ini data contoh, belum tersimpan ke database.");
    });

    /* ----- Tim ----- */
    function eventNames(a) {
      if (a === "semua") { return "Semua event"; }
      return a.map(function (id) { var e = eventById(id); return e ? e.nama : ""; }).filter(Boolean).join(", ") || "Belum dipilih";
    }
    function renderTim() {
      var aktif = team.filter(function (m) { return m.status === "aktif"; }).length;
      var tang = team.filter(function (m) { return m.status === "ditangguhkan"; }).length;
      var nc = $("#setNotifCount"); if (nc) { nc.textContent = invites.length; nc.hidden = !invites.length; }
      $("#timStats").innerHTML = [["Anggota aktif", aktif, "dari " + team.length + " anggota"], ["Undangan tertunda", invites.length, "belum diterima"], ["Ditangguhkan", tang, "tidak bisa masuk"]].map(function (s) {
        return '<article class="card stat"><p class="stat__label">' + s[0] + '</p><p class="stat__value">' + s[1] + '</p><p class="stat__note stat__note--muted">' + s[2] + "</p></article>";
      }).join("");
      $("#timBody").innerHTML = team.length ? team.map(function (m) {
        var st = STATUS[m.status];
        var opts = Object.keys(PERAN).map(function (k) { return '<option value="' + k + '"' + (k === m.peran ? " selected" : "") + ">" + PERAN[k].nama + "</option>"; }).join("");
        return '<tr><td><span class="cell-title">' + esc(m.nama) + '</span><span class="cell-sub">' + esc(m.email) + " &middot; " + esc(m.terakhir) + "</span></td>" +
          '<td><label class="pill-select sm"><span class="sr-only">Peran ' + esc(m.nama) + '</span><select data-role="' + m.id + '">' + opts + '</select><svg class="icon" aria-hidden="true"><use href="#i-chev"/></svg></label></td>' +
          "<td>" + esc(eventNames(m.akses)) + "</td><td>" + chip(st[0], st[1]) + "</td>" +
          '<td class="act"><button type="button" class="btn btn--ghost sm" data-toggle="' + m.id + '">' + (m.status === "ditangguhkan" ? "Aktifkan" : "Tangguhkan") + '</button> <button type="button" class="btn btn--ghost sm" data-remove="' + m.id + '">Cabut akses</button></td></tr>';
      }).join("") : '<tr><td colspan="5"><p class="tbl-empty">Belum ada anggota. Undang panitia pertamamu.</p></td></tr>';
      $("#invList").innerHTML = invites.length ? invites.map(function (i) {
        return '<li class="inv"><div><b>' + esc(i.email) + "</b><small>" + esc(PERAN[i.peran].nama) + " &middot; dikirim " + esc(i.kirim) + " &middot; " + (i.sisa <= 1 ? "kedaluwarsa besok" : "berlaku " + i.sisa + " hari lagi") + '</small></div><div class="act"><button type="button" class="btn btn--ghost sm" data-copy="' + i.id + '">Salin tautan</button> <button type="button" class="btn btn--ghost sm" data-resend="' + i.id + '">Kirim ulang</button> <button type="button" class="btn btn--ghost sm" data-cancel="' + i.id + '">Batalkan</button></div></li>';
      }).join("") : '<li><p class="tbl-empty">Tidak ada undangan tertunda.</p></li>';
    }
    function member(id) { return team.filter(function (m) { return String(m.id) === String(id); })[0]; }
    $("#timBody").addEventListener("change", function (ev) {
      var s = ev.target.closest("[data-role]"); if (!s) { return; }
      var m = member(s.dataset.role); m.peran = s.value;
      toast("Peran " + m.nama + " diubah menjadi " + PERAN[m.peran].nama + ". Data contoh.");
    });
    $("#timBody").addEventListener("click", function (ev) {
      var t = ev.target.closest("[data-toggle]"), r = ev.target.closest("[data-remove]");
      if (t) {
        var m = member(t.dataset.toggle);
        if (m.status === "ditangguhkan") { m.status = "aktif"; renderTim(); toast(m.nama + " diaktifkan kembali."); }
        else { confirmBox("Tangguhkan " + m.nama + "?", "Dia tidak bisa masuk ke dashboard sampai kamu mengaktifkannya lagi. Datanya tetap tersimpan.", "Tangguhkan", function () { m.status = "ditangguhkan"; renderTim(); toast(m.nama + " ditangguhkan."); }); }
      }
      if (r) {
        var x = member(r.dataset.remove);
        confirmBox("Cabut akses " + x.nama + "?", "Dia dikeluarkan dari tim dan harus diundang ulang untuk bisa masuk lagi.", "Cabut akses", function () { team = team.filter(function (q) { return q.id !== x.id; }); renderTim(); toast("Akses " + x.nama + " dicabut."); });
      }
    });
    $("#invList").addEventListener("click", function (ev) {
      var a = ev.target.closest("[data-resend]"), c = ev.target.closest("[data-cancel]"), k = ev.target.closest("[data-copy]");
      if (k) {
        var link = location.origin + "/undangan/contoh-" + k.dataset.copy + "/";
        if (navigator.clipboard) { navigator.clipboard.writeText(link).then(function () { toast("Tautan undangan disalin (contoh)."); }, function () { toast("Tautan contoh: " + link); }); }
        else { toast("Tautan contoh: " + link); }
      }
      if (a) { invites.forEach(function (i) { if (String(i.id) === a.dataset.resend) { i.sisa = 7; i.kirim = "baru saja"; } }); renderTim(); toast("Undangan dikirim ulang. Berlaku 7 hari."); }
      if (c) { invites = invites.filter(function (i) { return String(i.id) !== c.dataset.cancel; }); renderTim(); toast("Undangan dibatalkan."); }
    });

    /* undang */
    var dlg = $("#inviteDlg"), form = $("#inviteForm"), evList = $("#ivEventList");
    $("#ivPeran").innerHTML = Object.keys(PERAN).map(function (k, i) {
      return '<label class="role-card"><input type="radio" name="peran" value="' + k + '"' + (i === 0 ? " checked" : "") + '><span><b>' + PERAN[k].nama + "</b><small>" + esc(PERAN[k].info) + "</small><em>" + PERAN[k].poin.map(esc).join(" &middot; ") + "</em></span></label>";
    }).join("");
    evList.innerHTML = E.events.filter(function (e) { return e.status !== "selesai"; }).map(function (e) {
      return '<label class="iv-check"><input type="checkbox" name="ev" value="' + e.id + '"> ' + esc(e.nama) + "</label>";
    }).join("");
    $$("input[name=akses]", form).forEach(function (r) { r.addEventListener("change", function () { evList.hidden = form.akses.value !== "pilih"; }); });
    $("#inviteBtn").addEventListener("click", function () {
      form.reset(); evList.hidden = true; $$("small.err", form).forEach(function (x) { x.remove(); }); dlg.showModal(); $("#ivEmail").focus();
    });
    $$("[data-close]", dlg).forEach(function (b) { b.addEventListener("click", function () { dlg.close(); }); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) { dlg.close(); } });
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      $$("small.err", form).forEach(function (x) { x.remove(); });
      var emails = form.email.value.split(/[\s,;]+/).map(function (x) { return x.trim().toLowerCase(); }).filter(Boolean);
      var picked = $$("input[name=ev]:checked", form).map(function (c) { return parseInt(c.value, 10); });
      var err = "", field = form.email;
      var bad = emails.filter(function (x) { return !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(x); });
      var dup = emails.filter(function (x, i) { return emails.indexOf(x) !== i || team.some(function (m) { return m.email === x; }) || invites.some(function (q) { return q.email === x; }); });
      if (!emails.length) { err = "Isi minimal satu email."; }
      else if (bad.length) { err = "Email tidak valid: " + bad.join(", "); }
      else if (dup.length) { err = "Sudah ada di tim atau undangan: " + dup.join(", "); }
      else if (emails.length > 10) { err = "Maksimal 10 email sekali undang."; }
      else if (form.akses.value === "pilih" && !picked.length) { err = "Pilih minimal satu event."; field = null; }
      if (err) {
        var m = document.createElement("small"); m.className = "err"; m.textContent = err;
        (field ? field.closest(".field") : evList.parentNode).appendChild(m); if (field) { field.focus(); } return;
      }
      emails.forEach(function (x, i) { invites.unshift({ id: Date.now() + i, email: x, peran: form.peran.value, kirim: "baru saja", sisa: 7 }); });
      dlg.close(); renderTim();
      toast(emails.length + " undangan dikirim sebagai " + PERAN[form.peran.value].nama + ". Ini data contoh, belum ada email yang terkirim.");
    });
    renderTim();

    /* ----- Notifikasi ----- */
    $("#togList").innerHTML = NOTIF.map(function (n) {
      return '<li class="tog"><div><b id="tg-' + n.k + '">' + esc(n.t) + "</b><small>" + esc(n.d) + '</small></div><button type="button" class="switch" role="switch" aria-labelledby="tg-' + n.k + '" aria-checked="' + n.on + '" data-k="' + n.k + '"><i></i></button></li>';
    }).join("");
    $("#togList").addEventListener("click", function (ev) {
      var b = ev.target.closest(".switch"); if (!b) { return; }
      var on = b.getAttribute("aria-checked") !== "true"; b.setAttribute("aria-checked", on ? "true" : "false");
      toast("Pengaturan notifikasi disimpan (data contoh).");
    });
  }

  var pages = { dashboard: pageDashboard, event: pageEvent, peserta: pagePeserta, pendapatan: pagePendapatan, log: pageLog, support: pageSupport, pengaturan: pagePengaturan };  
  var fn = pages[document.body.dataset.page];
  if (fn) { fn(); }
  initNewEvent();
})();