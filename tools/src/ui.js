(function () {
  "use strict";
  const GM = makeCore(MODELS_DATA);
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const hashStr = (s) => { let h = 7; for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0; return Math.abs(h) % 100000 + 1; };
  const MAX_SITES = 8;
  const MINES = { Munsar: { seed: 11, planned: 150 }, Gumgaon: { seed: 23, planned: 110 } };

  /* ---------- text ---------- */
  const T = {
    title: ["GeoMine-AI Control Room", "जियोमाइन-एआई कंट्रोल रूम"],
    sub: ["Real-time manganese production intelligence for MOIL mines", "MOIL खदानों के लिए मैंगनीज़ उत्पादन की रियल-टाइम निगरानी"],
    tabs: [["Live control room", "Digital twin", "3D reserve model", "Both mines", "How it works"],
           ["लाइव कंट्रोल रूम", "डिजिटल ट्विन", "3D भंडार मॉडल", "दोनों खदानें", "यह कैसे काम करता है"]],
    High: ["HIGH", "उच्च"], Medium: ["MEDIUM", "मध्यम"], Low: ["LOW", "कम"],
    risk: ["shortfall risk tomorrow", "कल उत्पादन में कमी का जोखिम"],
    chance: ["chance that tomorrow's output falls below 90% of plan", "संभावना कि कल का उत्पादन योजना के 90% से कम रहेगा"],
    driver: ["top driver", "मुख्य कारण"],
    kRisk: ["Shortfall probability", "कमी की संभावना"], kRain: ["Rain forecast tomorrow", "कल की वर्षा"],
    kBefore: ["Expected output, no action", "अपेक्षित उत्पादन, बिना कार्रवाई"], kAfter: ["With recommended actions", "सुझाई कार्रवाई के साथ"],
    kPlan: ["Planned output", "योजनाबद्ध उत्पादन"],
    hChart: ["Shortfall risk over time", "समय के साथ कमी का जोखिम"], hWhy: ["Why this rating", "यह रेटिंग क्यों"],
    hAct: ["Recommended actions", "सुझाई गई कार्रवाइयाँ"], hMaint: ["Predictive maintenance", "पूर्वानुमानित रखरखाव"],
    hAlerts: ["Alert log", "अलर्ट लॉग"], hScen: ["What-if scenarios (tomorrow)", "क्या-अगर परिदृश्य (कल)"],
    raises: ["raises risk", "जोखिम बढ़ाता है"], lowers: ["lowers risk", "जोखिम घटाता है"],
    noAct: ["No action needed", "कार्रवाई की आवश्यकता नहीं"], cost: ["cost", "लागत"],
    stable: ["stable", "स्थिर"], down: ["DOWN", "बंद"],
    mine: ["Mine", "खदान"], season: ["Season for rainfall pattern", "वर्षा पैटर्न के लिए मौसम"],
    storm: ["Storm tomorrow, extra rain", "कल तूफ़ान, अतिरिक्त वर्षा"],
    fcast: ["Or enter your own rain forecast for tomorrow (mm)", "या कल के लिए अपना वर्षा पूर्वानुमान दर्ज करें (मिमी)"],
    speed: ["Simulation speed", "सिमुलेशन गति"], reset: ["Reset simulation", "सिमुलेशन रीसेट करें"],
    failDrill: ["Fail a drill", "ड्रिल बंद करें"], failHoist: ["Fail hoist", "हॉइस्ट बंद करें"],
    pause: ["Pause", "रोकें"], play: ["Resume", "चालू करें"], live: ["Live", "लाइव"], paused: ["Paused", "रुका हुआ"],
    note: ["Equipment, production and drill data are simulated. Rainfall is a seasonal simulation unless you enter a forecast. The AI models are real and run in your browser.",
           "उपकरण, उत्पादन और ड्रिल डेटा सिमुलेटेड हैं। जब तक आप पूर्वानुमान दर्ज न करें, वर्षा मौसमी सिमुलेशन है। एआई मॉडल असली हैं और आपके ब्राउज़र में चलते हैं।"],
    noAlert: ["No High-risk alerts yet. Move the storm slider to try one.", "अभी कोई उच्च-जोखिम अलर्ट नहीं। आज़माने के लिए तूफ़ान स्लाइडर चलाएँ।"],
    failsSoon: ["likely to fail in about", "लगभग इतने समय में खराब हो सकता है:"],
    drills: ["Drills working", "चालू ड्रिल"], loaders: ["Loaders working", "चालू लोडर"], hoist: ["Hoist uptime", "हॉइस्ट अपटाइम"],
    blast: ["Blasting delay", "ब्लास्टिंग में देरी"], absent: ["Absenteeism", "अनुपस्थिति"],
  };
  const FRIENDLY = {
    rain_forecast_mm: ["Rain forecast for tomorrow (mm)", "कल की वर्षा का पूर्वानुमान (मिमी)"],
    rain_forecast_3d_mm: ["3-day rain forecast (mm)", "3 दिन की वर्षा का पूर्वानुमान (मिमी)"],
    drills_available_lag1: ["Drill jumbos working", "चालू ड्रिल जंबो"], loaders_available_lag1: ["Loaders working", "चालू लोडर"],
    hoist_uptime_pct_lag1: ["Hoist uptime (%)", "हॉइस्ट अपटाइम (%)"], blast_delay_hours_lag1: ["Blasting delay (h)", "ब्लास्टिंग में देरी (घंटे)"],
    absentee_pct_lag1: ["Absenteeism (%)", "अनुपस्थिति (%)"], rain_3day_mm_lag1: ["Rain in last 3 days (mm)", "पिछले 3 दिनों की वर्षा (मिमी)"],
    achievement_pct_lag1: ["Today's output vs plan (%)", "आज का उत्पादन बनाम योजना (%)"], ach_mean7_lag1: ["7-day average output vs plan (%)", "7 दिन का औसत उत्पादन (%)"],
    drills_mean7_lag1: ["7-day average drills working", "7 दिन में औसत चालू ड्रिल"], loaders_mean7_lag1: ["7-day average loaders working", "7 दिन में औसत चालू लोडर"],
    shortfalls_last7: ["Shortfall days in last week", "पिछले सप्ताह कमी वाले दिन"], month_sin: ["Time of year", "वर्ष का समय"], month_cos: ["Time of year", "वर्ष का समय"],
  };
  const ADVICE = {
    rain: ["Heavy rain ahead: build an ore stockpile buffer today and check dewatering pumps.", "भारी वर्षा: आज ही अयस्क भंडार बढ़ाएँ और डीवॉटरिंग पंप जाँचें।"],
    drills: ["Few drills working: fast-track drill repairs.", "कम ड्रिल चालू: मरम्मत तेज़ करें।"],
    hoist: ["Hoist is weak: avoid planned hoist maintenance tomorrow.", "हॉइस्ट कमज़ोर: कल निर्धारित रखरखाव टालें।"],
    absent: ["High absenteeism: confirm shift manning tonight.", "अनुपस्थिति अधिक: आज रात शिफ्ट की पुष्टि करें।"],
  };

  /* ---------- state ---------- */
  const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const COORDS = { Munsar: [21.4042, 79.2792], Gumgaon: [21.4083, 78.9857] };
  const CUSTOM = []; // user-added sites anywhere in the world
  const nowMonth = new Date().getMonth() + 1;
  let mode = "sim", liveRain = {}, liveOk = false, liveAt = null;
  let L = 0, focus = "Munsar", month = nowMonth, storm = 0, override = null, speed = 3, playing = true;
  let sims, hist, lastLevel, alerts, collars, rm = null, rmKey = "", view = "3d", activeTab = "live", cutoff = 28;
  const t = (k) => T[k][L];
  const num = (v, d) => Number(v).toFixed(d == null ? 0 : d);

  function rainFor(name) {
    const base = mode === "live" && liveRain[name] ? liveRain[name] : GM.makeForecast(20261115 + (name === "Gumgaon" ? 7 : name === "Munsar" ? 0 : hashStr(name)) + month, month);
    if (name !== focus) return base;
    let r = Object.assign({}, base);
    if (override !== null && !isNaN(override)) r[1] = override;
    return GM.withStorm(r, storm);
  }
  function evalMine(name) { return GM.evaluate(sims[name], rainFor(name), month, MINES[name].planned); }
  function stress(name) { const r = rainFor(name); return Math.min((r[0] + r[1]) / 80, 1); }

  function resetSim() {
    sims = {}; hist = {}; lastLevel = {}; alerts = [];
    Object.keys(MINES).forEach((n) => {
      sims[n] = GM.MineSim(n, MINES[n].seed); hist[n] = [];
      for (let i = 0; i < 30; i++) sims[n].tick(0);
    });
    for (let i = 0; i < 40; i++) { stepOnce(true); }
  }
  function stepOnce(quiet) {
    Object.keys(MINES).forEach((n) => {
      sims[n].tick(stress(n));
      const r = evalMine(n);
      hist[n].push(r.prob); if (hist[n].length > 120) hist[n].shift();
      if (!quiet && r.level === "High" && lastLevel[n] !== "High") {
        const msg = new Date().toLocaleTimeString("en-IN", { hour12: false }) + "  " + n + ": HIGH risk (" + num(r.prob * 100) + "%)  " + FRIENDLY[r.reasons[0].f][L];
        alerts.unshift(msg); alerts.length = Math.min(alerts.length, 30); toast(msg);
      }
      lastLevel[n] = r.level;
    });
  }
  let toastTimer = null;
  function toast(msg) {
    const el = $("toast"); el.textContent = msg; el.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, 4500);
  }


  /* ---------- live weather (Open-Meteo, free, no key). Works on normal hosting; blocked inside some sandboxes. ---------- */
  async function fetchLive() {
    try {
      const out = {};
      for (const name of Object.keys(COORDS)) {
        const [lat, lon] = COORDS[name];
        const url = "https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lon +
          "&daily=precipitation_sum&past_days=2&forecast_days=7&timezone=auto";
        const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), 7000);
        const res = await fetch(url, { signal: ctl.signal }); clearTimeout(to);
        if (!res.ok) throw new Error("HTTP " + res.status);
        const d = (await res.json()).daily, rain = {};
        for (let off = -2; off <= 7; off++) { const v = d.precipitation_sum[off + 2]; rain[off] = v == null ? 0 : +v; }
        out[name] = rain;
      }
      liveRain = out; liveOk = true; liveAt = new Date(); return true;
    } catch (e) { liveOk = false; return false; }
  }
  function buildSeasonSelect() {
    const s = $("seasonSel"), cur = mode === "live" ? "live" : s.value || "now";
    s.innerHTML = '<option value="live"' + (liveOk ? "" : " disabled") + ">" + (liveOk ? "Live forecast (Open-Meteo)" : "Live forecast (not available here)") + "</option>" +
      '<option value="now">Simulated, ' + MONTHS[nowMonth - 1] + "</option>" + '<option value="7">Simulated, peak monsoon (July)</option>';
    s.value = cur === "live" && !liveOk ? "now" : cur;
    $("wxSrc").textContent = mode === "live" && liveOk
      ? (L ? "वर्षा स्रोत: लाइव Open-Meteo पूर्वानुमान, अपडेट " : "Rainfall: live Open-Meteo forecast, updated ") + liveAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
      : (L ? "वर्षा सिमुलेटेड है। अपना IMD पूर्वानुमान नीचे दर्ज करें।" : "Rainfall is simulated. Enter an IMD forecast below to override it.");
  }
  async function refreshLive(auto) {
    const ok = await fetchLive();
    if (ok && auto && mode === "sim" && !userPicked) { mode = "live"; month = nowMonth; resetSim(); }
    buildSeasonSelect(); renderAll();
  }
  let userPicked = false;

  /* ---------- helpers ---------- */
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const kpi = (l, n, s) => '<div class="kpi"><div class="l">' + l + '</div><div class="n">' + n + '</div>' + (s ? '<div class="s">' + s + "</div>" : "") + "</div>";
  const actName = (k) => GM.ACTIONS[k][L ? "hi" : "en"];
  const healthColor = (h, st) => (st === "down" || h < 40 ? "var(--bad)" : h < 60 ? "var(--warn)" : "var(--ok)");

  /* ---------- live tab ---------- */
  function renderStrip(r) {
    const el = $("strip"); el.className = "strip " + r.level;
    el.innerHTML = "<b>" + t(r.level) + " " + t("risk") + "</b><span>" + esc(focus) + " · " + num(r.prob * 100) + "% " + t("chance") +
      " · " + t("driver") + ": " + FRIENDLY[r.reasons[0].f][L] + "</span>";
  }
  function renderLive(r) {
    $("kpis").innerHTML =
      kpi(t("kRisk"), num(r.prob * 100) + "%", t(r.level)) +
      kpi(t("kRain"), num(r.rainTomorrow) + " mm", "3-day " + num(r.rain3d) + " mm") +
      kpi(t("kBefore"), num(r.achBefore) + "%", num(r.achBefore / 100 * r.planned) + " t / " + num(r.planned) + " t") +
      kpi(t("kAfter"), num(r.achAfter) + "%", "+" + num(r.tonnesRecovered) + " t");
    $("reasons").innerHTML = r.reasons.map((x) => {
      const up = x.c > 0, nm = FRIENDLY[x.f][L], val = x.f.startsWith("month") ? "" : ": <span class='mono'>" + num(x.value, x.value % 1 ? 1 : 0) + "</span>";
      return "<li><span>" + nm + val + "</span><span class='" + (up ? "up" : "down") + "'>" + (up ? "▲ " + t("raises") : "▼ " + t("lowers")) + "</span></li>";
    }).join("");
    $("actions").innerHTML = r.actions.length
      ? r.actions.map((k) => "<li><span>" + actName(k) + "</span><span class='muted mono'>" + t("cost") + " " + GM.ACTIONS[k].cost.toFixed(1) + "</span></li>").join("")
      : "<li><span>" + t("noAct") + "</span></li>";
    $("advice").innerHTML = r.advice.map((k) => "<div class='note'>" + ADVICE[k][L] + "</div>").join("");

    const m = sims[focus].maintenance();
    $("maint").innerHTML = "<thead><tr><th>Unit</th><th>Health</th><th>Next failure</th></tr></thead><tbody>" + m.map((u) =>
      "<tr><td>" + u.name + "</td><td><span class='bar'><i style='width:" + num(u.health) + "%;background:" + healthColor(u.health, u.status) + "'></i></span><span class='mono'>" + num(u.health) + "</span></td>" +
      "<td class='mono'>" + (u.status === "down" ? t("down") : u.eta == null ? t("stable") : "~" + num(u.eta) + " h") + "</td></tr>").join("") + "</tbody>";
    $("maintWarn").innerHTML = m.filter((u) => u.status === "ok" && u.eta != null && u.eta < 8)
      .map((u) => "<div class='note'>" + u.name + " " + t("failsSoon") + " " + num(u.eta) + " h</div>").join("");
    $("alertLog").innerHTML = alerts.length ? alerts.map((a) => "<div>" + a + "</div>").join("") : "<div class='muted'>" + t("noAlert") + "</div>";
    drawRisk();
  }

  function drawRisk() {
    const cv = $("riskChart"), dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth || 600, H = 220;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const col = { fg: css("--muted"), grid: css("--grid"), line: css("--accent"), bad: css("--bad"), warn: css("--warn"), surf: css("--surface") };
    const ml = 36, mr = 14, mt = 10, mb = 22, pw = W - ml - mr, ph = H - mt - mb;
    const y = (p) => mt + ph * (1 - p);
    g.clearRect(0, 0, W, H); g.font = "11px Inter, system-ui, sans-serif"; g.textBaseline = "middle";
    [0, 0.3, 0.6, 1].forEach((p) => {
      g.strokeStyle = col.grid; g.lineWidth = 1; g.beginPath(); g.moveTo(ml, y(p)); g.lineTo(W - mr, y(p)); g.stroke();
      g.fillStyle = col.fg; g.textAlign = "right"; g.fillText(Math.round(p * 100) + "%", ml - 6, y(p));
    });
    g.setLineDash([4, 4]); g.lineWidth = 1;
    g.strokeStyle = col.bad; g.beginPath(); g.moveTo(ml, y(0.6)); g.lineTo(W - mr, y(0.6)); g.stroke();
    g.strokeStyle = col.warn; g.beginPath(); g.moveTo(ml, y(0.3)); g.lineTo(W - mr, y(0.3)); g.stroke(); g.setLineDash([]);
    const h = hist[focus], n = h.length; if (n < 2) return;
    const x = (i) => ml + (pw * i) / (120 - 1) + pw * (1 - n / 120) * 0;
    const x0 = ml + pw * (1 - (n - 1) / 119);
    const xs = (i) => x0 + (pw * i) / 119;
    g.beginPath(); g.moveTo(xs(0), y(0));
    h.forEach((p, i) => g.lineTo(xs(i), y(p)));
    g.lineTo(xs(n - 1), y(0)); g.closePath(); g.fillStyle = col.line; g.globalAlpha = 0.14; g.fill(); g.globalAlpha = 1;
    g.beginPath(); h.forEach((p, i) => (i ? g.lineTo(xs(i), y(p)) : g.moveTo(xs(i), y(p))));
    g.strokeStyle = col.line; g.lineWidth = 2; g.stroke();
    const lp = h[n - 1]; g.beginPath(); g.arc(xs(n - 1), y(lp), 4.5, 0, 7); g.fillStyle = col.line; g.fill();
    g.lineWidth = 2; g.strokeStyle = col.surf; g.stroke();
    g.fillStyle = col.fg; g.textAlign = "left"; g.fillText("older", ml, H - 8); g.textAlign = "right"; g.fillText("now", W - mr, H - 8);
  }

  /* ---------- twin ---------- */
  function renderTwin(r) {
    const u = sims[focus].units;
    const pos = { "Main hoist": [0, 3], "Drill jumbo 1": [3, -30], "Drill jumbo 2": [6, -30], "Drill jumbo 3": [4, -60], "Drill jumbo 4": [7, -60],
      "Loader 1": [2, -60], "Loader 2": [5, -90], "Loader 3": [8, -90] };
    const X = (v) => 90 + v * 72, Y = (v) => 100 - v * 3.7;
    let s = "";
    s += '<rect x="0" y="0" width="900" height="100" style="fill:var(--surface-2)"/>';
    s += '<rect x="0" y="100" width="900" height="380" style="fill:var(--grid)"/>';
    s += '<rect x="0" y="94" width="900" height="10" style="fill:var(--muted);opacity:.45"/>';
    s += '<line x1="90" y1="100" x2="90" y2="' + Y(-97) + '" style="stroke:var(--muted);stroke-width:6"/>';
    [-30, -60, -90].forEach((lv, i) => {
      s += '<line x1="90" y1="' + Y(lv) + '" x2="' + X(9.4) + '" y2="' + Y(lv) + '" style="stroke:var(--muted);stroke-width:4"/>';
      s += '<text x="' + (X(9.4) + 10) + '" y="' + (Y(lv) + 4) + '" font-size="12" style="fill:var(--muted)">Level ' + (i + 1) + " · " + Math.abs(lv) + " m</text>";
    });
    s += '<path d="M70 94 L90 56 L110 94 Z" style="fill:var(--muted)"/><text x="90" y="46" font-size="12" text-anchor="middle">Headframe</text><line x1="110" y1="80" x2="175" y2="72" style="stroke:var(--muted);stroke-width:2"/>';
    u.forEach((q) => {
      const p = pos[q.name], cx = q.kind === "hoist" ? 190 : X(p[0]), cy = q.kind === "hoist" ? 66 : Y(p[1]);
      const c = healthColor(q.health, q.status), nm = q.name.replace("Drill jumbo ", "D").replace("Loader ", "L").replace("Main hoist", "Hoist");
      if (q.status === "down") s += '<g><rect x="' + (cx - 15) + '" y="' + (cy - 15) + '" width="30" height="30" rx="4" style="fill:var(--bad-soft);stroke:var(--bad);stroke-width:2"/><path d="M' + (cx - 9) + " " + (cy - 9) + " L" + (cx + 9) + " " + (cy + 9) + " M" + (cx + 9) + " " + (cy - 9) + " L" + (cx - 9) + " " + (cy + 9) + '" style="stroke:var(--bad);stroke-width:3"/>';
      else s += '<g><rect x="' + (cx - 15) + '" y="' + (cy - 15) + '" width="30" height="30" rx="4" style="fill:' + c + '"/>';
      s += '<text x="' + cx + '" y="' + (cy - 21) + '" font-size="12" text-anchor="middle">' + nm + '</text><title>' + q.name + ": " + num(q.health) + "% " + q.status + "</title></g>";
    });
    s += '<text x="450" y="30" font-size="15" text-anchor="middle">Rain tomorrow: ' + num(r.rainTomorrow) + " mm</text>";
    if (r.rainTomorrow > 25) s += '<text x="' + X(7.5) + '" y="' + (Y(-104) + 4) + '" font-size="13" text-anchor="middle" style="fill:var(--accent)">Water ingress risk</text>';
    $("twinSvg").innerHTML = s;
    const sn = r.snap;
    $("twinKpis").innerHTML = kpi(t("drills"), sn.drills_available + " / 4") + kpi(t("loaders"), sn.loaders_available + " / 3") +
      kpi(t("hoist"), num(sn.hoist_uptime_pct) + "%") + kpi(t("blast"), num(sn.blast_delay_hours, 1) + " h") + kpi(t("absent"), num(sn.absentee_pct) + "%");

    const sc = GM.scenarios(sims[focus], rainFor(focus), month, MINES[focus].planned);
    const colors = ["var(--accent)", "var(--ok)", "var(--bad)", "var(--warn)", "var(--accent)"];
    const x0 = 300, sw = 520, bx = (v) => x0 + (sw * Math.min(v, 115)) / 115;
    let b = "";
    sc.forEach((q, i) => {
      const yy = 14 + i * 46;
      b += '<text x="0" y="' + (yy + 19) + '" font-size="13">' + q.name + "</text>";
      b += '<rect x="' + x0 + '" y="' + yy + '" width="' + (bx(q.pct) - x0) + '" height="28" rx="4" style="fill:' + colors[i] + '"/>';
      b += '<text x="' + (bx(q.pct) + 8) + '" y="' + (yy + 19) + '" font-size="13" class="mono">' + num(q.pct) + "% · " + num(q.tonnes) + " t</text>";
    });
    b += '<line x1="' + bx(90) + '" y1="4" x2="' + bx(90) + '" y2="240" style="stroke:var(--bad);stroke-dasharray:4 4"/><text x="' + bx(90) + '" y="248" font-size="11" text-anchor="middle" style="fill:var(--bad)">90% of plan</text>';
    $("scenSvg").innerHTML = b;
  }

  /* ---------- reserve ---------- */
  function ensureReserve(force) {
    const key = collars.length + ":" + collars.reduce((a, c) => a + c[0] + c[1], 0).toFixed(1);
    if (rm && rmKey === key && !force) { renderReserve(); return; }
    $("resCheck").textContent = "Fitting the 3D model (1 to 2 seconds)…";
    setTimeout(() => { rm = GM.fitReserve(collars); rmKey = key; renderReserve(); }, 40);
  }
  function plotColors() { return { font: css("--fg"), grid: css("--line"), muted: css("--muted") }; }
  function renderReserve() {
    if (!rm) return;
    const tn = GM.tonnage(rm, cutoff), d = GM.dims, pc = plotColors();
    $("resKpis").innerHTML = kpi("Ore above cut-off", num(tn.est / 1e6, 2) + " Mt", "bulk density " + d.DENSITY + " t/m³") + kpi("Average ore grade", num(tn.meanGrade, 1) + "% Mn") +
      kpi("Drill holes", String(collars.length)) + kpi("Validation error", num(rm.rmse, 1) + "% Mn", "150 unseen points");
    const err = Math.abs(tn.est - tn.truth) / Math.max(tn.truth, 1) * 100;
    $("resCheck").textContent = "Hidden truth at this cut-off: " + num(tn.truth / 1e6, 2) + " Mt, so the estimate is off by " + num(err, 1) + "%. This check exists only because the orebody is simulated.";
    $("conf").innerHTML = "<thead><tr><th>Confidence</th><th>Mt</th></tr></thead><tbody>" +
      [["Higher (p ≥ 0.8)", tn.cls.high], ["Medium (0.5 to 0.8)", tn.cls.med], ["Low (0.2 to 0.5)", tn.cls.low]].map((r) => "<tr><td>" + r[0] + "</td><td class='mono'>" + num(r[1] / 1e6, 2) + "</td></tr>").join("") + "</tbody>";
    const picks = GM.nextHoles(rm, cutoff);
    $("picks").innerHTML = "<thead><tr><th>East (m)</th><th>North (m)</th><th>Doubt score</th></tr></thead><tbody>" +
      picks.map((p) => "<tr><td class='mono'>" + num(p.x) + "</td><td class='mono'>" + num(p.y) + "</td><td class='mono'>" + num(p.score, 1) + "</td></tr>").join("") + "</tbody>";
    $("drillBtn").onclick = () => { collars = collars.concat(picks.map((p) => [p.x, p.y])); ensureReserve(true); };

    if (typeof Plotly === "undefined") { $("plot3d").innerHTML = "<p class='status'>The 3D viewer could not load. Check your internet connection and reload.</p>"; return; }
    const layoutBase = { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: pc.font, family: "Inter, system-ui, sans-serif" }, margin: { l: 0, r: 0, t: 10, b: 0 } };
    const el = $("plot3d");
    if (view === "3d") {
      const lines = { x: [], y: [], z: [], mode: "lines", type: "scatter3d", line: { color: pc.muted, width: 2 }, hoverinfo: "skip", showlegend: false };
      collars.forEach((c) => { lines.x.push(c[0], c[0], null); lines.y.push(c[1], c[1], null); lines.z.push(0, -d.ZMAX, null); });
      const vol = { type: "volume", x: Array.from(rm.X), y: Array.from(rm.Y), z: Array.from(rm.Z, (v) => -v), value: Array.from(rm.mean),
        isomin: cutoff, isomax: 45, opacity: 0.2, surface_count: 8, colorscale: "YlOrRd", colorbar: { title: { text: "% Mn" }, thickness: 12 },
        caps: { x_show: false, y_show: false, z_show: false }, hovertemplate: "%{value:.1f}% Mn<extra></extra>" };
      const ax = (title) => ({ title: { text: title }, gridcolor: pc.grid, zerolinecolor: pc.grid, color: pc.font, backgroundcolor: "rgba(0,0,0,0)" });
      Plotly.react(el, [vol, lines], Object.assign({}, layoutBase, { scene: { xaxis: ax("East (m)"), yaxis: ax("North (m)"), zaxis: ax("Depth (m)"), aspectmode: "manual", aspectratio: { x: 2, y: 1, z: 0.6 } } }), { responsive: true, displaylogo: false });
    } else {
      const k = Math.min(Math.max(Math.round(($("depth").value - 2.5) / d.BZ), 0), d.NZ - 1);
      const src = view === "mean" ? rm.mean : rm.std;
      const z = []; for (let j = 0; j < d.NY; j++) { const row = []; for (let i = 0; i < d.NX; i++) row.push(src[(i * d.NY + j) * d.NZ + k]); z.push(row); }
      const xs = Array.from({ length: d.NX }, (_, i) => (i + 0.5) * d.BX), ys = Array.from({ length: d.NY }, (_, j) => (j + 0.5) * d.BY);
      const hm = { type: "heatmap", x: xs, y: ys, z, colorscale: view === "mean" ? "YlOrRd" : "Magma", colorbar: { title: { text: view === "mean" ? "% Mn" : "± % Mn" }, thickness: 12 } };
      const pts = { type: "scatter", mode: "markers", x: collars.map((c) => c[0]), y: collars.map((c) => c[1]), marker: { color: "#fff", size: 8, line: { color: "#222", width: 1 } }, name: "Drill collars", hovertemplate: "Hole at %{x:.0f}, %{y:.0f}<extra></extra>" };
      Plotly.react(el, [hm, pts], Object.assign({}, layoutBase, { margin: { l: 50, r: 10, t: 10, b: 40 }, xaxis: { title: { text: "East (m)" }, gridcolor: pc.grid }, yaxis: { title: { text: "North (m)" }, scaleanchor: "x", gridcolor: pc.grid }, legend: { orientation: "h" } }), { responsive: true, displaylogo: false });
    }
  }

  /* ---------- sites anywhere in the world ---------- */
  function persistSites() { try { localStorage.setItem("geomine.sites", JSON.stringify(CUSTOM)); } catch (e) {} }
  function fillMineSelect() {
    const sel = $("mineSel"); sel.innerHTML = "";
    const add = (v, label) => { const o = document.createElement("option"); o.value = v; o.textContent = label; sel.appendChild(o); };
    add("Munsar", "Munsar (Nagpur)"); add("Gumgaon", "Gumgaon (Nagpur)");
    CUSTOM.forEach((c) => add(c.key, c.label));
    sel.value = focus; $("rmSite").hidden = !CUSTOM.some((c) => c.key === focus);
  }
  async function addSite(label, lat, lon, quiet) {
    lat = +lat; lon = +lon;
    if (!isFinite(lat) || !isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return;
    const key = (label || "Site").slice(0, 40) + " (" + lat.toFixed(2) + ", " + lon.toFixed(2) + ")";
    if (!MINES[key]) {
      if (CUSTOM.length >= MAX_SITES) { const old = CUSTOM.shift(); delete MINES[old.key]; delete COORDS[old.key]; delete sims[old.key]; delete hist[old.key]; delete liveRain[old.key]; }
      CUSTOM.push({ key, label: key, lat, lon });
      MINES[key] = { seed: hashStr(key), planned: 120 }; COORDS[key] = [lat, lon];
      sims[key] = GM.MineSim(key, MINES[key].seed); hist[key] = [];
      for (let i = 0; i < 30; i++) sims[key].tick(0);
      for (let i = 0; i < 40; i++) { sims[key].tick(stress(key)); hist[key].push(evalMine(key).prob); }
      persistSites();
    }
    focus = key; fillMineSelect();
    const ok = await fetchLive();
    if (ok && mode === "sim" && !userPicked) { mode = "live"; month = nowMonth; resetSim(); }
    buildSeasonSelect(); renderAll();
    if (!quiet) toast(ok ? "Live forecast loaded for " + label : "Live weather unavailable here — using simulated rainfall for " + label);
  }
  function removeSite() {
    const i = CUSTOM.findIndex((c) => c.key === focus); if (i < 0) return;
    const k = CUSTOM[i].key; CUSTOM.splice(i, 1);
    delete MINES[k]; delete COORDS[k]; delete sims[k]; delete hist[k]; delete liveRain[k];
    focus = "Munsar"; persistSites(); fillMineSelect(); renderAll();
  }
  let siteTimer = null;
  $("siteQ").addEventListener("input", () => {
    clearTimeout(siteTimer); const v = $("siteQ").value.trim(), box = $("siteRes");
    if (v.length < 2) { box.hidden = true; return; }
    siteTimer = setTimeout(async () => {
      try {
        const r = await fetch("https://geocoding-api.open-meteo.com/v1/search?count=6&language=en&name=" + encodeURIComponent(v));
        const j = await r.json(); box.innerHTML = "";
        (j.results || []).forEach((x) => {
          const b = document.createElement("button"); b.type = "button"; b.className = "btn"; b.style.cssText = "display:block;width:100%;text-align:left;margin:2px 0";
          b.textContent = x.name + (x.admin1 ? ", " + x.admin1 : "") + (x.country ? ", " + x.country : "");
          b.addEventListener("click", () => { box.hidden = true; $("siteQ").value = ""; addSite(x.name, x.latitude, x.longitude); });
          box.appendChild(b);
        });
        if (!box.children.length) box.textContent = "No matches.";
        box.hidden = false;
      } catch (e) { box.textContent = "Search needs internet (works on normal hosting, not in the preview sandbox)."; box.hidden = false; }
    }, 300);
  });
  $("rmSite").addEventListener("click", removeSite);

  /* ---------- both mines ---------- */
  function renderNet() {
    let rows = "", tot = 0;
    Object.keys(MINES).forEach((n) => {
      const r = evalMine(n); tot += r.tonnesRecovered;
      rows += "<tr><td><b>" + esc(n) + "</b></td><td><span class='pill " + r.level + "'>" + t(r.level) + "</span></td><td class='mono'>" + num(r.prob * 100) + "%</td><td class='mono'>" + num(r.rainTomorrow) +
        " mm</td><td class='mono'>" + num(r.achBefore) + "%</td><td class='mono'>" + num(r.achAfter) + "%</td><td class='mono'>" + num(r.tonnesRecovered) + " t</td><td>" + (r.actions.map(actName).join(", ") || "-") + "</td></tr>";
    });
    $("netTable").innerHTML = "<thead><tr><th>Mine</th><th>Risk</th><th>Probability</th><th>Rain tomorrow</th><th>Output, no action</th><th>With actions</th><th>Recovered</th><th>Actions</th></tr></thead><tbody>" + rows + "</tbody>";
    $("netKpis").innerHTML = kpi("Recoverable tomorrow, both mines", num(tot) + " t", "with recommended actions");
  }

  /* ---------- render all ---------- */
  function renderAll() {
    const r = evalMine(focus);
    renderStrip(r);
    if (activeTab === "live") renderLive(r);
    else if (activeTab === "twin") renderTwin(r);
    else if (activeTab === "net") renderNet();
  }
  function statics() {
    $("t-title").textContent = t("title"); $("t-sub").textContent = t("sub");
    ["live", "twin", "res", "net", "about"].forEach((k, i) => { $("tab-" + k).textContent = T.tabs[L][i]; });
    $("t-mine").textContent = t("mine"); $("t-season").textContent = L ? "वर्षा का स्रोत" : "Rainfall source"; $("t-fcast").textContent = t("fcast");
    $("t-storm").firstChild.nodeValue = t("storm") + " "; $("t-speed").firstChild.nodeValue = t("speed") + " ";
    $("resetBtn").textContent = t("reset"); $("failDrill").textContent = t("failDrill"); $("failHoist").textContent = t("failHoist");
    $("t-note").textContent = t("note"); $("h-chart").textContent = t("hChart"); $("h-why").textContent = t("hWhy");
    $("h-act").textContent = t("hAct"); $("h-maint").textContent = t("hMaint"); $("h-alerts").textContent = t("hAlerts"); $("h-scen").textContent = t("hScen");
    $("playBtn").textContent = playing ? t("pause") : t("play"); $("liveTxt").textContent = playing ? t("live") : t("paused");
    $("liveDot").className = "dot" + (playing ? "" : " paused");
    document.documentElement.lang = L ? "hi" : "en";
  }

  /* ---------- events ---------- */
  function showTab(k) {
    activeTab = k;
    ["live", "twin", "res", "net", "about"].forEach((x) => { $("pane-" + x).hidden = x !== k; $("tab-" + x).setAttribute("aria-selected", String(x === k)); });
    if (k === "res") ensureReserve(); else renderAll();
  }
  ["live", "twin", "res", "net", "about"].forEach((k) => $("tab-" + k).addEventListener("click", () => showTab(k)));
  $("mineSel").addEventListener("change", (e) => { focus = e.target.value; $("rmSite").hidden = !CUSTOM.some((c) => c.key === focus); renderAll(); });
  $("seasonSel").addEventListener("change", (e) => {
    userPicked = true; const v = e.target.value;
    if (v === "live") { mode = "live"; month = nowMonth; } else { mode = "sim"; month = v === "now" ? nowMonth : +v; }
    resetSim(); buildSeasonSelect(); renderAll();
  });
  $("storm").addEventListener("input", (e) => { storm = +e.target.value; $("stormV").textContent = storm + " mm"; stepOnce(false); renderAll(); });
  $("rainOverride").addEventListener("input", (e) => { override = e.target.value === "" ? null : Math.max(0, +e.target.value); stepOnce(false); renderAll(); });
  $("speed").addEventListener("input", (e) => { speed = +e.target.value; $("speedV").textContent = speed + "x"; });
  $("failDrill").addEventListener("click", () => { sims[focus].fail("drill"); stepOnce(false); renderAll(); });
  $("failHoist").addEventListener("click", () => { sims[focus].fail("hoist"); stepOnce(false); renderAll(); });
  $("resetBtn").addEventListener("click", () => { storm = 0; override = null; $("storm").value = 0; $("stormV").textContent = "0 mm"; $("rainOverride").value = ""; resetSim(); renderAll(); });
  $("playBtn").addEventListener("click", () => { playing = !playing; statics(); });
  $("lang-en").addEventListener("click", () => { L = 0; $("lang-en").setAttribute("aria-pressed", "true"); $("lang-hi").setAttribute("aria-pressed", "false"); statics(); buildSeasonSelect(); renderAll(); });
  $("lang-hi").addEventListener("click", () => { L = 1; $("lang-hi").setAttribute("aria-pressed", "true"); $("lang-en").setAttribute("aria-pressed", "false"); statics(); buildSeasonSelect(); renderAll(); });
  $("cut").addEventListener("input", (e) => { cutoff = +e.target.value; $("cutV").textContent = cutoff; renderReserve(); });
  $("depth").addEventListener("input", (e) => { $("depthV").textContent = e.target.value; renderReserve(); });
  document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => {
    view = b.dataset.view; document.querySelectorAll("[data-view]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    $("depthWrap").hidden = view === "3d"; renderReserve();
  }));
  $("resetHoles").addEventListener("click", () => { collars = GM.baseCollars(30); ensureReserve(true); });
  window.addEventListener("resize", () => { if (activeTab === "live") drawRisk(); });
  if (window.matchMedia) window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { renderAll(); if (activeTab === "res") renderReserve(); });

  setInterval(() => {
    if (!playing) return;
    for (let i = 0; i < speed; i++) stepOnce(false);
    renderAll();
  }, 1000);

  /* ---------- start ---------- */
  collars = GM.baseCollars(30);
  resetSim(); statics(); buildSeasonSelect(); renderAll();
  refreshLive(true); setInterval(() => refreshLive(false), 10 * 60 * 1000);
  try { (JSON.parse(localStorage.getItem("geomine.sites") || "[]") || []).slice(0, MAX_SITES).forEach((c) => { if (c && isFinite(c.lat) && isFinite(c.lon) && !MINES[c.key]) { CUSTOM.push({ key: String(c.key), label: String(c.key), lat: +c.lat, lon: +c.lon }); MINES[c.key] = { seed: hashStr(c.key), planned: 120 }; COORDS[c.key] = [+c.lat, +c.lon]; } }); } catch (e) {}
  if (CUSTOM.length) { resetSim(); fillMineSelect(); renderAll(); fetchLive().then(() => { buildSeasonSelect(); renderAll(); }); }
  try {
    const qp = new URLSearchParams(location.search);
    if (qp.has("lat") && qp.has("lon")) addSite(qp.get("name") || "Selected site", qp.get("lat"), qp.get("lon"), true);
  } catch (e) {}
  const h = (location.hash || "").replace("#", "");
  if (["twin", "res", "net", "about"].includes(h)) showTab(h);
  window.__geomine = { GM, state: () => ({ focus, month, storm, hist, alerts }) };
})();
