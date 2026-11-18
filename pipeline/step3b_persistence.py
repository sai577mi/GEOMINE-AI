"""
Step 3b: Refine the prospectivity map using seasonal persistence.

Idea: farmland is bare in the dry season but green after the monsoon.
Mine ground (pits, dumps, stockyards) stays bare in BOTH seasons.
So: refined = prospectivity x persistence-of-bare-ground.

Needs:  indices.npz (dry), indices_wet.npz (post-monsoon),
        prospectivity.npz (from step3_prospectivity.py)
Output: prospectivity_refined.npz, prospectivity_refined.png
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

dry = np.load("indices.npz")
wet = np.load("indices_wet.npz")
pr = np.load("prospectivity.npz")

if not np.allclose(dry["bbox"], wet["bbox"]):
    raise SystemExit("Dry and wet runs must use the same BBOX.")

prob = pr["prob"]
uncert = pr["uncertainty"].copy()
water = pr["water"]

# bare ground in the wet season: NDVI 0.15 -> 1.0 persistence, NDVI 0.5 -> 0
ndvi_wet = gaussian_filter(wet["ndvi"], sigma=1.0)
ndvi_dry = gaussian_filter(dry["ndvi"], sigma=1.0)
persist = np.clip((0.5 - ndvi_wet) / (0.5 - 0.15), 0, 1)

# seasonal change: big greening between dry and wet = cropland
greening = np.clip(ndvi_wet - ndvi_dry, 0, None)
crop_like = np.clip(greening / 0.3, 0, 1)

refined = prob * persist * (1 - 0.5 * crop_like)
refined = gaussian_filter(refined, sigma=1.5)
refined[water] = 0
uncert[water] = 0

np.savez("prospectivity_refined.npz", refined=refined, uncertainty=uncert,
         persistence=persist, water=water, bbox=dry["bbox"])
print("Saved prospectivity_refined.npz")
print("Pixels > 0.6 before:", int((prob > 0.6).sum()),
      " after:", int((refined > 0.6).sum()))

rgb = np.clip(np.dstack([dry["red"], dry["green"], dry["blue"]]) * 3.5, 0, 1)
fig, ax = plt.subplots(2, 2, figsize=(13, 12))

ax[0, 0].imshow(rgb)
ax[0, 0].contour(refined, levels=[0.6], colors="red", linewidths=1.2)
ax[0, 0].set_title("True colour + refined high-prospectivity (red)")

im1 = ax[0, 1].imshow(prob, cmap="inferno", vmin=0, vmax=1)
ax[0, 1].set_title("BEFORE: dry-season prospectivity")
plt.colorbar(im1, ax=ax[0, 1], fraction=0.046)

im2 = ax[1, 0].imshow(persist, cmap="viridis", vmin=0, vmax=1)
ax[1, 0].set_title("Bare-ground persistence (1 = stays bare)")
plt.colorbar(im2, ax=ax[1, 0], fraction=0.046)

im3 = ax[1, 1].imshow(refined, cmap="inferno", vmin=0, vmax=1)
ax[1, 1].set_title("AFTER: refined prospectivity")
plt.colorbar(im3, ax=ax[1, 1], fraction=0.046)

for a in ax.ravel():
    a.axis("off")
plt.tight_layout()
plt.savefig("prospectivity_refined.png", dpi=150)
plt.show()
print("Saved prospectivity_refined.png")
