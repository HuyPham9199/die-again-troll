"""Persistent user-data directory + cross-version save migration.

v1.0.02 and earlier stored `save.dat` and `game.db` in the working
directory (i.e. next to the .exe). That broke when players downloaded
a new build to a different folder — their previous progress and
account were "lost" (still on disk, just not where the new .exe looked).

v1.0.03+ moves both files into a per-user AppData folder:

    Windows  C:\\Users\\<Name>\\AppData\\Roaming\\DieAgailTroll\\
    macOS    ~/Library/Application Support/DieAgailTroll/
    Linux    ~/.local/share/DieAgailTroll/

`user_data_dir()` creates the folder on first access and returns it.

`migrate_legacy_file(filename)` is called by save_mgr and auth_db. If the
target file already exists in AppData it does nothing — the player has
already been migrated. Otherwise it looks for the same filename in the
current working directory (legacy install) and copies it across.
"""
from __future__ import annotations

import os
import shutil
import sys


APP_NAME = "DieAgailTroll"


def user_data_dir() -> str:
    """Return the persistent data directory, creating it on first call."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = (os.environ.get("XDG_DATA_HOME")
                or os.path.join(os.path.expanduser("~"), ".local", "share"))
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def migrate_legacy_file(filename: str) -> str:
    """Resolve a save filename to its full AppData path, migrating from
    a legacy cwd location if needed.

    Returns the AppData path either way. If a copy attempt fails (disk
    full, permission denied) we still return the AppData path; the caller
    will treat it as a fresh save.
    """
    target = os.path.join(user_data_dir(), filename)
    if os.path.isfile(target):
        return target
    legacy = os.path.join(os.getcwd(), filename)
    if os.path.isfile(legacy):
        try:
            shutil.copy2(legacy, target)
        except OSError:
            pass
    return target
