"""Export the trained XGBoost models to JSON so the browser app can run them.

    python tools/export_models.py

Reads  streamlit_app/shortfall_model.json (from pipeline/step5_shortfall_model.py)
       streamlit_app/mine_daily.csv        (from pipeline/step4_generate_data.py or real data)
Writes tools/src/models.json, then run tools/build_web.py.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "streamlit_app"))
import engine as E  # noqa: E402


def export(path):
    j = json.loads(Path(path).read_text())
    base = float(j["learner"]["learner_model_param"]["base_score"].strip("[]"))
    trees = []
    for t in j["learner"]["gradient_booster"]["model"]["trees"]:
        left, right = t["left_children"], t["right_children"]
        f, th, l, r, v, c = [], [], [], [], [], []
        for i in range(len(left)):
            leaf = left[i] == -1
            f.append(-1 if leaf else t["split_indices"][i])
            th.append(0 if leaf else t["split_conditions"][i])
            l.append(left[i]); r.append(right[i])
            v.append(t["split_conditions"][i] if leaf else 0)
            c.append(t["sum_hessian"][i])
        trees.append({"f": f, "t": th, "l": l, "r": r, "v": v, "c": c})
    return base, trees


M = E.Models(str(ROOT / "streamlit_app"))
with tempfile.TemporaryDirectory() as d:
    sim_path = Path(d) / "sim.json"
    M.sim.save_model(str(sim_path))
    sb, st = export(sim_path)
cb, ct = export(ROOT / "streamlit_app" / "shortfall_model.json")
tail = M.daily.tail(7)
payload = {
    "clf": {"base": cb, "trees": ct, "features": E.FEATURES},
    "sim": {"base": sb, "trees": st, "features": E.SIM_FEATURES},
    "bd_dry": M.bd_dry, "bd_wet": M.bd_wet,
    "seed": {"ach": tail.achievement_pct.round(1).tolist(),
             "drills": tail.drills_available.tolist(),
             "loaders": tail.loaders_available.tolist()},
}
out = ROOT / "tools" / "src" / "models.json"
out.write_text(json.dumps(payload, separators=(",", ":")))
print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
