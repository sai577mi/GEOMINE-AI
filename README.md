# GeoMine-AI

AI/ML and space-data platform for **MOIL Ltd** (SIH 2026, problem statement 26009):
find manganese prospects, forecast production shortfalls, and recommend corrective actions.

| Part | What it is | Where |
|---|---|---|
| **Web app** | Real-time control room that runs entirely in the browser. Static files, no server. | `web/` |
| **Streamlit app** | Same ideas in Python, with live weather and an optional satellite tab. | `streamlit_app/` |
| **Pipeline** | Sentinel-2 indices, prospectivity map, synthetic data, shortfall model, recommendations. | `pipeline/` |
| **Tools and tests** | Model export, web build, Python and browser parity tests. | `tools/`, `tests/` |

## What is real and what is simulated

| Item | Status |
|---|---|
| Sentinel-2 imagery, mineral indices, prospectivity map | Real satellite data (pipeline steps 2 to 3b) |
| Rainfall forecast | Real, from the free Open-Meteo API when the app is online. Falls back to a seasonal simulation. You can also type an IMD forecast. |
| Equipment sensors, production history, absenteeism, blasting delays | **Simulated** (`pipeline/step4_generate_data.py`, and a live sensor simulator in the apps) |
| Drill-hole assays for the 3D model | **Simulated** from a hidden orebody |
| Shortfall model, what-if simulator, 3D kriging model | Real trained models. They learned from the simulated data, so their scores show the pipeline works, not accuracy on real mines. |

Measured on the simulated 2025 hold-out year: shortfall model AUC 0.84; a High alert was followed by a real
shortfall 87% of the time (Low days: 13%). Reserve model error on unseen points: about 2 % Mn.

To use MOIL's real data, replace `streamlit_app/mine_daily.csv` with real daily records using the same columns
(see below), rerun `pipeline/step5_shortfall_model.py`, then `python tools/export_models.py && python tools/build_web.py`.

## Run it locally

Web app (nothing to install): open `web/index.html` in a browser, or serve it:

    cd web && python -m http.server 8000      # then open http://localhost:8000

Streamlit app:

    pip install -r requirements.txt
    streamlit run streamlit_app/app.py

Tests:

    pytest -q            # Python engine
    node tests/parity.js # browser models match Python

## Deploy

### Option A: Netlify Drop (fastest, 1 minute)
1. Open https://app.netlify.com/drop
2. Drag the **`web`** folder onto the page.
3. You get a public `https://...netlify.app` link. Live weather works there because it is a normal website.

### Option B: GitHub Pages (automatic)
1. Create a GitHub repository and push this whole folder to the `main` branch.
2. Repository **Settings > Pages > Build and deployment > Source: GitHub Actions**.
3. The workflow in `.github/workflows/pages.yml` publishes `web/` at `https://<user>.github.io/<repo>/`.

### Option C: Streamlit Community Cloud (Python app)
1. Push this folder to GitHub.
2. Go to https://share.streamlit.io, choose **New app**, pick the repo and branch `main`.
3. Set **Main file path** to `streamlit_app/app.py` and, under Advanced settings, Python 3.12.
4. For the satellite tab, copy your real `indices.npz` and `prospectivity.npz` (from pipeline steps 2 and 3) into
   `streamlit_app/` before pushing. Without them that tab shows a notice and everything else works.

Vercel also works: `cd web && npx vercel --prod`.

## Data format (`mine_daily.csv`, one row per working day)

`date, rainfall_mm, rain_3day_mm, temp_c, drills_available, loaders_available, hoist_uptime_pct,
blast_delay_hours, absentee_pct, planned_tonnes, actual_tonnes, mn_grade_pct, stockpile_tonnes,
achievement_pct, shortfall_flag`

`achievement_pct = 100 * actual_tonnes / planned_tonnes` and `shortfall_flag = 1` when it is below 90.

## Satellite and ML pipeline (`pipeline/`)

Install `requirements-pipeline.txt`, then run in an empty working folder, in order:

    python step2_indices.py                              # dry-season indices for the Munsar area
    python step3_prospectivity.py                        # prospectivity map with uncertainty
    python step2_indices.py 2025-10-01/2025-12-31 _wet   # post-monsoon indices
    python step3b_persistence.py                         # keep ground that stays bare all year (separates mines from farms)
    python step4_generate_data.py                        # synthetic mine data
    python step5_shortfall_model.py                      # XGBoost + SHAP shortfall model
    python step6_recommendations.py                      # corrective-action optimizer

Satellite data comes from Microsoft Planetary Computer (no account needed). Munsar and Gumgaon coordinates come from
MOIL's public environmental-clearance documents.

## Limits worth stating in the pitch

- Surface satellite data ranks places worth investigating. It cannot measure ore underground; tonnage and grade need drill data.
- Action costs and effects are editable assumptions to agree with mine planners.
- Predictive maintenance uses a simple health-trend estimate, not a certified reliability model.
- The 3D tonnage uses an assumed bulk density of 3.6 t/m³ for the ore.

## 🌍 World viewer (web/earth.html)

Zoom-Earth-style 3D globe (MapLibre GL, bundled in `web/vendor/`, no API keys):
NASA daily satellite imagery with a date picker and 7-day loop, Esri hi-res / OSM / Blue Marble bases,
live rain radar (RainViewer, past ~2 h), NASA IMERG rainfall, NASA MODIS fires, USGS earthquakes (24 h),
NASA EONET events, 3D terrain, city search, and click-anywhere selection.
Selecting a place shows its 7-day forecast (Open-Meteo) plus a **shortfall outlook**: the GeoMine model run
for a healthy *reference* underground mine using that place's real forecast rain. This is indicative only —
the model is trained on simulated operations data.

Open it from the Control Room button, or go to `http://localhost:8000/web/earth.html`.
It needs internet for tiles/APIs and must be served over http(s) (not opened as a file).
Rebuild after edits: `python tools/build_web.py`. Layer IDs/zoom levels follow NASA GIBS naming; if a layer
shows blank for some date, try an earlier date.

## Any location in the world (Control Room)

In the Control Room left panel, use **Add any place in the world** to search any city/mine/region.
The site gets its own digital-twin simulation and the *live* 7-day Open-Meteo rainfall for its coordinates
(timezone auto-detected), then the same shortfall model, what-if and action optimizer run for it.
Up to 8 added sites are remembered in your browser and appear in the "Both mines" table.
You can also click **Open in Control Room →** on any place selected in the World viewer.
Caveat: added sites use generic simulated telemetry (no real mine data); only the weather is real.
Without live weather (offline), rainfall falls back to an India-monsoon-shaped simulation, which is not right
for other climates — use it online.
