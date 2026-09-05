"""
Stage 2 - Preprocessing: point cloud -> normalized depth map.

Pipeline (see SecuEAR_Technical_Documentation.md section 3):
  1. Load the .ply with Open3D.
  2. Statistical outlier removal (strip sensor noise).
  3. PCA-align to the two largest-variance axes ("facing plane"); the
     smallest-variance axis becomes depth.
  4. Project points into a fixed-size 2D grid, averaging depth per cell.
  5. Normalize to [0, 1].

Output is a single-channel float32 grayscale depth map, plus the raw grid
occupancy mask (which cells actually received points) for debugging/plots.
"""
from dataclasses import dataclass

import numpy as np
import open3d as o3d

from .. import config


@dataclass
class DepthMapResult:
    depth_map: np.ndarray      # float32, shape (grid_size, grid_size), values in [0, 1]
    occupied_mask: np.ndarray  # bool, same shape - True where a real point landed
    num_points_raw: int
    num_points_after_outlier_removal: int


def load_point_cloud(ply_path: str) -> o3d.geometry.PointCloud:
    pcd = o3d.io.read_point_cloud(str(ply_path))
    if len(pcd.points) == 0:
        raise ValueError(f"No points loaded from {ply_path} - is this a valid .ply file?")
    return pcd


def remove_outliers(pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """Statistical outlier removal - strips sensor noise (hair, edges, reflections)."""
    clean, _inlier_idx = pcd.remove_statistical_outlier(
        nb_neighbors=config.OUTLIER_NB_NEIGHBORS,
        std_ratio=config.OUTLIER_STD_RATIO,
    )
    return clean


def _fix_eigenvector_signs(eigvecs: np.ndarray, centered: np.ndarray) -> np.ndarray:
    """
    `np.linalg.eigh` returns each eigenvector with an arbitrary sign (either
    direction is a valid axis). Left unfixed, this makes the depth axis's
    polarity a coin flip per scan - two scans of the exact same ear can come
    out with inverted brightness (concha rendered as a bright bump in one,
    a dark hollow in the other), which looks like a totally different
    surface to the downstream embedding model despite identical geometry.

    Deterministic fix (same idea as sklearn's `svd_flip`): for each axis,
    orient it so the point with the largest-magnitude projection is on the
    positive side. This is derived purely from each scan's own point
    distribution, so it's reproducible across runs and doesn't depend on
    eigh's internal tie-breaking.
    """
    projections = centered @ eigvecs  # N x 3
    max_abs_idx = np.argmax(np.abs(projections), axis=0)
    signs = np.sign(projections[max_abs_idx, np.arange(eigvecs.shape[1])])
    signs[signs == 0] = 1
    return eigvecs * signs


def pca_align(points: np.ndarray) -> np.ndarray:
    """
    Re-expresses `points` (N x 3) in a frame defined by their own principal
    axes: columns 0-1 are the two largest-variance directions (the ear's
    "facing plane"), column 2 is the smallest-variance direction (depth).

    This makes the projection in `project_to_grid` robust to how the phone
    was actually held during capture, rather than requiring a fixed pose.
    """
    centered = points - points.mean(axis=0, keepdims=True)
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)  # ascending order
    order = np.argsort(eigvals)[::-1]       # descending: [largest, mid, smallest]
    eigvecs = eigvecs[:, order]
    eigvecs = _fix_eigenvector_signs(eigvecs, centered)
    return centered @ eigvecs  # columns: [plane_u, plane_v, depth]


def project_to_grid(aligned_points: np.ndarray, grid_size: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Bins the plane coordinates (columns 0, 1) into a grid_size x grid_size
    grid and averages the depth coordinate (column 2) per cell.

    Returns (depth_grid, occupied_mask). Empty cells (no points landed there,
    common near the edges of an irregularly-shaped ear scan) are filled with
    the mean depth of occupied cells so the output has no NaN/holes.
    """
    u, v, d = aligned_points[:, 0], aligned_points[:, 1], aligned_points[:, 2]

    u_min, u_max = u.min(), u.max()
    v_min, v_max = v.min(), v.max()
    u_span = max(u_max - u_min, 1e-8)
    v_span = max(v_max - v_min, 1e-8)

    # Bin index per point, clipped to valid range (max value falls in last bin).
    u_idx = np.clip(((u - u_min) / u_span * grid_size).astype(np.int32), 0, grid_size - 1)
    v_idx = np.clip(((v - v_min) / v_span * grid_size).astype(np.int32), 0, grid_size - 1)

    depth_sum = np.zeros((grid_size, grid_size), dtype=np.float64)
    depth_count = np.zeros((grid_size, grid_size), dtype=np.int32)
    np.add.at(depth_sum, (v_idx, u_idx), d)
    np.add.at(depth_count, (v_idx, u_idx), 1)

    occupied_mask = depth_count > 0
    depth_grid = np.zeros((grid_size, grid_size), dtype=np.float64)
    depth_grid[occupied_mask] = depth_sum[occupied_mask] / depth_count[occupied_mask]

    if occupied_mask.any():
        fill_value = depth_grid[occupied_mask].mean()
    else:
        fill_value = 0.0
    depth_grid[~occupied_mask] = fill_value

    return depth_grid.astype(np.float32), occupied_mask


def normalize_depth_map(depth_grid: np.ndarray) -> np.ndarray:
    lo, hi = depth_grid.min(), depth_grid.max()
    span = max(hi - lo, 1e-8)
    return ((depth_grid - lo) / span).astype(np.float32)


def ply_to_depth_map(ply_path: str, grid_size: int = None) -> DepthMapResult:
    """Runs the full Stage 2 pipeline on a single .ply file."""
    grid_size = grid_size or config.DEPTH_MAP_GRID_SIZE

    pcd = load_point_cloud(ply_path)
    num_raw = len(pcd.points)

    clean_pcd = remove_outliers(pcd)
    num_clean = len(clean_pcd.points)
    if num_clean < 50:
        raise ValueError(
            f"Only {num_clean} points survived outlier removal for {ply_path} - "
            "scan is likely corrupt or empty."
        )

    points = np.asarray(clean_pcd.points)
    aligned = pca_align(points)
    depth_grid, occupied_mask = project_to_grid(aligned, grid_size)
    depth_map = normalize_depth_map(depth_grid)

    return DepthMapResult(
        depth_map=depth_map,
        occupied_mask=occupied_mask,
        num_points_raw=num_raw,
        num_points_after_outlier_removal=num_clean,
    )


def mirror_depth_map(depth_map: np.ndarray) -> np.ndarray:
    """Horizontal flip (about the vertical axis) - the Stage 4 cross-side correction."""
    return np.fliplr(depth_map).copy()


def depth_map_to_uint8_image(depth_map: np.ndarray) -> np.ndarray:
    """Converts a [0,1] float depth map to a uint8 grayscale image for cv2 / PIL."""
    return (np.clip(depth_map, 0.0, 1.0) * 255).astype(np.uint8)
