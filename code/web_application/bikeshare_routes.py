"""HW7 Part 4 UI routes: GET /bikeshare (page) and POST /api/bikeshare/run (agent run)."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from bikeshare.agent import run_bike_agent, save_evidence  # noqa: E402

router = APIRouter(tags=["bikeshare"])
PAGE = Path(__file__).resolve().parent / "bikeshare.html"
UI_RUNS = ROOT / "reports" / "hw07" / "raw" / "part4_ui_runs"
MAX_BYTES = 20 * 1024 * 1024


@router.get("/bikeshare", include_in_schema=False)
def bikeshare_page() -> FileResponse:
    """Return the bike-share advisor page."""
    return FileResponse(PAGE)


@router.post("/api/bikeshare/run")
def bikeshare_run(file: UploadFile = File(...), url: str = Form(...)) -> dict:
    """Run the ReAct agent on the uploaded trip CSV and pricing URL; return the full result."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="upload a .csv trip file")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV larger than 20 MB")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="pricing URL must start with http(s)://")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "uploaded.csv"
        path.write_bytes(data)
        try:
            result = run_bike_agent(path, url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    run_dir = UI_RUNS / f"{datetime.now():%Y%m%d-%H%M%S}-{Path(file.filename).stem}"
    save_evidence(result, run_dir)
    result.pop("snapshots", None)
    result["evidence_dir"] = str(run_dir.relative_to(ROOT))
    result["filename"] = file.filename
    return result
