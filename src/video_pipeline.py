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
        self.hot_keywords = [
            "penting", "cara", "langkah", "hasil", "kesalahan", "solusi",
            "berhasil", "tips", "trik", "strategi", "poin", "highlight",
            "rekomendasi", "mengubah", "mengapa", "contoh", "insight",
            "bukti", "sering", "harus", "wajib", "jangan", "anda",
        ]

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
        hotspot_analysis: List[Dict[str, Any]] = []

        with VideoFileClip(str(upload_path)) as video:
            total_duration = float(video.duration)
            segments, hotspot_analysis = self._detect_hotspots(total_duration, transcript, video)
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

                score = self._score_segment(clip_transcript, start, end, video)
                clip = {
                    "index": idx,
                    "title": f"Highlight {idx}",
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(max(0.01, end - start), 2),
                    "moment_score": round(score, 2),
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
            "hotspot_analysis": hotspot_analysis,
            "clips": clips,
        }

        metadata_path = job_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return metadata

    def _detect_hotspots(
        self, total_duration: float, transcript: Dict[str, Any], video: VideoFileClip
    ) -> Tuple[List[Tuple[float, float]], List[Dict[str, Any]]]:
        if total_duration <= 0:
            return [(0.0, 1.0)], []

        raw_segments = transcript.get("segments", [])
        if not raw_segments:
            ideal_segment = self.clip_duration
            target_count = max(1, min(self.max_clips, int(math.ceil(total_duration / ideal_segment))))
            segment_length = total_duration / target_count
            fallback: List[Tuple[float, float]] = []
            for idx in range(target_count):
                start = idx * segment_length
                end = min(total_duration, (idx + 1) * segment_length)
                if idx == target_count - 1 and end - start < 2:
                    end = total_duration
                fallback.append((round(start, 2), round(end, 2)))
            return fallback, []

        scored_segments: List[Dict[str, Any]] = []
        for seg in raw_segments:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start))
            text = (seg.get("text") or "").strip()
            if not text or end <= start:
                continue
            score = self._score_segment(text, start, end, video)
            scored_segments.append({
                "start": start,
                "end": end,
                "text": text,
                "score": score,
            })

        if not scored_segments:
            return self._fallback_segments(total_duration), []

        scored_segments = sorted(scored_segments, key=lambda item: item["score"], reverse=True)
        selected: List[Dict[str, Any]] = []
        for item in scored_segments:
            if not selected or all(abs(item["start"] - chosen["start"]) > max(3.0, self.clip_duration * 0.75) for chosen in selected):
                selected.append(item)
            if len(selected) >= self.max_clips:
                break

        if not selected:
            selected = scored_segments[: self.max_clips]

        selected = sorted(selected, key=lambda item: item["start"])
        windows: List[Tuple[float, float]] = []
        analysis: List[Dict[str, Any]] = []
        for item in selected:
            start = max(0.0, item["start"] - 1.0)
            end = min(total_duration, item["end"] + 1.5)
            if end - start > self.clip_duration * 2.5:
                start = max(0.0, item["start"] - 0.5)
                end = min(total_duration, item["end"] + 0.5)
            windows.append((round(start, 2), round(end, 2)))
            analysis.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "score": round(item["score"], 2),
                "text": item["text"][:160],
            })

        return windows, analysis

    def _score_segment(self, transcript_text: str, start: float, end: float, video: VideoFileClip) -> float:
        text = self._clean_text(transcript_text)
        score = 0.0
        if text:
            score += max(0.0, len(text) / 25.0)
            words = re.findall(r"[a-zA-Z0-9]+", text.lower())
            keyword_hits = sum(1 for word in words if word in self.hot_keywords)
            score += keyword_hits * 3.5
            if any(token in text.lower() for token in ["!", "wow", "inilah", "berhasil", "cara", "tips", "trik", "mengapa"]):
                score += 4.0
            if any(ch in text for ch in ["!", "?"]):
                score += 2.0

        duration = max(0.1, end - start)
        score += duration * 2.0

        try:
            if video.audio is not None:
                subclip = video.audio.subclip(start, end)
                sound = subclip.to_soundarray(fps=22050, quantize=True)
                if sound.size > 0:
                    signal = sound.astype("float32")
                    rms = float((signal ** 2).mean()) ** 0.5
                    score += rms * 50.0
        except Exception:
            pass
        return score

    def _fallback_segments(self, total_duration: float) -> List[Tuple[float, float]]:
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






















































































































































































