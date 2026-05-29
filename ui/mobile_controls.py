"""On-screen touch controls for mobile / tablet builds.

Three round buttons: ← / → / Jump. Translates touch (which pygame surfaces
as MOUSEBUTTONDOWN with button=1) into virtual key state that PlayState
merges with the keyboard input vector.

Off by default. Toggle in Settings → DISPLAY → "Mobile controls".
"""
from __future__ import annotations

import pygame

import config


class MobileControls:
    BTN_SIZE = 76
    MARGIN_X = 28
    MARGIN_Y = 28
    GAP = 14

    def __init__(self):
        sw, sh = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        s = self.BTN_SIZE
        # Bottom-left: left / right pair.
        y = sh - s - self.MARGIN_Y
        self.left_rect = pygame.Rect(self.MARGIN_X, y, s, s)
        self.right_rect = pygame.Rect(
            self.MARGIN_X + s + self.GAP, y, s, s
        )
        # Bottom-right: jump.
        self.jump_rect = pygame.Rect(
            sw - s - self.MARGIN_X, y, s, s
        )

        self.left_held = False
        self.right_held = False
        # `jump_pressed` is one-shot — PlayState consumes it then resets.
        self._jump_pulse = False
        # Track which finger/click is on which button so dragging off
        # releases the button cleanly.
        self._left_finger = False
        self._right_finger = False
        self.visible = False

    # ----------------------------------------------------------- input
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True iff this event was consumed by a control."""
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.left_rect.collidepoint(event.pos):
                self.left_held = True
                self._left_finger = True
                return True
            if self.right_rect.collidepoint(event.pos):
                self.right_held = True
                self._right_finger = True
                return True
            if self.jump_rect.collidepoint(event.pos):
                self._jump_pulse = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # Release whichever direction was being held.
            if self._left_finger:
                self.left_held = False
                self._left_finger = False
            if self._right_finger:
                self.right_held = False
                self._right_finger = False
        return False

    def consume_jump(self) -> bool:
        if self._jump_pulse:
            self._jump_pulse = False
            return True
        return False

    # ----------------------------------------------------------- draw
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        self._draw_arrow(surface, self.left_rect, self.left_held, "left")
        self._draw_arrow(surface, self.right_rect, self.right_held, "right")
        self._draw_jump(surface, self.jump_rect)

    @staticmethod
    def _draw_arrow(surface: pygame.Surface, rect: pygame.Rect,
                    held: bool, direction: str) -> None:
        # Semi-transparent disc so the button doesn't obscure the world.
        disc = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill_alpha = 170 if held else 110
        border_color = (60, 220, 200) if held else (160, 180, 220)
        pygame.draw.circle(disc, (24, 28, 44, fill_alpha),
                           (rect.width // 2, rect.height // 2),
                           rect.width // 2)
        pygame.draw.circle(disc, border_color,
                           (rect.width // 2, rect.height // 2),
                           rect.width // 2 - 1, 2)
        surface.blit(disc, rect.topleft)

        # Arrow triangle.
        cx, cy = rect.center
        s = rect.width // 4
        if direction == "left":
            pts = [(cx + s // 2, cy - s),
                   (cx - s // 2, cy),
                   (cx + s // 2, cy + s)]
        else:
            pts = [(cx - s // 2, cy - s),
                   (cx + s // 2, cy),
                   (cx - s // 2, cy + s)]
        pygame.draw.polygon(surface, (240, 240, 250), pts)

    def _draw_jump(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        disc = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill_alpha = 170 if self._jump_pulse else 110
        border_color = (255, 220, 60) if self._jump_pulse else (255, 180, 80)
        pygame.draw.circle(disc, (40, 28, 24, fill_alpha),
                           (rect.width // 2, rect.height // 2),
                           rect.width // 2)
        pygame.draw.circle(disc, border_color,
                           (rect.width // 2, rect.height // 2),
                           rect.width // 2 - 1, 2)
        surface.blit(disc, rect.topleft)

        # Up-pointing chevron + small "JUMP" caption.
        cx, cy = rect.center
        pygame.draw.polygon(surface, (255, 230, 140), [
            (cx, cy - rect.width // 4),
            (cx - rect.width // 5, cy + 2),
            (cx + rect.width // 5, cy + 2),
        ])
