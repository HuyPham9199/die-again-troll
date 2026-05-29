"""Audio wrapper around pygame.mixer.

Drop-in friendly: every public function silently no-ops if mixer init failed
or the requested file isn't on disk. That way the game keeps running even
with zero audio assets shipped, and the user can add files gradually.

File layout
-----------
    assets/audio/sfx/   <name>.{ogg,wav,mp3}   — one-shot effects
    assets/audio/music/ <name>.{ogg,mp3,wav}   — looping background music

Volumes are tied to the settings dict via `apply_settings(settings)`:
    master_volume   0..100   global multiplier
    music_volume    0..100   applied on top of master for the BGM channel
    sfx_volume      0..100   applied on top of master for one-shot effects
"""
from __future__ import annotations

import os
from typing import Optional

import pygame


# Resolve directories relative to the project root, not the cwd. This means
# running `python main.py` from anywhere still finds the bundled assets.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SFX_DIR = os.path.join(_PROJECT_ROOT, "assets", "audio", "sfx")
_MUSIC_DIR = os.path.join(_PROJECT_ROOT, "assets", "audio", "music")

# `None` means "we already searched and there's no such file". Avoids
# re-checking the disk every time a missing sound is "played".
_sfx_cache: dict[str, Optional[pygame.mixer.Sound]] = {}
_missing_logged: set[str] = set()

_initialized = False
_current_music: Optional[str] = None

# Internal volume state (0.0..1.0). Re-applied to the mixer on every change.
_master = 0.8
_music = 0.6
_sfx = 0.8


# ----------------------------------------------------------------- lifecycle
def init() -> None:
    """Initialise pygame.mixer. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return
    try:
        # 44.1 kHz signed 16-bit stereo, smallish buffer for snappy SFX.
        pygame.mixer.pre_init(frequency=44100, size=-16,
                              channels=2, buffer=512)
        pygame.mixer.init()
        # Reserve enough channels so a death blast + click + portal don't
        # interrupt each other.
        pygame.mixer.set_num_channels(16)
        _initialized = True
    except pygame.error:
        # Headless CI / no sound card / SDL audio backend missing — fine,
        # we just stay silent.
        _initialized = False


def is_available() -> bool:
    return _initialized


# ------------------------------------------------------------------- volumes
def apply_settings(settings: dict) -> None:
    """Read music/sfx volume out of the settings dict and apply.

    Master is intentionally not exposed in the UI right now (only Music
    and SFX sliders), so we fix it at 100 — the per-channel sliders are
    the only knobs the player turns.
    """
    set_volumes(
        100,
        int(settings.get("music_volume", 60)),
        int(settings.get("sfx_volume", 80)),
    )


def set_volumes(master: int, music: int, sfx: int) -> None:
    global _master, _music, _sfx
    _master = max(0.0, min(1.0, master / 100.0))
    _music = max(0.0, min(1.0, music / 100.0))
    _sfx = max(0.0, min(1.0, sfx / 100.0))
    if _initialized:
        pygame.mixer.music.set_volume(_master * _music)


# ----------------------------------------------------------------- sound fx
def _find_path(directory: str, name: str,
               exts: tuple[str, ...] = (".ogg", ".wav", ".mp3")) -> Optional[str]:
    for ext in exts:
        path = os.path.join(directory, name + ext)
        if os.path.isfile(path):
            return path
    return None


def _get_sfx(name: str) -> Optional[pygame.mixer.Sound]:
    if not _initialized:
        return None
    if name in _sfx_cache:
        return _sfx_cache[name]
    path = _find_path(_SFX_DIR, name)
    if not path:
        _sfx_cache[name] = None
        return None
    try:
        snd = pygame.mixer.Sound(path)
        _sfx_cache[name] = snd
        return snd
    except pygame.error:
        _sfx_cache[name] = None
        return None


def play_sfx(name: str, volume: float = 1.0) -> None:
    """Play a one-shot effect. Missing files are silently skipped."""
    snd = _get_sfx(name)
    if snd is None:
        return
    snd.set_volume(max(0.0, min(1.0, volume)) * _master * _sfx)
    try:
        snd.play()
    except pygame.error:
        pass


# ------------------------------------------------------------------- music
def play_music(name: str, loop: bool = True, fade_ms: int = 400) -> None:
    """Switch background music. No-op if `name` is already playing."""
    global _current_music
    if not _initialized:
        return
    if _current_music == name and pygame.mixer.music.get_busy():
        return
    path = _find_path(_MUSIC_DIR, name, exts=(".ogg", ".mp3", ".wav"))
    if not path:
        # Stop whatever was playing so a missing track doesn't leave the
        # previous BGM looping over the new screen.
        pygame.mixer.music.stop()
        _current_music = None
        return
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(_master * _music)
        pygame.mixer.music.play(-1 if loop else 0, fade_ms=fade_ms)
        _current_music = name
    except pygame.error:
        _current_music = None


def stop_music(fade_ms: int = 200) -> None:
    global _current_music
    if not _initialized:
        return
    if fade_ms > 0:
        pygame.mixer.music.fadeout(fade_ms)
    else:
        pygame.mixer.music.stop()
    _current_music = None
