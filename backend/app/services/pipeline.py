"""
Orchestrates Stages 1-3 end-to-end for a single .ply file:
  Stage 1: parse {person}_{left|right|testN} filename convention
  Stage 2: point cloud -> normalized depth map
  Stage 3: Haar-cascade ear crop, with fallback to the full depth map

The result is a depth map ready for Stage 4 (embedding, in models/embedding.py),
which is kept separate because Stage 4's cross-side mirroring decision needs
the *enrolled* user's side as well, which this module has no knowledge of.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from . import ear_detection, preprocessing
from .filename_parsing import parse_person_and_side  # noqa: F401  (re-exported for callers)


@dataclass
class ScanProcessingResult:
    depth_map: np.ndarray            # normalized [0,1], post ear-crop (Stage 3), pre-mirror (Stage 4)
    ear_detection_path: str
    ear_bounding_box: tuple | None
    num_points_raw: int
    num_points_clean: int


def process_scan_to_depth_map(ply_path: str, side: str) -> ScanProcessingResult:
    """
    Runs Stage 2 (point cloud -> depth map) then Stage 3 (ear crop, using the
    cascade matching this scan's actual `side`, with fallback) on one .ply file.
    """
    stage2 = preprocessing.ply_to_depth_map(ply_path)
    gray_u8 = preprocessing.depth_map_to_uint8_image(stage2.depth_map)

    crop = ear_detection.isolate_ear_region(gray_u8, side=side)

    if crop.image.shape != gray_u8.shape:
        resized = cv2.resize(crop.image, gray_u8.shape[::-1], interpolation=cv2.INTER_LINEAR)
    else:
        resized = crop.image

    depth_map = resized.astype(np.float32) / 255.0

    return ScanProcessingResult(
        depth_map=depth_map,
        ear_detection_path=crop.path_taken.value,
        ear_bounding_box=crop.bounding_box,
        num_points_raw=stage2.num_points_raw,
        num_points_clean=stage2.num_points_after_outlier_removal,
    )
