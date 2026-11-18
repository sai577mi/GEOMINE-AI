"""
GeoMine-AI engine (v2).  Used by app_v2.py.

Contains
  1. Live weather      : Open-Meteo forecast (free, no key) with offline fallback
  2. Telemetry         : simulated equipment sensor stream + predictive maintenance
  3. Risk + actions    : shortfall model from Step 5, what-if simulator + optimizer
  4. Reserve model     : 3D Gaussian-process (kriging-equivalent) grade model,
                         drill-hole simulator, tonnage and next-drill-hole advice

Everything that is simulated is labelled as simulated in the dashboard.
"""

import itertools
import json
import os
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel as C, RBF, WhiteKernel

# Coordinates from MOIL's public environmental-clearance documents
MINES = {
    "Munsar": (21.4042, 79.2792),
    "Gumgaon": (21.4083, 78.9857),
}

FEATURES = [
    "rain_forecast_mm", "rain_forecast_3d_mm",
    "drills_available_lag1", "loaders_available_lag1", "hoist_uptime_pct_lag1",
    "blast_delay_hours_lag1", "absentee_pct_lag1", "rain_3day_mm_lag1",
    "achievement_pct_lag1", "ach_mean7_lag1", "drills_mean7_lag1",
    "loaders_mean7_lag1", "shortfalls_last7", "month_sin", "month_cos",
]

FRIENDLY = {
    "rain_forecast_mm": ("Rain forecast for tomorrow (mm)", "कल की वर्षा का पूर्वानुमान (मिमी)"),
    "rain_forecast_3d_mm": ("3-day rain forecast (mm)", "3 दिन की वर्षा का पूर्वानुमान (मिमी)"),
    "drills_available_lag1": ("Drill jumbos working", "चालू ड्रिल जंबो"),
    "loaders_available_lag1": ("Loaders working", "चालू लोडर"),
    "hoist_uptime_pct_lag1": ("Hoist uptime (%)", "हॉइस्ट अपटाइम (%)"),
    "blast_delay_hours_lag1": ("Blasting delay (h)", "ब्लास्टिंग में देरी (घंटे)"),
    "absentee_pct_lag1": ("Absenteeism (%)", "अनुपस्थिति (%)"),
    "rain_3day_mm_lag1": ("Rain in last 3 days (mm)", "पिछले 3 दिनों की वर्षा (मिमी)"),
    "achievement_pct_lag1": ("Today's output vs plan (%)", "आज का उत्पादन बनाम योजना (%)"),
    "ach_mean7_lag1": ("7-day average output vs plan (%)", "7 दिन का औसत उत्पादन (%)"),
    "drills_mean7_lag1": ("7-day average drills working", "7 दिन में औसत चालू ड्रिल"),
    "loaders_mean7_lag1": ("7-day average loaders working", "7 दिन में औसत चालू लोडर"),
    "shortfalls_last7": ("Shortfall days in last week", "पिछले सप्ताह कमी वाले दिन"),
    "month_sin": ("Season", "मौसम"),
    "month_cos": ("Season", "मौसम"),
}

SIM_FEATURES = ["drills_available", "loaders_available", "hoist_uptime_pct",
                "blast_delay_hours", "absentee_pct", "rain_3day_mm"]

# ---------------------------------------------------------------
# 1. Live weather
# ---------------------------------------------------------------
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def today_ist():
    return pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()


def parse_open_meteo(data):
    d = data["daily"]
    rain = pd.to_numeric(pd.Series(d["precipitation_sum"]), errors="coerce").fillna(0.0)
    return pd.DataFrame({"date": pd.to_datetime(d["time"]), "rain_mm": rain.values})


def simulated_forecast(today):
    days = pd.date_range(today - pd.Timedelta(days=2), periods=10)
    rng = np.random.default_rng(int(today.strftime("%Y%m%d")))
    month = days.month.values
    p = np.select([np.isin(month, [7, 8]), np.isin(month, [6, 9]), month == 10],
                  [0.60, 0.40, 0.10], default=0.03)
    scale = np.where(np.isin(month, [6, 7, 8, 9]), 22.0, 8.0)
    rain = np.where(rng.random(len(days)) < p, rng.gamma(0.9, scale), 0.0)
    return pd.DataFrame({"date": days, "rain_mm": np.round(rain, 1)})


def fetch_forecast(lat, lon, timeout=6):
    """Returns (DataFrame[date, rain_mm], 'live' | 'offline')."""
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "daily": "precipitation_sum",
        "past_days": 2, "forecast_days": 7, "timezone": "Asia/Kolkata",
    })
    try:
        with urllib.request.urlopen(f"{OPEN_METEO}?{q}", timeout=timeout) as r:
            return parse_open_meteo(json.load(r)), "live"
    except Exception:
        return simulated_forecast(today_ist()), "offline"


def apply_storm(fc, extra_mm, today):
    """Demo helper: overlay a storm on today+1 and today+2."""
    fc = fc.copy()
    if extra_mm > 0:
        fc.loc[fc.date == today, "rain_mm"] += 0.3 * extra_mm
        fc.loc[fc.date == today + pd.Timedelta(days=1), "rain_mm"] += extra_mm
        fc.loc[fc.date == today + pd.Timedelta(days=2), "rain_mm"] += 0.5 * extra_mm
    return fc


# ---------------------------------------------------------------
# 2. Telemetry simulator + predictive maintenance
# ---------------------------------------------------------------
@dataclass
class Unit:
    name: str
    kind: str                       # drill | loader | hoist
    health: float = 85.0
    status: str = "ok"              # ok | down
    repair_left: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=40))


class MineSim:
    """Simulated live sensor feed for one mine (1 tick = 15 simulated minutes)."""

    def __init__(self, name, seed, hist_ach, hist_drills, hist_loaders):
        self.name = name
        self.rng = np.random.default_rng(seed)
        self.units = (
            [Unit(f"Drill jumbo {i + 1}", "drill") for i in range(4)]
            + [Unit(f"Loader {i + 1}", "loader") for i in range(3)]
            + [Unit("Main hoist", "hoist")]
        )
        for u in self.units:
            u.health = float(self.rng.uniform(55, 95))
            u.history.append(u.health)
        self.absent = 6.0
        self.blast_delay = 1.0
        self.ticks = 0
        self.hist_ach = list(hist_ach)[-6:]
        self.hist_drills = list(hist_drills)[-6:]
        self.hist_loaders = list(hist_loaders)[-6:]

    def tick(self, rain_stress=0.0):
        rs = float(np.clip(rain_stress, 0, 1))
        for u in self.units:
            if u.status == "down":
                u.repair_left -= 1
                if u.repair_left <= 0:
                    u.status, u.health = "ok", float(self.rng.uniform(80, 95))
            else:
                u.health -= self.rng.gamma(1.2, 0.30) * (1 + 1.5 * rs)
                if self.rng.random() < 0.006 * (1 + 2 * rs):
                    u.health -= self.rng.uniform(10, 30)
                if u.health <= 20:
                    u.health, u.status = 20.0, "down"
                    u.repair_left = int(self.rng.integers(8, 24))
            u.history.append(u.health)
        self.absent = float(np.clip(self.absent + 0.2 * (6 - self.absent)
                                    + self.rng.normal(0, 0.5), 2, 20))
        self.blast_delay = float(np.clip(0.7 * self.blast_delay
                                         + 0.3 * self.rng.exponential(1.0)
                                         + 0.25 * rs, 0.2, 8))
        self.ticks += 1

    def force_failure(self, kind):
        for u in self.units:
            if u.kind == kind and u.status == "ok":
                u.health, u.status, u.repair_left = 20.0, "down", 20
                u.history.append(u.health)
                return u.name
        return None

    def snapshot(self):
        ok = lambda k: sum(1 for u in self.units if u.kind == k and u.status == "ok")
        hoist = next(u for u in self.units if u.kind == "hoist")
        return {
            "drills_available": ok("drill"),
            "loaders_available": ok("loader"),
            "hoist_uptime_pct": float(np.clip(hoist.health, 40, 100)) if hoist.status == "ok" else 40.0,
            "blast_delay_hours": self.blast_delay,
            "absentee_pct": self.absent,
        }

    def maintenance_forecast(self):
        """Linear trend of each unit's health -> estimated hours to failure."""
        rows = []
        for u in self.units:
            eta = None
            if u.status == "ok" and len(u.history) >= 10:
                y = np.array(u.history, dtype=float)[-20:]
                slope = np.polyfit(np.arange(len(y)), y, 1)[0]
                if slope < -0.05:
                    eta = max((u.health - 20.0) / (-slope), 0) * 0.25   # ticks -> hours
            rows.append({"unit": u.name, "kind": u.kind, "status": u.status,
                         "health": round(u.health, 1),
                         "hours_to_failure": None if eta is None else round(eta, 1)})
        return pd.DataFrame(rows)


# ---------------------------------------------------------------
# 3. Models, risk and corrective actions
# ---------------------------------------------------------------
ACTIONS = {
    "overtime": ("Call standby crew / overtime", "स्टैंडबाय क्रू / ओवरटाइम बुलाएँ", 1.0),
    "drill":    ("Redeploy 1 spare drill jumbo", "1 अतिरिक्त ड्रिल जंबो तैनात करें", 1.5),
    "loader":   ("Redeploy 1 loader from another face", "दूसरे फेस से 1 लोडर लगाएँ", 1.5),
    "hoist":    ("Priority repair / inspect the hoist", "हॉइस्ट की प्राथमिकता से मरम्मत/जाँच", 2.0),
    "blast":    ("Re-sequence blasting to a dry window", "ब्लास्टिंग को सूखे समय में स्थानांतरित करें", 0.5),
}


def apply_action(key, s):
    if key == "overtime":
        s["absentee_pct"] = max(s["absentee_pct"] - 4.0, 3.0)
    elif key == "drill":
        s["drills_available"] = min(s["drills_available"] + 1, 4)
    elif key == "loader":
        s["loaders_available"] = min(s["loaders_available"] + 1, 3)
    elif key == "hoist":
        s["hoist_uptime_pct"] = min(s["hoist_uptime_pct"] + 8.0, 100.0)
    elif key == "blast":
        s["blast_delay_hours"] = max(s["blast_delay_hours"] - 1.5, 0.5)


class Models:
    def __init__(self, folder):
        model_path = os.path.join(folder, "shortfall_model.json")
        daily_path = os.path.join(folder, "mine_daily.csv")
        if not (os.path.exists(model_path) and os.path.exists(daily_path)):
            raise FileNotFoundError("shortfall_model.json and mine_daily.csv are needed "
                                    "(created in Steps 4 and 5).")
        self.clf = xgb.XGBClassifier()
        self.clf.load_model(model_path)
        self.daily = pd.read_csv(daily_path, parse_dates=["date"])
        train = self.daily[self.daily.date < "2025-01-01"]
        self.sim = xgb.XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.9,
            min_child_weight=5, monotone_constraints="(1,1,1,-1,-1,-1)", random_state=42,
        ).fit(train[SIM_FEATURES], train.achievement_pct)
        self.bd_dry = float(train.loc[train.rainfall_mm <= 20, "blast_delay_hours"].mean())
        self.bd_wet = float(train.loc[train.rainfall_mm > 20, "blast_delay_hours"].mean())
        tail = self.daily.tail(7)
        self.seed_hist = (tail.achievement_pct.tolist(), tail.drills_available.tolist(),
                          tail.loaders_available.tolist())

    def predict_ach(self, states):
        return self.sim.predict(pd.DataFrame(states)[SIM_FEATURES])


def _rain(fc, day):
    r = fc.loc[fc.date == day, "rain_mm"]
    return float(r.iloc[0]) if len(r) else 0.0


def evaluate(models, mine, fc, today, planned=150.0, budget=3.0):
    """Tomorrow's shortfall risk, reasons and best corrective actions for one mine."""
    snap = mine.snapshot()
    tom = today + pd.Timedelta(days=1)
    d1 = pd.Timedelta(days=1)

    r_tom, r_today = _rain(fc, tom), _rain(fc, today)
    r3_fc = r_tom + r_today + _rain(fc, today - d1)
    r3_lag = r_today + _rain(fc, today - d1) + _rain(fc, today - 2 * d1)

    # today's output so far (projected by the what-if model) joins the history
    today_state = dict(snap, rain_3day_mm=r3_lag)
    ach_today = float(models.predict_ach([today_state])[0])
    ach7 = (mine.hist_ach + [ach_today])[-7:]
    dr7 = (mine.hist_drills + [snap["drills_available"]])[-7:]
    ld7 = (mine.hist_loaders + [snap["loaders_available"]])[-7:]

    row = pd.DataFrame([{
        "rain_forecast_mm": r_tom, "rain_forecast_3d_mm": r3_fc,
        "drills_available_lag1": snap["drills_available"],
        "loaders_available_lag1": snap["loaders_available"],
        "hoist_uptime_pct_lag1": snap["hoist_uptime_pct"],
        "blast_delay_hours_lag1": snap["blast_delay_hours"],
        "absentee_pct_lag1": snap["absentee_pct"], "rain_3day_mm_lag1": r3_lag,
        "achievement_pct_lag1": ach_today, "ach_mean7_lag1": float(np.mean(ach7)),
        "drills_mean7_lag1": float(np.mean(dr7)), "loaders_mean7_lag1": float(np.mean(ld7)),
        "shortfalls_last7": float(sum(a < 90 for a in ach7)),
        "month_sin": float(np.sin(2 * np.pi * tom.month / 12)),
        "month_cos": float(np.cos(2 * np.pi * tom.month / 12)),
    }])[FEATURES]

    prob = float(models.clf.predict_proba(row)[0, 1])
    level = "High" if prob >= 0.60 else "Medium" if prob >= 0.30 else "Low"

    booster = models.clf.get_booster()
    contrib = booster.predict(xgb.DMatrix(row), pred_contribs=True)[0][:-1]
    order = np.argsort(-np.abs(contrib))[:3]
    reasons = [(FEATURES[i], float(row.iloc[0, i]), float(contrib[i])) for i in order]

    # tomorrow's expected operating state and best actions
    state = dict(snap, blast_delay_hours=models.bd_wet if r_tom > 20 else models.bd_dry,
                 rain_3day_mm=r3_fc)
    keys = list(ACTIONS)
    combos = [c for k in range(len(keys) + 1) for c in itertools.combinations(keys, k)
              if sum(ACTIONS[a][2] for a in c) <= budget]
    states = []
    for c in combos:
        s2 = dict(state)
        for a in c:
            apply_action(a, s2)
        states.append(s2)
    ach = models.predict_ach(states)
    base = float(ach[0])
    best_i, best = 0, 0.0
    for i, c in enumerate(combos):
        score = (ach[i] - base) - 0.3 * sum(ACTIONS[a][2] for a in c)
        if score > best + 1e-9:
            best_i, best = i, score
    chosen = list(combos[best_i])

    advice = []
    if r_tom >= 25 or r3_fc >= 60:
        advice.append("rain")
    if snap["drills_available"] <= 2:
        advice.append("drills")
    if snap["hoist_uptime_pct"] < 85:
        advice.append("hoist")
    if snap["absentee_pct"] >= 10:
        advice.append("absent")

    return {
        "prob": prob, "level": level, "reasons": reasons, "snap": snap,
        "rain_tomorrow": r_tom, "rain_3d": r3_fc,
        "ach_before": base, "ach_after": float(ach[best_i]),
        "tonnes_recovered": (float(ach[best_i]) - base) / 100 * planned,
        "actions": chosen, "cost": sum(ACTIONS[a][2] for a in chosen),
        "advice": advice, "planned": planned,
    }


def scenario_table(models, mine, fc, today, planned=150.0):
    """Expected output tomorrow under what-if scenarios (healthy-mine reference + live state)."""
    live = evaluate(models, mine, fc, today, planned)
    healthy = {"drills_available": 4, "loaders_available": 3, "hoist_uptime_pct": 95.0,
               "blast_delay_hours": models.bd_dry, "absentee_pct": 6.0, "rain_3day_mm": 10.0}
    s_live = dict(live["snap"], blast_delay_hours=models.bd_wet if live["rain_tomorrow"] > 20
                  else models.bd_dry, rain_3day_mm=live["rain_3d"])
    s_storm = dict(healthy, rain_3day_mm=90.0, blast_delay_hours=models.bd_wet)
    s_fail = dict(healthy, drills_available=2, hoist_uptime_pct=80.0)
    s_fix = dict(s_storm)
    for a in ("overtime", "blast"):
        apply_action(a, s_fix)
    names = ["Live conditions now", "Healthy mine (reference)", "Heavy storm (90 mm / 3 days)",
             "Two drills down + weak hoist", "Storm + overtime + dry-window blasting"]
    ach = models.predict_ach([s_live, healthy, s_storm, s_fail, s_fix])
    return pd.DataFrame({"scenario": names, "output_pct": np.round(ach, 1),
                         "tonnes": np.round(ach / 100 * planned, 0)})


# ---------------------------------------------------------------
# 4. 3D reserve model (Gaussian process = kriging with uncertainty)
# ---------------------------------------------------------------
# Local mine grid in metres: x east (0-800), y north (0-400), z depth (0-100)
XMAX, YMAX, ZMAX = 800.0, 400.0, 100.0
BLOCK = (40.0, 40.0, 5.0)
DENSITY = 3.6          # t/m3, assumed bulk density of manganese ore (edit for real data)


def true_grade(x, y, z):
    """Hidden 'truth' used only to simulate drilling and to validate the model."""
    zc = 25 + 0.05 * x + 0.02 * y                           # dipping lens
    lens = np.exp(-((z - zc) ** 2) / (2 * 3.5 ** 2))
    env = np.exp(-0.5 * (((x - 400) / 280) ** 4 + ((y - 200) / 150) ** 2))
    ripple = 1.5 * np.sin(x / 70) * np.cos(y / 60)
    return 14 + 32 * lens * env + ripple


def base_collars(n, seed=7):
    rng = np.random.default_rng(seed)
    nx = int(np.ceil(np.sqrt(n * 2)))
    ny = int(np.ceil(n / nx))
    xs = (np.arange(nx) + 0.5) * XMAX / nx
    ys = (np.arange(ny) + 0.5) * YMAX / ny
    pts = np.array([(x, y) for x in xs for y in ys])[:n]
    return pts + rng.normal(0, 18, pts.shape)


def drill(collars):
    """Simulated assays every 5 m down each vertical hole (noise sd 1.5 % Mn)."""
    rows = []
    zs = np.arange(2.5, ZMAX, 5.0)
    for x, y in collars:
        rng = np.random.default_rng(int(abs(x) * 1000 + abs(y) * 7))
        g = true_grade(x, y, zs) + rng.normal(0, 1.5, len(zs))
        rows += [(x, y, z, gi) for z, gi in zip(zs, g)]
    return pd.DataFrame(rows, columns=["x", "y", "z", "grade"])


@dataclass
class ReserveModel:
    X: np.ndarray
    Y: np.ndarray
    Z: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    truth: np.ndarray
    shape: tuple
    collars: np.ndarray
    holdout_rmse: float


def fit_reserve(collars):
    data = drill(collars)
    pts = data[["x", "y", "z"]].values
    y = data.grade.values
    noise = (1.5 / y.std()) ** 2
    kernel = C(1.0, "fixed") * RBF([180.0, 130.0, 4.5], "fixed") + WhiteKernel(noise, "fixed")
    gp = GaussianProcessRegressor(kernel, normalize_y=True, optimizer=None).fit(pts, y)

    xs = np.arange(BLOCK[0] / 2, XMAX, BLOCK[0])
    ys = np.arange(BLOCK[1] / 2, YMAX, BLOCK[1])
    zs = np.arange(BLOCK[2] / 2, ZMAX, BLOCK[2])
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    grid = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    mean, std = gp.predict(grid, return_std=True)
    std = np.maximum(std, 0.3)
    truth = true_grade(grid[:, 0], grid[:, 1], grid[:, 2])

    # independent check: 150 random points the model has never seen
    rng = np.random.default_rng(99)
    t = np.column_stack([rng.uniform(0, XMAX, 150), rng.uniform(0, YMAX, 150),
                         rng.uniform(0, ZMAX, 150)])
    rmse = float(np.sqrt(np.mean((gp.predict(t) - true_grade(*t.T)) ** 2)))
    return ReserveModel(X.ravel(), Y.ravel(), Z.ravel(), mean, std, truth,
                        X.shape, np.asarray(collars), rmse)


def tonnage(rm, cutoff):
    vol = BLOCK[0] * BLOCK[1] * BLOCK[2]
    p = 1 - norm.cdf((cutoff - rm.mean) / rm.std)
    t_blk = vol * DENSITY
    est = float((p * t_blk).sum())
    true_t = float(((rm.truth >= cutoff) * t_blk).sum())
    ore = p >= 0.5
    mean_grade = float(rm.mean[ore].mean()) if ore.any() else 0.0
    classes = {
        "Higher confidence (p >= 0.8)": float((t_blk * p)[p >= 0.8].sum()),
        "Medium confidence (0.5 - 0.8)": float((t_blk * p)[(p >= 0.5) & (p < 0.8)].sum()),
        "Low confidence (0.2 - 0.5)": float((t_blk * p)[(p >= 0.2) & (p < 0.5)].sum()),
    }
    return {"est": est, "truth": true_t, "mean_grade": mean_grade,
            "classes": classes, "p": p}


def next_drill_holes(rm, cutoff, k=3, min_sep=120.0):
    """Surface locations where one more hole would remove the most ore/waste doubt."""
    p = 1 - norm.cdf((cutoff - rm.mean) / rm.std)
    nx, ny, nz = rm.shape
    score = (p * (1 - p)).reshape(nx, ny, nz).sum(axis=2)
    xs = rm.X.reshape(rm.shape)[:, 0, 0]
    ys = rm.Y.reshape(rm.shape)[0, :, 0]
    picks = []
    for flat in np.argsort(-score.ravel()):
        i, j = np.unravel_index(flat, score.shape)
        pt = (float(xs[i]), float(ys[j]))
        if all(np.hypot(pt[0] - a, pt[1] - b) >= min_sep for a, b, _ in picks) and \
           (len(rm.collars) == 0 or np.min(np.hypot(rm.collars[:, 0] - pt[0],
                                                    rm.collars[:, 1] - pt[1])) >= 60):
            picks.append((pt[0], pt[1], float(score[i, j])))
        if len(picks) == k:
            break
    return picks
