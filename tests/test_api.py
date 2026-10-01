from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from api import app


def test_health_check():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_and_login():
    client = TestClient(app)
    username = "testuser_demo"
    password = "demo123"

    register_response = client.post(
        "/register",
        data={"username": username, "password": password},
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/login",
        data={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    assert login_response.json()["user"]["username"] == username


def test_process_requires_auth():
    client = TestClient(app)
    response = client.post(
        "/process",
        data={"username": "bad_user", "password": "bad_pass", "max_clips": "3", "clip_duration": "30", "target_platform": "TikTok"},
    )
    assert response.status_code == 422
