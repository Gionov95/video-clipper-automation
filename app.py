from pathlib import Path
import json
from typing import List, Dict, Any

import streamlit as st

from src.video_pipeline import VideoPipeline


st.set_page_config(page_title="Video Clipper Automation", layout="wide")

st.title("🎬 Video Clipper Automation")
st.caption("Potong video panjang jadi bagian-bagian siap publikasi dengan subtitle, hook, caption, dan tagar otomatis.")

with st.sidebar:
    st.header("Pengaturan")
    max_clips = st.slider("Jumlah clip per video", min_value=1, max_value=10, value=5)
    max_duration = st.slider("Durasi clip ideal (detik)", min_value=10, max_value=120, value=30)
    target_platform = st.selectbox("Platform target", ["TikTok", "Reels", "Shorts", "YouTube", "LinkedIn"])

uploaded_file = st.file_uploader("Upload video panjang", type=["mp4", "mov", "mkv", "avi", "webm"])

if uploaded_file is not None:
    with st.spinner("Memproses video dan menyiapkan hasil..."):
        pipeline = VideoPipeline(
            upload_dir=Path("uploads"),
            workspace_dir=Path("workspace"),
            max_clips=max_clips,
            clip_duration=max_duration,
            target_platform=target_platform,
        )
        result = pipeline.process(uploaded_file)

    st.success(f"Video berhasil diproses dengan {len(result['clips'])} bagian utama.")

    tabs = st.tabs([f"Clip {idx + 1}" for idx in range(len(result['clips']))])

    for idx, clip in enumerate(result["clips"]):
        with tabs[idx]:
            st.subheader(f"{clip['title']}")
            st.write(f"Durasi: {clip['duration']} detik")
            st.write(f"Hook: {clip['hook']}")
            st.write(f"Caption: {clip['caption']}")
            st.write(f"Tagar: {', '.join(clip['tags'])}")

            st.code(clip["subtitle"], language="text")

            if clip.get("path"):
                st.video(str(clip["path"]))

    with st.expander("Lihat metadata lengkap"):
        st.json({k: v for k, v in result.items() if k != "clips"})

    with st.expander("Lihat semua hasil file"):
        for file in sorted(Path(result["workspace"]).rglob("*")):
            if file.is_file():
                st.write(file.relative_to(Path(result["workspace"])))
else:
    st.info("Silakan upload video panjang untuk memulai otomatisasi clipping.")

st.markdown("---")
st.caption("MVP: sistem otomatisasi konten video untuk strategi repurposing konten.")
