from __future__ import annotations

import json
import math
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from moviepy.editor import VideoFileClip

try:
    import whisper
except ImportError:  # pragma: no cover
    whisper = None


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
        self.whisper_model = None

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

        transcript = self._transcribe_from_video(upload_path, job_dir)
        total_duration = 0.0

        with VideoFileClip(str(upload_path)) as video:
            total_duration = float(video.duration)
            segments = self._generate_segments(total_duration, transcript)
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
                    logger=None,
                    progress_bar=False,
                )
                segment.save_frame(str(thumb_path), t=max(0.0, min(segment.duration / 2, 3.0)))
                segment.close()

                clip_transcript = self._clip_transcript_for_range(transcript, start, end)
                subtitle_text = self._build_subtitle_text(clip_transcript, idx, start, end)
                subtitle_path.write_text(subtitle_text, encoding="utf-8")

                clip = {
                    "index": idx,
                    "title": f"Highlight {idx}",
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(max(0.01, end - start), 2),
                    "hook": self._build_hook_from_text(clip_transcript, idx),
                    "caption": self._build_caption_from_text(clip_transcript, idx),
                    "tags": self._build_tags_from_text(clip_transcript),
                    "subtitle": subtitle_text,
                    "transcript": clip_transcript,
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
            "transcript": transcript.get("text", ""),
            "clips": clips,
        }

        metadata_path = job_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return metadata

    def _generate_segments(self, total_duration: float, transcript: Dict[str, Any]) -> List[Tuple[float, float]]:
        if total_duration <= 0:
            return [(0.0, 1.0)]

        transcript_segments = transcript.get("segments", [])
        if transcript_segments:
            spans: List[Tuple[float, float]] = []
            for seg in transcript_segments:
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", start))
                if end > start:
                    spans.append((start, end))
            if spans:
                # build clips around transcript hotspots with a light buffer
                windows: List[Tuple[float, float]] = []
                for idx in range(min(self.max_clips, len(spans))):
                    s, e = spans[idx]
                    start = max(0.0, s - 1.0)
                    end = min(total_duration, e + 1.5)
                    windows.append((round(start, 2), round(end, 2)))
                if windows:
                    return windows[: self.max_clips]

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

    def _transcribe_from_video(self, video_path: Path, job_dir: Path) -> Dict[str, Any]:
        audio_path = job_dir / "audio.wav"
        try:
            with VideoFileClip(str(video_path)) as video:
                if video.audio is None:
                    return {"segments": [], "text": ""}
                video.audio.write_audiofile(str(audio_path), codec="pcm_s16le", fps=16000, logger=None)
        except Exception:
            return {"segments": [], "text": ""}

        if whisper is None:
            return {"segments": [], "text": ""}

        try:
            if self.whisper_model is None:
                self.whisper_model = whisper.load_model("base")
            result = self.whisper_model.transcribe(str(audio_path), fp16=False, language="id")
            segments = result.get("segments", [])
            normalized = []
            for segment in segments:
                text = (segment.get("text") or "").strip()
                if not text:
                    continue
                normalized.append(
                    {
                        "start": float(segment.get("start", 0.0)),
                        "end": float(segment.get("end", segment.get("start", 0.0))),
                        "text": text,
                    }
                )
            return {"segments": normalized, "text": (result.get("text") or "").strip()}
        except Exception:
            return {"segments": [], "text": ""}

    def _clip_transcript_for_range(self, transcript: Dict[str, Any], start: float, end: float) -> str:
        parts: List[str] = []
        for segment in transcript.get("segments", []):
            seg_start = float(segment.get("start", 0.0))
            seg_end = float(segment.get("end", seg_start))
            if seg_end > start and seg_start < end:
                text = (segment.get("text") or "").strip()
                if text:
                    parts.append(text)
        return " ".join(parts).strip()

    def _safe_filename(self, name: str) -> str:
        cleaned = Path(name).name
        return "".join(ch if ch.isalnum() or ch in (".", "_", "-") else "_" for ch in cleaned)

    def _build_hook_from_text(self, transcript: str, idx: int) -> str:
        text = self._clean_text(transcript)
        if not text:
            platform_phrase = {
                "TikTok": "Lihat insight paling berharga dari video ini sebelum audiens berpindah!",
                "Reels": "Momen paling kuat dari video ini hadir dalam 1 klip singkat.",
                "Shorts": "Ini titik penting yang bikin orang berhenti menonton.",
                "YouTube": "Bagian paling berharga dari video ini bisa jadi penarik perhatian utama.",
                "LinkedIn": "Insight penting yang relevan untuk audiens profesional Anda.",
            }.get(self.target_platform, "Momen paling berharga dari video ini wajib Anda lihat.")
            return f"Clip {idx}: {platform_phrase}"
        preview = text[:150].strip()
        if preview.endswith((".", "!", "?")):
            return preview
        return preview + "..."

    def _build_caption_from_text(self, transcript: str, idx: int) -> str:
        text = self._clean_text(transcript)
        if not text:
            text = "Konten ini dibuat untuk menjelaskan inti pesan dengan cara yang cepat, jelas, dan mudah diingat."
        summary = text[:220].strip()
        if len(summary) < len(text):
            summary += "..."
        return (
            f"Clip {idx} | {self.target_platform}\n"
            f"{summary}\n"
            "Simpan dan bagikan ke audiens yang ingin cepat paham inti pesan.\n"
            "#contentcreator #shortvideo #hook #videoediting #branding"
        )

    def _build_tags_from_text(self, transcript: str) -> List[str]:
        cleaned = self._clean_text(transcript)
        tokens = re.findall(r"[a-zA-Z0-9]+", cleaned.lower())
        stop_words = {
            "yang", "dan", "untuk", "dari", "ini", "itu", "adalah", "dengan", "akan", "saat",
            "pada", "mereka", "kami", "kita", "lebih", "juga", "bisa", "jadi", "setiap",
            "tapi", "karena", "serta", "oleh", "seperti", "bila", "apalagi", "tentang"
        }
        selected = []
        for token in tokens:
            if len(token) > 3 and token not in stop_words and token not in selected:
                selected.append(token)
                if len(selected) >= 6:
                    break
        default_tags = [self.target_platform.lower(), "shortvideo", "contentstrategy", "creator", "hook", "videoediting"]
        for tag in default_tags:
            if tag not in selected:
                selected.append(tag)
        return selected[:8]

    def _build_subtitle_text(self, transcript: str, idx: int, start: float, end: float) -> str:
        start_label = self._format_timestamp(start)
        end_label = self._format_timestamp(end)
        text = self._clean_text(transcript) or "Poin penting dari video ini."
        return (
            f"{idx}\n"
            f"{start_label} --> {end_label}\n"
            f"{text[:180]}\n\n"
        )

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _format_timestamp(self, seconds: float) -> str:
        total_ms = int(round(seconds * 1000))
        hours, remainder = divmod(total_ms, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


__all__ = ["VideoPipeline"]


"""Quick usage example:
from pathlib import Path
from src.video_pipeline import VideoPipeline
pipeline = VideoPipeline(upload_dir=Path('uploads'), workspace_dir=Path('workspace'))
"""
