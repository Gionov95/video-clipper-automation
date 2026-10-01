from pathlib import Path
import io
import json
import zipfile
from datetime import datetime

import streamlit as st

from src.video_pipeline import VideoPipeline


HISTORY_PATH = Path("workspace/history.json")


def load_history():
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def save_history(result: dict, original_name: str):
    history = load_history()
    entry = {
        "job_id": result.get("job_id"),
        "generated_at": result.get("generated_at") or datetime.utcnow().isoformat() + "Z",
        "platform": result.get("platform"),
        "filename": original_name,
        "clip_count": len(result.get("clips", [])),
        "workspace": result.get("workspace"),
        "source_duration": result.get("source_duration"),
    }
    history.insert(0, entry)
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def get_history_jobs():
    return load_history()


def export_job_zip(job_dir: str) -> bytes:
    directory = Path(job_dir)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                zf.write(file, arcname=file.relative_to(directory.parent))
    return buffer.getvalue()


st.set_page_config(page_title="Video Clipper Automation", layout="wide")

st.title("🎬 Video Clipper Automation")
st.caption("Upload video panjang, pilih momen terpenting, lalu hasilkan klip dengan hook, subtitle, caption, tagar, dan thumbnail siap publish.")

with st.sidebar:
    st.header("Pengaturan otomatis")
    max_clips = st.slider("Jumlah klip", min_value=1, max_value=10, value=3)
    clip_duration = st.slider("Durasi target per klip (detik)", min_value=10, max_value=120, value=30)
    target_platform = st.selectbox("Platform target", ["TikTok", "Reels", "Shorts", "YouTube", "LinkedIn"])

    history = get_history_jobs()
    if history:
        st.subheader("Riwayat proses")
        history_labels = [f"{item['generated_at']} | {item['filename']}" for item in history]
        selected_history = st.selectbox("Pilih history", options=history_labels, index=0)
        selected_entry = next((item for item in history if f"{item['generated_at']} | {item['filename']}" == selected_history), None)
        if selected_entry:
            st.write(f"Platform: {selected_entry.get('platform')}")
            st.write(f"Klip: {selected_entry.get('clip_count')}")
            st.write(f"Workspace: {selected_entry.get('workspace')}")
            if selected_entry.get("workspace"):
                zip_bytes = export_job_zip(selected_entry["workspace"])
                st.download_button(
                    label="Download zip hasil",
                    data=zip_bytes,
                    file_name=f"{selected_entry['job_id']}_export.zip",
                    mime="application/zip",
                )

uploaded_file = st.file_uploader("Upload video panjang", type=["mp4", "mov", "mkv", "avi", "webm"])

if uploaded_file is not None:
    with st.spinner("Menganalisis momen paling kuat, membuat klip, subtitle, thumbnail, dan variasi copywriting..."):
        pipeline = VideoPipeline(
            upload_dir=Path("uploads"),
            workspace_dir=Path("workspace"),
            max_clips=max_clips,
            clip_duration=clip_duration,
            target_platform=target_platform,
        )
        result = pipeline.process(uploaded_file)
        save_history(result, uploaded_file.name)

    st.success(f"Selesai: {len(result['clips'])} klip paling menarik berhasil dibuat untuk {result['platform']}.")

    zip_bytes = export_job_zip(result["workspace"])
    st.download_button(
        label="Download seluruh hasil zip",
        data=zip_bytes,
        file_name=f"{result['job_id']}_export.zip",
        mime="application/zip",
    )

    if result.get("transcript"):
        with st.expander("Lihat transkrip keseluruhan"):
            st.code(result["transcript"], language="text")

    if result.get("hotspot_analysis"):
        with st.expander("Lihat analisis momen penting"):
            st.json(result["hotspot_analysis"])

    for clip in result["clips"]:
        st.markdown(f"---\n### {clip['title']}\n")
        col1, col2 = st.columns([1.6, 1])

        with col1:
            st.video(clip["path"])
        with col2:
            st.image(clip["thumbnail"], caption="Thumbnail utama")
            st.write(f"Durasi: {clip['duration']} detik")
            st.write(f"Skor momen: {clip['moment_score']}")
            st.write("Hook options:")
            for option in clip["hook_variants"]:
                st.code(option, language="text")
            st.write("Caption options:")
            for option in clip["caption_variants"]:
                st.code(option, language="text")
            st.write(f"Tagar: {', '.join(clip['tags'])}")

        st.write("Thumbnail variants:")
        thumb_cols = st.columns(len(clip["thumbnail_variants"]))
        for i, thumb in enumerate(clip["thumbnail_variants"]):
            with thumb_cols[i]:
                st.image(thumb, caption=f"Variant {i + 1}")

    with st.expander("Lihat metadata lengkap"):
        st.json({k: v for k, v in result.items() if k != "clips"})

    with st.expander("Lihat semua file hasil"):
        for file in sorted(Path(result["workspace"]).rglob("*")):
            if file.is_file():
                st.write(file.relative_to(Path(result["workspace"])))
else:
    st.info("Silakan upload video panjang untuk memulai proses clipping otomatis.")

st.markdown("---")
st.caption("Versi tahap 5: history proses dan export hasil batch untuk workflow yang lebih rapi dan siap dipakai.")
