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

  function csrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }
  async function postForm(url, values) {
    var body = new URLSearchParams();
    Object.keys(values || {}).forEach(function (key) { body.set(key, values[key]); });
    var response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), "Content-Type": "application/x-www-form-urlencoded" },
      body: body
    });
    var data = await response.json();
    if (!response.ok) { throw new Error(data.error || "Permintaan gagal."); }
    return data;
  }
  async function postJSON(url, values) {
    var response = await fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), "Content-Type": "application/json" },
      body: JSON.stringify(values || {})
    });
    var data = await response.json();
    if (!response.ok) { throw new Error(data.error || "Permintaan gagal."); }
    return data;
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
  if (!arr || arr.length < 2) return "Belum ada data";
  var a = Number(arr[arr.length - 1]) || 0;
  var b = Number(arr[arr.length - 2]) || 0;
  if (b === 0) {
    return a > 0 ? "Mulai ada transaksi" : "Belum ada perubahan";
  }
  var p = (a / b - 1) * 100;
  return (p >= 0 ? "+" : "") + p.toFixed(2) + "%";
}

  /* ---------- Dialog "Event baru" (dipakai semua halaman) ---------- */
  var onEventsChanged = function () {};
  /* Dropdown kustom (menu putih, item terpilih olive) sebagai pengganti menu bawaan browser/OS.
     Select asli tetap ada (disembunyikan) supaya form.jenis.value tetap bekerja. */
  function enhanceSelect(select) {
    if (!select || select.dataset.dd) { return; }
    select.dataset.dd = "1";
    var host = select.closest("dialog") || document.body;
    var wrap = document.createElement("div"); wrap.className = "dd";
    select.parentNode.insertBefore(wrap, select); wrap.appendChild(select);
    var btn = document.createElement("button"); btn.type = "button"; btn.className = "dd__btn";
    btn.setAttribute("aria-haspopup", "listbox"); btn.setAttribute("aria-expanded", "false");
    btn.innerHTML = '<span class="dd__val"></span><svg class="icon" aria-hidden="true"><use href="#i-chev"/></svg>';
    wrap.appendChild(btn);
    var menu = document.createElement("div"); menu.className = "dd__menu"; menu.setAttribute("role", "listbox"); menu.hidden = true;
    host.appendChild(menu);
    var open = false, active = -1;

    function sync() { var o = select.options[select.selectedIndex]; $(".dd__val", btn).textContent = o ? o.textContent : ""; }
    function build() {
      menu.innerHTML = Array.prototype.map.call(select.options, function (o, i) {
        return '<div class="dd__item' + (i === select.selectedIndex ? " is-selected" : "") + (i === active ? " is-active" : "") + '" role="option" data-i="' + i + '" aria-selected="' + (i === select.selectedIndex) + '">' + esc(o.textContent) + "</div>";
      }).join("");
    }
    function place() {
      var r = btn.getBoundingClientRect();
      menu.style.width = r.width + "px"; menu.style.left = r.left + "px";
      var h = Math.min(menu.scrollHeight, 280), below = window.innerHeight - r.bottom - 12;
      if (below < h && r.top > below) { menu.style.top = "auto"; menu.style.bottom = (window.innerHeight - r.top + 6) + "px"; menu.style.maxHeight = Math.min(280, r.top - 12) + "px"; }
      else { menu.style.bottom = "auto"; menu.style.top = (r.bottom + 6) + "px"; menu.style.maxHeight = Math.min(280, below) + "px"; }
    }
    function openMenu() {
      active = select.selectedIndex; build(); menu.hidden = false; open = true; wrap.classList.add("is-open"); btn.setAttribute("aria-expanded", "true"); place();
      var sel = $(".is-selected", menu); if (sel) { sel.scrollIntoView({ block: "nearest" }); }
    }
    function closeMenu() { menu.hidden = true; open = false; wrap.classList.remove("is-open"); btn.setAttribute("aria-expanded", "false"); }
    function choose(i) {
      select.selectedIndex = i; sync(); closeMenu();
      select.dispatchEvent(new Event("input", { bubbles: true })); select.dispatchEvent(new Event("change", { bubbles: true }));
      btn.focus();
    }
    function move(d) {
      var n = select.options.length; active = (active + d + n) % n; build();
      var a = $(".is-active", menu); if (a) { a.scrollIntoView({ block: "nearest" }); }
    }

    btn.addEventListener("click", function () { if (open) { closeMenu(); } else { openMenu(); } });
    btn.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); if (!open) { openMenu(); } else { move(ev.key === "ArrowDown" ? 1 : -1); } }
      else if ((ev.key === "Enter" || ev.key === " ") && open) { ev.preventDefault(); choose(active); }
      else if (ev.key === "Escape" && open) { ev.preventDefault(); ev.stopPropagation(); closeMenu(); }
    });
    menu.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
    menu.addEventListener("click", function (ev) { var it = ev.target.closest(".dd__item"); if (it) { choose(parseInt(it.dataset.i, 10)); } });
    document.addEventListener("mousedown", function (ev) { if (open && !ev.target.closest(".dd__menu") && !ev.target.closest(".dd__btn")) { closeMenu(); } });
    window.addEventListener("resize", function () { if (open) { place(); } });
    host.addEventListener("scroll", function () { if (open) { place(); } }, true);
    if (select.form) { select.form.addEventListener("reset", function () { setTimeout(function () { sync(); closeMenu(); }, 0); }); }
    new MutationObserver(sync).observe(select, { childList: true });
    sync();
  }

  
  function initNewEvent() {
    var dlg = $("#newEventDlg");
    if (!dlg) return;

    var form = $("form", dlg);
    var buttons = $$("[data-open-new-event]");
    var modeInput = $("#neMode", form);
    var meetingField = $("#neMeetingField", form);
    var meetingInput = $("#neMeetingUrl", form);
    var saveButton = $('button[type="submit"]', form);

    function field(name) {
      return form.elements.namedItem(name);
    }

    function val(name) {
      var input = field(name);
      return input ? String(input.value).trim() : "";
    }

    function localDatetime(date) {
      function pad(n) {
        return String(n).padStart(2, "0");
      }

      return (
        date.getFullYear() + "-" +
        pad(date.getMonth() + 1) + "-" +
        pad(date.getDate()) + "T" +
        pad(date.getHours()) + ":" +
        pad(date.getMinutes())
      );
    }

    function clearErrors() {
      $$(".event-form-error", form).forEach(function (node) {
        node.remove();
      });
    }

    function showError(name, message) {
      var input = field(name);
      var parent = input && input.closest(".field");

      if (parent) {
        var error = document.createElement("small");
        error.className = "event-form-error";
        error.style.color = "#b91c1c";
        error.textContent = message;
        parent.appendChild(error);
        input.focus();
      } else {
        toast(message);
      }
    }

    function syncMode() {
      var mode = val("mode");

      var showMeeting = mode !== "OFFLINE";

      meetingField.hidden = !showMeeting;
      meetingField.style.display = showMeeting ? "" : "none";
      meetingInput.required = showMeeting;

      field("lokasi").required = mode !== "ONLINE";
    }

    modeInput.addEventListener("change", syncMode);

    // Pertahankan kategori yang dikirim Django.
    // Jangan diganti dengan kategori localStorage.
    enhanceSelect(field("jenis"));

    buttons.forEach(function (button) {
      button.disabled = false;
      button.removeAttribute("title");

      button.addEventListener("click", function () {
        if (document.body.dataset.page !== "event") {
          window.location.href = "/ketua-panitia/event/";
          return;
        }

        form.reset();
        clearErrors();

        if (typeof resetGambarInput === "function") {
          resetGambarInput();
        }

        if (typeof resetProposalInput === "function") {
          resetProposalInput();
        }

        syncMode();
        dlg.showModal();
        $("#neNama", form).focus();
      });
    });

    $$("[data-close]", dlg).forEach(function (button) {
      button.addEventListener("click", function () {
        dlg.close();
      });
    });

    dlg.addEventListener("click", function (event) {
      if (event.target === dlg) {
        dlg.close();
      }
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearErrors();

      var title = val("nama");
      var description = val("deskripsi");
      var eventType = val("jenis");
      var eventDate = val("tanggal");
      var startTime = val("jam_mulai");
      var endTime = val("jam_selesai");
      var mode = val("mode");
      var meetingUrl = val("meeting_url");
      var venue = val("lokasi");

      var capacity = Number(val("kuota"));
      var price = Number(val("harga"));

      var banner = $("#neGambar", form).files[0];
      var proposal = $("#neProposal", form).files[0];

      // VALIDASI
      if (title.length < 3) {
        showError("nama", "Nama event minimal 3 karakter.");
        return;
      }

      if (!description) {
        showError("deskripsi", "Deskripsi event wajib diisi.");
        return;
      }

      if (!eventType) {
        showError("jenis", "Pilih jenis event.");
        return;
      }

      if (!eventDate || !startTime || !endTime) {
        showError("tanggal", "Tanggal dan jam wajib diisi.");
        return;
      }

      var start = new Date(eventDate + "T" + startTime);
      var end = new Date(eventDate + "T" + endTime);

      if (
        Number.isNaN(start.getTime()) ||
        Number.isNaN(end.getTime())
      ) {
        showError("tanggal", "Tanggal atau jam tidak valid.");
        return;
      }

      if (start <= new Date()) {
        showError("tanggal", "Waktu event harus di masa depan.");
        return;
      }

      if (end <= start) {
        showError(
          "jam_selesai",
          "Jam selesai harus setelah jam mulai."
        );
        return;
      }

      if (mode !== "ONLINE" && !venue) {
        showError("lokasi", "Lokasi wajib diisi.");
        return;
      }

      if (mode !== "OFFLINE") {
        try {
          var meeting = new URL(meetingUrl);

          if (meeting.protocol !== "https:") {
            throw new Error("invalid");
          }
        } catch (error) {
          showError(
            "meeting_url",
            "Link meeting wajib menggunakan HTTPS."
          );
          return;
        }
      }

      if (!Number.isInteger(capacity) || capacity < 1) {
        showError("kuota", "Kuota minimal 1 peserta.");
        return;
      }

      if (!Number.isFinite(price) || price < 0) {
        showError("harga", "Harga tiket tidak valid.");
        return;
      }

      if (banner) {
        if (!["image/jpeg", "image/png"].includes(banner.type)) {
          showError("gambar", "Cover harus JPG atau PNG.");
          return;
        }

        if (banner.size > 5 * 1024 * 1024) {
          showError("gambar", "Cover maksimal 5 MB.");
          return;
        }
      }

      if (proposal) {
        if (!proposal.name.toLowerCase().endsWith(".pdf")) {
          showError("proposal", "Proposal harus PDF.");
          return;
        }

        if (proposal.size > 10 * 1024 * 1024) {
          showError("proposal", "Proposal maksimal 10 MB.");
          return;
        }
      }

      // SIAPKAN DATA UNTUK DJANGO
      var now = new Date();

      var registrationOpen = new Date(
        now.getTime() - 60 * 1000
      );

      var registrationClose = new Date(
        start.getTime() - 30 * 60 * 1000
      );

      if (registrationClose <= registrationOpen) {
        showError(
          "tanggal",
          "Waktu event terlalu dekat untuk membuka pendaftaran."
        );
        return;
      }

      var payload = new FormData();

      var csrfInput = form.querySelector(
        '[name="csrfmiddlewaretoken"]'
      );

      if (!csrfInput) {
        toast("Token keamanan tidak ditemukan. Refresh halaman.");
        return;
      }

      payload.append(
        "csrfmiddlewaretoken",
        csrfInput.value
      );

      payload.append("title", title);
      payload.append("description", description);
      payload.append("event_type", eventType);

      payload.append("delivery_mode", mode);
      payload.append("start_datetime", localDatetime(start));
      payload.append("end_datetime", localDatetime(end));

      payload.append(
        "venue",
        mode === "ONLINE" ? "" : venue
      );

      payload.append("capacity", String(capacity));
      payload.append("price", String(price));

      payload.append(
        "registration_open",
        localDatetime(registrationOpen)
      );

      payload.append(
        "registration_close",
        localDatetime(registrationClose)
      );

      // LINK MEETING ONLINE / HYBRID
      if (mode !== "OFFLINE") {
        payload.append("meeting_url", meetingUrl);
      }

      // FILE UPLOAD
      if (banner) {
        payload.append("banner", banner);
      }

      if (proposal) {
        payload.append("proposal", proposal);
      }

      // KIRIM KE BACKEND
      var previousLabel = saveButton.textContent;
      saveButton.disabled = true;
      saveButton.textContent = "Menyimpan...";

      try {
        var response = await fetch("/events/manage/", {
          method: "POST",
          credentials: "same-origin",
          body: payload,
          headers: {
            "X-Requested-With": "XMLHttpRequest"
          }
        });

        var data = await response.json().catch(function () {
          return null;
        });

        if (!response.ok) {
          if (data && data.errors) {
            var details = Object.entries(data.errors)
              .map(function (entry) {
                return entry[0] + ": " +
                  (Array.isArray(entry[1])
                    ? entry[1].join(", ")
                    : String(entry[1]));
              })
              .join(" | ");

            throw new Error(details);
          }

          if (response.redirected) {
            throw new Error(
              "Sesi login mungkin berakhir. Silakan login kembali."
            );
          }

          throw new Error(
            data && (data.error || data.detail)
              ? data.error || data.detail
              : "HTTP " + response.status +
                ": Event gagal disimpan."
          );
        }

        if (!data || !data.id) {
          throw new Error(
            "Backend tidak mengembalikan ID event."
          );
        }

        dlg.close();

        toast(
          'Event "' + title +
          '" berhasil disimpan ke database.'
        );

        window.setTimeout(function () {
          window.location.reload();
        }, 900);

      } catch (error) {
        toast(
          error.message ||
          "Terjadi kesalahan saat menyimpan event."
        );

        console.error("Create event error:", error);
      } finally {
        saveButton.disabled = false;
        saveButton.textContent = previousLabel;
      }
    });

    syncMode();
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
    if (selEvent.options.length > 0) {
      selEvent.addEventListener("change", drawChart);
      selMetrik.addEventListener("change", drawChart);
      drawChart();
    } else {
      plot.innerHTML =
        '<p style="padding:40px 20px;text-align:center;color:#64748b">' +
        'Belum ada data kehadiran untuk event yang kamu kelola.' +
        '</p>';
    }

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
    var TABS_EXTRA = [
      ["draft", "Draft"],
      ["diajukan", "Menunggu Persetujuan"],
      ["disetujui", "Disetujui"],
      ["revisi", "Perlu Revisi"],
      ["ditolak", "Ditolak"],
      ["dibatalkan", "Dibatalkan"],
      ["ditangguhkan", "Ditangguhkan"]
    ];
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
    /* Data proposal: pakai yang diunggah saat "Event baru" (tersimpan di SIM.state.newEvents), kalau tidak ada pakai data contoh */
    var RINGKAS = window.SIMEVENT_DEMO.proposal_summaries;
    
  function proposalOf(e) {
    // Jika data event berasal dari PostgreSQL,
    // jangan membuat nama, ukuran, atau tanggal PDF palsu.
    if (window.EO_EVENTS_FROM_BACKEND) {
      return {
        file: e.has_proposal
          ? "Proposal event (PDF)"
          : "Belum ada proposal",
        size: e.has_proposal
          ? "Dokumen tersimpan di server"
          : "Tidak ada dokumen",
        uploaded: null,
        ringkasan: e.deskripsi || "Belum ada deskripsi event.",
        asli: Boolean(e.has_proposal),
        backend: true
      };
    }

    // Fallback untuk mode dummy lama.
    var S = window.SIM;
    var n = S && S.state.newEvents.filter(function (x) {
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

    dlg.addEventListener("click", function (ev) {
      if (!ev.target.closest("[data-open-doc]")) return;

      if (!window.EO_EVENTS_FROM_BACKEND) {
        toast("Proposal ini masih data contoh.");
        return;
      }

      var eventId = Number(dlg.dataset.eventId);
      var e = eventById(eventId);

      if (!e || !e.has_proposal) {
        toast("Proposal belum diunggah untuk event ini.");
        return;
      }

      window.open(
        "/events/manage/" + eventId + "/proposal/",
        "_blank",
        "noopener,noreferrer"
      );
    });
    
    tabsEl.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { filter = b.dataset.f; render(); } });
    q.addEventListener("input", render);
    tbody.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-detail]"); if (!b) { return; }
      var e = eventById(parseInt(b.dataset.detail, 10));
      dlg.dataset.eventId = String(e.id);
      $("#detailTitle").textContent = e.nama;
      $("#detailBody").innerHTML =
        "<dt>Jenis</dt><dd>" + esc(e.jenis) + "</dd><dt>Tanggal</dt><dd>" + fmtDate(e.tanggal) + "</dd><dt>Lokasi</dt><dd>" + esc(e.lokasi) + "</dd>" +
        "<dt>Status</dt><dd>" + chip(e.status, E.statusEvent[e.status]) + "</dd><dt>Tiket terjual</dt><dd>" + e.terjual + " dari " + e.kuota + " kuota</dd>" +
        "<dt>Hadir</dt><dd>" + e.hadir + " peserta</dd><dt>Harga tiket</dt><dd>" + rp(e.harga) + "</dd><dt>Pendapatan</dt><dd>" + (e.pendapatan ? "Rp " + num(e.pendapatan) : "Rp 0") + "</dd>" +
        (e.alasan ? "<dt>Catatan admin</dt><dd>" + esc(e.alasan) + "</dd>" : "");
      
var proposalMeta = p.backend
  ? p.size
  : p.size + " · diunggah " + fmtDate(p.uploaded);

var proposalButton = (!p.backend || p.asli)
  ? '<button type="button" class="btn btn--ghost" ' +
    'style="height:36px;padding:0 16px;font-size:13px" ' +
    'data-open-doc>Buka proposal</button>'
  : "";

    var proposalNote = p.backend
      ? (p.asli
          ? ""
          : '<p class="pdoc__note">Belum ada proposal PDF ' +
            'yang diunggah untuk event ini.</p>')
      : (p.asli
          ? ""
          : '<p class="pdoc__note">Proposal ini masih data contoh.</p>');

    $("#detailProposal").innerHTML =
      '<h3 class="prop-h">Proposal</h3>' +
      '<div class="pdoc">' +
        '<span class="pdoc__ico" aria-hidden="true">PDF</span>' +
        '<div><b>' + esc(p.file) + '</b>' +
        '<small>' + esc(proposalMeta) + '</small></div>' +
        proposalButton +
      '</div>' +
      '<dl class="detail-grid dl--prop">' +
        '<dt>Tujuan &amp; ringkasan</dt>' +
        '<dd>' + esc(p.ringkasan) + '</dd>' +
        '<dt>Target peserta</dt>' +
        '<dd>' + e.kuota + ' peserta, mahasiswa dan umum</dd>' +
        '<dt>Estimasi anggaran</dt>' +
        '<dd>Rp ' + num(anggaran) + '</dd>' +
      '</dl>' +
      proposalNote;

      // Tombol Ajukan ke Admin hanya untuk event
      // Draft atau event yang perlu revisi.
      dlg.dataset.eventId = String(e.id);

      if (
        window.EO_EVENTS_FROM_BACKEND &&
        (e.status === "draft" || e.status === "revisi")
      ) {
        $("#detailProposal").insertAdjacentHTML(
          "beforeend",
          `
          <div style="
            display: flex;
            justify-content: flex-end;
            margin-top: 24px;
            padding-top: 18px;
            border-top: 1px solid #e5dfcf;
          ">
            <button
              type="button"
              class="btn"
              data-submit-event
              style="min-width: 180px;"
            >
              Ajukan ke Admin
            </button>
          </div>
          `
        );
      }
      dlg.showModal();
    });
    $$("[data-close]", dlg).forEach(function (b) { b.addEventListener("click", function () { dlg.close(); }); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) { dlg.close(); } });
    
    // AJUKAN EVENT KE ADMIN PLATFORM
    dlg.addEventListener("click", async function (ev) {
      var button = ev.target.closest("[data-submit-event]");
      if (!button) return;

      var eventId = Number(dlg.dataset.eventId);
      var selectedEvent = eventById(eventId);

      if (!selectedEvent) {
        toast("Event tidak ditemukan.");
        return;
      }

      if (
        selectedEvent.status !== "draft" &&
        selectedEvent.status !== "revisi"
      ) {
        toast("Event ini tidak dapat diajukan.");
        return;
      }

      var confirmed = window.confirm(
        'Ajukan event "' + selectedEvent.nama +
        '" ke Admin Platform untuk diperiksa?'
      );

      if (!confirmed) return;

      // CSRF token dari form Event Baru.
      var csrfInput = document.querySelector(
        '#newEventDlg [name="csrfmiddlewaretoken"]'
      );

      if (!csrfInput) {
        toast("Token CSRF tidak ditemukan. Refresh halaman.");
        return;
      }

      var originalText = button.textContent;

      button.disabled = true;
      button.textContent = "Mengajukan...";

      try {
        var response = await fetch(
          "/events/manage/" + eventId + "/submit/",
          {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "X-CSRFToken": csrfInput.value,
              "X-Requested-With": "XMLHttpRequest",
              "Accept": "application/json"
            }
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
                var message = Array.isArray(entry[1])
                  ? entry[1].join(", ")
                  : String(entry[1]);

                return entry[0] + ": " + message;
              })
              .join(" | ");

            throw new Error(errors);
          }

          if (response.status === 403) {
            throw new Error(
              "Akses ditolak. Akun tidak memiliki izin " +
              "mengajukan event atau token CSRF tidak valid."
            );
          }

          throw new Error(
            (data && (data.error || data.detail)) ||
            "Gagal mengajukan event (HTTP " +
            response.status + ")."
          );
        }

        // Sinkronkan data frontend dengan perubahan status.
        selectedEvent.status = "diajukan";

        dlg.close();

        toast(
          'Event "' + selectedEvent.nama +
          '" berhasil diajukan ke Admin Platform.'
        );

        // Reload agar status terbaru berasal
        // langsung dari PostgreSQL.
        window.setTimeout(function () {
          window.location.reload();
        }, 1000);

      } catch (error) {
        console.error("Submit event error:", error);

        toast(
          error.message ||
          "Terjadi kesalahan saat mengajukan event."
        );

      } finally {
        button.disabled = false;
        button.textContent = originalText;
      }
    });

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
    $("#pdAvg").textContent = "Rp " + num(tiket ? Math.round(total / tiket) : 0);
    $("#pdTop").textContent = top.length ? top[0].nama : "Belum ada event";
    $("#pdTopNote").textContent = top.length && total
      ? "Rp " + num(top[0].pendapatan) + " (" + Math.round(top[0].pendapatan / total * 100) + "% dari total)"
      : "Data transaksi akan muncul di sini.";
    lineChart($("#pdChart"), { labels: E.monthly.labels, values: E.monthly.pendapatan, name: "Pendapatan", fmt: function (v) { return "Rp " + num(v); }, fmtY: rpShort });
    $("#pdBody").innerHTML = top.length ? top.map(function (e) {
      var pct = total ? Math.round(e.pendapatan / total * 100) : 0;
      return "<tr><td><span class=\"cell-title\">" + esc(e.nama) + '</span><span class="cell-sub">' + esc(e.jenis) + '</span></td><td class="num">' + e.terjual + '</td><td class="num">' + rp(e.harga) + '</td><td class="num"><b>Rp ' + num(e.pendapatan) + '</b></td><td><div class="meter"><div class="meter__bar" role="img" aria-label="' + pct + '% dari total"><i style="width:' + pct + '%"></i></div><small>' + pct + "%</small></div></td></tr>";
    }).join("") : '<tr><td colspan="5" class="tbl-empty">Belum ada event atau transaksi.</td></tr>';
    $("#pdFoot").innerHTML = '<tr><td><b>Total</b></td><td class="num"><b>' + tiket + '</b></td><td></td><td class="num"><b>Rp ' + num(total) + "</b></td><td></td></tr>";
  }

  /* ---------- Halaman: Support ---------- */
  function pageSupport() {
    var tickets = window.EO_SUPPORT ? window.EO_SUPPORT.tickets : [];
    var filter = "semua", tabsEl = $("#tkTabs"), list = $("#tkList");
    var TABS = [["semua", "Semua"], ["diaudit", "Sedang Diaudit"], ["selesai", "Selesai"]];
    function render() {
      tabsEl.innerHTML = TABS.map(function (t) {
        var c = t[0] === "semua" ? tickets.length : tickets.filter(function (x) { return x.status === t[0]; }).length;
        return '<button type="button" data-f="' + t[0] + '" class="' + (t[0] === filter ? "is-active" : "") + '" aria-pressed="' + (t[0] === filter) + '">' + t[1] + "<span>" + c + "</span></button>";
      }).join("");
      var rows = tickets.filter(function (t) { return filter === "semua" || t.status === filter; });
      list.innerHTML = rows.length ? rows.map(function (t) {
        var e = eventById(t.eventId);
        return '<li><details class="ticket"><summary><div><span class="ticket__title">' + esc(t.judul) + '</span><span class="ticket__meta">' + esc(t.id) + " &middot; " + esc(e ? e.nama : "Event") + " &middot; " + fmtDate(t.tanggal) + "</span></div>" + chip(t.status, E.statusTiket[t.status]) +
          '<span class="ticket__chev" aria-hidden="true"><svg class="icon"><use href="#i-chev"/></svg></span></summary><div class="ticket__body"><p>' + esc(t.isi) + '</p><p class="ticket__meta">Dilaporkan oleh ' + esc(t.pelapor) + "</p>" + (t.balasan ? '<p class="ticket__reply"><b>Balasan admin:</b> ' + esc(t.balasan) + "</p>" : "") +
          (t.status === "diaudit" ? '<div class="ticket__actions"><button type="button" class="btn" data-done="' + esc(t.id) + '">Tandai selesai</button></div>' : "") + "</div></details></li>";
      }).join("") : '<li><p class="tbl-empty">Belum ada tiket.</p></li>';
    }
    tabsEl.addEventListener("click", function (ev) { var b = ev.target.closest("button[data-f]"); if (b) { filter = b.dataset.f; render(); } });
    list.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-done]"); if (!b) { return; }
      b.disabled = true;
      postForm("/ketua-panitia/api/support/" + encodeURIComponent(b.dataset.done) + "/resolve/", {})
        .then(function () {
          tickets.forEach(function (ticket) { if (ticket.id === b.dataset.done) { ticket.status = "selesai"; } });
          toast("Tiket " + b.dataset.done + " ditandai selesai.");
          render();
        })
        .catch(function (error) { b.disabled = false; toast(error.message); });
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
      ["support", "Bantuan"]
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
      panitia: { nama: "Panitia", info: "Melihat event yang ditugaskan, check-in peserta saat acara, mengerjakan tugas, dan mengunggah dokumentasi. Bisa beralih ke tampilan peserta.",
                 poin: ["Check-in peserta", "Mengerjakan tugas", "Unggah dokumentasi"] }
    };
    var STATUS = { aktif: ["hadir", "Aktif"], tertunda: ["mendatang", "Menunggu"], ditangguhkan: ["selesai", "Ditangguhkan"] };
    var settings = window.EO_SETTINGS || {};
    var team = settings.team || [];
    var invites = settings.invitations || [];
    var NOTIF = (window.SIMEVENT_DEMO.organizer_notifications || []).map(function (item) {
      return Object.assign({}, item, {
        on: Object.prototype.hasOwnProperty.call(settings.notifications || {}, item.k)
          ? settings.notifications[item.k]
          : item.on
      });
    });

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

        /* ----- Profil: foto (dengan crop), nama, HP, organisasi ----- */
    function initials(n) { return n.trim().split(/\s+/).slice(0, 2).map(function (w) { return w[0] || ""; }).join("").toUpperCase() || "?"; }
    function profile() { return settings.profile || {}; }
    function curName() { return profile().name || ""; }
    function applyProfile() {
      var pr = profile(), ava = $("#avatarInit");
      ava.style.backgroundImage = pr.photo ? 'url("' + pr.photo + '")' : "";
      ava.textContent = pr.photo ? "" : initials(curName());
      $("#avatarName").textContent = curName();
      $("#pfNama").value = curName();
      applySidebarName();
    }
    var msg = $("#profMsg"), fIn = $("#profFoto"), nm = $("#nameForm"), nmIn = $("#pfNama");
    var modal = $("#profileCropModal"), vp = $("#profileCropViewport"), img = $("#profileCropImage"), zoom = $("#profileCropZoom"), okBtn = $("#profileCropSave"), noBtn = $("#profileCropCancel");
    var src = null, url = null, scale = 1, left = 0, top = 0, drag = null;
    function say(t) { msg.innerHTML = t ? '<small class="err">' + t + "</small>" : ""; }
    function fieldErr(input, text) {
      var m = document.createElement("small"); m.className = "err"; m.textContent = text;
      input.closest(".field").appendChild(m); input.focus();
    }
    nmIn.value = curName();
    $("#pfHp").value = profile().phone || "";
    $("#pfOrg").value = profile().organization || "";
    applyProfile();

    async function saveProfile(name, phone, organization, photo, removePhoto) {
      var body = new FormData();
      body.set("name", name);
      body.set("phone", phone);
      body.set("organization", organization);
      if (photo) { body.set("photo", photo, "profile.jpg"); }
      if (removePhoto) { body.set("remove_photo", "1"); }
      var response = await fetch("/ketua-panitia/api/settings/profile/", {
        method: "POST", credentials: "same-origin",
        headers: { "X-CSRFToken": csrfToken() }, body: body
      });
      var data = await response.json();
      if (!response.ok) { throw new Error(data.error || "Profil gagal disimpan."); }
      settings.profile = data.profile;
      window.EO_SETTINGS.profile = data.profile;
      applyProfile();
    }

    nm.addEventListener("submit", function (ev) {
      ev.preventDefault(); $$("small.err", nm).forEach(function (x) { x.remove(); });
      var v = nmIn.value.trim().replace(/\s+/g, " ");
      if (v.length < 3) { fieldErr(nmIn, "Nama minimal 3 karakter."); return; }
      if (v === curName()) { toast("Nama tidak berubah."); return; }
      saveProfile(v, $("#pfHp").value.trim(), $("#pfOrg").value.trim())
        .then(function () { toast("Nama tersimpan."); })
        .catch(function (error) { say(error.message); });
    });

    $("#profilForm").addEventListener("submit", function (ev) {
      ev.preventDefault();
      saveProfile(curName(), $("#pfHp").value.trim(), $("#pfOrg").value.trim())
        .then(function () { toast("Profil tersimpan."); })
        .catch(function (error) { say(error.message); });
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
      c.toBlob(function (blob) {
        if (!blob) { say("Foto gagal diproses."); return; }
        saveProfile(curName(), $("#pfHp").value.trim(), $("#pfOrg").value.trim(), blob)
          .then(function () { closeCrop(); toast("Foto profil tersimpan."); })
          .catch(function (error) { say(error.message); });
      }, "image/jpeg", .85);
    });
    $("#profFotoDel").addEventListener("click", function () {
      if (!profile().photo) { say("Belum ada foto yang bisa dihapus."); return; }
      saveProfile(curName(), $("#pfHp").value.trim(), $("#pfOrg").value.trim(), null, true)
        .then(function () { say(""); toast("Foto profil dihapus."); })
        .catch(function (error) { say(error.message); });
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
      postForm("/ketua-panitia/api/settings/password/", {
        current: pw.lama.value, password: pw.baru.value, confirm: pw.ulang.value
      }).then(function () {
        ev.target.reset(); pwState();
        toast("Kata sandi berhasil diperbarui.");
      }).catch(function (error) {
        var s = document.createElement("small"); s.className = "err"; s.textContent = error.message;
        $("#pwRules").after(s);
      });
    });

    /* ----- Tim ----- */
    function eventNames(a) {
      if (a === "semua") { return "Semua event"; }
      return a.map(function (id) { var e = eventById(id); return e ? e.nama : ""; }).filter(Boolean).join(", ") || "Belum dipilih";
    }
    function applySettings(data) {
      settings = data;
      window.EO_SETTINGS = data;
      team = data.team || [];
      invites = data.invitations || [];
      renderTim();
    }
    function renderTim() {
      var aktif = team.filter(function (m) { return m.status === "aktif"; }).length;
      var tang = team.filter(function (m) { return m.status === "ditangguhkan"; }).length;
      var nc = $("#setNotifCount"); if (nc) { nc.textContent = invites.length; nc.hidden = !invites.length; }
      var segera = invites.filter(function (i) { return i.sisa <= 1; }).length;
function kpi(label, x, y) {
  return '<article class="card kpi kpi--split"><p class="kpi__label">' + label + '</p><div class="kpi__pair">' +
    '<div><span class="kpi__num' + (x[2] ? " kpi__num--orange" : "") + '">' + x[0] + '</span><span class="kpi__cap' + (x[2] ? " kpi__cap--orange" : "") + '">' + x[1] + "</span></div><i></i>" +
    '<div><span class="kpi__num' + (y[2] ? " kpi__num--orange" : "") + '">' + y[0] + '</span><span class="kpi__cap' + (y[2] ? " kpi__cap--orange" : "") + '">' + y[1] + "</span></div></div></article>";
}
$("#timStats").innerHTML =
  kpi("Anggota aktif", [aktif, "Aktif"], [team.length, "Total anggota"]) +
  kpi("Undangan tertunda", [invites.length, "Belum diterima"], [segera, "Kedaluwarsa besok", true]) +
  kpi("Ditangguhkan", [tang, "Tidak bisa masuk", true], [aktif, "Bisa masuk"]);
      $("#timBody").innerHTML = team.length ? team.map(function (m) {
        var st = STATUS[m.status];
        return '<tr><td><span class="cell-title">' + esc(m.nama) + '</span><span class="cell-sub">' + esc(m.email) + " &middot; " + esc(m.terakhir) + "</span></td>" +
          "<td>" + esc(PERAN[m.peran].nama) + "</td>" +
          "<td>" + esc(eventNames(m.akses)) + "</td><td>" + chip(st[0], st[1]) + "</td>" +
          '<td class="act"><button type="button" class="btn btn--ghost sm" data-toggle="' + m.id + '">' + (m.status === "ditangguhkan" ? "Aktifkan" : "Tangguhkan") + '</button> <button type="button" class="btn btn--ghost sm" data-remove="' + m.id + '">Cabut akses</button></td></tr>';
      }).join("") : '<tr><td colspan="5"><p class="tbl-empty">Belum ada anggota. Undang panitia pertamamu.</p></td></tr>';
      $("#invList").innerHTML = invites.length ? invites.map(function (i) {
  return '<tr><td><span class="cell-title">' + esc(i.email) + "</span></td>" +
    "<td>" + esc(PERAN[i.peran].nama) + " &middot; tautan diperbarui " + esc(i.kirim) + " &middot; " + (i.sisa === 0 ? "kedaluwarsa" : i.sisa === 1 ? "berlaku kurang dari 1 hari" : "berlaku " + i.sisa + " hari lagi") +
    '<span class="cell-sub">' + (i.email_sent ? "Email terakhir dikirim " + esc(i.email_sent_at) : "Email belum terkirim. Gunakan Kirim ulang atau salin tautan.") + "</span></td>" +
    '<td class="act"><button type="button" class="btn btn--ghost sm" data-copy="' + i.id + '" data-url="' + esc(i.url) + '">Salin tautan</button> <button type="button" class="btn btn--ghost sm" data-resend="' + i.id + '">Kirim ulang</button> <button type="button" class="btn btn--ghost sm" data-cancel="' + i.id + '">Batalkan</button></td></tr>';
}).join("") : '<tr><td colspan="3"><p class="tbl-empty">Tidak ada undangan tertunda.</p></td></tr>';
    }
    function member(id) { return team.filter(function (m) { return String(m.id) === String(id); })[0]; }
    function invitationDeliveryMessage(data) {
      var delivery = data.delivery;
      if (delivery.failed.length) {
        return "Undangan tersimpan. " + delivery.sent.length + " email dikirim, " + delivery.failed.length + " gagal. Gunakan Kirim ulang atau salin tautan.";
      }
      return delivery.sent.length + " email undangan dikirim. Tautan berlaku 7 hari.";
    }
    $("#timBody").addEventListener("click", function (ev) {
      var t = ev.target.closest("[data-toggle]"), r = ev.target.closest("[data-remove]");
      if (t) {
        var m = member(t.dataset.toggle);
        function toggleMember(enabled) {
          postForm("/ketua-panitia/api/settings/team/", { action: "toggle", member_id: m.id, enabled: enabled })
            .then(function (data) { applySettings(data.settings); toast(enabled ? "Akses tim diaktifkan." : "Akses tim ditangguhkan."); })
            .catch(function (error) { toast(error.message); });
        }
        if (m.status === "ditangguhkan") { toggleMember(true); }
        else { confirmBox("Tangguhkan " + m.nama + "?", "Dia tidak bisa masuk ke event yang ditugaskan sampai aksesnya diaktifkan lagi.", "Tangguhkan", function () { toggleMember(false); }); }
      }
      if (r) {
        var x = member(r.dataset.remove);
        confirmBox("Cabut akses " + x.nama + "?", "Penugasan event-nya akan dihapus. Dia perlu undangan baru untuk bergabung lagi.", "Cabut akses", function () {
          postForm("/ketua-panitia/api/settings/team/", { action: "remove", member_id: x.id })
            .then(function (data) { applySettings(data.settings); toast("Akses " + x.nama + " dicabut."); })
            .catch(function (error) { toast(error.message); });
        });
      }
    });
    $("#invList").addEventListener("click", function (ev) {
      var a = ev.target.closest("[data-resend]"), c = ev.target.closest("[data-cancel]"), k = ev.target.closest("[data-copy]");
      if (k) {
        var link = location.origin + k.dataset.url;
        if (navigator.clipboard) { navigator.clipboard.writeText(link).then(function () { toast("Tautan undangan disalin."); }, function () { toast("Tautan: " + link); }); }
        else { toast("Tautan: " + link); }
      }
      if (a) {
        a.disabled = true;
        a.textContent = "Mengirim…";
        postForm("/ketua-panitia/api/settings/invitations/" + a.dataset.resend + "/", { action: "resend" })
          .then(function (data) { applySettings(data.settings); toast(invitationDeliveryMessage(data)); })
          .catch(function (error) { toast(error.message); })
          .finally(function () { a.disabled = false; a.textContent = "Kirim ulang"; });
      }
      if (c) {
        var invite = invites.filter(function (item) { return String(item.id) === c.dataset.cancel; })[0];
        confirmBox("Batalkan undangan?", "Tautan undangan untuk " + (invite ? invite.email : "penerima ini") + " tidak akan berlaku lagi.", "Batalkan", function () {
          postForm("/ketua-panitia/api/settings/invitations/" + c.dataset.cancel + "/", { action: "cancel" })
            .then(function (data) { applySettings(data.settings); toast("Undangan dibatalkan."); })
            .catch(function (error) { toast(error.message); });
        });
      }
    });

    /* undang */
    var dlg = $("#inviteDlg"), form = $("#inviteForm"), evList = $("#ivEventList");
    $("#ivPeran").innerHTML = Object.keys(PERAN).map(function (k, i) {
      return '<label class="role-card"><input type="radio" name="peran" value="' + k + '"' + (i === 0 ? " checked" : "") + '><span><b>' + PERAN[k].nama + "</b><small>" + esc(PERAN[k].info) + "</small><em>" + PERAN[k].poin.map(esc).join(" &middot; ") + "</em></span></label>";
    }).join("");
    evList.innerHTML = (settings.events || []).map(function (e) {
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
      var submit = form.querySelector('[type="submit"]');
      submit.disabled = true; submit.textContent = "Mengirim…";
      postJSON("/ketua-panitia/api/settings/invitations/", {
        emails: emails,
        event_ids: picked,
        access_all: form.akses.value === "semua",
        message: form.pesan.value.trim()
      }).then(function (data) {
        dlg.close(); applySettings(data.settings);
        toast(invitationDeliveryMessage(data));
      }).catch(function (error) {
        var m = document.createElement("small"); m.className = "err"; m.textContent = error.message;
        form.email.closest(".field").appendChild(m); form.email.focus();
      }).finally(function () { submit.disabled = false; submit.textContent = "Kirim undangan"; });
    });
    renderTim();

    /* ----- Notifikasi ----- */
    $("#togList").innerHTML = NOTIF.map(function (n) {
      return '<li class="tog"><div><b id="tg-' + n.k + '">' + esc(n.t) + "</b><small>" + esc(n.d) + '</small></div><button type="button" class="switch" role="switch" aria-labelledby="tg-' + n.k + '" aria-checked="' + n.on + '" data-k="' + n.k + '"><i></i></button></li>';
    }).join("");
    $("#togList").addEventListener("click", function (ev) {
      var b = ev.target.closest(".switch"); if (!b) { return; }
      var on = b.getAttribute("aria-checked") !== "true";
      b.disabled = true;
      postForm("/ketua-panitia/api/settings/notification/", { key: b.dataset.k, enabled: on })
        .then(function (data) {
          b.setAttribute("aria-checked", on ? "true" : "false");
          settings.notifications = data.notifications;
          window.EO_SETTINGS.notifications = data.notifications;
          toast("Preferensi notifikasi tersimpan.");
        }).catch(function (error) { toast(error.message); })
        .finally(function () { b.disabled = false; });
    });
  }

    /* ---------- Profil ketua panitia dari backend ---------- */
    function sbInitials(n) { return n.trim().split(/\s+/).slice(0, 2).map(function (w) { return w[0] || ""; }).join("").toUpperCase() || "?"; }
  function applySidebarName() {
    var pr = (window.EO_SETTINGS && window.EO_SETTINGS.profile) || {}, b = $(".eo-user b"), ava = $(".eo-user__ava");
    if (pr.name && b) { b.textContent = pr.name; }
    if (ava) {
      var hasProfileData = Boolean(window.EO_SETTINGS && window.EO_SETTINGS.profile);
      var photo = hasProfileData ? pr.photo : ava.dataset.photoUrl;
      ava.style.backgroundImage = photo ? 'url("' + photo + '")' : "";
      ava.textContent = photo ? "" : sbInitials(b ? b.textContent : "");
    }
  }

  applySidebarName();
  var pages = { dashboard: pageDashboard, event: pageEvent, peserta: pagePeserta, pendapatan: pagePendapatan, log: pageLog, support: pageSupport, pengaturan: pagePengaturan };  
  var fn = pages[document.body.dataset.page];
  if (fn) { fn(); }
  initNewEvent();
})();
