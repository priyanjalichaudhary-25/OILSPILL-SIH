from mfsse import run_mfsse

fake_polygon = {
    "type": "Polygon",
    "coordinates": [[[-88.4, 28.4], [-88.2, 28.4], [-88.2, 28.6], [-88.4, 28.6], [-88.4, 28.4]]]
}
fake_time_window = {"start": "2024-01-15T00:00:00", "end": "2024-01-15T12:00:00"}

result = run_mfsse(fake_polygon, fake_time_window)
print(result)