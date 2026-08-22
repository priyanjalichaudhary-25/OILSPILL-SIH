from datetime import timedelta
import numpy as np
from shapely.geometry import shape
from scipy.spatial import ConvexHull

def run_hindcast(spill_polygon: dict, detection_timestamp: str, bbox: list) -> dict:
    """
    Pipeline B - backward drift hindcasting using OpenDrift/OpenOil.
    See contracts.py for the full input/output spec.
    """
    # TODO: implement real OpenDrift backward run
    raise NotImplementedError("Pipeline B not yet implemented")