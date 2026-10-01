from pathlib import Path

import streamlit as st

from src.video_pipeline import VideoPipeline


st.set_page_config(page_title="Video Clipper Automation", layout="wide")

st.title("🎬 Video Clipper Automation")
st.caption("Upload video panjang, otomatis potong jadi klip pendek, transkripsi, subtitle, caption, tagar, serta hook siap publish.")

with st.sidebar:
    st.header("Pengaturan otomatis")
    max_clips = st.slider("Jumlah klip", min_value=1, max_value=10, value=3)
    clip_duration = st.slider("Durasi target per klip (detik)", min_value=10, max_value=120, value=30)
    target_platform = st.selectbox("Platform target", ["TikTok", "Reels", "Shorts", "YouTube", "LinkedIn"])

uploaded_file = st.file_uploader("Upload video panjang", type=["mp4", "mov", "mkv", "avi", "webm"])

if uploaded_file is not None:
    with st.spinner("Memproses video, transkripsi audio, dan menyiapkan subtitle serta metadata..."):
        pipeline = VideoPipeline(
            upload_dir=Path("uploads"),
            workspace_dir=Path("workspace"),
            max_clips=max_clips,
            clip_duration=clip_duration,
            target_platform=target_platform,
        )
        result = pipeline.process(uploaded_file)

    st.success(f"Selesai: {len(result['clips'])} klip dibuat untuk {result['platform']}.")

    if result.get("transcript"):
        with st.expander("Lihat transkrip keseluruhan"):
            st.code(result["transcript"], language="text")

    for clip in result["clips"]:
        st.markdown(f"---\n### {clip['title']}\n")
        col1, col2 = st.columns([1.6, 1])

        with col1:
            st.video(clip["path"])
        with col2:
            st.image(clip["thumbnail"], caption="Thumbnail preview")
            st.write(f"Durasi: {clip['duration']} detik")
            st.write(f"Hook: {clip['hook']}")
            st.write(f"Tagar: {', '.join(clip['tags'])}")
            st.write("Caption:")
            st.code(clip["caption"], language="text")
            st.write("Transkrip klip:")
            st.code(clip["transcript"] or "Transkrip tidak tersedia", language="text")
            st.write("Subtitle:")
            st.code(clip["subtitle"], language="text")

    with st.expander("Lihat metadata lengkap"):
        st.json({k: v for k, v in result.items() if k != "clips"})

    with st.expander("Lihat semua file hasil"):
        for file in sorted(Path(result["workspace"]).rglob("*")):
            if file.is_file():
                st.write(file.relative_to(Path(result["workspace"])))
else:
    st.info("Silakan upload video panjang untuk memulai proses clipping otomatis.")

st.markdown("---")
st.caption("Versi MVP dengan transkripsi audio, subtitle, thumbnail, hook, caption, dan tagar siap publish.")
