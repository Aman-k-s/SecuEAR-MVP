#!/usr/bin/env python3
"""
Stage 2 validation step (required by the build spec): plots depth maps for
every .ply in the scan data folder side by side, so it's easy to sanity-check
that same-person scans look similar and different-person scans look
different, before trusting anything downstream of them.

Usage (from backend/):
    venv/bin/python scripts/preview_depth_maps.py [path/to/scans_folder]

Defaults to SCAN_DATA_DIR from app.config (sample_data/ at the project root).
Writes a PNG grid to backend/depth_map_cache/preview.png and prints its path
rather than assuming a display is attached.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")  # headless-safe; script always saves a PNG rather than assuming a display
import matplotlib.pyplot as plt

from app import config
from app.services import preprocessing


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else config.SCAN_DATA_DIR
    ply_files = sorted(folder.glob("*.ply"))
    if not ply_files:
        print(f"No .ply files found in {folder}")
        return

    n = len(ply_files)
    cols = min(4, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 3.2 * rows))
    axes = axes.flatten() if n > 1 else [axes]

    for ax, ply_path in zip(axes, ply_files):
        print(f"Processing {ply_path.name} ...")
        try:
            result = preprocessing.ply_to_depth_map(str(ply_path))
            ax.imshow(result.depth_map, cmap="gray")
            ax.set_title(
                f"{ply_path.stem}\n{result.num_points_after_outlier_removal} pts (of {result.num_points_raw})",
                fontsize=9,
            )
        except Exception as e:
            ax.text(0.5, 0.5, f"FAILED:\n{e}", ha="center", va="center", fontsize=8, wrap=True)
        ax.axis("off")

    for ax in axes[n:]:
        ax.axis("off")

    fig.suptitle("Stage 2 sanity check: same-person depth maps should look visually similar", fontsize=11)
    fig.tight_layout()

    out_path = config.DEPTH_MAP_CACHE_DIR / "preview.png"
    fig.savefig(out_path, dpi=140)
    print(f"\nSaved preview grid to {out_path}")


if __name__ == "__main__":
    main()
