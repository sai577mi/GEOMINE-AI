"""
Step 5: Next-day production SHORTFALL predictor (XGBoost + SHAP).

Question answered each evening:
    "Will tomorrow's output fall below 90% of plan?"

Inputs known BEFORE the target day:
  - yesterday's equipment, blasting, absenteeism and recent production
  - a rainfall FORECAST for the target day (simulated here as actual rain
    plus forecast error; in real use, take it from IMD)

Input : mine_daily.csv (from step4_generate_data.py)
Output: shortfall_model.json, predictions_test.csv,
        shortfall_eval.png, shap_importance.png

Install:  pip install xgboost shap scikit-learn pandas numpy matplotlib
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap
import xgboost as xgb
from sklearn.metrics import (roc_auc_score, precision_score, recall_score,
                             f1_score, confusion_matrix, roc_curve,
                             average_precision_score)

SEED = 42
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------
df = pd.read_csv("mine_daily.csv", parse_dates=["date"]).sort_values("date")
df = df.reset_index(drop=True)
print("Rows:", len(df), " | Shortfall days: {:.1f}%".format(100 * df.shortfall_flag.mean()))

# ---------------------------------------------------------------
# 2. Features (everything is shifted so no future information leaks)
# ---------------------------------------------------------------
# Simulated rainfall forecast = true rain + forecast error
noise = rng.normal(0, 4, len(df))
df["rain_forecast_mm"] = np.clip(df.rainfall_mm * rng.uniform(0.7, 1.3, len(df)) + noise, 0, None)
df["rain_forecast_3d_mm"] = df.rain_forecast_mm.rolling(3, min_periods=1).sum()

lag_cols = ["drills_available", "loaders_available", "hoist_uptime_pct",
            "blast_delay_hours", "absentee_pct", "rain_3day_mm", "achievement_pct"]
for c in lag_cols:
    df[c + "_lag1"] = df[c].shift(1)

df["ach_mean7_lag1"] = df.achievement_pct.shift(1).rolling(7).mean()
df["drills_mean7_lag1"] = df.drills_available.shift(1).rolling(7).mean()
df["loaders_mean7_lag1"] = df.loaders_available.shift(1).rolling(7).mean()
df["shortfalls_last7"] = df.shortfall_flag.shift(1).rolling(7).sum()
df["month_sin"] = np.sin(2 * np.pi * df.date.dt.month / 12)
df["month_cos"] = np.cos(2 * np.pi * df.date.dt.month / 12)

FEATURES = [
    "rain_forecast_mm", "rain_forecast_3d_mm",
    "drills_available_lag1", "loaders_available_lag1", "hoist_uptime_pct_lag1",
    "blast_delay_hours_lag1", "absentee_pct_lag1", "rain_3day_mm_lag1",
    "achievement_pct_lag1", "ach_mean7_lag1", "drills_mean7_lag1",
    "loaders_mean7_lag1", "shortfalls_last7", "month_sin", "month_cos",
]
data = df.dropna(subset=FEATURES).reset_index(drop=True)

# ---------------------------------------------------------------
# 3. Time-based split (never shuffle time series)
#    train: 2023-2024  |  test: 2025
# ---------------------------------------------------------------
train = data[data.date < "2025-01-01"]
test = data[data.date >= "2025-01-01"].reset_index(drop=True)
train_all = train

X_tr, y_tr = train[FEATURES], train.shortfall_flag
X_te, y_te = test[FEATURES], test.shortfall_flag
print("Train (2023-2024):", len(train), " Test (2025):", len(test))

# ---------------------------------------------------------------
# 4. Train XGBoost
# ---------------------------------------------------------------
# Choose the number of trees with time-series cross-validation on the
# training years only (a single small validation block would be unreliable
# because it covers only a few seasons).
from sklearn.model_selection import TimeSeriesSplit

def make_model(n_trees):
    return xgb.XGBClassifier(
        n_estimators=n_trees, learning_rate=0.05, max_depth=3,
        subsample=0.85, colsample_bytree=0.85, min_child_weight=5,
        reg_lambda=2.0, eval_metric="logloss", random_state=SEED,
    )

best_n, best_score = None, -1
for n_trees in (50, 100, 150, 250, 400):
    scores = []
    for tr_idx, va_idx in TimeSeriesSplit(n_splits=4).split(X_tr):
        m = make_model(n_trees).fit(X_tr.iloc[tr_idx], y_tr.iloc[tr_idx])
        pv = m.predict_proba(X_tr.iloc[va_idx])[:, 1]
        if y_tr.iloc[va_idx].nunique() == 2:
            scores.append(roc_auc_score(y_tr.iloc[va_idx], pv))
    sc = float(np.mean(scores))
    print(f"  trees={n_trees:<4} CV AUC={sc:.3f}")
    if sc > best_score:
        best_n, best_score = n_trees, sc
print("Chosen number of trees:", best_n)

model = make_model(best_n).fit(X_tr, y_tr)

p_te = model.predict_proba(X_te)[:, 1]

# ---------------------------------------------------------------
# 5. Evaluate on 2025 and compare with simple baselines
# ---------------------------------------------------------------
def report(name, y, p, thr=0.5):
    pred = (p >= thr).astype(int)
    print(f"{name:<28} AUC={roc_auc_score(y, p):.3f}  "
          f"precision={precision_score(y, pred, zero_division=0):.2f}  "
          f"recall={recall_score(y, pred, zero_division=0):.2f}  "
          f"F1={f1_score(y, pred, zero_division=0):.2f}")

print("\n--- Test results (2025) ---")
report("XGBoost", y_te, p_te)

# baseline 1: "tomorrow = today's status"
base_persist = test.shortfalls_last7.values / 7.0
report("Baseline: last-7-day rate", y_te, base_persist, thr=0.4)

# baseline 2: seasonal rate per month from training years
month_rate = train_all.groupby(train_all.date.dt.month).shortfall_flag.mean()
base_season = test.date.dt.month.map(month_rate).values
report("Baseline: monthly average", y_te, base_season, thr=0.4)

print("PR-AUC (XGBoost):", round(average_precision_score(y_te, p_te), 3),
      " | positive rate in test:", round(float(y_te.mean()), 3))

# risk levels for the dashboard
def level(p):
    return np.where(p >= 0.60, "High", np.where(p >= 0.30, "Medium", "Low"))

test["shortfall_prob"] = np.round(p_te, 3)
test["risk_level"] = level(p_te)
print("\nRisk level vs actual shortfall rate:")
print(test.groupby("risk_level").shortfall_flag.agg(["count", "mean"])
      .rename(columns={"mean": "actual_shortfall_rate"}).round(2).to_string())

# ---------------------------------------------------------------
# 6. SHAP explanations
# ---------------------------------------------------------------
explainer = shap.TreeExplainer(model)
sv = explainer.shap_values(X_te)

plt.figure()
shap.summary_plot(sv, X_te, plot_type="bar", show=False)
plt.title("What drives shortfall risk (mean |SHAP|)")
plt.tight_layout()
plt.savefig("shap_importance.png", dpi=150)
plt.close()

def top_reasons(i, k=3):
    contrib = pd.Series(sv[i], index=FEATURES).sort_values(key=abs, ascending=False)
    out = []
    for f in contrib.index[:k]:
        direction = "raises" if contrib[f] > 0 else "lowers"
        out.append(f"{f} = {X_te.iloc[i][f]:.1f} ({direction} risk)")
    return "; ".join(out)

test["top_reasons"] = [top_reasons(i) for i in range(len(test))]

worst = int(np.argmax(p_te))
print("\nHighest-risk day:", test.date[worst].date(),
      "| predicted risk:", round(float(p_te[worst]), 2),
      "| actual shortfall:", int(y_te[worst]))
print("Why:", test.top_reasons[worst])

# ---------------------------------------------------------------
# 7. Save everything the dashboard needs
# ---------------------------------------------------------------
model.save_model("shortfall_model.json")
test[["date", "planned_tonnes", "actual_tonnes", "achievement_pct", "shortfall_flag",
      "shortfall_prob", "risk_level", "top_reasons"]].to_csv("predictions_test.csv", index=False)
data[["date"] + FEATURES].to_csv("features_all.csv", index=False)
print("\nSaved shortfall_model.json, predictions_test.csv, features_all.csv, shap_importance.png")

# ---------------------------------------------------------------
# 8. Evaluation figure
# ---------------------------------------------------------------
fig, ax = plt.subplots(2, 2, figsize=(13, 10))

fpr, tpr, _ = roc_curve(y_te, p_te)
ax[0, 0].plot(fpr, tpr, lw=2, label=f"XGBoost (AUC {roc_auc_score(y_te, p_te):.2f})")
f2, t2, _ = roc_curve(y_te, base_season)
ax[0, 0].plot(f2, t2, lw=1.5, ls="--", label=f"Monthly avg (AUC {roc_auc_score(y_te, base_season):.2f})")
ax[0, 0].plot([0, 1], [0, 1], color="grey", lw=0.8)
ax[0, 0].set_title("ROC curve on 2025 data")
ax[0, 0].set_xlabel("False positive rate")
ax[0, 0].set_ylabel("True positive rate")
ax[0, 0].legend()

cm = confusion_matrix(y_te, (p_te >= 0.5).astype(int))
ax[0, 1].imshow(cm, cmap="Blues")
for (i, j), v in np.ndenumerate(cm):
    ax[0, 1].text(j, i, str(v), ha="center", va="center", fontsize=16)
ax[0, 1].set_xticks([0, 1]); ax[0, 1].set_yticks([0, 1])
ax[0, 1].set_xticklabels(["No shortfall", "Shortfall"])
ax[0, 1].set_yticklabels(["No shortfall", "Shortfall"])
ax[0, 1].set_xlabel("Predicted"); ax[0, 1].set_ylabel("Actual")
ax[0, 1].set_title("Confusion matrix (threshold 0.5)")

ax[1, 0].plot(test.date, test.shortfall_prob, lw=1, label="Predicted risk")
ax[1, 0].fill_between(test.date, 0, test.shortfall_flag, color="tab:red",
                      alpha=0.25, step="mid", label="Actual shortfall days")
ax[1, 0].axhline(0.60, color="red", ls=":", lw=1)
ax[1, 0].axhline(0.30, color="orange", ls=":", lw=1)
ax[1, 0].set_title("2025: predicted risk vs actual shortfall days")
ax[1, 0].legend(loc="upper left")

imp = pd.Series(np.abs(sv).mean(axis=0), index=FEATURES).sort_values().tail(8)
ax[1, 1].barh(imp.index, imp.values)
ax[1, 1].set_title("Top drivers (mean |SHAP|)")

plt.tight_layout()
plt.savefig("shortfall_eval.png", dpi=150)
plt.show()
print("Saved shortfall_eval.png")
