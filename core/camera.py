"""Camera with smooth follow, math-based screen shake, and frustum culling.

GDD §6.2 — "Trauma System" : offset = trauma^2 * random(-1, 1) per axis,
trauma decays linearly each frame and is added to (not set) on damage events.
"""
from __future__ import annotations

import math
import random

import pygame

import config


class Camera:
    def __init__(self, view_w: int, view_h: int):
        self.view_w = view_w
        self.view_h = view_h
        self.x = 0.0
        self.y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.trauma = 0.0
        self.world_bounds: pygame.Rect | None = None  # optional clamp
        # Shake offset for the *current frame*. Computed once in update() so
        # every entity drawn this frame uses the same offset and the world
        # stays coherent. Reading random.uniform() during draw() was causing
        # per-entity desync (player shaking one way, tiles another).
        self._shake_ox: float = 0.0
        self._shake_oy: float = 0.0

    # --- Targeting ---------------------------------------------------------
    def set_target(self, world_x: float, world_y: float, snap: bool = False) -> None:
        self.target_x = world_x - self.view_w / 2
        self.target_y = world_y - self.view_h / 2
        if snap:
            self.x = self.target_x
            self.y = self.target_y

    def add_trauma(self, amount: float) -> None:
        # Clamp at 1.0 — beyond that the squared term gets silly.
        self.trauma = min(1.0, self.trauma + amount)

    # --- Update ------------------------------------------------------------
    def update(self, dt: float) -> None:
        # Exponential smoothing (frame-rate independent).
        k = 1.0 - math.exp(-config.CAMERA_LERP * dt)
        self.x += (self.target_x - self.x) * k
        self.y += (self.target_y - self.y) * k

        if self.world_bounds is not None:
            self.x = max(self.world_bounds.left,
                         min(self.x, self.world_bounds.right - self.view_w))
            self.y = max(self.world_bounds.top,
                         min(self.y, self.world_bounds.bottom - self.view_h))

        if self.trauma > 0:
            self.trauma = max(0.0, self.trauma - config.TRAUMA_DECAY * dt)

        # Resample shake offset *once* per frame.
        if self.trauma > 0:
            t2 = self.trauma * self.trauma
            self._shake_ox = t2 * random.uniform(-1.0, 1.0) * config.TRAUMA_MAX_OFFSET
            self._shake_oy = t2 * random.uniform(-1.0, 1.0) * config.TRAUMA_MAX_OFFSET
        else:
            self._shake_ox = 0.0
            self._shake_oy = 0.0

    # --- Transform ---------------------------------------------------------
    def world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
        return (world_x - self.x + self._shake_ox,
                world_y - self.y + self._shake_oy)

    def apply_rect(self, rect: pygame.Rect) -> pygame.Rect:
        # Rounds once at the end; keeps coords coherent across the frame.
        return rect.move(
            round(-self.x + self._shake_ox),
            round(-self.y + self._shake_oy),
        )

    # --- Frustum culling (GDD §6.2) ---------------------------------------
    def visible_tile_range(self, grid_size: int, cols: int, rows: int) -> tuple[int, int, int, int]:
        """Return (col_start, col_end, row_start, row_end) inclusive-exclusive."""
        c0 = max(0, int(self.x // grid_size) - 1)
        r0 = max(0, int(self.y // grid_size) - 1)
        c1 = min(cols, int((self.x + self.view_w) // grid_size) + 2)
        r1 = min(rows, int((self.y + self.view_h) // grid_size) + 2)
        return c0, c1, r0, r1
