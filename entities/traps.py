"""Traps & trigger areas — GDD §3.3, §4.1 (+ rage-game additions).

The base `TriggerArea` keeps the IDLE → ACTIVE flow. Concrete traps override
`on_activate` and (optionally) `update`/`draw`.

This module also defines the troll traps that subvert player trust:
  * `FakeFloor`       — looks solid until you step on it
  * `CeilingSpike`    — drops from above the moment you walk under it
  * `Crusher`         — wind-up + slam when you enter its column
  * `FakeGoal`        — looks identical to the real portal but kills on touch
  * `ReverseZone`     — invisible region that flips A↔D while you're inside
"""
from __future__ import annotations

import math

import pygame

import config


class TriggerArea:
    STATE_IDLE = "IDLE"
    STATE_ACTIVE = "ACTIVE"
    STATE_DONE = "DONE"

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.state = self.STATE_IDLE

    def check(self, player_rect: pygame.Rect) -> bool:
        if self.state == self.STATE_IDLE and self.rect.colliderect(player_rect):
            self.state = self.STATE_ACTIVE
            self.on_activate()
            return True
        return False

    def on_activate(self) -> None: ...

    def update(self, dt: float) -> None: ...

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if debug:
            pygame.draw.rect(surface, config.COLOR_HINT, camera.apply_rect(self.rect), 1)


# --------------------------------------------------------------------------
class HiddenSpike(TriggerArea):
    """Tile code 2.

    Stays invisible until the player gets within ~2 blocks; then it pops up
    as a solid spike. Touching the visible spike kills the player.
    """

    REVEAL_RADIUS_TILES = 2

    def __init__(self, rect: pygame.Rect, grid_size: int):
        super().__init__(rect)
        self.grid_size = grid_size
        self.revealed = False
        # Spike hitbox = top half of the tile (so the player has to actually
        # touch the pointy bit, not the floor below it).
        self.kill_rect = pygame.Rect(rect.x, rect.y + rect.height // 2,
                                     rect.width, rect.height // 2)

    def check_reveal(self, player_rect: pygame.Rect) -> None:
        if self.revealed:
            return
        reveal_dist = self.REVEAL_RADIUS_TILES * self.grid_size
        dx = (player_rect.centerx - self.rect.centerx)
        dy = (player_rect.centery - self.rect.centery)
        if dx * dx + dy * dy <= reveal_dist * reveal_dist:
            self.revealed = True
            from systems import audio
            audio.play_sfx("spike_reveal")

    def kills(self, player_rect: pygame.Rect) -> bool:
        return self.revealed and self.kill_rect.colliderect(player_rect)

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if self.revealed:
            r = camera.apply_rect(self.kill_rect)
            # Triangular spike shape — three points along the top of kill_rect.
            pts = [(r.left, r.bottom),
                   (r.centerx, r.top),
                   (r.right, r.bottom)]
            pygame.draw.polygon(surface, config.COLOR_SPIKE, pts)
            pygame.draw.polygon(surface, (255, 200, 200), pts, 1)
        elif debug:
            pygame.draw.rect(surface, config.COLOR_HINT,
                             camera.apply_rect(self.rect), 1)


# --------------------------------------------------------------------------
class InvisibleBlock(TriggerArea):
    """Tile code 3.

    Looks like air. Behaves like solid only after the player has hit it
    (typically from below — classic ceiling-block troll). Once active it
    joins the solids list for the rest of the level.
    """

    def __init__(self, rect: pygame.Rect):
        super().__init__(rect)
        self.solid = False

    def trigger(self) -> None:
        if not self.solid:
            self.solid = True
            self.state = self.STATE_ACTIVE
            from systems import audio
            audio.play_sfx("block_appear")

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if self.solid:
            r = camera.apply_rect(self.rect)
            pygame.draw.rect(surface, config.COLOR_SOLID, r)
            pygame.draw.rect(surface, config.COLOR_SOLID_EDGE, r, 1)
        elif debug:
            pygame.draw.rect(surface, config.COLOR_HINT,
                             camera.apply_rect(self.rect), 1)


# --------------------------------------------------------------------------
class FakeFloor:
    """Tile code 4 — the classic "wait, that floor isn't real" prank.

    Lives in the world as a solid block. The frame the player's rect overlaps
    it, the floor enters CRUMBLE: 1–2 frames of cracking visual, then it's
    gone for the rest of the level (until reset).
    """

    STATE_SOLID = 0
    STATE_CRUMBLE = 1
    STATE_GONE = 2

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.state = self.STATE_SOLID
        self.crumble_t = 0.0

    @property
    def is_solid(self) -> bool:
        return self.state == self.STATE_SOLID

    def reset(self) -> None:
        self.state = self.STATE_SOLID
        self.crumble_t = 0.0

    def check(self, player_rect: pygame.Rect) -> None:
        """Activated when the player stands on top OR side-overlaps.

        After Y-axis collision resolution the player's bottom equals the
        floor's top (touching, not intersecting), so we expand the trigger
        rect by a couple of pixels vertically to catch that case.
        """
        if self.state != self.STATE_SOLID:
            return
        trigger = self.rect.inflate(0, 4)
        if trigger.colliderect(player_rect):
            self.state = self.STATE_CRUMBLE
            self.crumble_t = 0.0
            from systems import audio
            audio.play_sfx("crumble")

    def update(self, dt: float) -> None:
        if self.state == self.STATE_CRUMBLE:
            self.crumble_t += dt
            if self.crumble_t >= config.FAKE_FLOOR_CRUMBLE_TIME:
                self.state = self.STATE_GONE

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if self.state == self.STATE_GONE:
            if debug:
                pygame.draw.rect(surface, config.COLOR_HINT,
                                 camera.apply_rect(self.rect), 1)
            return
        r = camera.apply_rect(self.rect)
        if self.state == self.STATE_SOLID:
            # Looks exactly like a regular solid — that's the point.
            pygame.draw.rect(surface, config.COLOR_SOLID, r)
            pygame.draw.rect(surface, config.COLOR_SOLID_EDGE, r, 1)
            if debug:
                # Small diagonal mark only visible in debug, so testers can
                # tell at a glance which tiles are fake.
                pygame.draw.line(surface, (255, 80, 90),
                                 r.topleft, r.bottomright, 1)
        else:  # CRUMBLE
            t = self.crumble_t / config.FAKE_FLOOR_CRUMBLE_TIME
            shade = int(60 * (1 - t)) + 20
            pygame.draw.rect(surface, (shade, shade + 30, shade + 20), r)
            # Crack lines.
            for i in range(3):
                yoff = int(r.height * (i + 1) / 4)
                pygame.draw.line(surface, (10, 10, 14),
                                 (r.left + 2, r.top + yoff),
                                 (r.right - 2, r.top + yoff), 1)


# --------------------------------------------------------------------------
class CeilingSpike:
    """Tile code 5 — spike attached to the ceiling that drops on the player.

    Pre-drop it sits in place, looking like a downward-pointing spike. The
    moment the player's centre-X enters its trigger radius and they're below,
    gravity takes over. Lethal during the fall and after landing.
    """

    STATE_IDLE = 0
    STATE_FALLING = 1
    STATE_LANDED = 2

    def __init__(self, rect: pygame.Rect, grid_size: int):
        self.start_rect = rect.copy()
        self.rect = rect.copy()
        self.grid_size = grid_size
        self.state = self.STATE_IDLE
        self.vy = 0.0

    def reset(self) -> None:
        self.rect = self.start_rect.copy()
        self.state = self.STATE_IDLE
        self.vy = 0.0

    def maybe_trigger(self, player_rect: pygame.Rect) -> None:
        if self.state != self.STATE_IDLE:
            return
        dx = abs(player_rect.centerx - self.rect.centerx)
        if (dx <= config.CEILING_SPIKE_TRIGGER_RADIUS * self.grid_size
                and player_rect.top > self.rect.bottom):
            self.state = self.STATE_FALLING
            from systems import audio
            audio.play_sfx("spike_drop")

    def update(self, dt: float, solids: list[pygame.Rect]) -> None:
        if self.state != self.STATE_FALLING:
            return
        # Constant high-velocity drop. A gravity-based fall took ~0.4s from
        # ceiling height — long enough for a walking player to clear the
        # column. Constant speed keeps the threat tight: catch them if they
        # entered the trigger radius, miss them if they hung back.
        self.vy = 2400.0
        self.rect.y += int(self.vy * dt)
        for s in solids:
            if self.rect.colliderect(s):
                self.rect.bottom = s.top
                self.state = self.STATE_LANDED
                self.vy = 0.0
                return

    def kills(self, player_rect: pygame.Rect) -> bool:
        return self.state in (self.STATE_FALLING, self.STATE_LANDED) \
               and self.rect.colliderect(player_rect)

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        r = camera.apply_rect(self.rect)
        # Downward-pointing triangle.
        pts = [(r.left, r.top), (r.right, r.top), (r.centerx, r.bottom)]
        color = (255, 70, 90) if self.state != self.STATE_IDLE else (220, 60, 80)
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (255, 200, 200), pts, 1)
        # In idle state, draw a thin "chain" up to the ceiling row to hint at
        # the threat. (Only one pixel wide so it's easy to miss — that's
        # half the point.)
        if self.state == self.STATE_IDLE:
            chain_top_y = r.top - 6
            pygame.draw.line(surface, (90, 30, 40),
                             (r.centerx, chain_top_y), (r.centerx, r.top), 1)


# --------------------------------------------------------------------------
class Crusher:
    """Tile code 6 — heavy block that slams down when the player enters its column.

    `wind_up` gives the player about a quarter-second to react after the
    trigger fires; once it expires the block accelerates downward at
    CRUSHER_SPEED and lethals on contact. After landing it remains a solid.
    """

    STATE_IDLE = 0
    STATE_WIND_UP = 1
    STATE_FALLING = 2
    STATE_LANDED = 3

    def __init__(self, rect: pygame.Rect):
        self.start_rect = rect.copy()
        self.rect = rect.copy()
        self.state = self.STATE_IDLE
        self.wind_up_t = 0.0
        self.vy = 0.0

    def reset(self) -> None:
        self.rect = self.start_rect.copy()
        self.state = self.STATE_IDLE
        self.wind_up_t = 0.0
        self.vy = 0.0

    @property
    def is_solid(self) -> bool:
        # Block obstructs movement once it has landed. Letting it act as a
        # solid mid-air would be visually inconsistent.
        return self.state == self.STATE_LANDED

    def maybe_trigger(self, player_rect: pygame.Rect) -> None:
        if self.state != self.STATE_IDLE:
            return
        # Column check: player center-x within crusher's horizontal span and
        # player below the crusher.
        if (self.rect.left <= player_rect.centerx <= self.rect.right
                and player_rect.top > self.rect.bottom):
            self.state = self.STATE_WIND_UP
            self.wind_up_t = 0.0

    def update(self, dt: float, solids: list[pygame.Rect]) -> None:
        if self.state == self.STATE_WIND_UP:
            self.wind_up_t += dt
            if self.wind_up_t >= config.CRUSHER_WIND_UP:
                self.state = self.STATE_FALLING
        elif self.state == self.STATE_FALLING:
            self.vy = config.CRUSHER_SPEED
            self.rect.y += int(self.vy * dt)
            for s in solids:
                if self.rect.colliderect(s):
                    self.rect.bottom = s.top
                    self.state = self.STATE_LANDED
                    from systems import audio
                    audio.play_sfx("crusher")
                    return

    def kills(self, player_rect: pygame.Rect) -> bool:
        if self.state == self.STATE_FALLING:
            return self.rect.colliderect(player_rect)
        return False

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        r = camera.apply_rect(self.rect)
        # Body — heavy metallic block with a centre bolt.
        base_color = (100, 110, 130)
        if self.state == self.STATE_WIND_UP:
            # Pre-slam shudder.
            wobble = int(math.sin(self.wind_up_t * 80) * 2)
            r = r.move(wobble, 0)
        pygame.draw.rect(surface, base_color, r, border_radius=3)
        pygame.draw.rect(surface, (160, 170, 200), r, 2, border_radius=3)
        pygame.draw.rect(surface, (40, 45, 60),
                         r.inflate(-8, -8), 1, border_radius=2)
        pygame.draw.circle(surface, (40, 45, 60), r.center, 3)


# --------------------------------------------------------------------------
class FakeGoal:
    """A decoy portal — looks identical to the real one but kills on touch.

    Reuses the same visual as `entities.portal.Portal` but the colour balance
    skews a touch warmer; only sharp-eyed players who survived once will
    spot the difference.
    """

    def __init__(self, rect: pygame.Rect):
        from entities.portal import Portal
        self.rect = rect
        # We compose rather than inherit — keeps Portal's draw code unforked.
        self._portal = Portal(rect)
        self._dead = False

    def reset(self) -> None:
        self._dead = False
        self._portal.t = 0.0

    def update(self, dt: float) -> None:
        self._portal.update(dt)

    def kills(self, player_rect: pygame.Rect) -> bool:
        return not self._dead and self.rect.colliderect(player_rect)

    def mark_triggered(self) -> None:
        self._dead = True

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if self._dead:
            return
        self._portal.draw(surface, camera)
        if debug:
            r = camera.apply_rect(self.rect)
            pygame.draw.rect(surface, (255, 60, 80), r, 2)


# --------------------------------------------------------------------------
class GroundSpike:
    """Tile 7 — "false ground". Renders identical to a regular solid floor
    tile. The instant the player stands on top, a quick wind-up plays and
    spikes erupt upward from the block; the spikes overlap whatever rests
    on the surface, so anyone standing there dies.

    Survival: jump over the tile, or speedrun across before the wind-up
    fires. Wind-up is short (~0.08 s) so casual walking gets caught.
    """
    STATE_IDLE = 0
    STATE_WIND_UP = 1
    STATE_ERUPTED = 2

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.state = self.STATE_IDLE
        self.wind_up_t = 0.0

    @property
    def is_solid(self) -> bool:
        # Block is always a normal solid — that's what sells the deception.
        return True

    def reset(self) -> None:
        self.state = self.STATE_IDLE
        self.wind_up_t = 0.0

    def maybe_trigger(self, player_rect: pygame.Rect) -> None:
        if self.state != self.STATE_IDLE:
            return
        # Trigger when the player is standing on top: rect.bottom touches
        # block.top *and* there's X overlap.
        if not (self.rect.left < player_rect.right
                and self.rect.right > player_rect.left):
            return
        if abs(player_rect.bottom - self.rect.top) <= 2:
            self.state = self.STATE_WIND_UP
            self.wind_up_t = 0.0

    def update(self, dt: float) -> None:
        if self.state == self.STATE_WIND_UP:
            self.wind_up_t += dt
            if self.wind_up_t >= config.GROUND_SPIKE_WIND_UP:
                self.state = self.STATE_ERUPTED
                from systems import audio
                audio.play_sfx("spike_reveal")

    def kills(self, player_rect: pygame.Rect) -> bool:
        if self.state != self.STATE_ERUPTED:
            return False
        # The lethal volume is a 16-px-tall strip above the block top.
        spike_rect = pygame.Rect(self.rect.x, self.rect.y - 16,
                                 self.rect.width, 16)
        return spike_rect.colliderect(player_rect)

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        r = camera.apply_rect(self.rect)
        # Always draw the block itself — it's the deception.
        pygame.draw.rect(surface, config.COLOR_SOLID, r)
        pygame.draw.rect(surface, config.COLOR_SOLID_EDGE, r, 1)
        if self.state == self.STATE_IDLE:
            if debug:
                pygame.draw.line(surface, (255, 60, 80),
                                 r.topleft, r.bottomright, 1)
            return
        # Wind-up or erupted: draw spike triangles emerging from the top.
        if self.state == self.STATE_WIND_UP:
            t = self.wind_up_t / config.GROUND_SPIKE_WIND_UP
            spike_h = int(16 * t)
        else:
            spike_h = 16
        count = 3
        spike_w = r.width // count
        for i in range(count):
            sx = r.left + i * spike_w
            pts = [
                (sx, r.top),
                (sx + spike_w, r.top),
                (sx + spike_w / 2, r.top - spike_h),
            ]
            pygame.draw.polygon(surface, (255, 70, 90), pts)
            if spike_h >= 8:
                pygame.draw.polygon(surface, (255, 200, 200), pts, 1)


class TimedFloor:
    """Tile 8 — looks like solid floor. The instant the player touches it,
    a fuse starts: it shakes, cracks, then disappears entirely. Forces the
    player to keep moving across a stretch instead of stopping to think.
    """
    STATE_INTACT = 0
    STATE_BREAKING = 1
    STATE_GONE = 2

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.state = self.STATE_INTACT
        self.break_t = 0.0

    @property
    def is_solid(self) -> bool:
        return self.state != self.STATE_GONE

    def reset(self) -> None:
        self.state = self.STATE_INTACT
        self.break_t = 0.0

    def check(self, player_rect: pygame.Rect) -> None:
        if self.state != self.STATE_INTACT:
            return
        trigger = self.rect.inflate(0, 4)
        if trigger.colliderect(player_rect):
            self.state = self.STATE_BREAKING
            self.break_t = 0.0
            from systems import audio
            audio.play_sfx("crumble")

    def update(self, dt: float) -> None:
        if self.state == self.STATE_BREAKING:
            self.break_t += dt
            if self.break_t >= config.TIMED_FLOOR_BREAK_TIME:
                self.state = self.STATE_GONE

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if self.state == self.STATE_GONE:
            if debug:
                pygame.draw.rect(surface, config.COLOR_HINT,
                                 camera.apply_rect(self.rect), 1)
            return
        r = camera.apply_rect(self.rect)
        if self.state == self.STATE_INTACT:
            pygame.draw.rect(surface, config.COLOR_SOLID, r)
            pygame.draw.rect(surface, config.COLOR_SOLID_EDGE, r, 1)
            if debug:
                pygame.draw.circle(surface, (255, 200, 60),
                                   r.center, 3)
            return
        # BREAKING — shake + darken + crack lines.
        t = self.break_t / config.TIMED_FLOOR_BREAK_TIME
        shake = int(math.sin(self.break_t * 90) * 2 * t)
        shaken = r.move(shake, 0)
        shade = int(30 + (1 - t) * 80)
        pygame.draw.rect(surface, (shade, shade + 30, shade + 20), shaken)
        pygame.draw.rect(surface, config.COLOR_SOLID_EDGE, shaken, 1)
        # Diagonal cracks getting deeper with t.
        crack_count = 1 + int(t * 3)
        for i in range(crack_count):
            x0 = shaken.left + 4 + i * 6
            y0 = shaken.top + 2
            x1 = x0 + 8 - i * 2
            y1 = shaken.bottom - 2
            pygame.draw.line(surface, (10, 10, 14), (x0, y0), (x1, y1), 1)


class FallingBlock:
    """Tile 9 — heavy stone block parked in the air. When the player walks
    into the block's column they get one warning frame of wobble, then the
    block falls fast (no wind-up). Differs from Crusher: no telegraphed
    wind-up, faster drop, smaller visual footprint.
    """
    STATE_IDLE = 0
    STATE_FALLING = 1
    STATE_LANDED = 2

    def __init__(self, rect: pygame.Rect):
        self.start_rect = rect.copy()
        self.rect = rect.copy()
        self.state = self.STATE_IDLE
        self.vy = 0.0

    def reset(self) -> None:
        self.rect = self.start_rect.copy()
        self.state = self.STATE_IDLE
        self.vy = 0.0

    @property
    def is_solid(self) -> bool:
        return self.state == self.STATE_LANDED

    def maybe_trigger(self, player_rect: pygame.Rect) -> None:
        if self.state != self.STATE_IDLE:
            return
        if (self.rect.left <= player_rect.centerx <= self.rect.right
                and player_rect.top > self.rect.bottom):
            self.state = self.STATE_FALLING
            from systems import audio
            audio.play_sfx("crusher")

    def update(self, dt: float, solids: list[pygame.Rect]) -> None:
        if self.state != self.STATE_FALLING:
            return
        self.vy = config.FALLING_BLOCK_SPEED
        self.rect.y += int(self.vy * dt)
        for s in solids:
            if self.rect.colliderect(s):
                self.rect.bottom = s.top
                self.state = self.STATE_LANDED
                return

    def kills(self, player_rect: pygame.Rect) -> bool:
        return (self.state == self.STATE_FALLING
                and self.rect.colliderect(player_rect))

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        r = camera.apply_rect(self.rect)
        # Stone block with cross-shaped crack — visually distinct from
        # the metallic Crusher (so players can tell which is which once
        # they've seen both).
        pygame.draw.rect(surface, (130, 100, 78), r, border_radius=2)
        pygame.draw.rect(surface, (210, 170, 130), r, 2, border_radius=2)
        pygame.draw.line(surface, (60, 40, 30),
                         (r.left + 4, r.centery),
                         (r.right - 4, r.centery), 1)
        pygame.draw.line(surface, (60, 40, 30),
                         (r.centerx, r.top + 4),
                         (r.centerx, r.bottom - 4), 1)


class FakeCheckpoint:
    """A glittering star that exists only to murder you. JSON-driven via
    `fake_checkpoints: [[col, row], ...]`. Visually it looks like a power-up
    or bonus item; the troll is that grabbing it kills.
    """

    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.dead = False
        self.t = 0.0

    def reset(self) -> None:
        self.dead = False
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt

    def kills(self, player_rect: pygame.Rect) -> bool:
        return not self.dead and self.rect.colliderect(player_rect)

    def mark_triggered(self) -> None:
        self.dead = True

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if self.dead:
            return
        r = camera.apply_rect(self.rect)
        cx, cy = r.center
        outer = r.width * 0.35
        inner = outer * 0.5
        rot = self.t * 1.5
        pts: list[tuple[float, float]] = []
        for i in range(10):
            angle = rot + i * (math.pi / 5) - math.pi / 2
            rad = outer if i % 2 == 0 else inner
            pts.append((cx + math.cos(angle) * rad,
                        cy + math.sin(angle) * rad))
        glow = 200 + int(math.sin(self.t * 4) * 30)
        pygame.draw.polygon(surface, (255, glow, 80), pts)
        pygame.draw.polygon(surface, (255, 255, 200), pts, 1)


class ReverseZone:
    """Invisible rectangle. While the player rect overlaps, A↔D are flipped.

    Constructed from JSON `reverse_zones`: list of [c0, r0, c1, r1] (inclusive)
    in tile coordinates.
    """

    def __init__(self, rect: pygame.Rect):
        self.rect = rect

    def active_for(self, player_rect: pygame.Rect) -> bool:
        return self.rect.colliderect(player_rect)

    def draw(self, surface: pygame.Surface, camera, debug: bool = False) -> None:
        if not debug:
            return
        r = camera.apply_rect(self.rect)
        overlay = pygame.Surface(r.size, pygame.SRCALPHA)
        overlay.fill((180, 120, 255, 60))
        surface.blit(overlay, r.topleft)
        pygame.draw.rect(surface, (180, 120, 255), r, 1)
