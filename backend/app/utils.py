"""Small helpers shared by the enroll/verify/pay routers."""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from . import config
from .services.filename_parsing import parse_person_and_side


async def save_upload_to_tmp(file: UploadFile) -> Path:
    """Writes an uploaded .ply file to a scratch path and returns it. Callers
    are responsible for deleting it (`path.unlink(missing_ok=True)`) once done -
    kept explicit rather than a context manager so it's obvious in each router
    that cleanup happens even on a processing error (via try/finally)."""
    suffix = Path(file.filename or "scan.ply").suffix or ".ply"
    dest = config.UPLOAD_TMP_DIR / f"{uuid.uuid4().hex}{suffix}"
    contents = await file.read()
    dest.write_bytes(contents)
    return dest


def resolve_side(filename: str | None, side_override: str | None) -> str:
    """
    Determines the ear side for an uploaded scan (Stage 1 metadata that must
    be tracked, not discarded). An explicit `side` form field always wins;
    otherwise it's parsed from the `{person}_{left|right}` filename
    convention. Raises a clear 400 rather than silently guessing when neither
    source yields a definite side (e.g. a `testN` filename) - see
    pipeline.parse_person_and_side and the README note on why this project's
    own `guransh_test1/2.ply` files were excluded from the demo dataset.
    """
    if side_override:
        side_override = side_override.strip().lower()
        if side_override not in config.ALLOWED_SIDES:
            raise HTTPException(400, f"side must be 'left' or 'right', got '{side_override}'")
        return side_override

    _, parsed_side = parse_person_and_side(filename or "")
    if parsed_side is None:
        raise HTTPException(
            400,
            f"Could not determine ear side from filename '{filename}'. Upload a file "
            "named '{person}_left.ply' / '{person}_right.ply', or pass an explicit "
            "`side` form field ('left'/'right').",
        )
    return parsed_side
