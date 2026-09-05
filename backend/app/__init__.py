"""
SecuEAR backend package.

Open3D and PyTorch each bundle their own OpenMP runtime. Loading both in one
process is only safe with two fixes applied, both established by isolated
testing on this environment (see README "Known Limitations" / troubleshooting
notes):

  1. Import order: open3d must be imported before torch/torchvision, or the
     conflicting OpenMP runtimes abort the process on load
     ("OMP: Error #179: Function pthread_mutex_init failed"). Forcing the
     import here - before any submodule (models/embedding.py,
     services/preprocessing.py, etc.) gets a chance to import either in the
     "wrong" order - makes this independent of which router/script happens
     to run first.
  2. `torch.set_num_threads(1)` (done in models/embedding.py, once torch is
     imported): without it, PyTorch's own thread pool can deadlock the first
     time it actually runs a tensor op, racing with Open3D's already-active
     OpenMP threads. KMP_DUPLICATE_LIB_OK alone silences the load-time abort
     but does NOT fix this runtime deadlock - both fixes are required.

This is a local workaround for a native-library interaction, not a
production concern.
"""
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import open3d as _o3d  # noqa: E402,F401  (import order matters - see docstring)
