"""
Pipeline B - Backward drift hindcasting using OpenDrift/OpenOil.
Given a detected spill polygon + timestamp, estimates the likely origin
point/time window by running particle tracking backward in time.
"""

from datetime import timedelta
import numpy as np
from shapely.geometry import shape, mapping
from scipy.spatial import ConvexHull
import geojson

from opendrift.models.openoil import OpenOil
from opendrift.readers import reader_netCDF_CF_generic

def compute_validation_confidence(forward_validation_polygon: dict, real_sar_polygon: dict) -> dict:
    """
    Compares the forward-validation polygon (re-seeded at computed origin, drifted forward)
    against the real SAR-detected spill polygon. Returns overlap area and a confidence ratio.
    """
    if forward_validation_polygon is None:
        return {"overlap_area": None, "confidence": None, "note": "forward_validation_polygon was None"}

    fwd_shape = shape(forward_validation_polygon)
    sar_shape = shape(real_sar_polygon)

    if not fwd_shape.is_valid or not sar_shape.is_valid:
        fwd_shape = fwd_shape.buffer(0)
        sar_shape = sar_shape.buffer(0)

    overlap_area = fwd_shape.intersection(sar_shape).area
    sar_area = sar_shape.area

    confidence = overlap_area / sar_area if sar_area > 0 else None

    return {
        "overlap_area": overlap_area,
        "sar_area": sar_area,
        "confidence": confidence
    }

def run_forward_validation(origin_lons, origin_lats, origin_time, forward_hours,
                            currents_path="data/currents_kerala_demo.nc",
                            wind_path="data/wind_kerala_demo.nc",
                            n_particles=750):
    """
    Re-seeds particles at the computed origin and runs forward in time,
    to check whether the resulting slick shape resembles the real SAR-detected polygon.
    """
    o2 = OpenOil(loglevel=20)
    reader_currents = reader_netCDF_CF_generic.Reader(currents_path)
    reader_wind = reader_netCDF_CF_generic.Reader(wind_path)
    o2.add_reader([reader_currents, reader_wind])

    o2.seed_within_polygon(
        lons=origin_lons,
        lats=origin_lats,
        number=n_particles,
        time=origin_time
    )
    o2.run(
        time_step=900,   # positive = forward
        duration=timedelta(hours=forward_hours)
    )

    lons = o2.result['lon'].values
    lats = o2.result['lat'].values
    final_lons = lons[:, -1]
    final_lats = lats[:, -1]
    valid = ~np.isnan(final_lons) & ~np.isnan(final_lats)
    final_lons = final_lons[valid]
    final_lats = final_lats[valid]

    if len(final_lons) < 3:
        return None  # can't build a hull, skip validation

    points = np.column_stack([final_lons, final_lats])
    hull = ConvexHull(points)
    hull_coords = points[hull.vertices].tolist()
    hull_coords.append(hull_coords[0])
    return geojson.Polygon([hull_coords])

def run_hindcast(spill_polygon: dict, detection_timestamp, bbox: list,
                  currents_path: str = "data/currents_kerala_demo.nc",
                  wind_path: str = "data/wind_kerala_demo.nc",
                  n_particles: int = 750,
                  backward_hours: int = 48) -> dict:
    """
    Pipeline B - backward drift hindcasting.
    See contracts.py for the full input/output spec.
    """

    # --- Set up model and readers ---
    o = OpenOil(loglevel=20)  # 20 = INFO; use 0 for verbose debugging
    reader_currents = reader_netCDF_CF_generic.Reader(currents_path)
    reader_wind = reader_netCDF_CF_generic.Reader(wind_path)
    o.add_reader([reader_currents, reader_wind])

    # --- Seed particles inside the detected spill polygon ---
    polygon = shape(spill_polygon)
    exterior_coords = list(polygon.exterior.coords)
    poly_lons = np.array([c[0] for c in exterior_coords])
    poly_lats = np.array([c[1] for c in exterior_coords])

    o.seed_within_polygon(
        lons=poly_lons,
        lats=poly_lats,
        number=n_particles,
        time=detection_timestamp
    )
    # --- Run backward in time ---
    o.run(
        time_step=-900,                        # -15 min steps (negative = backward)
        duration=timedelta(hours=backward_hours),
        outfile=None                            # skip disk output for speed; keep in memory
    )

    # --- Extract particle positions at the final (earliest) timestep ---
    lons = o.result['lon'].values   # shape: (n_particles, n_timesteps)
    lats = o.result['lat'].values
    final_lons = lons[:, -1]
    final_lats = lats[:, -1]

    # Drop any inactive/NaN particles (stranded, deactivated, etc.)
    valid = ~np.isnan(final_lons) & ~np.isnan(final_lats)
    final_lons = final_lons[valid]
    final_lats = final_lats[valid]

    if len(final_lons) < 3:
        raise RuntimeError(
            f"Only {len(final_lons)} valid particles remained after backward run — "
            "cannot compute a convex hull. Check forcing data coverage/bbox."
        )

    # --- Convex hull origin polygon ---
    points = np.column_stack([final_lons, final_lats])
    hull = ConvexHull(points)
    hull_coords = points[hull.vertices].tolist()
    hull_coords.append(hull_coords[0])  # close the ring

    origin_polygon = geojson.Polygon([hull_coords])

    # --- Time window (start = earliest particle time, end = detection time) ---
    origin_datetime_start = detection_timestamp - timedelta(hours=backward_hours)
    origin_time_window = {
        "start": origin_datetime_start.isoformat()
                 if hasattr(detection_timestamp, "isoformat") else None,
        "end": detection_timestamp.isoformat() if hasattr(detection_timestamp, "isoformat") else None
    }

    # --- Particle tracks for animation (GeoJSON FeatureCollection of LineStrings) ---
    features = []
    for i in range(lons.shape[0]):
        track_lons = lons[i, :]
        track_lats = lats[i, :]
        valid_track = ~np.isnan(track_lons) & ~np.isnan(track_lats)
        if valid_track.sum() < 2:
            continue
        coords = list(zip(track_lons[valid_track].tolist(), track_lats[valid_track].tolist()))
        features.append(geojson.Feature(geometry=geojson.LineString(coords), properties={"particle_id": i}))
    particle_tracks = geojson.FeatureCollection(features)

    return {
        "origin_polygon": origin_polygon,
        "origin_time_window": origin_time_window,
        "particle_tracks": particle_tracks,
        "forward_validation_polygon": run_forward_validation(
            [c[0] for c in hull_coords], [c[1] for c in hull_coords],
            origin_datetime_start, backward_hours
           )
     }

if __name__ == "__main__":
    # Manual test using the real MSC ELSA 3 case
    from datetime import datetime

    # Small placeholder polygon around the SAR-detected spill area
    # (Replace with Pipeline A's real output once available)
    test_spill_polygon = {
        "type": "Polygon",
        "coordinates": [[
            [76.10, 9.28], [76.20, 9.28], [76.20, 9.38], [76.10, 9.38], [76.10, 9.28]
        ]]
    }
    detection_time = datetime(2025, 5, 27, 0, 0, 0)
    bbox = [75.9, 9.0, 76.5, 9.7]

    result = run_hindcast(test_spill_polygon, detection_time, bbox, backward_hours=36)
    print("Origin polygon:", result["origin_polygon"])
    print("Time window:", result["origin_time_window"])
    print("Num particle tracks:", len(result["particle_tracks"]["features"]))
    # --- Placeholder "real SAR polygon" for validation sanity-check ---
    # TODO: replace with Pipeline A's real detection output once available
    placeholder_real_sar_polygon = {
        "type": "Polygon",
        "coordinates": [[
            [76.10, 9.28], [76.20, 9.28], [76.20, 9.38], [76.10, 9.38], [76.10, 9.28]
        ]]
    }

    validation = compute_validation_confidence(
        result["forward_validation_polygon"],
        placeholder_real_sar_polygon
    )
    print("Validation:", validation)
def load_cached_hindcast(case_name: str, cache_dir: str = "data/cache") -> dict:
    """Load a pre-computed hindcast result for demo safety."""
    import json
    import os
    path = os.path.join(cache_dir, f"{case_name}.json")
    with open(path, "r") as f:
        return json.load(f)