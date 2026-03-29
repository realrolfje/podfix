from __future__ import annotations

import hashlib
import re


def sanitize_filename(value: str, fallback: str = "episode") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("._-")
    return cleaned or fallback


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()
