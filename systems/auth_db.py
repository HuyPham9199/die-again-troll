"""SQLite-backed auth + cloud-progress store.

GDD §5 mandates Supabase or Firebase via REST. Both require credentials and a
running internet connection. To keep the game usable offline (and during
development), we ship a SQLite implementation that exposes the same public
surface a remote backend would expose:

    register(username, password, email)        -> dict | None
    login(username, password)                  -> dict | None
    logout(save_data)                          -> None
    sync_progress(user_id, save_data)          -> None     (push)
    pull_progress(save_data)                   -> None     (pull)

To swap for Supabase/Firebase later, replace the bodies of these five
functions; the rest of the codebase doesn't need to change.

Passwords are salted (16 random bytes) and SHA-256 hashed. That's not
bcrypt-grade but enough for a local single-player save store.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional


def _db_path() -> str:
    # Tests can override via DIEAGAIN_DB_PATH so the smoke run doesn't
    # destroy the real player's accounts. Production launches use AppData
    # (same folder as save.dat), migrating from cwd on first run so
    # upgrading from v1.0.02 keeps every account intact.
    override = os.environ.get("DIEAGAIN_DB_PATH")
    if override:
        return override
    from systems.paths import migrate_legacy_file
    return migrate_legacy_file("game.db")


# ---------------------------------------------------------------- internals
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                max_normal_level INTEGER NOT NULL DEFAULT 1,
                max_nightmare_level INTEGER NOT NULL DEFAULT 0,
                total_deaths INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- validation
USERNAME_MIN = 3
USERNAME_MAX = 24
PASSWORD_MIN = 4


def validate_credentials(username: str, password: str,
                         email: Optional[str] = None) -> Optional[str]:
    """Return an error message, or None if everything is OK."""
    if not username or len(username) < USERNAME_MIN:
        return f"Username must be at least {USERNAME_MIN} characters."
    if len(username) > USERNAME_MAX:
        return f"Username max {USERNAME_MAX} characters."
    if any(c.isspace() for c in username):
        return "Username can't contain spaces."
    if not password or len(password) < PASSWORD_MIN:
        return f"Password must be at least {PASSWORD_MIN} characters."
    if email is not None and email and "@" not in email:
        return "Email looks invalid."
    return None


# ---------------------------------------------------------------- API
def register(username: str, password: str,
             email: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    """Create a new user. Returns (user_dict, error_message).

    On success error_message is None; on failure user_dict is None.
    """
    err = validate_credentials(username, password, email)
    if err:
        return None, err

    _ensure_schema()
    salt = secrets.token_hex(16)
    ph = _hash(password, salt)
    user_id = secrets.token_hex(16)
    now = _now()

    try:
        with _connect() as conn:
            conn.execute("""
                INSERT INTO users (user_id, username, email, password_hash, salt,
                                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, email or None, ph, salt, now, now))
    except sqlite3.IntegrityError:
        return None, "Username already taken."

    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "max_normal_level": 1,
        "max_nightmare_level": 0,
        "total_deaths": 0,
    }, None


def login(username: str,
          password: str) -> tuple[Optional[dict], Optional[str]]:
    if not username or not password:
        return None, "Username and password required."

    _ensure_schema()
    with _connect() as conn:
        row = conn.execute("""
            SELECT user_id, username, email, password_hash, salt,
                   max_normal_level, max_nightmare_level, total_deaths
            FROM users WHERE username = ?
        """, (username,)).fetchone()

    if not row:
        return None, "No user with that name."
    (user_id, uname, email, ph, salt,
     mnl, mhl, td) = row
    if _hash(password, salt) != ph:
        return None, "Wrong password."
    return {
        "user_id": user_id,
        "username": uname,
        "email": email,
        "max_normal_level": mnl,
        "max_nightmare_level": mhl,
        "total_deaths": td,
    }, None


def apply_login_to_save(save_data: dict[str, Any], user: dict) -> None:
    """Merge logged-in user fields into the local save_data in place.

    Pick the more-progressed value for each numeric field so logging in
    never *loses* progress (whether it lived locally or in the DB).
    Also stamps `last_username` so the next launch can pre-fill the form.
    """
    save_data["user_id"] = user["user_id"]
    save_data["username"] = user["username"]
    save_data["email"] = user.get("email")
    save_data["last_username"] = user["username"]
    save_data["max_normal_level"] = max(
        save_data.get("max_normal_level", 1), user.get("max_normal_level", 1)
    )
    save_data["max_nightmare_level"] = max(
        save_data.get("max_nightmare_level", 0), user.get("max_nightmare_level", 0)
    )
    save_data["total_deaths"] = max(
        save_data.get("total_deaths", 0), user.get("total_deaths", 0)
    )


def logout(save_data: dict[str, Any]) -> None:
    save_data["user_id"] = None
    save_data["username"] = None
    save_data["email"] = None
    # Local-only progress sticks around for the guest session.


def sync_progress(user_id: str, save_data: dict[str, Any]) -> None:
    """Push (upsert max) the local save_data values to the DB row."""
    if not user_id:
        return
    _ensure_schema()
    with _connect() as conn:
        conn.execute("""
            UPDATE users
               SET max_normal_level = MAX(max_normal_level, ?),
                   max_nightmare_level = MAX(max_nightmare_level, ?),
                   total_deaths = MAX(total_deaths, ?),
                   updated_at = ?
             WHERE user_id = ?
        """, (
            save_data.get("max_normal_level", 1),
            save_data.get("max_nightmare_level", 0),
            save_data.get("total_deaths", 0),
            _now(),
            user_id,
        ))


def pull_progress(save_data: dict[str, Any]) -> None:
    """Fetch latest progress from DB and merge into save_data.

    Called at boot when the local cache says a user is logged in.
    """
    user_id = save_data.get("user_id")
    if not user_id:
        return
    _ensure_schema()
    with _connect() as conn:
        row = conn.execute("""
            SELECT max_normal_level, max_nightmare_level, total_deaths
            FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
    if not row:
        return
    mnl, mhl, td = row
    save_data["max_normal_level"] = max(save_data.get("max_normal_level", 1), mnl)
    save_data["max_nightmare_level"] = max(save_data.get("max_nightmare_level", 0), mhl)
    save_data["total_deaths"] = max(save_data.get("total_deaths", 0), td)
