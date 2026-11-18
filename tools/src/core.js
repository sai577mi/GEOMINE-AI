/* GeoMine-AI core: models, telemetry simulator, risk + actions, 3D reserve model.
   Port of engine.py so the app runs fully in the browser. */
function makeCore(MODELS) {
  "use strict";

  /* ---------- random numbers ---------- */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function Rng(seed) {
    const u = mulberry32(seed);
    const self = {
      u: u,
      uniform: (a, b) => a + (b - a) * u(),
      normal: (m, s) => {
        let x = 0, y = 0;
        while (x === 0) x = u();
        y = u();
        return m + s * Math.sqrt(-2 * Math.log(x)) * Math.cos(2 * Math.PI * y);
      },
      exp: (scale) => -scale * Math.log(1 - u()),
      int: (a, b) => a + Math.floor(u() * (b - a)),
      gamma: (shape, scale) => {
        if (shape < 1) return self.gamma(shape + 1, scale) * Math.pow(u(), 1 / shape);
        const d = shape - 1 / 3, c = 1 / Math.sqrt(9 * d);
        for (;;) {
          let x, v;
          do { x = self.normal(0, 1); v = 1 + c * x; } while (v <= 0);
          v = v * v * v;
          const uu = u();
          if (Math.log(uu) < 0.5 * x * x + d - d * v + d * Math.log(v)) return d * v * scale;
        }
      },
    };
    return self;
  }

  /* ---------- tree models (XGBoost exported to JSON) ---------- */
  function prepare(m) {
    m.trees.forEach((t) => {
      const n = t.f.length;
      t.t = t.t.map(Math.fround);
      t.val = new Array(n);
      for (let i = n - 1; i >= 0; i--) {
        if (t.f[i] < 0) t.val[i] = t.v[i];
        else {
          const cl = t.c[t.l[i]], cr = t.c[t.r[i]];
          t.val[i] = (cl * t.val[t.l[i]] + cr * t.val[t.r[i]]) / (cl + cr);
        }
      }
    });
    return m;
  }
  prepare(MODELS.clf); prepare(MODELS.sim);
  const CLF_F = MODELS.clf.features, SIM_F = MODELS.sim.features;
  const sigmoid = (z) => 1 / (1 + Math.exp(-z));

  function leaf(t, x) {
    let i = 0;
    while (t.f[i] >= 0) i = Math.fround(x[t.f[i]]) < t.t[i] ? t.l[i] : t.r[i];
    return t.v[i];
  }
  function predictClf(x) {
    let m = Math.log(MODELS.clf.base / (1 - MODELS.clf.base));
    for (const t of MODELS.clf.trees) m += leaf(t, x);
    return sigmoid(m);
  }
  function contribs(x) {
    const out = new Array(CLF_F.length).fill(0);
    for (const t of MODELS.clf.trees) {
      let i = 0;
      while (t.f[i] >= 0) {
        const nx = Math.fround(x[t.f[i]]) < t.t[i] ? t.l[i] : t.r[i];
        out[t.f[i]] += t.val[nx] - t.val[i];
        i = nx;
      }
    }
    return out;
  }
  function predictSimRow(x) {
    let m = MODELS.sim.base;
    for (const t of MODELS.sim.trees) m += leaf(t, x);
    return m;
  }
  const predictAch = (s) => predictSimRow(SIM_F.map((k) => s[k]));

  /* ---------- forecast ---------- */
  function makeForecast(seedDay, month) {
    const rng = Rng(seedDay);
    const rain = {};
    for (let off = -2; off <= 7; off++) {
      const m = month;
      const p = (m === 7 || m === 8) ? 0.60 : (m === 6 || m === 9) ? 0.40 : m === 10 ? 0.10 : 0.03;
      const scale = (m >= 6 && m <= 9) ? 22 : 8;
      rain[off] = rng.u() < p ? Math.round(rng.gamma(0.9, scale) * 10) / 10 : 0;
    }
    return rain;
  }
  function withStorm(rain, extra) {
    const r = Object.assign({}, rain);
    if (extra > 0) { r[0] += 0.3 * extra; r[1] += extra; r[2] += 0.5 * extra; }
    return r;
  }

  /* ---------- telemetry simulator ---------- */
  function MineSim(name, seed) {
    const rng = Rng(seed);
    const units = [];
    for (let i = 1; i <= 4; i++) units.push({ name: "Drill jumbo " + i, kind: "drill" });
    for (let i = 1; i <= 3; i++) units.push({ name: "Loader " + i, kind: "loader" });
    units.push({ name: "Main hoist", kind: "hoist" });
    units.forEach((u) => {
      u.health = rng.uniform(55, 95); u.status = "ok"; u.repair = 0; u.hist = [u.health];
    });
    return {
      name, units, rng, absent: 6, blast: 1, ticks: 0,
      histAch: MODELS.seed.ach.slice(-6), histDrills: MODELS.seed.drills.slice(-6),
      histLoaders: MODELS.seed.loaders.slice(-6),
      tick(rs) {
        rs = Math.min(Math.max(rs, 0), 1);
        for (const u of units) {
          if (u.status === "down") {
            if (--u.repair <= 0) { u.status = "ok"; u.health = rng.uniform(80, 95); }
          } else {
            u.health -= rng.gamma(1.2, 0.30) * (1 + 1.5 * rs);
            if (rng.u() < 0.006 * (1 + 2 * rs)) u.health -= rng.uniform(10, 30);
            if (u.health <= 20) { u.health = 20; u.status = "down"; u.repair = rng.int(8, 24); }
          }
          u.hist.push(u.health); if (u.hist.length > 40) u.hist.shift();
        }
        this.absent = Math.min(Math.max(this.absent + 0.2 * (6 - this.absent) + rng.normal(0, 0.5), 2), 20);
        this.blast = Math.min(Math.max(0.7 * this.blast + 0.3 * rng.exp(1) + 0.25 * rs, 0.2), 8);
        this.ticks++;
      },
      fail(kind) {
        for (const u of units) if (u.kind === kind && u.status === "ok") {
          u.health = 20; u.status = "down"; u.repair = 20; u.hist.push(20); return u.name;
        }
        return null;
      },
      snapshot() {
        const ok = (k) => units.filter((u) => u.kind === k && u.status === "ok").length;
        const h = units.find((u) => u.kind === "hoist");
        return {
          drills_available: ok("drill"), loaders_available: ok("loader"),
          hoist_uptime_pct: h.status === "ok" ? Math.min(Math.max(h.health, 40), 100) : 40,
          blast_delay_hours: this.blast, absentee_pct: this.absent,
        };
      },
      maintenance() {
        return units.map((u) => {
          let eta = null;
          if (u.status === "ok" && u.hist.length >= 10) {
            const y = u.hist.slice(-20), n = y.length;
            const mx = (n - 1) / 2, my = y.reduce((a, b) => a + b, 0) / n;
            let sxy = 0, sxx = 0;
            y.forEach((v, i) => { sxy += (i - mx) * (v - my); sxx += (i - mx) * (i - mx); });
            const slope = sxy / sxx;
            if (slope < -0.05) eta = Math.max((u.health - 20) / -slope, 0) * 0.25;
          }
          return { name: u.name, kind: u.kind, status: u.status, health: u.health, eta };
        });
      },
    };
  }

  /* ---------- risk and actions ---------- */
  const ACTIONS = {
    overtime: { en: "Call standby crew / overtime", hi: "स्टैंडबाय क्रू / ओवरटाइम बुलाएँ", cost: 1.0 },
    drill: { en: "Redeploy 1 spare drill jumbo", hi: "1 अतिरिक्त ड्रिल जंबो तैनात करें", cost: 1.5 },
    loader: { en: "Redeploy 1 loader from another face", hi: "दूसरे फेस से 1 लोडर लगाएँ", cost: 1.5 },
    hoist: { en: "Priority repair / inspect the hoist", hi: "हॉइस्ट की प्राथमिकता से मरम्मत/जाँच", cost: 2.0 },
    blast: { en: "Re-sequence blasting to a dry window", hi: "ब्लास्टिंग को सूखे समय में स्थानांतरित करें", cost: 0.5 },
  };
  function applyAction(k, s) {
    if (k === "overtime") s.absentee_pct = Math.max(s.absentee_pct - 4, 3);
    else if (k === "drill") s.drills_available = Math.min(s.drills_available + 1, 4);
    else if (k === "loader") s.loaders_available = Math.min(s.loaders_available + 1, 3);
    else if (k === "hoist") s.hoist_uptime_pct = Math.min(s.hoist_uptime_pct + 8, 100);
    else if (k === "blast") s.blast_delay_hours = Math.max(s.blast_delay_hours - 1.5, 0.5);
  }
  const KEYS = Object.keys(ACTIONS);
  function combosWithin(budget) {
    const out = [];
    for (let mask = 0; mask < (1 << KEYS.length); mask++) {
      const c = KEYS.filter((_, i) => mask & (1 << i));
      const cost = c.reduce((a, k) => a + ACTIONS[k].cost, 0);
      if (cost <= budget + 1e-9) out.push({ keys: c, cost });
    }
    out.sort((a, b) => a.keys.length - b.keys.length);
    return out;
  }
  const COMBOS = combosWithin(3.0);

  function evaluate(mine, rain, month, planned) {
    const snap = mine.snapshot();
    const rTom = rain[1], rToday = rain[0];
    const r3fc = rTom + rToday + rain[-1];
    const r3lag = rToday + rain[-1] + rain[-2];
    const achToday = predictAch(Object.assign({}, snap, { rain_3day_mm: r3lag }));
    const a7 = mine.histAch.concat([achToday]).slice(-7);
    const d7 = mine.histDrills.concat([snap.drills_available]).slice(-7);
    const l7 = mine.histLoaders.concat([snap.loaders_available]).slice(-7);
    const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
    const x = [
      rTom, r3fc, snap.drills_available, snap.loaders_available, snap.hoist_uptime_pct,
      snap.blast_delay_hours, snap.absentee_pct, r3lag, achToday, mean(a7), mean(d7), mean(l7),
      a7.filter((v) => v < 90).length,
      Math.sin((2 * Math.PI * month) / 12), Math.cos((2 * Math.PI * month) / 12),
    ];
    const prob = predictClf(x);
    const level = prob >= 0.6 ? "High" : prob >= 0.3 ? "Medium" : "Low";
    const c = contribs(x);
    const reasons = c.map((v, i) => ({ f: CLF_F[i], value: x[i], c: v }))
      .sort((a, b) => Math.abs(b.c) - Math.abs(a.c)).slice(0, 3);

    const state = Object.assign({}, snap, {
      blast_delay_hours: rTom > 20 ? MODELS.bd_wet : MODELS.bd_dry, rain_3day_mm: r3fc,
    });
    let base = null, best = { score: 0, ach: 0, combo: COMBOS[0] };
    COMBOS.forEach((cb, i) => {
      const s = Object.assign({}, state);
      cb.keys.forEach((k) => applyAction(k, s));
      const a = predictAch(s);
      if (i === 0) { base = a; best = { score: 0, ach: a, combo: cb }; return; }
      const score = a - base - 0.3 * cb.cost;
      if (score > best.score + 1e-9) best = { score, ach: a, combo: cb };
    });
    const advice = [];
    if (rTom >= 25 || r3fc >= 60) advice.push("rain");
    if (snap.drills_available <= 2) advice.push("drills");
    if (snap.hoist_uptime_pct < 85) advice.push("hoist");
    if (snap.absentee_pct >= 10) advice.push("absent");
    return {
      prob, level, reasons, snap, rainTomorrow: rTom, rain3d: r3fc,
      achBefore: base, achAfter: best.ach, tonnesRecovered: ((best.ach - base) / 100) * planned,
      actions: best.combo.keys, cost: best.combo.cost, advice, planned,
    };
  }

  function scenarios(mine, rain, month, planned) {
    const live = evaluate(mine, rain, month, planned);
    const healthy = { drills_available: 4, loaders_available: 3, hoist_uptime_pct: 95, blast_delay_hours: MODELS.bd_dry, absentee_pct: 6, rain_3day_mm: 10 };
    const sLive = Object.assign({}, live.snap, {
      blast_delay_hours: live.rainTomorrow > 20 ? MODELS.bd_wet : MODELS.bd_dry, rain_3day_mm: live.rain3d,
    });
    const sStorm = Object.assign({}, healthy, { rain_3day_mm: 90, blast_delay_hours: MODELS.bd_wet });
    const sFail = Object.assign({}, healthy, { drills_available: 2, hoist_uptime_pct: 80 });
    const sFix = Object.assign({}, sStorm); ["overtime", "blast"].forEach((k) => applyAction(k, sFix));
    const rows = [
      ["Live conditions now", sLive], ["Healthy mine (reference)", healthy],
      ["Heavy storm (90 mm / 3 days)", sStorm], ["Two drills down + weak hoist", sFail],
      ["Storm + overtime + dry-window blasting", sFix],
    ];
    return rows.map(([name, s]) => { const a = predictAch(s); return { name, pct: a, tonnes: (a / 100) * planned }; });
  }

  /* ---------- 3D reserve model (Gaussian process / kriging) ---------- */
  const XMAX = 800, YMAX = 400, ZMAX = 100, BX = 40, BY = 40, BZ = 5, DENSITY = 3.6;
  const LS = [180, 130, 4.5], NOISE_SD = 1.5;
  const NX = XMAX / BX, NY = YMAX / BY, NZ = ZMAX / BZ;

  function trueGrade(x, y, z) {
    const zc = 25 + 0.05 * x + 0.02 * y;
    const lens = Math.exp(-((z - zc) ** 2) / (2 * 3.5 ** 2));
    const env = Math.exp(-0.5 * (((x - 400) / 280) ** 4 + ((y - 200) / 150) ** 2));
    const ripple = 1.5 * Math.sin(x / 70) * Math.cos(y / 60);
    return 14 + 32 * lens * env + ripple;
  }
  function baseCollars(n, seed) {
    const rng = Rng(seed || 7);
    const nx = Math.ceil(Math.sqrt(n * 2)), ny = Math.ceil(n / nx);
    const pts = [];
    for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++)
      pts.push([((i + 0.5) * XMAX) / nx, ((j + 0.5) * YMAX) / ny]);
    return pts.slice(0, n).map(([x, y]) => [x + rng.normal(0, 18), y + rng.normal(0, 18)]);
  }
  function drillAssays(collars) {
    const pts = [], g = [];
    for (const [x, y] of collars) {
      const rng = Rng(Math.floor(Math.abs(x) * 1000 + Math.abs(y) * 7));
      for (let z = 2.5; z < ZMAX; z += 5) { pts.push([x, y, z]); g.push(trueGrade(x, y, z) + rng.normal(0, NOISE_SD)); }
    }
    return { pts, g };
  }
  const kern = (a, b) => Math.exp(-0.5 * (((a[0] - b[0]) / LS[0]) ** 2 + ((a[1] - b[1]) / LS[1]) ** 2 + ((a[2] - b[2]) / LS[2]) ** 2));

  function fitReserve(collars) {
    const { pts, g } = drillAssays(collars);
    const n = pts.length;
    const mu = g.reduce((a, b) => a + b, 0) / n;
    const sd = Math.sqrt(g.reduce((a, b) => a + (b - mu) ** 2, 0) / n);
    const ys = g.map((v) => (v - mu) / sd);
    const noise = (NOISE_SD / sd) ** 2;
    const L = new Float64Array(n * n);
    for (let i = 0; i < n; i++) {
      for (let j = 0; j <= i; j++) {
        let s = kern(pts[i], pts[j]) + (i === j ? noise : 0);
        for (let k = 0; k < j; k++) s -= L[i * n + k] * L[j * n + k];
        L[i * n + j] = i === j ? Math.sqrt(Math.max(s, 1e-12)) : s / L[j * n + j];
      }
    }
    const z = new Float64Array(n), alpha = new Float64Array(n);
    for (let i = 0; i < n; i++) { let s = ys[i]; for (let k = 0; k < i; k++) s -= L[i * n + k] * z[k]; z[i] = s / L[i * n + i]; }
    for (let i = n - 1; i >= 0; i--) { let s = z[i]; for (let k = i + 1; k < n; k++) s -= L[k * n + i] * alpha[k]; alpha[i] = s / L[i * n + i]; }

    const total = NX * NY * NZ;
    const X = new Float32Array(total), Y = new Float32Array(total), Z = new Float32Array(total);
    const mean = new Float32Array(total), std = new Float32Array(total), truth = new Float32Array(total);
    const kv = new Float64Array(n), v = new Float64Array(n);
    let idx = 0;
    for (let i = 0; i < NX; i++) for (let j = 0; j < NY; j++) for (let k = 0; k < NZ; k++) {
      const p = [(i + 0.5) * BX, (j + 0.5) * BY, (k + 0.5) * BZ];
      let m = 0;
      for (let a = 0; a < n; a++) { kv[a] = kern(p, pts[a]); m += kv[a] * alpha[a]; }
      let vv = 0;
      for (let a = 0; a < n; a++) { let s = kv[a]; for (let b = 0; b < a; b++) s -= L[a * n + b] * v[b]; v[a] = s / L[a * n + a]; vv += v[a] * v[a]; }
      X[idx] = p[0]; Y[idx] = p[1]; Z[idx] = p[2];
      mean[idx] = mu + sd * m; std[idx] = Math.max(sd * Math.sqrt(Math.max(1 - vv, 0)), 0.3);
      truth[idx] = trueGrade(p[0], p[1], p[2]); idx++;
    }
    // independent check on 150 random points
    const rng = Rng(99); let se = 0;
    for (let t = 0; t < 150; t++) {
      const p = [rng.uniform(0, XMAX), rng.uniform(0, YMAX), rng.uniform(0, ZMAX)];
      let m = 0; for (let a = 0; a < n; a++) m += kern(p, pts[a]) * alpha[a];
      se += (mu + sd * m - trueGrade(p[0], p[1], p[2])) ** 2;
    }
    return { X, Y, Z, mean, std, truth, collars, rmse: Math.sqrt(se / 150), n: total };
  }

  function erf(x) {
    const s = Math.sign(x); x = Math.abs(x);
    const t = 1 / (1 + 0.3275911 * x);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y;
  }
  const cdf = (z) => 0.5 * (1 + erf(z / Math.SQRT2));

  function tonnage(rm, cutoff) {
    const blk = BX * BY * BZ * DENSITY;
    let est = 0, truth = 0, gSum = 0, gN = 0;
    const cls = { high: 0, med: 0, low: 0 };
    for (let i = 0; i < rm.n; i++) {
      const p = 1 - cdf((cutoff - rm.mean[i]) / rm.std[i]);
      est += p * blk; if (rm.truth[i] >= cutoff) truth += blk;
      if (p >= 0.5) { gSum += rm.mean[i]; gN++; }
      if (p >= 0.8) cls.high += p * blk; else if (p >= 0.5) cls.med += p * blk; else if (p >= 0.2) cls.low += p * blk;
    }
    return { est, truth, meanGrade: gN ? gSum / gN : 0, cls };
  }
  function nextHoles(rm, cutoff, k, minSep) {
    k = k || 3; minSep = minSep || 120;
    const score = new Float64Array(NX * NY);
    for (let i = 0; i < rm.n; i++) {
      const ix = Math.floor(rm.X[i] / BX), iy = Math.floor(rm.Y[i] / BY);
      const p = 1 - cdf((cutoff - rm.mean[i]) / rm.std[i]);
      score[ix * NY + iy] += p * (1 - p);
    }
    const order = Array.from(score.keys()).sort((a, b) => score[b] - score[a]);
    const picks = [];
    for (const f of order) {
      const x = ((Math.floor(f / NY) + 0.5) * BX), y = ((f % NY) + 0.5) * BY;
      const farFromPicks = picks.every((q) => Math.hypot(x - q.x, y - q.y) >= minSep);
      const farFromHoles = rm.collars.every(([cx, cy]) => Math.hypot(x - cx, y - cy) >= 60);
      if (farFromPicks && farFromHoles) picks.push({ x, y, score: score[f] });
      if (picks.length === k) break;
    }
    return picks;
  }

  return {
    CLF_F, SIM_F, MODELS, predictClf, predictAch, contribs, makeForecast, withStorm, MineSim,
    ACTIONS, evaluate, scenarios, baseCollars, fitReserve, tonnage, nextHoles,
    dims: { NX, NY, NZ, XMAX, YMAX, ZMAX, BX, BY, BZ, DENSITY },
  };
}
