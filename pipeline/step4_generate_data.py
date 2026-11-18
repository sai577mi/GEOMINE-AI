"""
Step 4: Generate SYNTHETIC daily mine operations data (3 years).

Scaled to a small underground manganese mine (about 50,000 tonnes/year,
roughly the size of Munsar). All numbers are simulated, NOT real MOIL data.
Replace mine_daily.csv with real data later; the later steps only need the
same column names.

Install:  pip install numpy pandas matplotlib
Output:   mine_daily.csv, data_overview.png
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

SEED = 42
rng = np.random.default_rng(SEED)

dates = pd.date_range("2023-01-01", "2025-12-31", freq="D")
n = len(dates)
doy = dates.dayofyear.values
month = dates.month.values
year_idx = dates.year.values - dates.year.min()

# ------------------------------------------------------------------
# 1. Weather
# ------------------------------------------------------------------
monsoon_strength = rng.uniform(0.8, 1.25, size=year_idx.max() + 1)   # varies by year
p_rain = np.select(
    [np.isin(month, [7, 8]), np.isin(month, [6, 9]), np.isin(month, [10])],
    [0.60, 0.40, 0.10],
    default=0.03,
)
scale = np.select(
    [np.isin(month, [6, 7, 8, 9])], [22.0], default=8.0
) * monsoon_strength[year_idx]
rain = np.where(rng.random(n) < p_rain, rng.gamma(0.9, scale), 0.0)
rain = np.round(rain, 1)

temp = 27 + 8 * np.sin(2 * np.pi * (doy - 45) / 365) + rng.normal(0, 1.5, n)
rain_3d = pd.Series(rain).rolling(3, min_periods=1).sum().values

# ------------------------------------------------------------------
# 2. Equipment availability (breakdowns more likely after heavy rain)
# ------------------------------------------------------------------
def simulate_units(n_units, base_rate, repair_days):
    avail = np.ones((n, n_units), dtype=int)
    down_until = np.zeros(n_units, dtype=int)
    for t in range(n):
        rate = base_rate * (1 + 1.2 * (rain_3d[t] > 40))
        for u in range(n_units):
            if down_until[u] > t:
                avail[t, u] = 0
            elif rng.random() < rate:
                down_until[u] = t + rng.integers(repair_days[0], repair_days[1] + 1)
                avail[t, u] = 0
    return avail

drills = simulate_units(4, 0.015, (1, 5)).sum(axis=1)      # 4 drill jumbos
loaders = simulate_units(3, 0.012, (1, 6)).sum(axis=1)     # 3 loaders (LHD)
hoist_up = np.clip(
    97 - 18 * (rain_3d > 60) - rng.exponential(2.0, n) - 25 * (rng.random(n) < 0.01),
    40, 100,
)                                                           # hoist uptime %

# ------------------------------------------------------------------
# 3. Operations: blasting delays and absenteeism
# ------------------------------------------------------------------
blast_delay_h = rng.exponential(1.0, n) + 1.5 * (rain > 20) + 0.8 * (drills <= 2)
blast_delay_h = np.round(np.clip(blast_delay_h, 0, 10), 1)

absent_pct = 6 + rng.normal(0, 1.5, n)
absent_pct += 7 * np.isin(month, [3, 11]) * (rng.random(n) < 0.35)   # festival periods
absent_pct = np.round(np.clip(absent_pct, 1, 30), 1)

# ------------------------------------------------------------------
# 4. Planned vs actual production
# ------------------------------------------------------------------
planned = np.round(150 + rng.normal(0, 4, n), 1)       # plan ignores weather and breakdowns

capacity_factor = (
    0.30
    + 0.25 * (drills / 4)
    + 0.25 * (loaders / 3)
    + 0.20 * (hoist_up / 100)
)
rain_penalty = 1 - 0.20 * np.clip(rain_3d / 80, 0, 1)
blast_penalty = 1 - 0.35 * np.clip(blast_delay_h / 8, 0, 1)
absent_penalty = 1 - 0.6 * (absent_pct / 100)
noise = rng.normal(1.0, 0.04, n)

# plans assume normal operations, so on a typical day output is about 100% of plan
BASELINE = 1.10
actual = planned * BASELINE * capacity_factor * rain_penalty * blast_penalty * absent_penalty * noise
actual = np.round(np.clip(actual, 0, None), 1)

grade = np.round(
    np.clip(36 + 4 * np.sin(2 * np.pi * doy / 365) + rng.normal(0, 2, n), 25, 48), 1
)

dispatch = np.round(planned * 0.97 * rng.normal(1, 0.05, n), 1)
stock = np.zeros(n)
for t in range(1, n):
    stock[t] = max(0, stock[t - 1] + actual[t] - dispatch[t])

df = pd.DataFrame({
    "date": dates,
    "rainfall_mm": rain,
    "rain_3day_mm": np.round(rain_3d, 1),
    "temp_c": np.round(temp, 1),
    "drills_available": drills,
    "loaders_available": loaders,
    "hoist_uptime_pct": np.round(hoist_up, 1),
    "blast_delay_hours": blast_delay_h,
    "absentee_pct": absent_pct,
    "planned_tonnes": planned,
    "actual_tonnes": actual,
    "mn_grade_pct": grade,
    "stockpile_tonnes": np.round(stock, 1),
})
df["achievement_pct"] = np.round(100 * df.actual_tonnes / df.planned_tonnes, 1)
df["shortfall_flag"] = (df.achievement_pct < 90).astype(int)

# mine rests on Sundays
df = df[df.date.dt.dayofweek != 6].reset_index(drop=True)
df.to_csv("mine_daily.csv", index=False)

# ------------------------------------------------------------------
# 5. Summary and overview plot
# ------------------------------------------------------------------
print("Rows:", len(df))
print("Total planned (t):", round(df.planned_tonnes.sum()))
print("Total actual (t): ", round(df.actual_tonnes.sum()))
print("Days with shortfall (<90% of plan): {:.1f}%".format(100 * df.shortfall_flag.mean()))
print("Shortfall rate by month:")
print((df.groupby(df.date.dt.month).shortfall_flag.mean() * 100).round(0).astype(int).to_string())

monthly = df.set_index("date").resample("MS").agg(
    {"planned_tonnes": "sum", "actual_tonnes": "sum", "rainfall_mm": "sum"}
)

fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
ax[0].plot(monthly.index, monthly.planned_tonnes, label="Planned", lw=2)
ax[0].plot(monthly.index, monthly.actual_tonnes, label="Actual", lw=2)
ax[0].set_ylabel("Tonnes / month")
ax[0].set_title("Synthetic data: planned vs actual production")
ax[0].legend()
ax[1].bar(monthly.index, monthly.rainfall_mm, width=20, color="tab:blue")
ax[1].set_ylabel("Rainfall (mm / month)")
plt.tight_layout()
plt.savefig("data_overview.png", dpi=150)
plt.show()
print("Saved mine_daily.csv and data_overview.png")
