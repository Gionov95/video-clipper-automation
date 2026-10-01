from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


@dataclass
class ClipResult:
    index: int
    title: str
    hook: str
    caption: str
    tags: List[str]
    subtitle: str
    duration: int
    path: str | None = None


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
        self.max_clips = max_clips
        self.clip_duration = clip_duration
        self.target_platform = target_platform

    def process(self, uploaded_file) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:8]
        upload_path = self.upload_dir / f"{job_id}_{uploaded_file.name}"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        with open(upload_path, "wb") as f:
            shutil.copyfileobj(uploaded_file, f)

        job_dir = self.workspace_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        clip_specs = self._build_clip_specs()
        clips: List[Dict[str, Any]] = []

        for idx, spec in enumerate(clip_specs):
            clip_file = self._create_mock_clip(upload_path, job_dir, idx)
            subtitles = self._build_subtitle(spec, idx)
            hook = self._build_hook(spec)
            caption = self._build_caption(spec)
            tags = self._build_tags(spec)

            clip = {
                "index": idx,
                "title": spec["title"],
                "hook": hook,
                "caption": caption,
                "tags": tags,
                "subtitle": subtitles,
                "duration": spec["duration"],
                "path": str(clip_file),
            }
            clips.append(clip)

        metadata_path = job_dir / "metadata.json"
        metadata = {
            "job_id": job_id,
            "input_file": upload_path.name,
            "platform": self.target_platform,
            "clip_duration": self.clip_duration,
            "workspace": str(job_dir),
            "clips": clips,
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return metadata

    def _build_clip_specs(self) -> List[Dict[str, Any]]:
        return [
            {
                "title": f"Highlight {idx + 1}",
                "duration": self.clip_duration,
                "topic": "momen utama",
                "angle": "insight menarik",
            }
            for idx in range(self.max_clips)
        ]

    def _create_mock_clip(self, source_path: Path, target_dir: Path, idx: int) -> Path:
        output = target_dir / f"clip_{idx + 1}.mp4"

        with open(output, "wb") as f:
            f.write(b"")

        return output

    def _build_hook(self, spec: Dict[str, Any]) -> str:
        return f"Ini momen paling penting yang harus Anda lihat: {spec['angle']}"

    def _build_caption(self, spec: Dict[str, Any]) -> str:
        text = (
            f"{spec['title']} | {spec['topic']}\n"
            f"Bukan cuma konten, tapi cara paling efektif untuk menarik perhatian audiens.\n"
            f"#creator #contentstrategy #digitalmarketing #videoediting #viral"
        )
        return text

    def _build_tags(self, spec: Dict[str, Any]) -> List[str]:
        return [
            self.target_platform.lower(),
            "contentstrategy",
            "videoediting",
            "creator",
            "viral",
            "hook",
        ]

    def _build_subtitle(self, spec: Dict[str, Any], idx: int) -> str:
        return (
            f"{idx + 1}\n"
            f"00:00:00,000 --> 00:00:{str(self.clip_duration).zfill(2)},000\n"
            f"Halo, ini adalah bagian penting dari video ini.\n"
            f"Kita fokus pada {spec['angle']} supaya audiens tertarik sejak detik pertama.\n"
        )


__all__ = ["VideoPipeline"]
