"""
Pipeline A - SAR oil spill detection.
Uses a fine-tuned ResNet18 classifier + Grad-CAM to localize spill regions,
then converts the pixel-space region into a geo-referenced polygon.
See contracts.py for the full input/output spec.
"""

import os
import numpy as np
import cv2
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
from datetime import datetime, timezone
from pytorch_grad_cam import GradCAM

IMG_SIZE = 224
MODEL_PATH = os.path.join(os.path.dirname(__file__), "pipeline_a_best_model.pth")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

val_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def _load_model():
    m = models.resnet18(weights=None)
    m.fc = nn.Linear(m.fc.in_features, 2)
    m.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    m = m.to(device)
    m.eval()
    return m


_model = _load_model()
_target_layer = [_model.layer4[-1]]
_cam = GradCAM(model=_model, target_layers=_target_layer)


def _pixel_to_geo(px, py, geotransform):
    """
    Convert (pixel_x, pixel_y) to (lon, lat) using a GDAL-style geotransform:
    geotransform = (origin_lon, pixel_width, 0, origin_lat, 0, pixel_height)
    pixel_height is typically negative.
    """
    origin_lon, pixel_width, _, origin_lat, _, pixel_height = geotransform
    lon = origin_lon + px * pixel_width
    lat = origin_lat + py * pixel_height
    return lon, lat


def run_detection(sar_image_path: str, geotransform=None, oil_class_idx: int = 1,
                   cam_threshold: float = 0.5) -> dict:
    """
    Pipeline A - SAR oil spill detection.
    Returns: {
        "spill_polygon": <GeoJSON Polygon>,
        "detection_timestamp": "ISO8601 string",
        "confidence": float,
        "is_lookalike_flagged": bool
    }

    geotransform: (origin_lon, pixel_width, 0, origin_lat, 0, pixel_height)
                  Required to convert pixel coordinates to real lat/lon.
    """
    if geotransform is None:
        raise ValueError(
            "geotransform is required to convert pixel polygon to lat/lon. "
            "Extract it from the SAR image's metadata (e.g. via rasterio)."
        )

    img = Image.open(sar_image_path).convert("RGB")
    img_resized = img.resize((IMG_SIZE, IMG_SIZE))
    tensor = val_transform(img)

    with torch.no_grad():
        output = _model(tensor.unsqueeze(0).to(device))
        probs = torch.softmax(output, dim=1)[0]
        pred_class = torch.argmax(probs).item()
        confidence = probs[pred_class].item()

    is_oil = pred_class == oil_class_idx
    spill_polygon = None

    if is_oil:
        grayscale_cam = _cam(input_tensor=tensor.unsqueeze(0).to(device), targets=None)[0]
        mask = (grayscale_cam > cam_threshold).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            pixel_coords = largest.reshape(-1, 2).tolist()

            geo_coords = [_pixel_to_geo(px, py, geotransform) for px, py in pixel_coords]
            if geo_coords[0] != geo_coords[-1]:
                geo_coords.append(geo_coords[0])

            spill_polygon = {
                "type": "Polygon",
                "coordinates": [geo_coords]
            }

    detection_timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "spill_polygon": spill_polygon,
        "detection_timestamp": detection_timestamp,
        "confidence": round(confidence, 4),
        "is_lookalike_flagged": False
    }


if __name__ == "__main__":
    import glob

    # Placeholder geotransform approximating the Kerala coast near the spill site
    # TODO: replace with real values extracted from a downloaded Sentinel-1 .SAFE scene
    placeholder_geotransform = (75.9, 0.0001, 0, 9.7, 0, -0.0001)
    # (origin_lon, pixel_width, 0, origin_lat, 0, pixel_height)

    test_image = glob.glob("kaggle/data/Class_1/*.jpg")[0]
    print("Testing with:", test_image)

    result = run_detection(test_image, geotransform=placeholder_geotransform)
    print("confidence:", result["confidence"])
    print("spill_polygon:", result["spill_polygon"])
    print("detection_timestamp:", result["detection_timestamp"])
    print("is_lookalike_flagged:", result["is_lookalike_flagged"])