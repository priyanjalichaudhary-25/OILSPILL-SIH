"""
OILSPILL-SIH — Space-to-Sea Attribution Dashboard
Builds against contracts.py shapes with dummy data first; swap to real
pipeline calls once A/B/C land (see SWAP block below).

UI patterns adapted from gSulpizio/sat_tracker (github.com/gSulpizio/sat_tracker,
MIT licensed) — specifically its config-panel data-source toggle and its
color-coded classification markers. No code copied from that repo; these
are re-implemented for our own contracts.py shapes.
"""

import random
from datetime import datetime, timedelta, timezone

import folium
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="Space-to-Sea Attribution", page_icon="🧭", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    h1 { font-weight: 650; letter-spacing: -0.02em; }
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# SWAP TO REAL PIPELINES — uncomment once A/B/C are merged, delete the dummy
# generator calls further down, and call these instead. Signatures already
# match contracts.py, so this is a drop-in swap, not a rewrite.
# ---------------------------------------------------------------------------
# from pipeline_a_detection.detection import run_detection
# from pipeline_b_hindcast.hindcast import run_hindcast
# from pipeline_c_ais.mfsse import run_mfsse

DEMO_BBOX = [71.5, 18.5, 72.5, 19.5]  # lon_min, lat_min, lon_max, lat_max


# ---------------------------------------------------------------------------
# Dummy data generators — return values match contracts.py exactly, so
# nothing else in this file needs to change when the real functions land.
# ---------------------------------------------------------------------------
def dummy_detection() -> dict:
    """Matches run_detection() output shape."""
    cx, cy = 72.05, 19.05
    ring = [
        [cx - 0.05, cy - 0.03], [cx + 0.02, cy - 0.05], [cx + 0.07, cy - 0.01],
        [cx + 0.05, cy + 0.04], [cx - 0.02, cy + 0.05], [cx - 0.06, cy + 0.01],
        [cx - 0.05, cy - 0.03],
    ]
    return {
        "spill_polygon": {"type": "Polygon", "coordinates": [ring]},
        "detection_timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.87,
        "is_lookalike_flagged": False,
    }


def dummy_hindcast(spill_polygon: dict, detection_timestamp: str, bbox: list) -> dict:
    """Matches run_hindcast() output shape."""
    spill_coords = spill_polygon["coordinates"][0]
    spill_cx = sum(p[0] for p in spill_coords) / len(spill_coords)
    spill_cy = sum(p[1] for p in spill_coords) / len(spill_coords)
    origin_cx, origin_cy = spill_cx - 0.18, spill_cy + 0.12  # drifted from NW

    origin_ring = [
        [origin_cx - 0.04, origin_cy - 0.03], [origin_cx + 0.03, origin_cy - 0.04],
        [origin_cx + 0.05, origin_cy + 0.02], [origin_cx - 0.01, origin_cy + 0.05],
        [origin_cx - 0.05, origin_cy + 0.01], [origin_cx - 0.04, origin_cy - 0.03],
    ]

    n_particles, n_steps = 10, 8
    features = []
    for pid in range(n_particles):
        jitter_x = random.uniform(-0.015, 0.015)
        jitter_y = random.uniform(-0.015, 0.015)
        for t in range(n_steps):
            frac = t / (n_steps - 1)  # 0 = at spill (now), 1 = at origin (36h back)
            lon = spill_cx + (origin_cx - spill_cx) * frac + jitter_x * (1 - frac)
            lat = spill_cy + (origin_cy - spill_cy) * frac + jitter_y * (1 - frac)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"particle_id": pid, "timestep": t},
            })

    det_time = datetime.fromisoformat(detection_timestamp)
    return {
        "origin_polygon": {"type": "Polygon", "coordinates": [origin_ring]},
        "origin_time_window": {
            "start": (det_time - timedelta(hours=36)).isoformat(),
            "end": (det_time - timedelta(hours=30)).isoformat(),
        },
        "particle_tracks": {"type": "FeatureCollection", "features": features},
        "forward_validation_polygon": spill_polygon,  # dummy: pretend perfect match
        "_n_steps": n_steps,  # UI-only convenience, not part of the real contract
    }


def dummy_mfsse(origin_polygon: dict, time_window: dict) -> dict:
    """
    Matches run_mfsse() output shape — with one addition: 'lat'/'lon' per
    suspect. NOTE FOR YOUR AIS TEAMMATE: the contract as currently written
    (contracts.py) does NOT return vessel position, only mmsi/scores/text.
    The UI needs a position to put a marker on the map — either add lat/lon
    to run_mfsse()'s output, or the UI has to separately join mmsi -> last
    known position against the raw AIS store. Flag this before pipeline C
    is finalized so nobody discovers it at merge time.
    """
    ring = origin_polygon["coordinates"][0]
    ocx = sum(p[0] for p in ring) / len(ring)
    ocy = sum(p[1] for p in ring) / len(ring)

    names = ["MV Kaveri", "Sea Falcon", "Ocean Star 7", "Blue Marlin", "MT Indra", "Coastal Trader"]
    suspects = []
    for i, name in enumerate(names):
        score = round(random.uniform(0.2, 0.95), 2)
        suspects.append({
            "mmsi": f"41{100000 + i * 37}",
            "vessel_name": name,          # UI-only extra, not in the core contract
            "lat": ocy + random.uniform(-0.08, 0.08),   # UI-only extra, see note above
            "lon": ocx + random.uniform(-0.08, 0.08),   # UI-only extra, see note above
            "score": score,
            "proximity": round(random.uniform(0.1, 1.0), 2),
            "kinematic": round(random.uniform(0.1, 1.0), 2),
            "integrity": round(random.uniform(0.1, 1.0), 2),
            "why_flagged": random.choice([
                "AIS gap during origin time window, present before/after",
                "Loitering pattern near origin polygon",
                "Speed drop consistent with discharge, then resumed course",
                "Track re-appears just outside origin polygon boundary",
            ]),
        })
    return {"suspects": suspects}


def score_color(score: float) -> str:
    """Suspicion-tier coloring: high / medium / low, muted maritime palette."""
    if score >= 0.7:
        return "#b91c1c"   # high
    if score >= 0.4:
        return "#d97706"   # medium
    return "#64748b"       # low


# ---------------------------------------------------------------------------
# Sidebar — config panel
# ---------------------------------------------------------------------------
st.sidebar.header("Pipeline configuration")
data_source = st.sidebar.radio(
    "Data source",
    ["Simulated (dummy)", "Real pipelines"],
    help="Simulated uses fake data matching contracts.py shapes. "
         "Real calls run_detection/run_hindcast/run_mfsse — only works once A/B/C are merged.",
)
st.sidebar.caption("Map and marker patterns adapted from gSulpizio/sat_tracker (MIT).")

# ---------------------------------------------------------------------------
# Fetch pipeline outputs
# ---------------------------------------------------------------------------
if data_source == "Real pipelines":
    try:
        detection = run_detection("path/to/sar_image.tif")           # noqa: F821
        hindcast = run_hindcast(
            detection["spill_polygon"], detection["detection_timestamp"], DEMO_BBOX
        )                                                              # noqa: F821
        mfsse = run_mfsse(hindcast["origin_polygon"], hindcast["origin_time_window"])  # noqa: F821
        simulated = False
    except NameError:
        st.error(
            "Real pipeline functions aren't imported yet — uncomment the SWAP block "
            "at the top of this file once pipeline_a/b/c are merged. Falling back to simulated data."
        )
        detection = dummy_detection()
        hindcast = dummy_hindcast(detection["spill_polygon"], detection["detection_timestamp"], DEMO_BBOX)
        mfsse = dummy_mfsse(hindcast["origin_polygon"], hindcast["origin_time_window"])
        simulated = True
else:
    detection = dummy_detection()
    hindcast = dummy_hindcast(detection["spill_polygon"], detection["detection_timestamp"], DEMO_BBOX)
    mfsse = dummy_mfsse(hindcast["origin_polygon"], hindcast["origin_time_window"])
    simulated = True

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Space-to-Sea Attribution Dashboard")
st.markdown("Oil spill detection, drift hindcasting, and AIS-based vessel attribution.")

mode_label = "Simulated data" if simulated else "Live pipeline output"
det_time_display = detection["detection_timestamp"][:19].replace("T", " ")
st.caption(f"{mode_label} · detection timestamp {det_time_display} UTC")

st.divider()

# ---------------------------------------------------------------------------
# Phase 1 — Detection
# ---------------------------------------------------------------------------
st.subheader("1 · Detection")
st.caption("Sentinel-1 SAR dark-formation classification")

col1, col2, col3 = st.columns(3)
col1.metric(
    "Detection confidence", f"{detection['confidence']:.0%}",
    help="Classifier confidence that the flagged dark formation is oil rather than a look-alike "
         "(low wind, biogenic film, current shear, etc.)",
)
col2.metric(
    "Look-alike flag", "Flagged" if detection["is_lookalike_flagged"] else "Clear",
    help="Meteorological gating check — flags detections made under wind conditions "
         "below the ~2–3 m/s threshold needed for reliable Bragg-scatter contrast.",
)
col3.metric(
    "Suspect vessels", len(mfsse["suspects"]),
    help="Vessels whose AIS trajectory intersects the hindcast origin polygon "
         "within the temporal window, ranked by MFSSE score.",
)

st.divider()

# ---------------------------------------------------------------------------
# Phase 2 — Hindcast
# ---------------------------------------------------------------------------
st.subheader("2 · Hindcast")
st.caption("OpenDrift / OpenOil backward particle trajectory")

n_steps = hindcast.get("_n_steps", 8)
timestep = st.slider(
    "Timestep — 0 = detection time (spill location), max = furthest back in time (origin)",
    min_value=0, max_value=n_steps - 1, value=0,
)

spill_coords = detection["spill_polygon"]["coordinates"][0]
center_lat = sum(p[1] for p in spill_coords) / len(spill_coords)
center_lon = sum(p[0] for p in spill_coords) / len(spill_coords)

m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="CartoDB positron")

folium.GeoJson(
    detection["spill_polygon"],
    name="Detected spill",
    style_function=lambda f: {"fillColor": "#b91c1c", "color": "#b91c1c", "fillOpacity": 0.3, "weight": 2},
).add_to(m)

folium.GeoJson(
    hindcast["origin_polygon"],
    name="Probable origin (hindcast)",
    style_function=lambda f: {"fillColor": "#1d4ed8", "color": "#1d4ed8", "fillOpacity": 0.2, "weight": 2},
).add_to(m)

for pid in {f["properties"]["particle_id"] for f in hindcast["particle_tracks"]["features"]}:
    track = [
        f["geometry"]["coordinates"]
        for f in hindcast["particle_tracks"]["features"]
        if f["properties"]["particle_id"] == pid and f["properties"]["timestep"] <= timestep
    ]
    if len(track) >= 2:
        folium.PolyLine([[lat, lon] for lon, lat in track], color="#1d4ed8", weight=1.5, opacity=0.6).add_to(m)
    if track:
        lon, lat = track[-1]
        folium.CircleMarker([lat, lon], radius=3, color="#1d4ed8", fill=True, fill_opacity=0.9).add_to(m)

for s in mfsse["suspects"]:
    folium.CircleMarker(
        location=[s["lat"], s["lon"]],
        radius=7,
        color=score_color(s["score"]),
        fill=True,
        fill_color=score_color(s["score"]),
        fill_opacity=0.9,
        popup=folium.Popup(
            f"<b>{s['vessel_name']}</b> ({s['mmsi']})<br>Score: {s['score']}<br>{s['why_flagged']}",
            max_width=250,
        ),
    ).add_to(m)

folium.LayerControl().add_to(m)
st_folium(m, width=None, height=540, returned_objects=[])
st.caption("Marker color reflects suspicion score — high (≥0.70), medium (0.40–0.69), low (<0.40).")

st.divider()

# ---------------------------------------------------------------------------
# Phase 3 — Attribution (MFSSE)
# ---------------------------------------------------------------------------
st.subheader("3 · Attribution")
st.caption("Multi-Factor Suspicion Scoring Engine — proximity, kinematic anomaly, AIS integrity")

table_rows = sorted(mfsse["suspects"], key=lambda s: s["score"], reverse=True)
st.dataframe(
    [
        {
            "Vessel": s["vessel_name"], "MMSI": s["mmsi"], "Score": s["score"],
            "Proximity": s["proximity"], "Kinematic": s["kinematic"],
            "Integrity": s["integrity"], "Why flagged": s["why_flagged"],
        }
        for s in table_rows
    ],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Score": st.column_config.NumberColumn(
            help="Weighted composite of proximity, kinematic, and integrity sub-scores."),
        "Proximity": st.column_config.NumberColumn(
            help="Spatio-temporal intersection confidence — how closely the vessel's interpolated "
                 "position aligns with the hindcast origin centroid."),
        "Kinematic": st.column_config.NumberColumn(
            help="Anomaly score for unexplained deceleration during the intersection window, "
                 "consistent with discharge operations."),
        "Integrity": st.column_config.NumberColumn(
            help="AIS integrity score — penalizes transmission gaps or spoofing indicative "
                 "of deliberate silence."),
    },
)

selected_mmsi = st.selectbox(
    "Inspect a suspect", [s["mmsi"] for s in table_rows],
    format_func=lambda mmsi: next(s["vessel_name"] for s in table_rows if s["mmsi"] == mmsi),
)
selected = next(s for s in table_rows if s["mmsi"] == selected_mmsi)
d1, d2, d3, d4 = st.columns(4)
d1.metric("Overall score", selected["score"])
d2.metric("Proximity", selected["proximity"])
d3.metric("Kinematic", selected["kinematic"])
d4.metric("Integrity", selected["integrity"])
st.info(selected["why_flagged"])
