#!/usr/bin/env python3
"""
End-to-end demo/smoke script that exercises the full pipeline against the
provided .ply scans folder WITHOUT needing the HTTP server running - this is
what "point it at the .ply scans folder" (README) means in practice.

For every person found (via the `{person}_left.ply` / `{person}_right.ply`
naming convention - see app.services.pipeline.parse_person_and_side):
  1. Enrolls them using their `left` scan (Stage 1-4).
  2. Verifies their own `right` scan against their enrolled profile
     (genuine attempt - expect a cross-side "mirrored_cross_side" comparison,
     since this dataset has no same-side verification scan for anyone).
  3. Verifies their `right` scan against every OTHER enrolled person's
     profile (impostor attempt - expect a low score / deny).

Every enroll/verify event is written to the real audit_log table (same DB
the FastAPI app uses), so results are also visible at once in audit.html.

Usage (from backend/):
    venv/bin/python scripts/seed_demo_data.py [path/to/scans_folder]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, database
from app.models import embedding as embedding_model
from app.services import pipeline
from app.verification import verify_scan


def discover_people(folder: Path) -> dict[str, dict[str, Path]]:
    """Groups .ply files by person, keeping only files with an unambiguous
    left/right side (testN files are skipped - see pipeline.parse_person_and_side
    and README "Known Limitations" for why this dataset's guransh_test1/2.ply
    are intentionally excluded here)."""
    people: dict[str, dict[str, Path]] = {}
    skipped = []
    for ply_path in sorted(folder.glob("*.ply")):
        person, side = pipeline.parse_person_and_side(ply_path.name)
        if person is None or side is None:
            skipped.append(ply_path.name)
            continue
        people.setdefault(person, {})[side] = ply_path

    if skipped:
        print(f"Skipping (ambiguous side, not left/right): {', '.join(skipped)}")
    return people


def enroll_person(person: str, left_path: Path) -> None:
    scan = pipeline.process_scan_to_depth_map(str(left_path), side="left")
    emb = embedding_model.extract_embedding(scan.depth_map)
    database.create_user(user_id=person, name=person.capitalize(), embedding=emb.tolist(), side="left")
    database.log_event(
        user_id=person,
        event_type="enroll",
        reasoning=(
            f"[demo seed] Enrolled '{person}' with left-ear scan {left_path.name} "
            f"(ear detection: {scan.ear_detection_path})."
        ),
    )
    print(f"  enrolled {person} <- {left_path.name} (ear detection: {scan.ear_detection_path})")


def run_verification(verifier_person: str, scan_path: Path, against_user_id: str, txn_prefix: str) -> None:
    result = verify_scan(against_user_id, str(scan_path), side="right")
    database.log_event(
        user_id=against_user_id,
        event_type="verify",
        txn_ref=f"{txn_prefix}_{verifier_person}_vs_{against_user_id}",
        match_score=result.score,
        high_threshold=result.decision.high_threshold,
        med_threshold=result.decision.med_threshold,
        decision_tier=result.decision.tier.value,
        comparison_mode=result.comparison_mode,
        reasoning=f"[demo seed] {result.decision.reasoning} (ear detection: {result.ear_detection_path})",
    )
    tag = "GENUINE " if verifier_person == against_user_id else "IMPOSTOR"
    print(
        f"  [{tag}] {scan_path.name} vs enrolled({against_user_id}): "
        f"score={result.score:.4f}  tier={result.decision.tier.value:<12}  mode={result.comparison_mode}"
    )


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else config.SCAN_DATA_DIR
    database.init_db()

    people = discover_people(folder)
    people = {p: files for p, files in people.items() if "left" in files and "right" in files}
    if not people:
        print(f"No complete {{person}}_left.ply + {{person}}_right.ply pairs found in {folder}")
        return

    print(f"Found {len(people)} people in {folder}: {', '.join(sorted(people))}\n")

    print("-- Enrolling (Stage 1-4) --")
    for person, files in sorted(people.items()):
        enroll_person(person, files["left"])

    print("\n-- Verifying (genuine + impostor attempts, Stage 4+6) --")
    for verifier_person, files in sorted(people.items()):
        for against_person in sorted(people):
            run_verification(verifier_person, files["right"], against_person, txn_prefix="demo")

    print(f"\nDone. Balances/audit trail written to {config.DB_PATH}")
    print("Start the server (`uvicorn app.main:app --reload`) and open audit.html to see these entries.")


if __name__ == "__main__":
    main()
