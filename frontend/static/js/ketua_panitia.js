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

      var id = Math.max.apply(null, E.events.map(function (e) { return e.id; })) + 1;
      E.events.push({ id: id, nama: v.nama, jenis: v.jenis, tanggal: v.tanggal, lokasi: v.lokasi, kuota: v.kuota, terjual: 0, harga: v.harga, status: "mendatang", hadir: 0, pendapatan: 0 });
      E.activity.unshift({ tipe: "event", teks: "Event baru \"" + v.nama + "\" dibuat", waktu: "Baru saja" });
      dlg.close();
      onEventsChanged();
      toast("Event \"" + v.nama + "\" ditambahkan. Ini data contoh, belum tersimpan ke database.");
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
    E.events.filter(function (e) { return e.status !== "mendatang"; }).forEach(function (e) {
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
    function counts() {
      return TABS.map(function (t) { return [t[0], t[1], t[0] === "semua" ? E.events.length : E.events.filter(function (e) { return e.status === t[0]; }).length]; });
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
        "<dt>Hadir</dt><dd>" + e.hadir + " peserta</dd><dt>Harga tiket</dt><dd>" + rp(e.harga) + "</dd><dt>Pendapatan</dt><dd>" + (e.pendapatan ? "Rp " + num(e.pendapatan) : "Rp 0") + "</dd>";
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
    barChart($("#pdChart"), { labels: E.monthly.labels, values: E.monthly.pendapatan, name: "Pendapatan", fmt: function (v) { return "Rp " + num(v); }, fmtY: rpShort });
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
          '<span class="ticket__chev" aria-hidden="true"><svg class="icon"><use href="#i-chev"/></svg></span></summary><div class="ticket__body"><p>' + esc(t.isi) + '</p><p class="ticket__meta">Dilaporkan oleh ' + esc(t.pelapor) + "</p>" +
          (t.status === "diaudit" ? '<div class="ticket__actions"><button type="button" class="btn" data-done="' + esc(t.id) + '">Tandai selesai</button></div>' : "") + "</div></details></li>";
      }).join("") : '<li><p class="tbl-empty">Belum ada tiket.</p></li>';
    }
    tabsEl.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { filter = b.dataset.f; render(); } });
    list.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-done]"); if (!b) { return; }
      E.tickets.forEach(function (t) { if (t.id === b.dataset.done) { t.status = "selesai"; } });
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
  var pages = { dashboard: pageDashboard, event: pageEvent, peserta: pagePeserta, pendapatan: pagePendapatan, log: pageLog, support: pageSupport };  
  var fn = pages[document.body.dataset.page];
  if (fn) { fn(); }
  initNewEvent();
})();
