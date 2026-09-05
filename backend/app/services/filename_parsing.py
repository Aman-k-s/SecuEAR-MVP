"""
Stage 1 filename parsing - kept in its own module, separate from
services/pipeline.py, so utils.resolve_side can parse a `side` out of an
uploaded filename without needing to import the rest of the (heavier) Stage
2-4 pipeline just for that.
"""
import re

# {person}_{left|right|testN}.ply - see SecuEAR_Coding_Agent_Prompt.md "Input Data".
_FILENAME_RE = re.compile(r"^(?P<person>[A-Za-z0-9]+)_(?P<role>left|right|test\d+)", re.IGNORECASE)


def parse_person_and_side(filename: str) -> tuple[str | None, str | None]:
    """
    Parses the `{person}_{left|right|testN}.ply` naming convention (Stage 1).

    Returns (person, side). `side` is 'left'/'right' when the filename states
    it directly, or None when the file uses an ambiguous `testN` token (or
    doesn't match the convention at all) - callers must not guess a side in
    that case. In this project's own sample dataset, `guransh_test1.ply` /
    `guransh_test2.ply` hit exactly this case and were excluded from the demo
    seed set for that reason (see README "Known Limitations").
    """
    stem = filename.rsplit("/", 1)[-1]
    stem = re.sub(r"\.ply$", "", stem, flags=re.IGNORECASE)
    m = _FILENAME_RE.match(stem)
    if not m:
        return None, None
    person = m.group("person").lower()
    role = m.group("role").lower()
    side = role if role in ("left", "right") else None
    return person, side
