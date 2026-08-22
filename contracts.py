"""
Shared function signatures for all pipelines.
Everyone builds to these input/output shapes so integration in app/ is trivial.
"""

def run_detection(sar_image_path: str) -> dict:
    """
    Pipeline A - SAR oil spill detection.
    Returns: {
        "spill_polygon": <GeoJSON Polygon>,
        "detection_timestamp": "ISO8601 string",
        "confidence": float,
        "is_lookalike_flagged": bool
    }
    """
    raise NotImplementedError

def run_hindcast(spill_polygon: dict, detection_timestamp: str, bbox: list) -> dict:
    """
    Pipeline B - backward drift hindcasting.
    Returns: {
        "origin_polygon": <GeoJSON Polygon>,
        "origin_time_window": {"start": "ISO8601", "end": "ISO8601"},
        "particle_tracks": <GeoJSON FeatureCollection>,
        "forward_validation_polygon": <GeoJSON Polygon>
    }
    """
    raise NotImplementedError

def run_mfsse(origin_polygon: dict, time_window: dict) -> dict:
    """
    Pipeline C - AIS suspect vessel scoring.
    Returns: {
        "suspects": [{"mmsi": str, "score": float, "proximity": float,
                       "kinematic": float, "integrity": float, "why_flagged": str}, ...]
    }
    """
    raise NotImplementedError