"""
Step 3: Reserve prospectivity map from Sentinel-2 indices.

Input : indices.npz (made by step2_indices.py)
Output: prospectivity.npz, prospectivity_map.png

NOTE: With no real drill-hole labels, labels are PSEUDO-labels from a
spectral anomaly score. Replace them with real drill/grade labels when
MOIL data is available; the rest of the pipeline stays the same.

Install:  pip install scikit-learn scipy matplotlib numpy
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter, uniform_filter
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score

RNG = 42
d = np.load("indices.npz")
H, W = d["ndvi"].shape
print("Grid size:", H, "x", W)


def z(a):
    return (a - a.mean()) / (a.std() + 1e-6)


# ---------------------------------------------------------------
# 1. Water mask (green > NIR means water)
# ---------------------------------------------------------------
ndwi = (d["green"] - d["nir"]) / (d["green"] + d["nir"] + 1e-6)
water = ndwi > 0.05
print("Water pixels masked:", int(water.sum()))

# ---------------------------------------------------------------
# 2. Spectral anomaly score
#    bare ground + iron oxide + ferrous signal, minus vegetation
# ---------------------------------------------------------------
score = z(d["bsi"]) + z(d["iron_oxide"]) + z(d["ferrous"]) - z(d["ndvi"])
score = gaussian_filter(score, sigma=1.5)
score[water] = score.min()
lo, hi = np.percentile(score, [1, 99])
score_n = np.clip((score - lo) / (hi - lo), 0, 1)

# ---------------------------------------------------------------
# 3. Pseudo-labels
# ---------------------------------------------------------------
pos_thr = np.percentile(score_n[~water], 92)   # top 8%
neg_thr = np.percentile(score_n[~water], 40)   # bottom 40%
labels = np.full((H, W), -1, dtype=int)        # -1 = unlabeled
labels[(score_n >= pos_thr) & ~water] = 1
labels[(score_n <= neg_thr) & ~water] = 0
print("Positives:", int((labels == 1).sum()), " Negatives:", int((labels == 0).sum()))

# ---------------------------------------------------------------
# 4. Features: raw bands + neighbourhood context + texture
#    (the 4 indices used in the score are deliberately left out)
# ---------------------------------------------------------------
feats = []
names = []
for k in ["blue", "green", "red", "nir", "swir1", "swir2"]:
    feats.append(d[k])
    names.append(k)
for k in ["blue", "red", "nir", "swir1"]:
    feats.append(gaussian_filter(d[k], sigma=3))
    names.append(k + "_ctx3")
for k in ["nir", "swir1"]:
    m = uniform_filter(d[k], size=5)
    m2 = uniform_filter(d[k] ** 2, size=5)
    feats.append(np.sqrt(np.clip(m2 - m ** 2, 0, None)))
    names.append(k + "_texture")
X_all = np.stack(feats, axis=-1).reshape(-1, len(feats))
y_all = labels.reshape(-1)

# spatial blocks (50x50 px) so train/test regions do not overlap
rows, cols = np.indices((H, W))
blocks = ((rows // 50) * 100 + (cols // 50)).reshape(-1)

mask = y_all >= 0
X, y, g = X_all[mask], y_all[mask], blocks[mask]

# ---------------------------------------------------------------
# 5. Spatial block cross-validation
# ---------------------------------------------------------------
rf_params = dict(n_estimators=60, max_depth=12, min_samples_leaf=5,
                 class_weight="balanced", n_jobs=-1, random_state=RNG)
aucs = []
for tr, te in GroupKFold(n_splits=5).split(X, y, g):
    m = RandomForestClassifier(**rf_params).fit(X[tr], y[tr])
    p = m.predict_proba(X[te])[:, 1]
    if len(np.unique(y[te])) == 2:
        aucs.append(roc_auc_score(y[te], p))
print("Spatial-CV AUC per fold:", np.round(aucs, 3), " mean:", round(float(np.mean(aucs)), 3))

# ---------------------------------------------------------------
# 6. Final model, probability and uncertainty
# ---------------------------------------------------------------
model = RandomForestClassifier(**rf_params).fit(X, y)
tree_preds = np.stack([t.predict_proba(X_all)[:, 1] for t in model.estimators_])
prob = tree_preds.mean(axis=0).reshape(H, W)
uncert = tree_preds.std(axis=0).reshape(H, W)
prob[water] = 0

imp = sorted(zip(model.feature_importances_, names), reverse=True)[:5]
print("Top features:", [(n, round(float(v), 3)) for v, n in imp])

# ---------------------------------------------------------------
# 7. Land-cover style clusters (quick unsupervised view)
# ---------------------------------------------------------------
Xs = (X_all - X_all.mean(0)) / (X_all.std(0) + 1e-6)
sample = np.random.RandomState(RNG).choice(len(Xs), 30000, replace=False)
km = KMeans(n_clusters=5, n_init=5, random_state=RNG).fit(Xs[sample])
clusters = km.predict(Xs).reshape(H, W)

# ---------------------------------------------------------------
# 8. Save + plot
# ---------------------------------------------------------------
np.savez("prospectivity.npz", prob=prob, uncertainty=uncert, score=score_n,
         clusters=clusters, water=water, bbox=d["bbox"])
print("Saved prospectivity.npz")

rgb = np.clip(np.dstack([d["red"], d["green"], d["blue"]]) * 3.5, 0, 1)
fig, ax = plt.subplots(2, 2, figsize=(13, 12))

ax[0, 0].imshow(rgb)
ax[0, 0].contour(prob, levels=[0.6], colors="red", linewidths=1)
ax[0, 0].set_title("True colour + high-prospectivity outline (red)")

im1 = ax[0, 1].imshow(prob, cmap="inferno", vmin=0, vmax=1)
ax[0, 1].set_title("Prospectivity probability")
plt.colorbar(im1, ax=ax[0, 1], fraction=0.046)

im2 = ax[1, 0].imshow(uncert, cmap="magma")
ax[1, 0].set_title("Uncertainty (std across trees)")
plt.colorbar(im2, ax=ax[1, 0], fraction=0.046)

im3 = ax[1, 1].imshow(clusters, cmap="tab10")
ax[1, 1].set_title("Unsupervised surface clusters (k=5)")

for a in ax.ravel():
    a.axis("off")
plt.tight_layout()
plt.savefig("prospectivity_map.png", dpi=150)
plt.show()
print("Saved prospectivity_map.png")
