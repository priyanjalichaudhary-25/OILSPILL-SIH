import numpy as np
import pandas as pd
from geopy.distance import geodesic
import math

def proximity_score(vessel_df, origin, origin_time):
    vessel_df = vessel_df.copy()
    vessel_df['time_diff'] = (vessel_df['BaseDateTime'] - origin_time).abs()
    closest = vessel_df.loc[vessel_df['time_diff'].idxmin()]
    dist = geodesic((closest['LAT'], closest['LON']), origin).km
    return dist, closest['BaseDateTime']

def bearing_to_origin(lat1, lon1, lat2, lon2):
    dLon = math.radians(lon2 - lon1)
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dLon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def trajectory_alignment_score(vessel_df, origin):
    vessel_df = vessel_df.sort_values('BaseDateTime')
    if len(vessel_df) < 2:
        return 0
    row = vessel_df.iloc[-1]
    bearing_needed = bearing_to_origin(row['LAT'], row['LON'], origin[0], origin[1])
    heading = row.get('Heading', row.get('COG', np.nan))
    if pd.isna(heading):
        return 0
    diff = abs(heading - bearing_needed)
    diff = min(diff, 360 - diff)
    return max(0, 1 - diff/180)

def speed_anomaly_score(vessel_df):
    vessel_df = vessel_df.sort_values('BaseDateTime')
    speeds = vessel_df['SOG'].dropna()
    if len(speeds) < 2:
        return 0
    initial_speed = speeds.iloc[0]
    min_speed = speeds.min()
    if initial_speed < 1:  # already slow/stationary, nothing to detect
        return 0
    drop_ratio = (initial_speed - min_speed) / initial_speed
    return max(0, min(1, drop_ratio))

def ais_gap_score(vessel_df, expected_interval_minutes=15):
    vessel_df = vessel_df.sort_values('BaseDateTime')
    if len(vessel_df) < 2:
        return 0
    gaps = vessel_df['BaseDateTime'].diff().dt.total_seconds() / 60
    max_gap = gaps.max()
    if max_gap > expected_interval_minutes * 4:
        return min(1, max_gap / (expected_interval_minutes * 20))
    return 0

def vessel_type_score(vessel_type_code):
    if pd.isna(vessel_type_code):
        return 0.3
    try:
        code = int(float(vessel_type_code))
    except (ValueError, TypeError):
        return 0.3
    if 80 <= code <= 89:
        return 1.0
    elif 70 <= code <= 79:
        return 0.7
    else:
        return 0.3