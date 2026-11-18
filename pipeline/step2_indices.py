"""
Step 2: Download Sentinel-2 bands for a pilot mine area, compute mineral
indices, save them for Step 3, and plot quick-look images.

Install first:
    pip install pystac-client planetary-computer rasterio numpy matplotlib
"""

import numpy as np
import rasterio
import planetary_computer as pc
import matplotlib.pyplot as plt
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.enums import Resampling
from pystac_client import Client

# =====================================================================
# SETTINGS - EDIT THESE
# =====================================================================
# [west, south, east, north] in degrees.
# Find a real MOIL mine pit on Google Maps (Satellite view), right-click it
# to copy "latitude, longitude", then use about +/- 0.025 around it.
# Example: pit at lat 21.30, lon 79.35 -> [79.325, 21.275, 79.375, 21.325]
BBOX = [79.259, 21.384, 79.299, 21.424]   # Munsar mine area

# Dry season shows bare ground and pits much better than post-monsoon.
DATES = "2025-02-01/2025-04-30"

# Optional command-line use:  python step2_indices.py 2025-10-01/2025-12-31 _wet
#   argument 1 = date range, argument 2 = tag added to output file names
import sys
OUT_TAG = ""
if len(sys.argv) > 2:
    DATES = sys.argv[1]
    OUT_TAG = sys.argv[2]

SIZE = 500            # output grid is SIZE x SIZE pixels (lower = faster)
MAX_IMAGES = 3        # how many clear images to combine

BANDS = {
    "blue": "B02",
    "green": "B03",
    "red": "B04",
    "nir": "B08",
    "swir1": "B11",
    "swir2": "B12",
}

# =====================================================================
# 1. FIND THE CLEAREST IMAGES
# =====================================================================
catalog = Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=pc.sign_inplace,
)

items = []
for max_cloud in (10, 30, 60):        # relax the cloud limit if nothing found
    items = list(
        catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=BBOX,
            datetime=DATES,
            query={"eo:cloud_cover": {"lt": max_cloud}},
        ).items()
    )
    if items:
        print(f"Found {len(items)} images with cloud cover < {max_cloud}%")
        break

if not items:
    raise SystemExit("No images found. Try a longer DATES range or check BBOX.")

items.sort(key=lambda i: i.properties["eo:cloud_cover"])
tile = items[0].properties["s2:mgrs_tile"]            # stay on a single tile
items = [i for i in items if i.properties["s2:mgrs_tile"] == tile][:MAX_IMAGES]
print(f"Using {len(items)} images from tile {tile}")
for it in items:
    print("  ", it.id, "cloud:", round(it.properties["eo:cloud_cover"], 1))


# =====================================================================
# 2. READ ONE BAND FOR ONE IMAGE (cropped to BBOX)
# =====================================================================
def read_band(item, band_code):
    href = item.assets[band_code].href
    with rasterio.open(href) as src:
        bounds = transform_bounds("EPSG:4326", src.crs, *BBOX)
        window = from_bounds(*bounds, transform=src.transform)
        data = src.read(
            1,
            window=window,
            out_shape=(SIZE, SIZE),
            resampling=Resampling.bilinear,
        )
    reflectance = (data.astype("float32") - 1000) / 10000   # scale to 0-1
    return np.clip(reflectance, 0, 1)


# =====================================================================
# 3. MEDIAN COMPOSITE (removes clouds/shadows that differ between dates)
# =====================================================================
bands = {}
for name, code in BANDS.items():
    stack = [read_band(it, code) for it in items]
    bands[name] = np.median(stack, axis=0)
    print("Loaded", name)

b = bands["blue"]
g = bands["green"]
r = bands["red"]
n = bands["nir"]
s1 = bands["swir1"]
s2 = bands["swir2"]
eps = 1e-6

# =====================================================================
# 4. INDICES
# =====================================================================
ndvi = (n - r) / (n + r + eps)          # vegetation (low = bare ground / pit)
iron_oxide = r / (b + eps)              # iron oxide ratio
ferrous = s1 / (n + eps)                # ferrous minerals
clay = s1 / (s2 + eps)                  # clay / hydroxyl minerals
bsi = ((s1 + r) - (n + b)) / ((s1 + r) + (n + b) + eps)   # bare soil index

# =====================================================================
# 5. SAVE FOR STEP 3
# =====================================================================
np.savez(
    f"indices{OUT_TAG}.npz",
    blue=b, green=g, red=r, nir=n, swir1=s1, swir2=s2,
    ndvi=ndvi, iron_oxide=iron_oxide, ferrous=ferrous, clay=clay, bsi=bsi,
    bbox=np.array(BBOX),
)
print(f"Saved indices{OUT_TAG}.npz")

# =====================================================================
# 6. QUICK-LOOK PLOTS
# =====================================================================
# True colour: confirms you are really looking at a mine
rgb = np.dstack([r, g, b])
plt.figure(figsize=(7, 7))
plt.imshow(np.clip(rgb * 3.5, 0, 1))
plt.title("True colour")
plt.axis("off")
plt.savefig(f"true_colour{OUT_TAG}.png", dpi=150, bbox_inches="tight")

# Indices
fig, ax = plt.subplots(1, 5, figsize=(22, 5))
panels = [
    ("NDVI", ndvi),
    ("Bare soil index", bsi),
    ("Iron oxide", iron_oxide),
    ("Ferrous", ferrous),
    ("Clay", clay),
]
for a, (title, arr) in zip(ax, panels):
    im = a.imshow(arr, cmap="viridis")
    a.set_title(title)
    a.axis("off")
    plt.colorbar(im, ax=a, fraction=0.046)
plt.tight_layout()
plt.savefig(f"indices_preview{OUT_TAG}.png", dpi=150)

plt.show()
print(f"Saved true_colour{OUT_TAG}.png and indices_preview{OUT_TAG}.png")
