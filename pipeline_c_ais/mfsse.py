from shapely.geometry import shape
import pandas as pd

from .ais_loader import load_ais_data, generate_synthetic_ais
from .scoring import (
    proximity_score, trajectory_alignment_score,
    speed_anomaly_score, ais_gap_score, vessel_type_score
)
def run_mfsse(origin_polygon: dict, time_window: dict, ais_csv_path: str = None) -> dict:
    poly = shape(origin_polygon)
    centroid = poly.centroid
    origin = (centroid.y, centroid.x)

    time_start = pd.to_datetime(time_window['start'])
    time_end = pd.to_datetime(time_window['end'])
    origin_time = time_start

    minx, miny, maxx, maxy = poly.bounds
    bbox = (miny - 0.25, maxy + 0.25, minx - 0.25, maxx + 0.25)

    if ais_csv_path:
        ais_df = load_ais_data(ais_csv_path, bbox=bbox)
    else:
        ais_df = generate_synthetic_ais(origin, origin_time)

    ais_df = ais_df[(ais_df['BaseDateTime'] >= time_start) &
                     (ais_df['BaseDateTime'] <= time_end)]

    spatial_radius_km = 25
    suspects = []

    for mmsi, group in ais_df.groupby('MMSI'):
        dist, _ = proximity_score(group, origin, origin_time)
        if dist > spatial_radius_km:
            continue

        proximity = max(0, 1 - dist / spatial_radius_km)
        trajectory = trajectory_alignment_score(group, origin)
        speed = speed_anomaly_score(group)
        gap = ais_gap_score(group)
        vtype_col = group['VesselType']
        vtype = vessel_type_score(vtype_col.mode()[0] if not vtype_col.isna().all() else None)

        composite = (0.3*proximity + 0.2*trajectory + 0.2*speed + 0.2*gap + 0.1*vtype)

        reasons = []
        if gap > 0.5: reasons.append("AIS dark period detected")
        if speed > 0.5: reasons.append("unusual slowdown")
        if proximity > 0.7: reasons.append("very close to spill origin")

        suspects.append({
            "mmsi": str(mmsi),
            "score": round(composite, 3),
            "proximity": round(proximity, 3),
            "kinematic": round((trajectory + speed) / 2, 3),
            "integrity": round(gap, 3),
            "why_flagged": "; ".join(reasons) if reasons else "moderate suspicion profile"
        })

    suspects.sort(key=lambda x: x['score'], reverse=True)
    return {"suspects": suspects}
