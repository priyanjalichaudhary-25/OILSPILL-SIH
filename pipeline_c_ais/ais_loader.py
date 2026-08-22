import pandas as pd
import numpy as np

def load_ais_data(csv_path, bbox=None, cols=None):
    """Load AIS CSV, optionally bbox-filtered, cleaned."""
    df = pd.read_csv(csv_path, usecols=cols)
    df = df.dropna(subset=['MMSI', 'BaseDateTime', 'LAT', 'LON'])
    df['BaseDateTime'] = pd.to_datetime(df['BaseDateTime'], errors='coerce')
    df = df.dropna(subset=['BaseDateTime'])
    df = df[(df['LAT'].between(-90, 90)) & (df['LON'].between(-180, 180))]
    if bbox:
        lat_min, lat_max, lon_min, lon_max = bbox
        df = df[df['LAT'].between(lat_min, lat_max) & df['LON'].between(lon_min, lon_max)]
    return df

def generate_synthetic_ais(origin, time_center, n_vessels=20, hours_span=24, seed=42):
    """Fallback synthetic data — used until real AIS download is confirmed working."""
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