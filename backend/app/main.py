"""
SecuEAR backend entrypoint.

Run with:  uvicorn app.main:app --reload   (from the backend/ directory)

Wires together the Stage 7 FastAPI app: DB init on startup, the five routers
(enroll/verify/pay/wallet/audit), and the plain HTML/CSS/JS frontend served
as static files so the whole demo runs from a single `uvicorn` process.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, database
from .routers import audit, enroll, pay, verify, wallet


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="SecuEAR",
    description="Ear-shape biometric authentication gating a closed-loop prepaid wallet (MVP).",
    lifespan=lifespan,
)

# Permissive CORS: this is a local hackathon demo, not an internet-facing
# service (see README Non-Goals re: production hardening).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(enroll.router, tags=["enroll"])
app.include_router(verify.router, tags=["verify"])
app.include_router(pay.router, tags=["pay"])
app.include_router(wallet.router, tags=["wallet"])
app.include_router(audit.router, tags=["audit"])


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve the plain HTML/CSS/JS frontend (Stage 10) from the same process.
# Mounted *after* the API routers above so /enroll, /pay, etc. are matched
# as API calls first; only unmatched paths (e.g. /enroll.html) fall through
# to these static files.
_frontend_dir = config.PROJECT_ROOT / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
