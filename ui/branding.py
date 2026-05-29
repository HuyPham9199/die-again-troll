"""Logo for "Die Again: Troll".

`make_logo(size)` returns a `pygame.Surface` of the requested size. If a
file `assets/logo.{png,jpg,jpeg,bmp}` exists it is loaded, scaled with
smoothscale and cached per size. Otherwise we fall back to a procedural
devil-mask drawing so the game still ships with a recognisable mark even
before a real asset is dropped in.
"""
from __future__ import annotations

import math
import os
from typing import Optional

import pygame

import config


_ASSET_CANDIDATES = ("logo.png", "logo.jpg", "logo.jpeg", "logo.bmp")
_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
)
# size -> Surface cache so we don't re-load + re-scale every frame.
_cache: dict[int, pygame.Surface] = {}
_loaded_path: Optional[str] = None


def _find_logo_file() -> Optional[str]:
    for name in _ASSET_CANDIDATES:
        path = os.path.join(_ASSETS_DIR, name)
        if os.path.isfile(path):
            return path
    return None


def clear_cache() -> None:
    """Drop cached surfaces — call this if the file on disk has changed."""
    _cache.clear()
    global _loaded_path
    _loaded_path = None


def make_logo(size: int) -> pygame.Surface:
    if size in _cache:
        return _cache[size]

    path = _find_logo_file()
    if path is not None:
        try:
            raw = pygame.image.load(path)
            # convert_alpha needs a display; guarded for headless tests.
            try:
                raw = raw.convert_alpha()
            except pygame.error:
                pass
            scaled = pygame.transform.smoothscale(raw, (size, size))
            _cache[size] = scaled
            global _loaded_path
            _loaded_path = path
            return scaled
        except (pygame.error, OSError):
            # Fall through to the procedural fallback if the file is broken.
            pass

    surf = _draw_procedural(size)
    _cache[size] = surf
    return surf


def _draw_procedural(size: int) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size / 2
    cy = size / 2

    # Rounded square backplate.
    pygame.draw.rect(s, (20, 16, 30, 255),
                     (0, 0, size, size), border_radius=max(2, size // 6))
    pygame.draw.rect(s, (60, 220, 200),
                     (1, 1, size - 2, size - 2), 1,
                     border_radius=max(2, size // 6))

    # Horns — neon yellow, jagged triangles on top corners of the face.
    face_r = size * 0.34
    horn_h = size * 0.22
    horn_w = size * 0.10

    for side in (-1, +1):
        base_x = cx + side * face_r * 0.78
        base_y = cy - face_r * 0.55
        tip_x = base_x + side * horn_w * 0.6
        tip_y = base_y - horn_h
        inner_x = base_x - side * horn_w * 0.35
        pygame.draw.polygon(s, (255, 220, 60), [
            (base_x, base_y),
            (tip_x, tip_y),
            (inner_x, base_y - horn_h * 0.18),
        ])
        pygame.draw.polygon(s, (180, 130, 0), [
            (base_x, base_y),
            (tip_x, tip_y),
            (inner_x, base_y - horn_h * 0.18),
        ], 1)

    # Face — neon pink with darker outline.
    pygame.draw.circle(s, config.COLOR_PLAYER, (cx, cy), face_r)
    pygame.draw.circle(s, (40, 10, 30), (cx, cy), face_r, max(1, size // 24))

    # Eyes — slanted to look smug. Yellow pupils inside a dark socket.
    eye_dx = face_r * 0.4
    eye_y = cy - face_r * 0.12
    eye_w = max(2, size // 8)
    eye_h = max(1, size // 16)
    for side in (-1, +1):
        ex = cx + side * eye_dx
        # Dark slot
        pygame.draw.ellipse(s, (10, 0, 6),
                            (ex - eye_w / 2, eye_y - eye_h / 2, eye_w, eye_h))
        # Pupil
        pup_r = max(1, size // 18)
        pygame.draw.circle(s, (255, 220, 60), (ex, eye_y), pup_r)
        pygame.draw.circle(s, (255, 90, 90), (ex, eye_y), max(1, pup_r // 2))

    # Smug grin — arc from lower-left of face to lower-right.
    grin_w = face_r * 1.15
    grin_h = face_r * 0.7
    grin_rect = pygame.Rect(cx - grin_w / 2, cy + face_r * 0.05,
                            grin_w, grin_h)
    pygame.draw.arc(s, (30, 0, 16), grin_rect, math.pi, 2 * math.pi,
                    max(2, size // 14))
    # Tooth fangs — two small triangles inside the grin.
    fang_y = cy + face_r * 0.18
    fang_size = max(1, size // 18)
    for side in (-1, +1):
        fx = cx + side * face_r * 0.18
        pygame.draw.polygon(s, (240, 240, 240), [
            (fx, fang_y),
            (fx + fang_size, fang_y),
            (fx + fang_size / 2, fang_y + fang_size * 1.3),
        ])

    return s
