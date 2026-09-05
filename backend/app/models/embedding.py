"""
Stage 4 - Embedding via transfer learning (frozen, pretrained, no training).

See SecuEAR_Technical_Documentation.md section 5 for the full rationale.
Short version: a from-scratch or fine-tuned network has no meaningful way to
demonstrate generalization on a 3-identity dataset, so this MVP uses an
ImageNet-pretrained ResNet18 purely as a fixed feature extractor:

  depth map (1ch, HxW) -> replicate to 3ch -> ResNet18 up to penultimate layer
    -> 512-dim feature vector -> L2-normalize -> compare via cosine similarity

The network's weights are never updated. This module also implements the
Stage 4 cross-side mirroring rule: verification against an enrolled embedding
of the *opposite* ear side horizontally flips the depth map before embedding,
approximating the anatomical left/right mirror relationship. Which mode was
used is returned alongside the embedding so callers can log it.
"""
from dataclasses import dataclass
from enum import Enum

import numpy as np
import torch
import torchvision.transforms as T
from torchvision.models import ResNet18_Weights, resnet18

from ..services.preprocessing import mirror_depth_map

# Without this, PyTorch's own thread pool can deadlock the first time it runs
# an actual tensor op (e.g. inside torchvision's `to_tensor`), racing with
# Open3D's already-active OpenMP threads - see app/__init__.py docstring.
# Harmless to pin to 1 thread: these are single-image, CPU-only, ~200ms
# inferences: there's no batch of work here for multiple threads to help with.
torch.set_num_threads(1)

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ImageNet normalization stats - required by the pretrained weights regardless
# of the fact our "RGB" image is really a replicated grayscale depth map.
_PREPROCESS = T.Compose([
    T.ToTensor(),                      # HxWx3 uint8 -> 3xHxW float in [0,1]
    T.Resize((224, 224)),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

_model = None


def _get_model() -> torch.nn.Module:
    """Lazily builds the frozen feature extractor (ResNet18 minus its final
    classification layer) and caches it at module scope - it's the same
    network for every request, so there's no reason to rebuild it."""
    global _model
    if _model is None:
        net = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        net.fc = torch.nn.Identity()   # strip classification head -> penultimate-layer output
        net.eval()
        for p in net.parameters():
            p.requires_grad = False    # frozen: no training/fine-tuning, per Stage 4 spec
        _model = net.to(_DEVICE)
    return _model


class ComparisonMode(str, Enum):
    SAME_SIDE = "same_side"
    MIRRORED_CROSS_SIDE = "mirrored_cross_side"


def _depth_map_to_rgb_tensor(depth_map: np.ndarray) -> torch.Tensor:
    """Replicates a single-channel [0,1] depth map across 3 channels, per Stage 4."""
    img_uint8 = (np.clip(depth_map, 0.0, 1.0) * 255).astype(np.uint8)
    rgb = np.stack([img_uint8, img_uint8, img_uint8], axis=-1)  # HxWx3
    return _PREPROCESS(rgb)


@torch.no_grad()
def extract_embedding(depth_map: np.ndarray) -> np.ndarray:
    """Runs the frozen ResNet18 feature extractor on a single depth map and
    returns the L2-normalized 512-dim embedding as a plain numpy float32 array."""
    tensor = _depth_map_to_rgb_tensor(depth_map).unsqueeze(0).to(_DEVICE)  # 1x3x224x224
    features = _get_model()(tensor).squeeze(0)                            # 512-dim
    norm = features.norm(p=2).clamp_min(1e-8)
    normalized = features / norm
    return normalized.cpu().numpy().astype(np.float32)


def extract_embedding_for_verification(
    depth_map: np.ndarray, scan_side: str, enrolled_side: str
) -> tuple[np.ndarray, ComparisonMode]:
    """
    Applies the Stage 4 cross-side correction: mirrors the depth map before
    embedding if the scan's side differs from the enrolled side, then
    extracts the embedding. Returns (embedding, comparison_mode) so the
    caller can log which path was used, per the required audit trail.
    """
    if scan_side == enrolled_side:
        return extract_embedding(depth_map), ComparisonMode.SAME_SIDE

    mirrored = mirror_depth_map(depth_map)
    return extract_embedding(mirrored), ComparisonMode.MIRRORED_CROSS_SIDE


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Both inputs are expected to already be L2-normalized (extract_embedding
    guarantees this), so this is just the dot product - kept as an explicit
    named function for readability at call sites and to be robust if a caller
    passes in a not-quite-unit vector (e.g. loaded from older stored JSON)."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    a_norm = a / max(np.linalg.norm(a), 1e-8)
    b_norm = b / max(np.linalg.norm(b), 1e-8)
    return float(np.dot(a_norm, b_norm))
