"""
Pre-runs Pipeline B for demo cases and saves output to JSON,
so the live demo doesn't depend on a ~2min runtime in front of judges.
"""
import json
import os
from datetime import datetime
from hindcast import run_hindcast

CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Demo case 1: MSC ELSA 3 (real spill, placeholder polygon for now)
demo_cases = [
    {
        "name": "msc_elsa_3_kerala",
        "spill_polygon": {
            "type": "Polygon",
            "coordinates": [[
                [76.10, 9.28], [76.20, 9.28], [76.20, 9.38], [76.10, 9.38], [76.10, 9.28]
            ]]
        },
        "detection_timestamp": datetime(2025, 5, 27, 0, 0, 0),
        "bbox": [74.9, 8.0, 77.6, 10.6]
    }
    # Add 1-2 more cases here later if you have other test polygons
]

for case in demo_cases:
    print(f"Running: {case['name']}...")
    result = run_hindcast(
        case["spill_polygon"],
        case["detection_timestamp"],
        case["bbox"],
        backward_hours=36
    )
    out_path = os.path.join(CACHE_DIR, f"{case['name']}.json")
    with open(out_path, "w") as f:
        json.dump(result, f)
    print(f"  Saved to {out_path}")

print("Done caching all demo cases.")