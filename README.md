# SecuEAR

Ear-shape biometric authentication gating a closed-loop prepaid wallet — an MVP built for the Razorpay AI Buildathon (Open Track).

Full pipeline: `.ply` scan → depth map → ear crop → embedding → similarity score → tiered decision → wallet debit → audit log.

Build spec: [docs/SecuEAR_Coding_Agent_Prompt.md](docs/SecuEAR_Coding_Agent_Prompt.md) · Design rationale: [docs/SecuEAR_Technical_Documentation.md](docs/SecuEAR_Technical_Documentation.md) (read this for *why* each stage works the way it does — this README covers setup/running and defers to it for rationale).

---

## Setup

Requires **Python 3.11** specifically — Open3D and PyTorch don't yet ship wheels for Python 3.13+/3.14, so a newer system Python won't work. On macOS: `brew install python@3.11`.

```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv venv     # or wherever your python3.11 lives
venv/bin/pip install -r requirements.txt
```

## Running

```bash
cd backend
venv/bin/uvicorn app.main:app --reload
```

Then open:
- `http://localhost:8000/enroll.html` — enroll a user
- `http://localhost:8000/pay.html` — kiosk payment simulation
- `http://localhost:8000/recharge.html` — add wallet balance
- `http://localhost:8000/audit.html` — audit log viewer

The frontend is served by the same FastAPI process (see `app/main.py`), so there's nothing else to start.

## Pointing it at the `.ply` scans folder

The provided scans live in `sample_data/` (copied from the original `ply_scans/` folder). Two ways to use them:

1. **Through the UI** — upload a file like `sample_data/aman_left.ply` via `enroll.html`, matching name to file.
2. **End-to-end smoke test, no server needed** — enrolls everyone found in the folder and runs genuine + impostor verification attempts against each:
   ```bash
   cd backend
   venv/bin/python scripts/seed_demo_data.py [path/to/scans_folder]   # defaults to ../sample_data
   ```
   This writes to the same `secuear.db` the server uses, so results show up immediately in `audit.html`.

There's also a Stage 2 sanity-check script (required by the build spec) that plots depth maps side by side, so you can visually confirm same-person scans look similar and different-person scans look different:
```bash
venv/bin/python scripts/preview_depth_maps.py   # writes backend/depth_map_cache/preview.png
```

To point either script at a different folder of `.ply` files, pass it as an argument, or set `SECUEAR_DATA_DIR`.

---

## Pipeline stages implemented

Mirrors the 10-stage spec in `docs/SecuEAR_Coding_Agent_Prompt.md` exactly — no substitutions:

| Stage | What | Where |
|---|---|---|
| 1 | Parse `{person}_{left\|right\|testN}.ply` filenames | `app/services/filename_parsing.py` |
| 2 | Point cloud → normalized depth map (Open3D outlier removal, PCA align, grid projection) | `app/services/preprocessing.py` |
| 3 | Haar-cascade ear crop, with fallback to uncropped | `app/services/ear_detection.py` |
| 4 | Frozen ResNet18 embedding + cross-side mirroring | `app/models/embedding.py` |
| 5 | Liveness detection — **skipped**, see below | — |
| 6 | Confidence-gated tiered decision | `app/models/decision.py` |
| 7 | FastAPI app | `app/main.py`, `app/routers/*.py` |
| 8 | SQLite (plain `sqlite3`, no ORM) | `app/database.py` |
| 9 | Mocked Razorpay (`create_order`/`capture_payment`) | `app/services/razorpay_mock_service.py` |
| 10 | Plain HTML/CSS/JS frontend | `frontend/*.html` |

**Stage 5 (liveness) is deliberately not implemented** — the dataset is single static scans with no head-turn/motion sequences to build or validate a liveness check against. Shipping one anyway would mean unvalidated code with no way to verify it works. Flagged here as a scope cut, not an oversight; see `docs/SecuEAR_Technical_Documentation.md` §6.

---

## API

| Endpoint | Purpose |
|---|---|
| `POST /enroll` | `user_id`, `name`, `file` (+optional `side`) → stores embedding, inits wallet at 0 |
| `POST /verify` | `user_id`, `txn_ref`, `file` (+optional `side`) → decision tier + score, no debit |
| `POST /pay` | `user_id`, `txn_ref`, `amount`, `file`, optional `pin_confirmed` (+optional `side`) → verifies, debits if approved |
| `POST /wallet/recharge` | `user_id`, `amount` → mock Razorpay credit |
| `GET /wallet/{user_id}` | current balance |
| `GET /audit-log?limit=100` | recent decisions, most recent first |

`side` ("left"/"right") is normally parsed from the uploaded filename per the `{person}_{left|right}.ply` convention; pass it explicitly as a form field to override when a filename doesn't follow that convention.

Decision thresholds (`HIGH_THRESHOLD=0.85`, `MED_THRESHOLD=0.65` by default) are configurable via env vars — see `app/config.py`.

---

## Known limitations

Beyond what's already covered in `docs/SecuEAR_Technical_Documentation.md` §9 (dataset size, no liveness, unverified ear-detection reliability, generic embedding model, mocked payments):

- **`guransh_test1.ply` / `guransh_test2.ply` are excluded from `sample_data/`.** Their ear side can't be determined from the filename or the `.ply` metadata, and the build spec is explicit that ambiguous side should be asked about rather than assumed. Left out of the dataset by request rather than guessed. The pipeline still parses `testN` filenames generically (`filename_parsing.py`) and will happily use one if you rename it to state its side, or pass `side` explicitly.
- **No same-side verification example exists in this dataset.** Every person only has one enrollment scan (`left`) and one verification scan (`right`), so every genuine verification in this demo is necessarily a cross-side (`mirrored_cross_side`) comparison — there's no `{person}_left2.ply` to demonstrate the `same_side` path against. The code path exists and is exercised by unit-level logic in `models/embedding.py`; it's just not represented in this particular sample dataset.
- **Score separation is narrower than the default thresholds assume.** Against this actual dataset, genuine cross-side scores land around 0.82–0.87 and impostor scores around 0.78–0.85 — close enough that most comparisons land in `pin_required` rather than cleanly at the extremes (run `scripts/seed_demo_data.py` to see current numbers). This is a real, expected consequence of using a generic frozen ImageNet feature extractor (see Technical Documentation §5) rather than a threshold miscalibration — the tiers behave correctly given the score, but the score itself doesn't separate identities as cleanly as a purpose-trained ear embedding model would. Stated here rather than tuned away, in keeping with this project's honest-positioning approach.
- **macOS + Open3D + PyTorch native-library interaction.** Open3D and PyTorch each bundle their own OpenMP runtime; running both in one process needs two fixes, both already applied in the code (`app/__init__.py` forces import order; `app/models/embedding.py` calls `torch.set_num_threads(1)`). If you ever see `OMP: Error #179` or a request that hangs forever on first use after modifying import order in these files, this is why — see the docstrings in those two files before changing them.

---

## Project structure

```
SecuEAR/
├── backend/
│   ├── app/
│   │   ├── main.py, database.py, config.py, utils.py, verification.py
│   │   ├── models/       # decision.py, embedding.py, similarity.py
│   │   ├── routers/      # enroll, verify, pay, wallet, audit
│   │   ├── services/     # preprocessing, ear_detection, pipeline, razorpay_mock_service
│   │   └── assets/cascades/   # haarcascade_mcs_{left,right}ear.xml
│   ├── scripts/          # seed_demo_data.py, preview_depth_maps.py
│   └── requirements.txt
├── frontend/              # enroll.html, pay.html, recharge.html, audit.html
├── sample_data/           # provided .ply scans (testN excluded, see Known Limitations)
├── docs/                  # original build spec + technical documentation
└── README.md
```

## Non-goals

No real Razorpay calls, no liveness/anti-spoofing, no auth beyond a plain `user_id`, no production-grade hardening, no neural network training — all per the locked spec.
