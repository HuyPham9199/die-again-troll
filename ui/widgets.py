"""Reusable UI widgets — Button, Panel, Slider, Lock icon.

Drawing aesthetic: classical/clean — bordered panels, soft accent lines, no
emojis. Colors come from config.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import pygame

import config


# --- Background ambience -----------------------------------------------------

_gradient_cache: dict[tuple[int, int], pygame.Surface] = {}


def _build_gradient(w: int, h: int) -> pygame.Surface:
    """Precomputed vertical gradient backdrop.

    Top: muted indigo (28, 22, 48) — bottom: near-black (4, 4, 12).
    Built once per resolution and cached; blitting the result each frame
    is essentially free.
    """
    surf = pygame.Surface((w, h))
    for y in range(h):
        ratio = y / max(1, h - 1)
        r = int(28 - 24 * ratio)
        g = int(22 - 18 * ratio)
        b = int(48 - 36 * ratio)
        pygame.draw.line(surf, (r, g, b), (0, y), (w, y))
    return surf


def draw_starfield(surface: pygame.Surface, t: float) -> None:
    """Gradient backdrop + three parallax star layers.

    Stars are placed deterministically from a pseudo-random hash on their
    index, so no per-frame allocation — just a few hundred set_at calls
    that the SDL2 backend handles in microseconds.
    """
    w, h = surface.get_size()
    key = (w, h)
    if key not in _gradient_cache:
        _gradient_cache[key] = _build_gradient(w, h)
    surface.blit(_gradient_cache[key], (0, 0))

    # Three parallax layers — distant dim slow stars in the back, bright
    # fast accents up front. Counts tuned for density without noise.
    LAYERS = (
        (90, 6, (40, 60), 1),    # far     — count, speed, brightness, size
        (50, 14, (90, 150), 1),  # middle
        (28, 26, (160, 230), 2), # near
    )
    for layer_i, (count, speed, br_range, size) in enumerate(LAYERS):
        br_lo, br_span = br_range[0], br_range[1] - br_range[0]
        for i in range(count):
            seed = ((i + layer_i * 1000) * 9301 + 49297) % 233280
            x_base = seed % w
            y = (seed * 7 + layer_i * 31) % h
            x = int((x_base - t * speed) % w)
            bright = br_lo + (seed % br_span)
            c = (bright, bright, min(255, bright + 30))
            if size == 1:
                surface.set_at((x, y), c)
            else:
                # 2-px star with a 1-px highlight for a soft twinkle.
                pygame.draw.rect(surface, c, (x, y, 2, 2))
                surface.set_at((x, y), (min(255, bright + 60),
                                       min(255, bright + 60),
                                       min(255, bright + 80)))


def draw_panel(surface: pygame.Surface, rect: pygame.Rect,
               title: Optional[str] = None,
               font: Optional[pygame.font.Font] = None) -> None:
    """Bordered panel with optional title bar — the classical frame look."""
    # Interior fill (slightly lighter than page background).
    pygame.draw.rect(surface, (18, 18, 30), rect, border_radius=6)
    # Outer accent border.
    pygame.draw.rect(surface, (70, 70, 110), rect, 1, border_radius=6)
    # Inner highlight border (2px inset, gives a bevel feel).
    inset = rect.inflate(-4, -4)
    pygame.draw.rect(surface, (40, 40, 64), inset, 1, border_radius=4)
    if title and font:
        label = font.render(title, True, config.COLOR_TEXT)
        surface.blit(label, (rect.x + 16, rect.y + 8))
        underline_y = rect.y + 8 + label.get_height() + 2
        pygame.draw.line(surface, (60, 220, 200),
                         (rect.x + 16, underline_y),
                         (rect.x + 16 + label.get_width(), underline_y), 1)


def draw_card(surface: pygame.Surface, rect: pygame.Rect,
              glow: bool = True) -> None:
    """Modern card: dark fill, soft outer glow, single thin accent border."""
    # Outer glow — concentric semi-transparent rects falling off in alpha.
    if glow:
        glow_surf = pygame.Surface(
            (rect.width + 32, rect.height + 32), pygame.SRCALPHA
        )
        for i in range(6, 0, -1):
            alpha = 8 + i * 6
            grect = pygame.Rect(16 - i * 2, 16 - i * 2,
                                rect.width + i * 4, rect.height + i * 4)
            pygame.draw.rect(glow_surf, (60, 220, 200, alpha),
                             grect, border_radius=18 + i)
        surface.blit(glow_surf, (rect.x - 16, rect.y - 16))

    # Card fill — slightly bluish dark.
    pygame.draw.rect(surface, (24, 26, 42), rect, border_radius=14)
    # Single thin accent border at full opacity.
    pygame.draw.rect(surface, (70, 90, 130), rect, 1, border_radius=14)
    # Inner top highlight (1px line just below the top edge — fakes a bevel).
    pygame.draw.line(
        surface, (50, 60, 90),
        (rect.left + 14, rect.top + 1),
        (rect.right - 14, rect.top + 1),
    )


# --- Button ------------------------------------------------------------------

@dataclass
class Button:
    rect: pygame.Rect
    text: str
    on_click: Callable[[], None] | None = None
    enabled: bool = True
    accent: tuple[int, int, int] = (60, 220, 200)
    _hover: bool = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if this event triggered the button."""
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                # Click SFX — local import avoids hard-coupling widgets to
                # the audio module (e.g., for unit tests that import widgets
                # without initialising audio).
                try:
                    from systems import audio
                    audio.play_sfx("click")
                except Exception:
                    pass
                if self.on_click:
                    self.on_click()
                return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             selected: bool = False) -> None:
        if not self.enabled:
            bg = (22, 22, 32)
            border = (60, 60, 80)
            text_color = config.COLOR_TEXT_DIM
        elif selected or self._hover:
            bg = (32, 36, 52)
            border = self.accent
            text_color = config.COLOR_TEXT
        else:
            bg = (22, 24, 38)
            border = (80, 84, 110)
            text_color = config.COLOR_TEXT

        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=4)
        # Soft inner stroke.
        pygame.draw.rect(surface, (10, 10, 18),
                         self.rect.inflate(-4, -4), 1, border_radius=3)

        label = font.render(self.text, True, text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))


# --- TextField ---------------------------------------------------------------

@dataclass
class TextField:
    """Single-line text input.

    Click to focus; printable Unicode chars and Backspace edit the text;
    Enter fires `on_submit`. Tab moves focus elsewhere — callers handle Tab.
    """
    rect: pygame.Rect
    label: str = ""
    text: str = ""
    max_len: int = 32
    password: bool = False
    on_submit: Callable[[], None] | None = None
    focused: bool = False
    _blink_t: float = 0.0

    def set_focus(self, v: bool) -> None:
        self.focused = v
        self._blink_t = 0.0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.set_focus(self.rect.collidepoint(event.pos))
            return self.focused
        if self.focused and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            if event.key == pygame.K_RETURN:
                if self.on_submit:
                    self.on_submit()
                return True
            if event.key == pygame.K_TAB:
                # Caller wires the Tab handoff. We just signal it.
                return False
            ch = event.unicode
            if ch and ch.isprintable() and len(self.text) < self.max_len:
                self.text += ch
                return True
        return False

    def update(self, dt: float) -> None:
        self._blink_t = (self._blink_t + dt) % 1.0

    def draw(self, surface: pygame.Surface,
             font_label: pygame.font.Font,
             font_text: pygame.font.Font) -> None:
        # Label sits 10 px above the input — clear of the border so it never
        # collides with the field outline.
        if self.label:
            lbl = font_label.render(self.label, True, (170, 180, 210))
            surface.blit(lbl, (self.rect.left + 2,
                               self.rect.top - lbl.get_height() - 8))

        bg = (32, 34, 52) if self.focused else (20, 22, 34)
        border = (60, 220, 200) if self.focused else (70, 76, 100)
        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect,
                         2 if self.focused else 1, border_radius=8)

        display = ("•" * len(self.text)) if self.password else self.text
        ts = font_text.render(display, True, config.COLOR_TEXT)
        text_x = self.rect.left + 14
        text_y = self.rect.centery - ts.get_height() // 2
        surface.blit(ts, (text_x, text_y))

        # Blinking caret while focused.
        if self.focused and self._blink_t < 0.5:
            caret_x = text_x + ts.get_width() + 1
            pygame.draw.line(
                surface, (60, 220, 200),
                (caret_x, self.rect.top + 8),
                (caret_x, self.rect.bottom - 8), 2,
            )


# --- Slider (button-driven, no mouse drag) ----------------------------------

@dataclass
class Slider:
    rect: pygame.Rect             # the track rect; minus/plus buttons sit beside
    label: str
    value: int                    # 0..100
    on_change: Callable[[int], None] | None = None
    step: int = 10
    _minus: Button | None = None
    _plus: Button | None = None

    def __post_init__(self):
        bw = 28
        self._minus = Button(
            pygame.Rect(self.rect.left - bw - 8, self.rect.top - 4,
                        bw, self.rect.height + 8),
            "-",
            on_click=lambda: self._set(self.value - self.step),
        )
        self._plus = Button(
            pygame.Rect(self.rect.right + 8, self.rect.top - 4,
                        bw, self.rect.height + 8),
            "+",
            on_click=lambda: self._set(self.value + self.step),
        )

    def _set(self, v: int) -> None:
        v = max(0, min(100, v))
        if v != self.value:
            self.value = v
            if self.on_change:
                self.on_change(self.value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        return bool(self._minus.handle_event(event) or self._plus.handle_event(event))

    def draw(self, surface: pygame.Surface,
             font_label: pygame.font.Font,
             font_value: pygame.font.Font) -> None:
        # Label centred on the track's horizontal centre. Caller is expected
        # to place the track so its centerx equals the desired column centre;
        # the label then naturally lands centred too.
        lbl = font_label.render(self.label, True, config.COLOR_TEXT)
        surface.blit(lbl, lbl.get_rect(midbottom=(
            self.rect.centerx, self.rect.top - 6,
        )))
        # Track background.
        pygame.draw.rect(surface, (24, 24, 36), self.rect, border_radius=4)
        pygame.draw.rect(surface, (70, 70, 100), self.rect, 1, border_radius=4)
        # Fill bar.
        fill_w = int(self.rect.width * self.value / 100)
        if fill_w > 0:
            fill_rect = pygame.Rect(self.rect.left, self.rect.top,
                                    fill_w, self.rect.height)
            pygame.draw.rect(surface, (60, 220, 200), fill_rect, border_radius=4)
        # Value text on the right.
        val = font_value.render(f"{self.value}", True, config.COLOR_TEXT)
        surface.blit(val, (self.rect.right + 44, self.rect.centery - val.get_height() // 2))
        self._minus.draw(surface, font_value)
        self._plus.draw(surface, font_value)


# --- Lock icon ---------------------------------------------------------------

def draw_lock(surface: pygame.Surface, center: tuple[int, int],
              size: int = 16,
              color: tuple[int, int, int] = (200, 200, 220)) -> None:
    """Tiny padlock — used on locked level tiles + nightmare mode entry."""
    cx, cy = center
    body_w = size
    body_h = int(size * 0.7)
    body_rect = pygame.Rect(cx - body_w // 2, cy - body_h // 4,
                            body_w, body_h)
    pygame.draw.rect(surface, color, body_rect, border_radius=2)
    # Shackle arc.
    arc_rect = pygame.Rect(cx - body_w // 2 + 2, cy - body_h,
                           body_w - 4, body_h)
    pygame.draw.arc(surface, color, arc_rect, 3.14, 0, 2)
    # Keyhole.
    pygame.draw.circle(surface, (30, 30, 40),
                       (cx, cy + body_h // 8), 2)


def draw_check(surface: pygame.Surface, center: tuple[int, int],
               size: int = 14,
               color: tuple[int, int, int] = (90, 230, 130)) -> None:
    """Bright green check mark — overlays cleared level tiles."""
    cx, cy = center
    pad = size * 0.18
    # Two-segment polyline: down-stroke then up-stroke.
    pts_in = [
        (cx - size / 2 + pad, cy),
        (cx - size / 6, cy + size / 2.5 - pad),
        (cx + size / 2 - pad, cy - size / 2 + pad),
    ]
    # Drop shadow for legibility against the tile.
    shadow = [(x + 1, y + 1) for x, y in pts_in]
    pygame.draw.lines(surface, (0, 0, 0, 200), False, shadow, max(2, size // 5))
    pygame.draw.lines(surface, color, False, pts_in, max(2, size // 5))
