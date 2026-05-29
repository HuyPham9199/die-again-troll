"""Player sprite loader.

Reads `assets/sprites/player.png` once, slices it into a fixed grid of
character cells, and caches a small dict of named frames (idle, walk_a,
walk_b, jump) that `Player.draw` consumes.

If the sheet is missing or fails to load, `get_player_sprites()` returns
None — the player falls back to the procedural skeleton render so the
game still works without art assets.

Sheet layout (default):
    columns × rows = 6 × 4
    Each row is one character variant. The PLAYER_ROW constant picks one.

Per-row frame columns (0-indexed):
    0: standing / idle
    1: standing alt
    2: both arms up                (jump pose)
    3: right arm raised            (walk frame A)
    4: right arm forward           (walk frame B)
    5: body turned right, pointing (unused for now; available for "victory")
"""
from __future__ import annotations

import os
from typing import Optional

import pygame


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHEET_PATH = os.path.join(_PROJECT_ROOT, "assets", "sprites", "player.png")

# Grid dimensions of the sheet. If you replace the art, update these.
SHEET_COLS = 6
SHEET_ROWS = 4

# Which row of the sheet to use as the player character (0-indexed).
# Row 0 = blonde + suit, 1 = brown + blue shirt, 2 = blonde + blue shirt, 3 = women.
PLAYER_ROW = 1

# Display height in pixels. The player collision rect is 36 tall; we draw
# the sprite ~44 px so feet/head poke a tiny bit beyond the hitbox, which
# reads better than a sprite cramped exactly into the hitbox.
DISPLAY_H = 44

# If the source PNG was exported with a solid white background instead of
# transparency, treat (255, 255, 255) as the transparent colour.
WHITE_KEY: tuple[int, int, int] = (255, 255, 255)


_cache: Optional[dict[str, pygame.Surface]] = None


def _scale_to_height(surf: pygame.Surface, target_h: int) -> pygame.Surface:
    """Nearest-neighbour scale that preserves pixel-art crispness."""
    ratio = target_h / surf.get_height()
    new_w = max(1, int(round(surf.get_width() * ratio)))
    return pygame.transform.scale(surf, (new_w, target_h))


def _trim_white(surf: pygame.Surface) -> pygame.Surface:
    """Crop fully-white padding around the character so the sprite hugs
    its bounding box. Lets DISPLAY_H scale the *character*, not the cell."""
    w, h = surf.get_size()
    mask = pygame.mask.from_surface(surf)
    bounds = mask.get_bounding_rects()
    if not bounds:
        return surf
    box = bounds[0]
    for r in bounds[1:]:
        box = box.union(r)
    box = box.inflate(2, 2).clip(surf.get_rect())
    return surf.subsurface(box).copy()


def _load_sheet() -> Optional[pygame.Surface]:
    if not os.path.isfile(_SHEET_PATH):
        return None
    try:
        sheet = pygame.image.load(_SHEET_PATH)
    except pygame.error:
        return None
    # If we can convert with alpha (display exists), do so.
    try:
        sheet = sheet.convert_alpha()
    except pygame.error:
        pass
    # If the asset uses a solid white backdrop, key it to transparent.
    sheet.set_colorkey(WHITE_KEY)
    return sheet


def get_player_sprites() -> Optional[dict[str, pygame.Surface]]:
    """Return the cached frame dict, building it on first call."""
    global _cache
    if _cache is not None:
        return _cache

    sheet = _load_sheet()
    if sheet is None:
        return None

    cell_w = sheet.get_width() // SHEET_COLS
    cell_h = sheet.get_height() // SHEET_ROWS

    def cell(col: int, row: int) -> pygame.Surface:
        rect = pygame.Rect(col * cell_w, row * cell_h, cell_w, cell_h)
        # subsurface shares pixels; copy so set_colorkey on the trimmed
        # surface doesn't propagate back to the parent.
        return sheet.subsurface(rect).copy()

    row = min(PLAYER_ROW, SHEET_ROWS - 1)

    raw = {
        "idle":   cell(0, row),
        "walk_a": cell(3, row),
        "walk_b": cell(4, row),
        "jump":   cell(2, row),
        "point":  cell(5, row),    # available for victory / level-clear pose
    }

    out: dict[str, pygame.Surface] = {}
    for name, surf in raw.items():
        # Re-key after subsurface copy.
        surf.set_colorkey(WHITE_KEY)
        trimmed = _trim_white(surf)
        out[name] = _scale_to_height(trimmed, DISPLAY_H)

    _cache = out
    return _cache


def clear_cache() -> None:
    """Reset the cache — useful if you swap the asset at runtime."""
    global _cache
    _cache = None
