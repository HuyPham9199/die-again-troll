"""Animated portal — the level goal.

Drawn procedurally: vertical archway frame with a pulsing inner gradient.
"""
from __future__ import annotations

import math

import pygame

import config


class Portal:
    def __init__(self, rect: pygame.Rect):
        # The hitbox stays a 1-tile rect (kept by LevelData). For display we
        # draw a portal that extends roughly 1 tile above the hitbox center.
        self.rect = rect
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, camera) -> None:
        sr = camera.apply_rect(self.rect)
        # Portal visual extends 1.5x the tile height upward.
        portal_h = int(self.rect.height * 1.8)
        portal_w = int(self.rect.width * 1.1)
        cx = sr.centerx
        bottom = sr.bottom
        top = bottom - portal_h
        left = cx - portal_w // 2
        right = cx + portal_w // 2

        pulse = (math.sin(self.t * 4.0) + 1.0) * 0.5     # 0..1
        glow = int(80 + 80 * pulse)

        # Inner gradient — a series of vertical bands, brightest at the
        # centre. Drawn first so the frame sits on top.
        for i in range(6, 0, -1):
            inset_w = portal_w - i * 4
            inset_h = portal_h - i * 4
            if inset_w <= 0 or inset_h <= 0:
                continue
            shade = int(40 + (60 - i * 6) + pulse * 40)
            color = (shade, shade + 30, max(0, shade - 20))
            band_rect = pygame.Rect(
                cx - inset_w // 2,
                bottom - inset_h,
                inset_w, inset_h,
            )
            pygame.draw.rect(surface, color, band_rect, border_radius=8)

        # Core hot stripe.
        core_w = max(4, portal_w // 3)
        core_rect = pygame.Rect(cx - core_w // 2, top + 6, core_w, portal_h - 12)
        core_color = (255, 220, 80 + glow // 4)
        pygame.draw.rect(surface, core_color, core_rect, border_radius=6)

        # Outer frame (archway): two vertical pillars + a half-ellipse top.
        pillar_w = 4
        frame_color = (255, 230, 120)
        pygame.draw.rect(surface, frame_color,
                         (left, top + portal_w // 2,
                          pillar_w, portal_h - portal_w // 2))
        pygame.draw.rect(surface, frame_color,
                         (right - pillar_w, top + portal_w // 2,
                          pillar_w, portal_h - portal_w // 2))
        arch_rect = pygame.Rect(left, top, portal_w, portal_w)
        pygame.draw.arc(surface, frame_color, arch_rect, 0, math.pi, pillar_w)

        # Floating sparkles — three deterministic dots that orbit on a sine.
        for i in range(3):
            phase = self.t * 2.2 + i * 2.094
            sx = cx + int(math.cos(phase) * (portal_w // 3))
            sy = bottom - 8 - int((math.sin(phase * 0.7) + 1) * (portal_h // 3))
            pygame.draw.circle(surface, (255, 255, 200), (sx, sy), 2)
