from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = Path("workspace/app.db")


def ensure_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER,
            job_id TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            platform TEXT NOT NULL,
            clip_count INTEGER NOT NULL,
            source_duration REAL,
            workspace TEXT NOT NULL,
            generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
        """
    )
    conn.commit()
    return conn


def create_user(username: str, password_hash: str) -> int:
    conn = ensure_db()
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    conn.commit()
    user_id = int(cursor.lastrowid)
    conn.close()
    return user_id


def get_user_by_username(username: str) -> Dict[str, Any] | None:
    conn = ensure_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(user_id: int, name: str) -> int:
    conn = ensure_db()
    cursor = conn.execute(
        "INSERT INTO projects (user_id, name) VALUES (?, ?)",
        (user_id, name),
    )
    conn.commit()
    project_id = int(cursor.lastrowid)
    conn.close()
    return project_id


def list_projects(user_id: int) -> List[Dict[str, Any]]:
    conn = ensure_db()
    rows = conn.execute(
        "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_job(user_id: int, project_id: int | None, job_id: str, filename: str, platform: str, clip_count: int, source_duration: float | None, workspace: str) -> int:
    conn = ensure_db()
    cursor = conn.execute(
        """
        INSERT INTO jobs (user_id, project_id, job_id, filename, platform, clip_count, source_duration, workspace)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, project_id, job_id, filename, platform, clip_count, source_duration, workspace),
    )
    conn.commit()
    job_row_id = int(cursor.lastrowid)
    conn.close()
    return job_row_id


def list_jobs(user_id: int, project_id: int | None = None) -> List[Dict[str, Any]]:
    conn = ensure_db()
    if project_id is not None:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? AND project_id = ? ORDER BY generated_at DESC",
            (user_id, project_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY generated_at DESC",
            (user_id,),
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_job_by_id(user_id: int, job_id: str) -> Dict[str, Any] | None:
    conn = ensure_db()
    row = conn.execute(
        "SELECT * FROM jobs WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


if __name__ == "__main__":
    ensure_db()
    print("Database ready")
