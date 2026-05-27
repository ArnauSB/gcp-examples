import os

from fastapi import FastAPI, HTTPException

# ============================================================================
# Demo configuration — edit these between pushes to walk the V1 → V4 demo.
# ============================================================================

VERSION = "v3"
COLOR = "red"
MESSAGE = "Hello from Cloud Run — stable version"

# Flip to True for the V3 broken-canary demo. Only `/` returns 500; `/health`
# stays healthy so the smoke test still passes and the progressive ramp
# actually starts — the inline bake check is what we want to catch the failure.
FAIL_ROOT = False

# ============================================================================

app = FastAPI(
    title="GCP Bootcamp Masterclass API",
    description="Progressive canary deployments on Cloud Run.",
    version=VERSION,
)

# K_REVISION is set automatically by Cloud Run on every revision.
REVISION = os.environ.get("K_REVISION", "local")


@app.get("/")
async def read_root() -> dict:
    if FAIL_ROOT:
        raise HTTPException(status_code=500, detail=f"{VERSION} canary on fire")
    return {
        "version": VERSION,
        "revision": REVISION,
        "color": COLOR,
        "message": MESSAGE,
    }


@app.get("/health")
async def health_check() -> dict:
    return {"status": "healthy", "version": VERSION}
