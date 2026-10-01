from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import io
import json
from datetime import datetime, timezone

from auth import authenticate_user, register_user
from db import add_job, create_project, get_job_by_id, list_jobs, list_projects
from src.video_pipeline import VideoPipeline


app = FastAPI(
    title="Video Clipper Automation API",
    description="API untuk memproses video panjang menjadi klip pendek dengan subtitle, hook, caption, tagar, thumbnail, dan export hasil.",
    version="1.0.0",
)

UPLOAD_DIR = Path("uploads")
WORKSPACE_DIR = Path("workspace")


class UploadedMemory(io.BytesIO):
    def __init__(self, data: bytes, filename: str):
        super().__init__(data)
        self.name = filename


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "video-clipper-automation"}


@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    try:
        user = register_user(username, password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": user}


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    return {"user": user}


@app.get("/projects")
async def get_projects(username: str, password: str):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    return JSONResponse(content=list_projects(user["id"]))


@app.post("/projects")
async def create_project_route(name: str = Form(...), username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    project_id = create_project(user["id"], name)
    return {"id": project_id, "name": name, "user_id": user["id"]}


@app.post("/process")
async def process_video(
    file: UploadFile = File(...),
    username: str = Form(...),
    password: str = Form(...),
    project_id: int | None = Form(None),
    max_clips: int = Form(3),
    clip_duration: int = Form(30),
    target_platform: str = Form("TikTok"),
):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")

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

    add_job(
        user_id=user["id"],
        project_id=project_id,
        job_id=result.get("job_id"),
        filename=file.filename,
        platform=result.get("platform"),
        clip_count=len(result.get("clips", [])),
        source_duration=result.get("source_duration"),
        workspace=result.get("workspace"),
    )

    return JSONResponse(content=result)


@app.get("/jobs")
async def list_user_jobs(username: str, password: str, project_id: int | None = None):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    return JSONResponse(content=list_jobs(user["id"], project_id))


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, username: str, password: str):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    row = get_job_by_id(user["id"], job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    workspace = Path(row["workspace"])
    metadata_path = workspace / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Metadata job tidak ditemukan")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return JSONResponse(content=metadata)


@app.get("/jobs/{job_id}/download")
async def download_job(job_id: str, username: str, password: str):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")
    row = get_job_by_id(user["id"], job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    job_dir = Path(row["workspace"])
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
