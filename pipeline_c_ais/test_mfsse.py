from .mfsse import run_mfsse

guam_polygon = {
    "type": "Polygon",
    "coordinates": [[[144.55, 13.35], [144.75, 13.35], [144.75, 13.55], [144.55, 13.55], [144.55, 13.35]]]
}
guam_time_window = {"start": "2025-06-01T00:00:00", "end": "2025-06-01T12:00:00"}


def test_synthetic_ranking_is_plausible():
    result = run_mfsse(guam_polygon, guam_time_window, ais_csv_path="../data/guam_2025.csv")
    suspects = result["suspects"]
    assert isinstance(suspects, list), "suspects must be a list"
    if len(suspects) > 0:
        top = suspects[0]
        assert 0 <= top["score"] <= 1, "score must be normalized 0-1"
        assert "why_flagged" in top and len(top["why_flagged"]) > 0
    scores = [s["score"] for s in suspects]
    assert scores == sorted(scores, reverse=True), "suspects must be sorted by score descending"
    print("Synthetic ranking sanity check passed.")


if __name__ == "__main__":
    result = run_mfsse(guam_polygon, guam_time_window, ais_csv_path="../data/guam_2025.csv")
    print(result)
    test_synthetic_ranking_is_plausible()