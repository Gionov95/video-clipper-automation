from __future__ import annotations

import io
import json
import math
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from moviepy.editor import VideoFileClip
from PIL import Image, ImageDraw, ImageFont, ImageOps

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
                segment.close()

                clip_transcript = self._clip_transcript_for_range(transcript, start, end)
                subtitle_text = self._build_subtitle_text(clip_transcript, idx, start, end)
                subtitle_path.write_text(subtitle_text, encoding="utf-8")

                score = self._score_segment(clip_transcript, start, end, video)
                thumbnail_variants = self._generate_thumbnail_variants(video, start, end, job_dir, idx)
                hook_variants = self._build_hook_variants(clip_transcript, idx)
                caption_variants = self._build_caption_variants(clip_transcript, idx)

                clip = {
                    "index": idx,
                    "title": f"Highlight {idx}",
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(max(0.01, end - start), 2),
                    "moment_score": round(score, 2),
                    "hook": hook_variants[0],
                    "hook_variants": hook_variants,
                    "caption": caption_variants[0],
                    "caption_variants": caption_variants,
                    "tags": self._build_tags_from_text(clip_transcript),
                    "subtitle": subtitle_text,
                    "transcript": clip_transcript,
                    "path": str(clip_path),
                    "thumbnail": thumbnail_variants[0],
                    "thumbnail_variants": thumbnail_variants,
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
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
            return self._fallback_segments(total_duration), []

        scored_segments: List[Dict[str, Any]] = []
        for seg in raw_segments:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start))
            text = (seg.get("text") or "").strip()
            if not text or end <= start:
                continue
            score = self._score_segment(text, start, end, video)
            scored_segments.append({"start": start, "end": end, "text": text, "score": score})

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

    def _build_hook_variants(self, transcript: str, idx: int) -> List[str]:
        text = self._clean_text(transcript)
        base = text[:110].strip() if text else "Ini momen paling berharga dari video ini."
        variants = [
            f"{base[:90]}..." if len(base) > 90 else base,
            f"Poin paling penting di clip {idx}: {base[:80]}",
            f"Jangan lewatkan ini — {base[:75]}",
        ]
        platform_variants = {
            "TikTok": [
                f"Ini yang bikin orang berhenti scroll: {base[:80]}",
                f"Momen paling mengejutkan dari video ini: {base[:80]}",
                f"Kalau Anda skip, Anda akan kehilangan inti videonya.",
            ],
            "Reels": [
                f"Momen utama dari video ini: {base[:80]}",
                f"Satu insight penting yang harus Anda lihat.",
                f"Bagian paling berharga dari video ini.",
            ],
            "Shorts": [
                f"1 momen penting yang bikin orang menonton sampai akhir.",
                f"Poin utama dalam 15 detik: {base[:60]}",
                f"Inilah alasan kenapa videonya worth to watch.",
            ],
            "YouTube": [
                f"Bagian paling berharga dari video ini: {base[:80]}",
                f"Ini insight yang paling banyak ditunggu audiens.",
                f"Poin utama yang paling berpengaruh di video ini.",
            ],
            "LinkedIn": [
                f"Insight penting yang relevan untuk audiens profesional: {base[:80]}",
                f"Kenapa ini penting untuk strategi Anda?",
                f"Bagian paling bernilai dari pembahasan ini.",
            ],
        }
        platform_list = platform_variants.get(self.target_platform, variants)
        merged = [*platform_list, *variants]
        deduped: List[str] = []
        for item in merged:
            text_item = self._clean_text(item)
            if text_item and text_item not in deduped:
                deduped.append(text_item)
        return deduped[:3]

    def _build_caption_variants(self, transcript: str, idx: int) -> List[str]:
        text = self._clean_text(transcript)
        summary = text[:240].strip() if text else "Konten ini dibuat untuk menjelaskan inti pesan dengan cara yang cepat, jelas, dan mudah diingat."
        if len(summary) < len(text):
            summary += "..."

        captions = [
            f"Clip {idx} | {self.target_platform}\n{summary}\nSimpan dan bagikan untuk yang mau paham inti videonya.\n#contentcreator #shortvideo #hook #videoediting #marketing",
            f"Clip {idx} | {self.target_platform}\n{summary}\nPoin penting dalam 1 klip singkat.\n#creator #contentstrategy #viral #reels #growth",
            f"Clip {idx} | {self.target_platform}\n{summary}\nJangan lewatkan insight penting yang ada di sini.\n#shortvideo #branding #creator #marketing #hook",
        ]
        return captions

    def _generate_thumbnail_variants(self, video: VideoFileClip, start: float, end: float, output_dir: Path, idx: int) -> List[str]:
        frame_time = max(0.0, min((start + end) / 2, video.duration - 0.1))
        frame = video.get_frame(frame_time)
        image = Image.fromarray(frame)
        image = ImageOps.fit(image, (1280, 720), method=Image.Resampling.LANCZOS)

        palette = [
            ("curiosity", (18, 28, 52), (244, 133, 66)),
            ("value", (12, 52, 43), (82, 211, 165)),
            ("urgency", (55, 15, 25), (255, 86, 108)),
        ]

        output_paths: List[str] = []
        for name, bg, accent in palette:
            thumb = self._build_thumbnail_image(image.copy(), name, bg, accent, idx)
            path = output_dir / f"thumbnail_{idx}_{name}.jpg"
            thumb.save(path, quality=90)
            output_paths.append(str(path))
        return output_paths

    def _build_thumbnail_image(self, base_image: Image.Image, style_name: str, bg_color: tuple[int, int, int], accent_color: tuple[int, int, int], idx: int) -> Image.Image:
        canvas = Image.new("RGB", base_image.size, bg_color)
        canvas.paste(base_image, (0, 0))

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rounded_rectangle((60, 60, canvas.width - 60, canvas.height - 60), radius=28, fill=(0, 0, 0, 140))
        draw.rounded_rectangle((80, 80, 260, 150), radius=20, fill=accent_color + (220,))
        draw.text((100, 95), f"CLIP {idx}", fill=(255, 255, 255), font=self._get_font(36))
        draw.text((90, 500), self._thumbnail_title(style_name), fill=(255, 255, 255), font=self._get_font(58), anchor="la")
        draw.text((90, 590), "STOP SCROLLING", fill=(255, 255, 255), font=self._get_font(32), anchor="la")
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        return canvas

    def _thumbnail_title(self, style_name: str) -> str:
        mapping = {
            "curiosity": "WHY THIS MATTERS",
            "value": "MOST VALUABLE PART",
            "urgency": "DON'T MISS THIS",
        }
        return mapping.get(style_name, "KEY MOMENT")

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
        except Exception:
            return ImageFont.load_default()

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
        return re.sub(r"\s+", " ", text).strip()

    def _format_timestamp(self, seconds: float) -> str:
        total_ms = int(round(seconds * 1000))
        hours, remainder = divmod(total_ms, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        secs, millis = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


__all__ = ["VideoPipeline"]






























































































































































































































































































