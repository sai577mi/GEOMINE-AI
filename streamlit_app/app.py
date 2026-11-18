"""
GeoMine-AI v2: real-time control room for manganese mining.

Run:  streamlit run app_v2.py

Folder must contain: engine.py, app_v2.py, shortfall_model.json, mine_daily.csv
Optional (satellite tab): indices.npz, prospectivity.npz / prospectivity_refined.npz

Install: pip install streamlit plotly xgboost scikit-learn scipy pandas numpy matplotlib

What is real and what is simulated
  REAL      : Open-Meteo weather forecast (when online), Sentinel-2 satellite layers
  SIMULATED : equipment telemetry, production history, drill-hole assays
              (replace with MOIL's SCADA / production / drill databases)
"""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import engine as E

st.set_page_config(page_title="GeoMine-AI Control Room", layout="wide", page_icon="⛏️")

import intro
intro.show_intro()

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------
# Language
# ---------------------------------------------------------------
TXT = {
    "title": ("GeoMine-AI Control Room", "जियोमाइन-एआई कंट्रोल रूम"),
    "sub": ("Real-time manganese production intelligence", "मैंगनीज़ उत्पादन की रियल-टाइम निगरानी"),
    "tab_live": ("Live control room", "लाइव कंट्रोल रूम"),
    "tab_twin": ("Digital twin", "डिजिटल ट्विन"),
    "tab_res": ("3D reserve model", "3D भंडार मॉडल"),
    "tab_net": ("Mines and scenarios", "खदानें और परिदृश्य"),
    "tab_sat": ("Satellite map", "उपग्रह नक्शा"),
    "risk": ("Shortfall risk tomorrow", "कल उत्पादन में कमी का जोखिम"),
    "prob": ("Probability", "संभावना"),
    "exp0": ("Expected output, no action", "अपेक्षित उत्पादन, बिना कार्रवाई"),
    "exp1": ("With recommended actions", "सुझाई कार्रवाई के साथ"),
    "rain": ("Rain forecast tomorrow", "कल की वर्षा का पूर्वानुमान"),
    "why": ("Why", "कारण"),
    "actions": ("Recommended actions", "सुझाई गई कार्रवाइयाँ"),
    "maint": ("Predictive maintenance", "पूर्वानुमानित रखरखाव"),
    "alerts": ("Alert log", "अलर्ट लॉग"),
    "High": ("HIGH", "उच्च"), "Medium": ("MEDIUM", "मध्यम"), "Low": ("LOW", "कम"),
}
lang_choice = st.sidebar.radio("Language / भाषा", ["English", "हिन्दी"], horizontal=True)
LI = 0 if lang_choice == "English" else 1


def t(k):
    return TXT[k][LI]


# ---------------------------------------------------------------
# Models and state
# ---------------------------------------------------------------
@st.cache_resource
def load_models():
    return E.Models(HERE)


try:
    M = load_models()
except FileNotFoundError as e:
    st.error(str(e) + " Put shortfall_model.json and mine_daily.csv next to app_v2.py.")
    st.stop()

MINE_INFO = {"Munsar": {"seed": 11, "planned": 150.0}, "Gumgaon": {"seed": 23, "planned": 110.0}}


@st.cache_data(ttl=600, show_spinner=False)
def get_forecast(lat, lon):
    return E.fetch_forecast(lat, lon)


if "sims" not in st.session_state:
    a, d, l = M.seed_hist
    st.session_state.sims = {n: E.MineSim(n, i["seed"], a, d, l) for n, i in MINE_INFO.items()}
    st.session_state.history = {n: [] for n in MINE_INFO}
    st.session_state.last_level = {}
    st.session_state.alerts = []
    st.session_state.tick = 0
    st.session_state.collars = E.base_collars(30)

# ---------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------
st.sidebar.title("⛏️ GeoMine-AI")
focus = st.sidebar.selectbox("Mine", list(MINE_INFO), index=0)
auto = st.sidebar.toggle("Auto-refresh (live)", value=True)
speed = st.sidebar.slider("Simulation speed (steps / refresh)", 1, 10, 3)
st.sidebar.markdown("**Demo controls**")
storm_mm = st.sidebar.slider("Inject storm (mm tomorrow)", 0, 150, 0, 10)
storm_scope = st.sidebar.selectbox("Storm applies to", ["Selected mine", "Both mines"])
c1, c2 = st.sidebar.columns(2)
if c1.button("Drill failure"):
    st.sidebar.warning("Failed: " + str(st.session_state.sims[focus].force_failure("drill")))
if c2.button("Hoist failure"):
    st.sidebar.warning("Failed: " + str(st.session_state.sims[focus].force_failure("hoist")))
if st.sidebar.button("Reset simulation"):
    for k in ("sims", "history", "last_level", "alerts", "tick"):
        st.session_state.pop(k, None)
    st.rerun()
st.sidebar.caption("Equipment, production and drill data are SIMULATED. "
                   "Weather is live from Open-Meteo when online.")

st.title("⛏️ " + t("title"))
st.caption(t("sub"))

# forecasts
FC = {}
SRC = {}
today = E.today_ist()
for n, (lat, lon) in E.MINES.items():
    fc, src = get_forecast(lat, lon)
    if storm_mm > 0 and (storm_scope == "Both mines" or n == focus):
        fc = E.apply_storm(fc, storm_mm, today)
    FC[n], SRC[n] = fc, src


def level_text(level):
    return t(level)


def reason_text(f, v, c):
    name = E.FRIENDLY[f][LI]
    arrow = "↑" if c > 0 else "↓"
    return f"{name}: {v:.0f} ({arrow})"


def action_text(k):
    return E.ACTIONS[k][1 if LI else 0]


tab_live, tab_twin, tab_res, tab_net, tab_sat = st.tabs(
    ["🔴 " + t("tab_live"), "🏗️ " + t("tab_twin"), "🧊 " + t("tab_res"),
     "🗺️ " + t("tab_net"), "🛰️ " + t("tab_sat")]
)

# ---------------------------------------------------------------
# Tab 1: live control room
# ---------------------------------------------------------------
LEVEL_COL = {"Low": "#2e7d32", "Medium": "#ef6c00", "High": "#c62828"}


@st.fragment(run_every=2.0 if auto else None)
def live_panel():
    sims = st.session_state.sims
    results = {}
    for _ in range(speed if auto else 0):
        for n, sim in sims.items():
            f = FC[n]
            rs = min((E._rain(f, today) + E._rain(f, today + pd.Timedelta(days=1))) / 80, 1.0)
            sim.tick(rs)
        st.session_state.tick += 1
    for n, sim in sims.items():
        res = E.evaluate(M, sim, FC[n], today, planned=MINE_INFO[n]["planned"])
        results[n] = res
        hist = st.session_state.history[n]
        hist.append((st.session_state.tick, res["prob"]))
        del hist[:-120]
        prev = st.session_state.last_level.get(n)
        if res["level"] == "High" and prev != "High":
            top = reason_text(*res["reasons"][0])
            msg = f"{pd.Timestamp.now(tz='Asia/Kolkata'):%H:%M:%S}  {n}: HIGH shortfall risk " \
                  f"({res['prob']*100:.0f}%)  top driver: {top}"
            st.session_state.alerts.insert(0, msg)
            st.toast("🚨 " + msg)
        st.session_state.last_level[n] = res["level"]

    r = results[focus]
    sim = sims[focus]
    lvl = r["level"]
    msg = f"**{focus}** | {t('risk')}: **{level_text(lvl)}** ({r['prob']*100:.0f}%)"
    {"High": st.error, "Medium": st.warning, "Low": st.success}[lvl](msg)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(t("prob"), f"{r['prob']*100:.0f}%")
    m2.metric(t("rain"), f"{r['rain_tomorrow']:.0f} mm", help=f"3-day total {r['rain_3d']:.0f} mm")
    m3.metric(t("exp0"), f"{r['ach_before']:.0f}%")
    m4.metric(t("exp1"), f"{r['ach_after']:.0f}%", delta=f"+{r['tonnes_recovered']:.0f} t")
    m5.metric("Weather source", "Live" if SRC[focus] == "live" else "Offline (simulated)")

    left, right = st.columns([3, 2])
    with left:
        h = st.session_state.history[focus]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[a for a, _ in h], y=[b * 100 for _, b in h],
                                 mode="lines", line=dict(color="#1565c0", width=2), name="Risk"))
        fig.add_hline(y=60, line_dash="dot", line_color="#c62828")
        fig.add_hline(y=30, line_dash="dot", line_color="#ef6c00")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10),
                          title="Shortfall risk (%) over time", yaxis=dict(range=[0, 100]),
                          xaxis_title="Simulation step", showlegend=False)
        st.plotly_chart(fig, width="stretch")

        st.markdown(f"**{t('why')}**")
        for f_, v_, c_ in r["reasons"]:
            st.markdown("- " + reason_text(f_, v_, c_))
        st.markdown(f"**{t('actions')}** (cost {r['cost']:.1f})")
        if r["actions"]:
            for k in r["actions"]:
                st.markdown("- " + action_text(k))
        else:
            st.markdown("- " + ("No action needed" if LI == 0 else "कार्रवाई की आवश्यकता नहीं"))
        notes = {
            "rain": ("Heavy rain: build an ore stockpile buffer today, check dewatering pumps.",
                     "भारी वर्षा: आज ही अयस्क भंडार बढ़ाएँ, डीवॉटरिंग पंप जाँचें।"),
            "drills": ("Few drills working: fast-track drill repairs.", "कम ड्रिल चालू: मरम्मत तेज़ करें।"),
            "hoist": ("Hoist weak: avoid planned hoist maintenance tomorrow.",
                      "हॉइस्ट कमज़ोर: कल निर्धारित रखरखाव टालें।"),
            "absent": ("High absenteeism: confirm shift manning tonight.",
                       "अनुपस्थिति अधिक: आज रात शिफ्ट की पुष्टि करें।"),
        }
        for k in r["advice"]:
            st.info(notes[k][LI])

    with right:
        mf = sim.maintenance_forecast()
        mf["next failure"] = mf.hours_to_failure.apply(
            lambda v: "stable" if pd.isna(v) else f"~{v:.0f} h")
        mf.loc[mf.status == "down", "next failure"] = "DOWN"
        st.markdown(f"**{t('maint')}**")
        st.dataframe(
            mf[["unit", "health", "next failure"]], hide_index=True, width="stretch",
            column_config={"health": st.column_config.ProgressColumn(
                "health", min_value=0, max_value=100, format="%.0f")},
        )
        soon = mf[(mf.hours_to_failure.notna()) & (mf.hours_to_failure < 8) & (mf.status == "ok")]
        for u in soon.itertuples():
            st.warning(f"{u.unit}: likely to fail in ~{u.hours_to_failure:.0f} h. Plan a repair now.")
        st.markdown(f"**{t('alerts')}**")
        if st.session_state.alerts:
            for a in st.session_state.alerts[:6]:
                st.code(a, language=None)
        else:
            st.caption("No High-risk alerts yet. Try 'Inject storm' in the sidebar.")


with tab_live:
    live_panel()

# ---------------------------------------------------------------
# Tab 2: digital twin
# ---------------------------------------------------------------
with tab_twin:
    sim = st.session_state.sims[focus]
    res = E.evaluate(M, sim, FC[focus], today, planned=MINE_INFO[focus]["planned"])
    st.caption("Schematic cross-section of an underground mine. Colours follow the live sensor health.")
    layout = {
        "Main hoist": (0, 3), "Drill jumbo 1": (3, -30), "Drill jumbo 2": (6, -30),
        "Drill jumbo 3": (4, -60), "Drill jumbo 4": (7, -60),
        "Loader 1": (2, -60), "Loader 2": (5, -90), "Loader 3": (8, -90),
    }

    def colour(u):
        if u.status == "down":
            return "#c62828"
        return "#2e7d32" if u.health >= 60 else "#ef6c00" if u.health >= 40 else "#c62828"

    fig = go.Figure()
    fig.add_shape(type="rect", x0=-1, x1=11, y0=0, y1=6, fillcolor="#8d6e63", line_width=0, opacity=0.35)
    fig.add_shape(type="rect", x0=-1, x1=11, y0=-110, y1=0, fillcolor="#78909c", line_width=0, opacity=0.18)
    fig.add_shape(type="line", x0=0, x1=0, y0=0, y1=-95, line=dict(color="#37474f", width=5))
    for lv in (-30, -60, -90):
        fig.add_shape(type="line", x0=0, x1=10, y0=lv, y1=lv, line=dict(color="#455a64", width=3))
    for u in sim.units:
        x, y = layout[u.name]
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text", text=[u.name.replace("Drill jumbo", "D").replace("Loader", "L")
                                                    .replace("Main hoist", "Hoist")],
            textposition="top center",
            marker=dict(size=26, color=colour(u), symbol="x" if u.status == "down" else "square",
                        line=dict(width=1, color="black")),
            hovertemplate=f"{u.name}<br>health {u.health:.0f}%<br>{u.status}<extra></extra>",
            showlegend=False))
    rain = res["rain_tomorrow"]
    fig.add_annotation(x=5, y=12, text=f"☁️ Rain tomorrow: {rain:.0f} mm", showarrow=False,
                       font=dict(size=16))
    if rain > 25:
        fig.add_annotation(x=9.3, y=-100, text="💧 Water ingress risk", showarrow=False,
                           font=dict(size=13, color="#1565c0"))
    fig.update_layout(height=470, xaxis=dict(visible=False, range=[-1, 11]),
                      yaxis=dict(visible=False, range=[-110, 20]),
                      margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")
    snap = res["snap"]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Drills working", f"{snap['drills_available']} / 4")
    k2.metric("Loaders working", f"{snap['loaders_available']} / 3")
    k3.metric("Hoist uptime", f"{snap['hoist_uptime_pct']:.0f}%")
    k4.metric("Blasting delay", f"{snap['blast_delay_hours']:.1f} h")
    k5.metric("Absenteeism", f"{snap['absentee_pct']:.0f}%")

    st.subheader("What-if scenarios (tomorrow)")
    sc = E.scenario_table(M, sim, FC[focus], today, MINE_INFO[focus]["planned"])
    figb = go.Figure(go.Bar(x=sc.output_pct, y=sc.scenario, orientation="h",
                            marker_color=["#1565c0", "#2e7d32", "#c62828", "#ef6c00", "#6a1b9a"],
                            text=[f"{a:.0f}% ({b:.0f} t)" for a, b in zip(sc.output_pct, sc.tonnes)],
                            textposition="outside"))
    figb.add_vline(x=90, line_dash="dot", line_color="#c62828")
    figb.update_layout(height=320, xaxis=dict(range=[0, 115], title="Output (% of plan)"),
                       yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(figb, width="stretch")

# ---------------------------------------------------------------
# Tab 3: 3D reserve model
# ---------------------------------------------------------------
with tab_res:
    st.caption("Drill-hole grades are SIMULATED from a hidden orebody. The model (Gaussian process, "
               "the machine-learning form of kriging) estimates grade everywhere, with uncertainty. "
               "With MOIL's real assays you replace the simulator and nothing else changes.")


    @st.cache_data(show_spinner="Fitting 3D model...")
    def fit_cached(collars_bytes, n):
        arr = np.frombuffer(collars_bytes, dtype=float).reshape(n, 2)
        return E.fit_reserve(arr)


    collars = st.session_state.collars
    rm = fit_cached(collars.tobytes(), len(collars))

    cc1, cc2 = st.columns([1, 2])
    cutoff = cc1.slider("Cut-off grade (% Mn)", 18, 36, 28)
    tn = E.tonnage(rm, cutoff)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Estimated ore above cut-off", f"{tn['est']/1e6:.2f} Mt")
    k2.metric("Average ore grade", f"{tn['mean_grade']:.1f}% Mn")
    k3.metric("Drill holes", f"{len(collars)}")
    k4.metric("Validation error (RMSE)", f"{rm.holdout_rmse:.1f}% Mn",
              help="Checked on 150 random points the model never saw. Possible only because the data is simulated.")
    err = abs(tn["est"] - tn["truth"]) / max(tn["truth"], 1) * 100
    st.caption(f"Simulated truth at this cut-off: {tn['truth']/1e6:.2f} Mt (tonnage error {err:.1f}%). "
               f"Bulk density assumed {E.DENSITY} t/m³.")
    cl = tn["classes"]
    st.markdown("**Tonnage by confidence:** " + " | ".join(f"{k}: {v/1e6:.2f} Mt" for k, v in cl.items()))

    view = st.radio("View", ["3D ore body", "Depth slice", "Uncertainty slice"], horizontal=True)
    if view == "3D ore body":
        fig = go.Figure()
        fig.add_trace(go.Volume(x=rm.X, y=rm.Y, z=-rm.Z, value=rm.mean, isomin=cutoff, isomax=45,
                                opacity=0.18, surface_count=8, colorscale="YlOrRd",
                                colorbar=dict(title="% Mn"), caps=dict(x_show=False, y_show=False, z_show=False)))
        for x, y in collars:
            fig.add_trace(go.Scatter3d(x=[x, x], y=[y, y], z=[0, -E.ZMAX], mode="lines",
                                       line=dict(color="black", width=2), showlegend=False,
                                       hoverinfo="skip"))
        fig.update_layout(height=560, margin=dict(l=0, r=0, t=0, b=0),
                          scene=dict(xaxis_title="East (m)", yaxis_title="North (m)", zaxis_title="Depth (m)",
                                     aspectmode="manual", aspectratio=dict(x=2, y=1, z=0.6)))
        st.plotly_chart(fig, width="stretch")
    else:
        depth = st.slider("Depth (m)", 2.5, 97.5, 25.0, 5.0)
        zs = np.unique(rm.Z)
        zi = int(np.argmin(np.abs(zs - depth)))
        nx, ny, nz = rm.shape
        grid = (rm.mean if view == "Depth slice" else rm.std).reshape(rm.shape)[:, :, zi]
        xs = rm.X.reshape(rm.shape)[:, 0, 0]
        ys = rm.Y.reshape(rm.shape)[0, :, 0]
        fig = go.Figure(go.Heatmap(x=xs, y=ys, z=grid.T, colorscale="YlOrRd" if view == "Depth slice" else "Magma",
                                   colorbar=dict(title="% Mn" if view == "Depth slice" else "± % Mn")))
        fig.add_trace(go.Scatter(x=collars[:, 0], y=collars[:, 1], mode="markers",
                                 marker=dict(color="white", line=dict(color="black", width=1), size=7),
                                 name="Drill collars"))
        fig.update_layout(height=480, xaxis_title="East (m)", yaxis_title="North (m)",
                          yaxis=dict(scaleanchor="x"), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Where to drill next")
    picks = E.next_drill_holes(rm, cutoff)
    st.dataframe(pd.DataFrame(picks, columns=["East (m)", "North (m)", "ore/waste doubt score"]).round(1),
                 hide_index=True, width="stretch")
    st.caption("Picks the spots where grade is most uncertain around the cut-off.")
    d1, d2 = st.columns(2)
    if d1.button("Drill these 3 holes (simulate)"):
        st.session_state.collars = np.vstack([collars, [[p[0], p[1]] for p in picks]])
        st.rerun()
    if d2.button("Reset to 30 holes"):
        st.session_state.collars = E.base_collars(30)
        st.rerun()

# ---------------------------------------------------------------
# Tab 4: mines and scenarios
# ---------------------------------------------------------------
with tab_net:
    rows = []
    for n in MINE_INFO:
        r = E.evaluate(M, st.session_state.sims[n], FC[n], today, planned=MINE_INFO[n]["planned"])
        rows.append({"mine": n, "risk": level_text(r["level"]), "probability %": round(r["prob"] * 100),
                     "rain tomorrow (mm)": round(r["rain_tomorrow"]), "output % (no action)": round(r["ach_before"]),
                     "output % (with actions)": round(r["ach_after"]),
                     "tonnes recovered": round(r["tonnes_recovered"]),
                     "weather": "live" if SRC[n] == "live" else "offline"})
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")
    mp = pd.DataFrame([{"lat": E.MINES[n][0], "lon": E.MINES[n][1], "mine": n,
                        "color": {"Low": "#2e7d32", "Medium": "#ef6c00", "High": "#c62828"}[
                            E.evaluate(M, st.session_state.sims[n], FC[n], today)["level"]],
                        "size": 4000} for n in MINE_INFO])
    st.map(mp, latitude="lat", longitude="lon", color="color", size="size")
    st.caption("Mine coordinates from MOIL's public environmental-clearance documents. "
               "Add more mines by extending MINES in engine.py.")
    tot_rec = sum(r["tonnes recovered"] for r in rows)
    st.metric("Tonnes recoverable tomorrow across mines (with recommended actions)", f"{tot_rec:.0f} t")

# ---------------------------------------------------------------
# Tab 5: satellite
# ---------------------------------------------------------------
with tab_sat:
    import matplotlib.pyplot as plt

    f_idx = os.path.join(HERE, "indices.npz")
    f_ref = os.path.join(HERE, "prospectivity_refined.npz")
    f_pro = os.path.join(HERE, "prospectivity.npz")
    if not (os.path.exists(f_idx) and (os.path.exists(f_ref) or os.path.exists(f_pro))):
        st.warning("Copy indices.npz and prospectivity.npz (Steps 2-3) into this folder to see this tab.")
    else:
        refined = os.path.exists(f_ref)
        idx = np.load(f_idx)
        pro = np.load(f_ref if refined else f_pro)
        prob = pro["refined"] if refined else pro["prob"]
        w, s, e, n = [float(v) for v in idx["bbox"]]
        rgb = np.clip(np.dstack([idx["red"], idx["green"], idx["blue"]]) * 3.5, 0, 1)
        thr = st.slider("Show areas above probability", 0.1, 0.95, 0.6, 0.05, key="satthr")
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.imshow(rgb, extent=[w, e, s, n], aspect="auto")
        ax.imshow(np.ma.masked_where(prob < thr, prob), extent=[w, e, s, n], aspect="auto",
                  cmap="autumn_r", alpha=0.65, vmin=0, vmax=1)
        ax.set_title("Sentinel-2 view + " + ("seasonally refined " if refined else "") + "prospectivity")
        st.pyplot(fig)
        plt.close(fig)
        st.info("Ranks surface ground worth investigating first; it does not measure ore underground. "
                "Tonnage and grade come from the 3D drill-hole model.")
