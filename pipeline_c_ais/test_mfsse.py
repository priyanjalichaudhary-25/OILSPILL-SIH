from mfsse import run_mfsse

guam_polygon = {
    "type": "Polygon",
    "coordinates": [[[144.55, 13.35], [144.75, 13.35], [144.75, 13.55], [144.55, 13.55], [144.55, 13.35]]]
}
guam_time_window = {"start": "2025-06-01T00:00:00", "end": "2025-06-01T12:00:00"}

result = run_mfsse(guam_polygon, guam_time_window, ais_csv_path="../data/guam_2025.csv")
print(result)