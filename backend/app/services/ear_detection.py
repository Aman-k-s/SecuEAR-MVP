"""
Stage 3 - Ear region isolation via OpenCV Haar cascade, with a mandatory
fallback (see SecuEAR_Technical_Documentation.md section 4).

Honest caveat baked into this module: `haarcascade_mcs_leftear.xml` /
`haarcascade_mcs_rightear.xml` were trained on natural ear photographs, not
synthetic PCA-projected depth-map renders like ours. They may simply never
fire on this kind of input - that is expected, not a bug. The fallback path
(use the full Stage 2 depth map, uncropped) is therefore the common case for
this dataset, and every call reports which path was taken so it's visible
rather than silently masked.
"""
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np

from .. import config


class DetectionPath(str, Enum):
    DETECTED = "detected"
    FALLBACK_NO_DETECTION = "fallback_no_detection"
    FALLBACK_IMPLAUSIBLE = "fallback_implausible_region"
    FALLBACK_NO_CASCADE = "fallback_cascade_unavailable"


@dataclass
class EarCropResult:
    image: np.ndarray            # uint8 grayscale, cropped (or the original if fallback)
    path_taken: DetectionPath
    bounding_box: tuple | None   # (x, y, w, h) in the *input* image, or None on fallback


_cascade_cache: dict[str, cv2.CascadeClassifier] = {}


def _load_cascade(side: str) -> cv2.CascadeClassifier | None:
    """Loads (and caches) the Haar cascade for the given side. Returns None if
    the XML file isn't present or fails to load, in which case callers must
    treat every scan as a fallback."""
    if side in _cascade_cache:
        return _cascade_cache[side]

    path = config.LEFT_EAR_CASCADE_PATH if side == "left" else config.RIGHT_EAR_CASCADE_PATH
    if not path.exists():
        _cascade_cache[side] = None
        return None

    cascade = cv2.CascadeClassifier(str(path))
    if cascade.empty():
        _cascade_cache[side] = None
        return None

    _cascade_cache[side] = cascade
    return cascade


def _is_plausible(box: tuple, image_shape: tuple) -> bool:
    """Sanity-checks a detected region: it should cover a reasonable fraction
    of the frame (not a 3-pixel speck, not the whole image) and be roughly
    ear-shaped (taller than wide, per the cascade's own 12x20 training aspect)."""
    x, y, w, h = box
    img_h, img_w = image_shape[:2]
    area_frac = (w * h) / float(img_w * img_h)
    if area_frac < 0.02 or area_frac > 0.90:
        return False
    aspect = h / float(w)
    if aspect < 0.5 or aspect > 3.5:
        return False
    return True


def isolate_ear_region(gray_image: np.ndarray, side: str) -> EarCropResult:
    """
    Attempts to detect and crop the ear region from `gray_image` (uint8,
    single-channel) using the Haar cascade matching `side`. Falls back to
    the full uncropped image if detection is unavailable, empty, or the
    detected region fails a basic plausibility check.
    """
    cascade = _load_cascade(side)
    if cascade is None:
        return EarCropResult(image=gray_image, path_taken=DetectionPath.FALLBACK_NO_CASCADE, bounding_box=None)

    detections = cascade.detectMultiScale(
        gray_image,
        scaleFactor=1.05,
        minNeighbors=3,
        minSize=(max(8, gray_image.shape[1] // 16), max(8, gray_image.shape[0] // 16)),
    )

    if len(detections) == 0:
        return EarCropResult(image=gray_image, path_taken=DetectionPath.FALLBACK_NO_DETECTION, bounding_box=None)

    # If multiple candidate regions fire, take the largest one.
    box = max(detections, key=lambda b: b[2] * b[3])
    if not _is_plausible(box, gray_image.shape):
        return EarCropResult(
            image=gray_image, path_taken=DetectionPath.FALLBACK_IMPLAUSIBLE, bounding_box=tuple(box)
        )

    x, y, w, h = box
    cropped = gray_image[y:y + h, x:x + w]
    return EarCropResult(image=cropped, path_taken=DetectionPath.DETECTED, bounding_box=tuple(box))
