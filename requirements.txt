from __future__ import annotations

import hashlib
from typing import Any, Dict

from db import create_user, get_user_by_username


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(username: str, password: str) -> Dict[str, Any]:
    if not username or not password:
        raise ValueError("Username dan password wajib diisi")
    if get_user_by_username(username):
        raise ValueError("Username sudah dipakai")
    user_id = create_user(username, hash_password(password))
    return {"id": user_id, "username": username}


def authenticate_user(username: str, password: str) -> Dict[str, Any] | None:
    user = get_user_by_username(username)
    if not user:
        return None
    if user["password_hash"] != hash_password(password):
        return None
    return {"id": user["id"], "username": user["username"]}
