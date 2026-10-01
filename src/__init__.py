from __future__ import annotations

import json
import math
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from moviepy.editor import VideoFileClip


class VideoPipeline:
    def __init__(
        self,
        upload_dir: Path,
        workspace_dir: Path,
        max_clips: int = 5,
        clip_duration: int = 30,
        target_platform: str = "TikTok",
    ):
        self.upload_dir = Path(upload_dir)
        self.workspace_dir = Path(workspace_dir)
        self.max_clips = max(1, int(max_clips))
        self.clip_duration = max(5, int(clip_duration))
        self.target_platform = target_platform

    def process(self, uploaded_file) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:8]
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self._safe_filename(uploaded_file.name)
        upload_path = self.upload_dir / f"{job_id}_{safe_name}"
        with open(upload_path, "wb") as file:
            shutil.copyfileobj(uploaded_file, file)

        job_dir = self.workspace_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        with VideoFileClip(str(upload_path)) as video:
            total_duration = float(video.duration)
            segments = self._generate_segments(total_duration)
            clips: List[Dict[str, Any]] = []

            for idx, (start, end) in enumerate(segments, start=1):
                clip_path = job_dir / f"clip_{idx}.mp4"
                thumb_path = job_dir / f"clip_{idx}_thumb.jpg"
                subtitle_path = job_dir / f"clip_{idx}.srt"

                segment = video.subclip(start, end)
                segment.write_videofile(
                    str(clip_path),
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile=str(job_dir / f"temp_audio_{idx}.m4a"),
                    remove_temp=True,
                )
                segment.save_frame(str(thumb_path), t=max(0.0, min(segment.duration / 2, 2.0)))
                segment.close()

                subtitle_text = self._build_subtitle(start, end, idx, total_duration)
                subtitle_path.write_text(subtitle_text, encoding="utf-8")

                clip = {
                    "index": idx,
                    "title": f"Highlight {idx}",
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(max(0.01, end - start), 2),
                    "hook": self._build_hook(idx),
                    "caption": self._build_caption(idx),
                    "tags": self._build_tags(),
                    "subtitle": subtitle_text,
                    "path": str(clip_path),
                    "thumbnail": str(thumb_path),
                    "subtitle_path": str(subtitle_path),
                }
                clips.append(clip)

        metadata = {
            "job_id": job_id,
            "input_file": upload_path.name,
            "platform": self.target_platform,
            "source_duration": round(total_duration, 2),
            "clip_duration": self.clip_duration,
            "workspace": str(job_dir),
            "clips": clips,
        }

        metadata_path = job_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return metadata

    def _generate_segments(self, total_duration: float) -> List[Tuple[float, float]]:
        if total_duration <= 0:
            return [(0.0, 1.0)]

        ideal_segment = self.clip_duration
        target_count = max(1, min(self.max_clips, int(math.ceil(total_duration / ideal_segment))))
        segment_length = total_duration / target_count
        segments: List[Tuple[float, float]] = []

        for idx in range(target_count):
            start = idx * segment_length
            end = min(total_duration, (idx + 1) * segment_length)
            if idx == target_count - 1 and end - start < 2:
                end = total_duration
            segments.append((round(start, 2), round(end, 2)))

        return segments

    def _safe_filename(self, name: str) -> str:
        cleaned = Path(name).name
        return "".join(ch if ch.isalnum() or ch in (".", "_", "-") else "_" for ch in cleaned)

    def _build_hook(self, idx: int) -> str:
        platform_phrase = {
            "TikTok": "Lihat momen paling menarik ini sebelum audiens berpindah!",
            "Reels": "Ini titik paling kuat dari video Anda untuk narik perhatian cepat.",
            "Shorts": "Satu momen penting yang siap bikin orang berhenti dan menonton.",
            "YouTube": "Bagian paling berharga dari video ini bisa jadi pembuka yang kuat.",
            "LinkedIn": "Insight penting yang cocok untuk audiens profesional Anda.",
        }.get(self.target_platform, "Momen paling berharga dari video ini yang wajib Anda lihat.")
        return f"Clip {idx}: {platform_phrase}"

    def _build_caption(self, idx: int) -> str:
        return (
            f"Clip {idx} | {self.target_platform}\n"
            "Konten yang dibuat untuk audiens cepat, fokus, dan ingin langsung paham inti pesan.\n"
            "Simpan ini untuk inspirasi strategi konten berikutnya.\n"
            "#contentcreator #videoediting #marketing #shortvideo #growth"
        )

    def _build_tags(self) -> List[str]:
        return [
            self.target_platform.lower(),
            "shortvideo",
            "contentstrategy",
            "hook",
            "creator",
            "videoediting",
            "marketing",
        ]

    def _build_subtitle(self, start: float, end: float, idx: int, total_duration: float) -> str:
        start_text = self._format_time(start)
        end_text = self._format_time(end)
        return (
            f"{idx}\n"
            f"{start_text} --> {end_text}\n"
            f"Bagian penting dari video ini.\n"
            f"Highlight #{idx} siap dipakai untuk konten {self.target_platform}.\n\n"
        )

    def _format_time(self, seconds: float) -> str:
        total_ms = int(round(seconds * 1000))
        hours, remainder = divmod(total_ms, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


__all__ = ["VideoPipeline"]


"""If you need a quick CLI runner, use: python -m src.video_pipeline"""
