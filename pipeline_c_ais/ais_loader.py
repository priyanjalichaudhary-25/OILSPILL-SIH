import pandas as pd
import numpy as np
import re

def load_ais_data(csv_path, bbox=None):
    """Load real AIS CSV (Guam-format), extract lat/lon from geometry, rename to standard schema."""
    df = pd.read_csv(csv_path)

    # Extract lon/lat from "POINT (lon lat)" strings
    coords = df['geometry'].str.extract(r'POINT \(([-\d.]+) ([-\d.]+)\)')
    df['LON'] = pd.to_numeric(coords[0], errors='coerce')
    df['LAT'] = pd.to_numeric(coords[1], errors='coerce')

    df = df.rename(columns={
        'mmsi': 'MMSI',
        'base_date_time': 'BaseDateTime',
        'sog': 'SOG',
        'cog': 'COG',
        'heading': 'Heading',
        'vessel_type': 'VesselType'
    })

    df = df.dropna(subset=['MMSI', 'BaseDateTime', 'LAT', 'LON'])
    df['BaseDateTime'] = pd.to_datetime(df['BaseDateTime'], errors='coerce')
    df = df.dropna(subset=['BaseDateTime'])
    df = df[(df['LAT'].between(-90, 90)) & (df['LON'].between(-180, 180))]

    if bbox:
        lat_min, lat_max, lon_min, lon_max = bbox
        df = df[df['LAT'].between(lat_min, lat_max) & df['LON'].between(lon_min, lon_max)]

    return df

def generate_synthetic_ais(origin, time_center, n_vessels=20, hours_span=24, seed=42):
    """Fallback synthetic data — used when no real AIS file is provided."""
    np.random.seed(seed)
    records = []
    for i in range(n_vessels):
        mmsi = 200000000 + i
        lat = origin[0] + np.random.uniform(-0.15, 0.15)
        lon = origin[1] + np.random.uniform(-0.15, 0.15)
        t = time_center + pd.Timedelta(hours=np.random.uniform(-hours_span/2, hours_span/2))
        for step in range(10):
            records.append({
                'MMSI': mmsi,
                'BaseDateTime': t + pd.Timedelta(minutes=15*step),
                'LAT': lat + np.random.normal(0, 0.02)*step,
                'LON': lon + np.random.normal(0, 0.02)*step,
                'SOG': np.random.uniform(0, 20),
                'COG': np.random.uniform(0, 360),
                'Heading': np.random.uniform(0, 360),
                'VesselType': np.random.choice([80, 70, 30, np.nan])
            })
    return pd.DataFrame(records)