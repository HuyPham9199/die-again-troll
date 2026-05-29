"""Local save manager — GDD §5.1, §5.2.

Saves to `save.dat` as base64-encoded JSON. Base64 is not security, just a
"don't tempt the casual user to edit it" obfuscation, exactly as the GDD
specifies. Cloud sync (Supabase/Firebase HTTP PATCH) is handled separately
in `systems/auth_db.py` (TODO — phase 2).
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any

import config


DEFAULT_SETTINGS: dict[str, Any] = {
    "master_volume": 80,
    "music_volume": 60,
    "sfx_volume": 80,
    "show_fps": True,
    "show_mobile_controls": False,
    # "windowed" → 960x540 window. "fullscreen" → native resolution with
    # pygame's SCALED flag so all game logic still runs in 960x540 space.
    "display_mode": "windowed",
}

DEFAULT_DATA: dict[str, Any] = {
    "user_id": None,
    "username": None,
    "email": None,
    # Device-remembered username — persists across sign-out so the login
    # form can pre-fill it next time. Cleared only by explicit user action.
    "last_username": None,
    "max_normal_level": 1,
    "max_nightmare_level": 0,
    "total_deaths": 0,
    "settings": dict(DEFAULT_SETTINGS),
}


def _path() -> str:
    # Tests can override via DIEAGAIN_SAVE_PATH so a smoke run doesn't
    # clobber the real player's save.dat. Production launches see the
    # env var unset and fall back to the default cwd path.
    override = os.environ.get("DIEAGAIN_SAVE_PATH")
    if override:
        return override
    return os.path.join(os.getcwd(), config.SAVE_FILE)


def load() -> dict[str, Any]:
    p = _path()
    if not os.path.exists(p):
        return dict(DEFAULT_DATA)
    try:
        with open(p, "rb") as f:
            raw = f.read()
        decoded = base64.b64decode(raw).decode("utf-8")
        data = json.loads(decoded)
        # merge with defaults so an older save missing keys still works
        merged = dict(DEFAULT_DATA)
        merged["settings"] = dict(DEFAULT_SETTINGS)
        merged.update(data)
        # also merge settings sub-dict
        if isinstance(data.get("settings"), dict):
            s = dict(DEFAULT_SETTINGS)
            s.update(data["settings"])
            merged["settings"] = s
        else:
            merged["settings"] = dict(DEFAULT_SETTINGS)
        return merged
    except (OSError, ValueError, json.JSONDecodeError):
        # Corrupt file — fall back to defaults rather than crash. The cloud
        # sync (when online) will overwrite from the server copy.
        return dict(DEFAULT_DATA)


def save(data: dict[str, Any]) -> None:
    payload = json.dumps(data).encode("utf-8")
    encoded = base64.b64encode(payload)
    with open(_path(), "wb") as f:
        f.write(encoded)


def record_death(data: dict[str, Any]) -> None:
    data["total_deaths"] = data.get("total_deaths", 0) + 1


def record_level_complete(data: dict[str, Any], level_id: int,
                          mode: str = "normal") -> None:
    """Bump max_{mode}_level. Does nothing if we've already beaten this level."""
    key = "max_normal_level" if mode == "normal" else "max_nightmare_level"
    default = 1 if mode == "normal" else 0
    if level_id >= data.get(key, default):
        data[key] = level_id + 1


def nightmare_unlocked_count(data: dict[str, Any]) -> int:
    """GDD §5.3: floor(max_normal_level / 5)."""
    import math
    # max_normal_level is 1-based "next-to-clear"; the number of levels the
    # player has actually beaten is (max_normal_level - 1).
    cleared = max(0, data.get("max_normal_level", 1) - 1)
    return math.floor(cleared / 5)


def get_settings(data: dict[str, Any]) -> dict[str, Any]:
    if "settings" not in data or not isinstance(data["settings"], dict):
        data["settings"] = dict(DEFAULT_SETTINGS)
    return data["settings"]
