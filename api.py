from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import io
import json
from datetime import datetime, timezone

from src.video_pipeline import VideoPipeline


app = FastAPI(
    title="Video Clipper Automation API",
    description="API untuk memproses video panjang menjadi klip pendek dengan subtitle, hook, caption, tagar, thumbnail, dan export hasil.",
    version="1.0.0",
)

UPLOAD_DIR = Path("uploads")
WORKSPACE_DIR = Path("workspace")
HISTORY_PATH = WORKSPACE_DIR / "history.json"


class UploadedMemory(io.BytesIO):
    def __init__(self, data: bytes, filename: str):
        super().__init__(data)
        self.name = filename


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def save_history(entry: dict):
    history = load_history()
    history.insert(0, entry)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "video-clipper-automation"}


@app.post("/process")
async def process_video(
    file: UploadFile = File(...),
    max_clips: int = Form(3),
    clip_duration: int = Form(30),
    target_platform: str = Form("TikTok"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nama file tidak valid")

    contents = await file.read()
    uploaded = UploadedMemory(contents, file.filename)

    pipeline = VideoPipeline(
        upload_dir=UPLOAD_DIR,
        workspace_dir=WORKSPACE_DIR,
        max_clips=max_clips,
        clip_duration=clip_duration,
        target_platform=target_platform,
    )
    result = pipeline.process(uploaded)

    entry = {
        "job_id": result.get("job_id"),
        "generated_at": result.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "platform": result.get("platform"),
        "filename": file.filename,
        "clip_count": len(result.get("clips", [])),
        "workspace": result.get("workspace"),
        "source_duration": result.get("source_duration"),
    }
    save_history(entry)
    return JSONResponse(content=result)


@app.get("/jobs")
async def list_jobs():
    return JSONResponse(content=load_history())


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    workspace = WORKSPACE_DIR / job_id
    metadata_path = workspace / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return JSONResponse(content=metadata)


@app.get("/jobs/{job_id}/download")
async def download_job(job_id: str):
    job_dir = WORKSPACE_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    zip_path = job_dir.parent / f"{job_id}_export.zip"
    if not zip_path.exists():
        import zipfile
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(job_dir.rglob("*")):
                if file.is_file():
                    zf.write(file, arcname=file.relative_to(job_dir.parent))
    return FileResponse(zip_path, media_type="application/zip", filename=f"{job_id}_export.zip")
