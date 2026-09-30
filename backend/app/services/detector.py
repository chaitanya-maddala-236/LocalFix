from __future__ import annotations

from typing import Any


def preprocess_yolov8(image_bytes: bytes, input_size: tuple[int, int]) -> tuple[Any, tuple[int, int], tuple[float, float, float]]:
    import numpy as np
    from PIL import Image

    with Image.open(__import__("io").BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
        original_width, original_height = image.size
        if original_width > 4096 or original_height > 4096 or original_width * original_height > 12_000_000:
            raise ValueError("Image dimensions exceed the local detector limit of 4096 px or 12 megapixels.")
        target_height, target_width = input_size
        scale = min(target_width / original_width, target_height / original_height)
        resized_width = max(1, round(original_width * scale))
        resized_height = max(1, round(original_height * scale))
        resized = image.resize((resized_width, resized_height), Image.Resampling.BILINEAR)
        canvas = Image.new("RGB", (target_width, target_height), (114, 114, 114))
        pad_x = (target_width - resized_width) / 2
        pad_y = (target_height - resized_height) / 2
        canvas.paste(resized, (round(pad_x), round(pad_y)))
        tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
    return tensor, (original_width, original_height), (scale, pad_x, pad_y)


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_first = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    area_second = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    return intersection / max(1e-9, area_first + area_second - intersection)


def decode_yolov8(output: Any, *, labels: list[str], original_size: tuple[int, int],
                  transform: tuple[float, float, float], input_size: tuple[int, int],
                  score_threshold: float = 0.25, nms_threshold: float = 0.5,
                  max_detections: int = 50) -> list[dict[str, Any]]:
    import numpy as np

    if not labels:
        raise ValueError("Configure the detector's class labels in models/manifest.json.")
    values = np.asarray(output, dtype=np.float32)
    if values.ndim == 3:
        values = values[0]
    if values.ndim != 2:
        raise ValueError(f"Unsupported YOLOv8 output rank: {values.ndim}.")
    expected_features = 4 + len(labels)
    if values.shape[0] == expected_features and values.shape[1] != expected_features:
        values = values.T
    if values.shape[1] != expected_features:
        raise ValueError(f"YOLOv8 output has {values.shape[1]} features; expected {expected_features} for configured labels.")

    original_width, original_height = original_size
    scale, pad_x, pad_y = transform
    input_height, input_width = input_size
    boxes_by_class: dict[int, list[tuple[tuple[float, float, float, float], float]]] = {}
    for row in values:
        class_scores = row[4:]
        class_index = int(np.argmax(class_scores))
        confidence = float(class_scores[class_index])
        if confidence < score_threshold:
            continue
        center_x, center_y, box_width, box_height = (float(value) for value in row[:4])
        x0 = max(0.0, min(1.0, (center_x - box_width / 2 - pad_x) / scale / original_width))
        y0 = max(0.0, min(1.0, (center_y - box_height / 2 - pad_y) / scale / original_height))
        x1 = max(0.0, min(1.0, (center_x + box_width / 2 - pad_x) / scale / original_width))
        y1 = max(0.0, min(1.0, (center_y + box_height / 2 - pad_y) / scale / original_height))
        if x1 <= x0 or y1 <= y0:
            continue
        boxes_by_class.setdefault(class_index, []).append(((x0, y0, x1, y1), confidence))

    detections: list[dict[str, Any]] = []
    for class_index, class_boxes in boxes_by_class.items():
        class_boxes.sort(key=lambda item: item[1], reverse=True)
        kept: list[tuple[tuple[float, float, float, float], float]] = []
        for candidate in class_boxes:
            if all(_iou(candidate[0], prior[0]) <= nms_threshold for prior in kept):
                kept.append(candidate)
            if len(kept) >= max_detections:
                break
        detections.extend({"label": labels[class_index], "box": box, "confidence": score} for box, score in kept)
    detections.sort(key=lambda item: item["confidence"], reverse=True)
    return detections[:max_detections]
