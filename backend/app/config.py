"""
Central configuration for SecuEAR.

Everything here is deliberately a plain module-level constant (overridable via
environment variables) rather than a settings framework - this is a hackathon
MVP, not a production service (see README "Non-Goals").
"""
import os
from pathlib import Path

# --- Paths -------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent          # .../SecuEAR/backend
PROJECT_ROOT = BACKEND_DIR.parent                              # .../SecuEAR
APP_DIR = BACKEND_DIR / "app"

DB_PATH = Path(os.environ.get("SECUEAR_DB_PATH", BACKEND_DIR / "secuear.db"))

# Folder of raw .ply scans this instance is "pointed at" for the demo seed
# script (see backend/scripts/seed_demo_data.py). Defaults to the
# sample_data/ folder shipped alongside this project.
SCAN_DATA_DIR = Path(os.environ.get("SECUEAR_DATA_DIR", PROJECT_ROOT / "sample_data"))

# Where uploaded scans are temporarily written before processing, and where
# generated depth-map preview images are cached for debugging.
UPLOAD_TMP_DIR = Path(os.environ.get("SECUEAR_UPLOAD_DIR", BACKEND_DIR / "tmp_uploads"))
DEPTH_MAP_CACHE_DIR = Path(os.environ.get("SECUEAR_DEPTHMAP_DIR", BACKEND_DIR / "depth_map_cache"))
UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
DEPTH_MAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Haar cascades for Stage 3 (ear region isolation). See services/ear_detection.py
# for the fallback behavior when these don't fire on synthetic depth-map input.
CASCADE_DIR = APP_DIR / "assets" / "cascades"
LEFT_EAR_CASCADE_PATH = CASCADE_DIR / "haarcascade_mcs_leftear.xml"
RIGHT_EAR_CASCADE_PATH = CASCADE_DIR / "haarcascade_mcs_rightear.xml"

# --- Stage 2: point cloud -> depth map ----------------------------------
DEPTH_MAP_GRID_SIZE = int(os.environ.get("SECUEAR_GRID_SIZE", 128))
OUTLIER_NB_NEIGHBORS = 20
OUTLIER_STD_RATIO = 2.0

# --- Stage 6: confidence-gated decision thresholds ----------------------
# Cosine similarity in [-1, 1] (in practice ~[0, 1] for related depth maps).
HIGH_THRESHOLD = float(os.environ.get("SECUEAR_HIGH_THRESHOLD", 0.85))
MED_THRESHOLD = float(os.environ.get("SECUEAR_MED_THRESHOLD", 0.65))

# --- Misc ----------------------------------------------------------------
ALLOWED_SIDES = ("left", "right")
