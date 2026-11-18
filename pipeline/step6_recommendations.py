"""
Step 6: Recommendation engine (what-if simulator + optimizer).

For every day flagged Medium/High risk by Step 5, answer:
    "Which corrective actions should we take, within a limited budget,
     to recover the most ore?"

How it works
  1. WHAT-IF SIMULATOR: a model trained on 2023-2024 that predicts
     achievement % from equipment, blasting, absentee and rain conditions.
     It is forced to behave sensibly (more drills = more output, more rain
     = less output) with monotonic constraints.
  2. ACTION CATALOGUE: each action changes the expected conditions and has a cost.
  3. OPTIMIZER: tries every combination of actions that fits the budget and
     keeps the best one (exact, because there are only 5 actions = 32
     combinations; with dozens of actions switch to a MILP solver such as
     scipy.optimize.milp, PuLP or OR-Tools).
  4. RULE NOTES: plain-language advice for things the simulator can't
     represent (e.g. build a stockpile buffer before heavy rain).

Inputs : mine_daily.csv, predictions_test.csv, features_all.csv
Outputs: recommendations.csv, recommendations_summary.png

Install:  pip install xgboost scikit-learn pandas numpy matplotlib
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import xgboost as xgb
import itertools
from sklearn.metrics import r2_score, mean_absolute_error

SEED = 42
BUDGET = 3.0          # cost units available per day (edit to test scenarios)
RISK_THRESHOLD = 0.30 # recommend for Medium (>=0.30) and High (>=0.60) days
MIN_POINTS_PER_COST = 0.3  # an action must add at least this many % of plan per cost unit

# ---------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------
daily = pd.read_csv("mine_daily.csv", parse_dates=["date"])
pred = pd.read_csv("predictions_test.csv", parse_dates=["date"])
feat = pd.read_csv("features_all.csv", parse_dates=["date"])

# ---------------------------------------------------------------
# 2. What-if simulator (achievement % from operating conditions)
# ---------------------------------------------------------------
SIM_FEATURES = ["drills_available", "loaders_available", "hoist_uptime_pct",
                "blast_delay_hours", "absentee_pct", "rain_3day_mm"]
# +1 = more of this raises output, -1 = more of this lowers output
MONOTONE = "(1,1,1,-1,-1,-1)"

train = daily[daily.date < "2025-01-01"]
test_d = daily[daily.date >= "2025-01-01"]

sim = xgb.XGBRegressor(
    n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.9,
    min_child_weight=5, monotone_constraints=MONOTONE, random_state=SEED,
)
sim.fit(train[SIM_FEATURES], train.achievement_pct)
p = sim.predict(test_d[SIM_FEATURES])
print("What-if simulator on 2025 data:  R2 = {:.3f}   MAE = {:.1f} points of plan".format(
    r2_score(test_d.achievement_pct, p), mean_absolute_error(test_d.achievement_pct, p)))


def predict_ach(state):
    row = pd.DataFrame([{k: state[k] for k in SIM_FEATURES}])
    return float(sim.predict(row)[0])


# ---------------------------------------------------------------
# 3. Action catalogue (edit these to match real mine options)
# ---------------------------------------------------------------
def a_overtime(s):  s["absentee_pct"] = max(s["absentee_pct"] - 4.0, 3.0)
def a_drill(s):     s["drills_available"] = min(s["drills_available"] + 1, 4)
def a_loader(s):    s["loaders_available"] = min(s["loaders_available"] + 1, 3)
def a_hoist(s):     s["hoist_uptime_pct"] = min(s["hoist_uptime_pct"] + 8.0, 100.0)
def a_blast(s):     s["blast_delay_hours"] = max(s["blast_delay_hours"] - 1.5, 0.5)

ACTIONS = {
    "Call standby crew / overtime":            (a_overtime, 1.0),
    "Redeploy 1 spare drill jumbo":            (a_drill,    1.5),
    "Redeploy 1 loader from another face":     (a_loader,   1.5),
    "Priority repair / inspect the hoist":     (a_hoist,    2.0),
    "Re-sequence blasting to a dry window":    (a_blast,    0.5),
}

# typical blasting delay by weather, learned from the training years
bd_dry = train.loc[train.rainfall_mm <= 20, "blast_delay_hours"].mean()
bd_wet = train.loc[train.rainfall_mm > 20, "blast_delay_hours"].mean()


def optimise(state):
    """Try every affordable combination of actions and keep the best one."""
    names = list(ACTIONS)
    combos = []
    for k in range(len(names) + 1):
        for c in itertools.combinations(names, k):
            cost = sum(ACTIONS[n][1] for n in c)
            if cost <= BUDGET:
                combos.append((c, cost))

    states = []
    for c, _ in combos:
        s2 = dict(state)
        for n in c:
            ACTIONS[n][0](s2)
        states.append(s2)
    ach = sim.predict(pd.DataFrame(states)[SIM_FEATURES])   # joint effect of each combo

    base = float(ach[0])                                    # first combo = do nothing
    best_i, best_score = 0, 0.0
    for i, (c, cost) in enumerate(combos):
        score = (ach[i] - base) - MIN_POINTS_PER_COST * cost
        if score > best_score + 1e-9:
            best_i, best_score = i, score
    chosen, cost = combos[best_i]
    return base, float(ach[best_i]), list(chosen), cost


def rule_notes(r):
    notes = []
    if r.rain_forecast_mm >= 25 or r.rain_forecast_3d_mm >= 60:
        notes.append("Heavy rain forecast: build an ore stockpile buffer the day before, "
                     "check dewatering pumps, keep haulage on dry routes.")
    if r.drills_available_lag1 <= 2:
        notes.append("Drill availability low: fast-track drill repairs.")
    if r.hoist_uptime_pct_lag1 < 85:
        notes.append("Hoist uptime weak: avoid planned hoist maintenance tomorrow.")
    if r.absentee_pct_lag1 >= 10:
        notes.append("High absenteeism: confirm shift manning in the evening.")
    return " ".join(notes)


# ---------------------------------------------------------------
# 4. Build recommendations for flagged days
# ---------------------------------------------------------------
df = pred.merge(feat, on="date", how="left")
flag = df[df.shortfall_prob >= RISK_THRESHOLD].reset_index(drop=True)
print(f"\nDays flagged Medium/High in 2025: {len(flag)} of {len(df)}")

rows = []
for r in flag.itertuples():
    wet = r.rain_forecast_mm > 20
    state = {
        "drills_available": r.drills_available_lag1,
        "loaders_available": r.loaders_available_lag1,
        "hoist_uptime_pct": r.hoist_uptime_pct_lag1,
        "blast_delay_hours": bd_wet if wet else bd_dry,
        "absentee_pct": r.absentee_pct_lag1,
        "rain_3day_mm": r.rain_forecast_3d_mm,
    }
    before, after, chosen, cost = optimise(state)
    rows.append({
        "date": r.date.date(),
        "risk_level": r.risk_level,
        "shortfall_prob": r.shortfall_prob,
        "expected_ach_before_pct": round(before, 1),
        "expected_ach_after_pct": round(after, 1),
        "tonnes_recovered": round((after - before) / 100 * r.planned_tonnes, 1),
        "action_cost": cost,
        "actions": " | ".join(chosen) if chosen else "No budget-effective action",
        "advice": rule_notes(r),
        "why_flagged": r.top_reasons,
    })

rec = pd.DataFrame(rows)
rec.to_csv("recommendations.csv", index=False)

# ---------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------
print("\nBudget per day:", BUDGET)
print(rec.groupby("risk_level")[["expected_ach_before_pct", "expected_ach_after_pct",
                                 "tonnes_recovered", "action_cost"]].mean().round(1).to_string())
print("\nTotal expected tonnes recovered in 2025 (flagged days):",
      round(rec.tonnes_recovered.sum()))

counts = {}
for a in rec.actions:
    for n in a.split(" | "):
        counts[n] = counts.get(n, 0) + 1
print("\nMost recommended actions:")
for n, c in sorted(counts.items(), key=lambda kv: -kv[1]):
    print(f"  {c:>3}  {n}")

top = rec.sort_values("shortfall_prob", ascending=False).iloc[0]
print("\nExample (highest-risk day):", top["date"])
print("  Risk:", top.shortfall_prob, "| expected output", top.expected_ach_before_pct,
      "% -> ", top.expected_ach_after_pct, "% of plan")
print("  Do:", top.actions)
print("  Note:", top.advice)
print("  Why flagged:", top.why_flagged)
print("\nSaved recommendations.csv")

# ---------------------------------------------------------------
# 6. Chart
# ---------------------------------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(14, 5.5))
hi = rec[rec.risk_level == "High"].reset_index(drop=True)
ax[0].scatter(hi.expected_ach_before_pct, hi.expected_ach_after_pct, alpha=0.7)
lims = [min(hi.expected_ach_before_pct.min(), hi.expected_ach_after_pct.min()) - 2,
        max(hi.expected_ach_before_pct.max(), hi.expected_ach_after_pct.max()) + 2]
ax[0].plot(lims, lims, color="grey", lw=1)
ax[0].axhline(90, color="red", ls=":", lw=1)
ax[0].set_xlabel("Expected output WITHOUT action (% of plan)")
ax[0].set_ylabel("Expected output WITH recommended actions (% of plan)")
ax[0].set_title("High-risk days: effect of recommendations")

names = list(counts.keys())
ax[1].barh([n.replace(" ", "\n", 2) if len(n) > 28 else n for n in names],
           [counts[n] for n in names])
ax[1].set_xlabel("Days recommended (2025)")
ax[1].set_title("Which actions the optimizer chooses")
plt.tight_layout()
plt.savefig("recommendations_summary.png", dpi=150)
plt.show()
print("Saved recommendations_summary.png")
