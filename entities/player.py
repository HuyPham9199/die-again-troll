"""Player kinematics + AABB collision + procedural skeleton render.

Per GDD §3.1–3.2:
  * Velocities in pixels/sec, all integration uses `pos += vel * dt`.
  * Collision is resolved one axis at a time (X first, then Y) to avoid
    corner-clipping.

The body is drawn as a stick-figure (head + torso + 2 arms + 2 legs) whose
limbs swing on a phase variable. No sprite assets needed.
"""
from __future__ import annotations

import math

import pygame

import config


class Player:
    WIDTH = 28
    HEIGHT = 36

    def __init__(self, spawn_x: float, spawn_y: float):
        self.spawn_x = spawn_x
        self.spawn_y = spawn_y
        self.rect = pygame.Rect(int(spawn_x), int(spawn_y), self.WIDTH, self.HEIGHT)
        # Float position kept separately — pygame.Rect only stores ints, and
        # accumulating sub-pixel velocity into ints loses precision fast.
        self.fx = float(spawn_x)
        self.fy = float(spawn_y)
        self.vx = 0.0
        self.vy = 0.0
        self.is_grounded = False
        self.facing = 1                  # +1 right, -1 left
        self.alive = True
        self.coyote_timer = 0.0
        self.jump_buffer = 0.0
        # Animation phase — accumulates with horizontal travel for the walk
        # cycle and ticks slowly while idle for the breathing bob.
        self.anim_phase = 0.0
        self.idle_phase = 0.0

    # ----------------------------------------------------------------------
    def respawn(self) -> None:
        self.fx = self.spawn_x
        self.fy = self.spawn_y
        self.rect.x = int(self.fx)
        self.rect.y = int(self.fy)
        self.vx = 0.0
        self.vy = 0.0
        self.alive = True
        self.is_grounded = False

    def kill(self) -> None:
        self.alive = False

    def request_jump(self) -> None:
        self.jump_buffer = config.PLAYER_JUMP_BUFFER

    # ----------------------------------------------------------------------
    def update(self, dt: float, input_x: int, solids: list[pygame.Rect]) -> None:
        """input_x ∈ {-1, 0, +1} — horizontal intent for this frame."""
        if not self.alive:
            return

        # Horizontal velocity: snap-to-target. No acceleration; rage games
        # want crisp, twitchy movement.
        self.vx = input_x * config.PLAYER_MOVE_SPEED
        if input_x != 0:
            self.facing = input_x

        # Gravity.
        self.vy += config.GRAVITY * dt
        if self.vy > config.PLAYER_MAX_FALL:
            self.vy = config.PLAYER_MAX_FALL

        # Jump (with coyote + buffer).
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        self.coyote_timer = max(0.0, self.coyote_timer - dt)
        if self.jump_buffer > 0 and (self.is_grounded or self.coyote_timer > 0):
            self.vy = config.PLAYER_JUMP_VELOCITY
            self.is_grounded = False
            self.jump_buffer = 0.0
            self.coyote_timer = 0.0
            # Local import — avoids a circular at module load.
            from systems import audio
            audio.play_sfx("jump")

        # --- Axis-separated AABB resolve (GDD §3.2) --------------------
        # X first
        self.fx += self.vx * dt
        self.rect.x = int(self.fx)
        for s in solids:
            if not self.rect.colliderect(s):
                continue
            if self.vx > 0:
                self.rect.right = s.left
            elif self.vx < 0:
                self.rect.left = s.right
            self.fx = float(self.rect.x)
            self.vx = 0.0

        # Y second
        was_grounded = self.is_grounded
        self.is_grounded = False
        self.fy += self.vy * dt
        self.rect.y = int(self.fy)
        for s in solids:
            if not self.rect.colliderect(s):
                continue
            if self.vy > 0:           # falling — hit floor
                self.rect.bottom = s.top
                self.is_grounded = True
            elif self.vy < 0:         # rising — hit ceiling
                self.rect.top = s.bottom
            self.fy = float(self.rect.y)
            self.vy = 0.0

        # Coyote: just walked off a ledge this frame.
        if was_grounded and not self.is_grounded:
            self.coyote_timer = config.PLAYER_COYOTE_TIME

        # Animation phases.
        if abs(self.vx) > 1.0 and self.is_grounded:
            self.anim_phase += abs(self.vx) * dt * 0.04
        else:
            # Ease the limb swing back to neutral when stopping. Keeps the
            # transition fluid instead of freezing on whatever mid-step pose
            # the player was in.
            decay = math.exp(-12.0 * dt)
            target = round(self.anim_phase / math.pi) * math.pi  # nearest 0/π
            self.anim_phase = target + (self.anim_phase - target) * decay
        self.idle_phase += dt * 3.0
        # Smooth facing — store a float that lerps toward the discrete facing.
        if not hasattr(self, "facing_smooth"):
            self.facing_smooth = float(self.facing)
        k = 1.0 - math.exp(-18.0 * dt)
        self.facing_smooth += (self.facing - self.facing_smooth) * k

    # ----------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, camera) -> None:
        """Draw a 5-limb skeleton in float screen space.

        Everything that follows treats `screen_x/y` as float; pygame's draw
        primitives round once internally, so the player never stutters
        between two pixel positions per frame.
        """
        if not self.alive:
            return

        body_color = config.COLOR_PLAYER
        outline = (40, 10, 30)
        accent = (255, 200, 230)

        # Float screen-space origin (top-left of the player rect).
        sx0, sy0 = camera.world_to_screen(self.fx, self.fy)
        cx = sx0 + self.WIDTH / 2

        # Smooth bob — runs all the time, but amplitude only ramps up when
        # grounded and still. Keeps transitions imperceptible.
        idle_factor = 0.0
        if self.is_grounded and abs(self.vx) < 1.0:
            idle_factor = 1.0
        bob = math.sin(self.idle_phase) * 1.4 * idle_factor

        # Pose blend factors.
        airborne = 1.0 if not self.is_grounded else 0.0
        walk_amp = min(1.0, abs(self.vx) / config.PLAYER_MOVE_SPEED) if self.is_grounded else 0.0
        s = math.sin(self.anim_phase)
        # Smoothly mix walk swing into air pose.
        swing_arm = (-s * 1.0) * walk_amp + (-1.2) * airborne \
                    + math.sin(self.idle_phase * 0.7) * 0.15 * (1 - walk_amp - airborne)
        swing_leg = (s * 0.9) * walk_amp + (-0.4) * airborne

        # Anchors (floats).
        head_r = 6.0
        head_cy = sy0 + head_r + 2 + bob
        shoulder_y = head_cy + head_r + 2
        hip_y = sy0 + 24 + bob
        foot_y_max = sy0 + self.HEIGHT - 1
        shoulder_dx = 5.0
        hip_dx = 4.0
        face = self.facing_smooth  # float in roughly [-1, +1] during turn

        # --- Limbs (arms first, then legs — drawn behind torso) --------
        arm_len = 11.0
        for side in (-1.0, +1.0):
            ax = cx + side * shoulder_dx
            ay = shoulder_y
            angle = (math.pi / 2) + swing_arm * side * face
            ex = ax + math.cos(angle) * arm_len
            ey = ay + math.sin(angle) * arm_len
            _thick_line(surface, body_color, outline, ax, ay, ex, ey, 3.0)

        leg_len = 12.0
        for side in (-1.0, +1.0):
            hx = cx + side * hip_dx
            hy = hip_y
            angle = (math.pi / 2) + swing_leg * side * face
            ex = hx + math.cos(angle) * leg_len
            ey = min(hy + math.sin(angle) * leg_len, foot_y_max)
            _thick_line(surface, body_color, outline, hx, hy, ex, ey, 3.0)

        # --- Torso ----------------------------------------------------
        torso_x = cx - 7.0
        torso_y = shoulder_y - 1
        torso_w = 14.0
        torso_h = (hip_y - shoulder_y) + 2
        pygame.draw.rect(surface, body_color,
                         (torso_x, torso_y, torso_w, torso_h),
                         border_radius=3)
        pygame.draw.rect(surface, outline,
                         (torso_x, torso_y, torso_w, torso_h),
                         1, border_radius=3)
        pygame.draw.aaline(
            surface, accent,
            (torso_x + torso_w / 2, torso_y + 1),
            (torso_x + torso_w / 2, torso_y + torso_h - 2),
        )

        # --- Head -----------------------------------------------------
        head_pos = (cx, head_cy)
        pygame.draw.circle(surface, body_color, head_pos, head_r)
        pygame.draw.circle(surface, outline, head_pos, head_r, 1)

        # Eye + cheek accent — track facing_smooth for fluid turn.
        eye_off = 2.0 * face
        pygame.draw.circle(surface, (20, 20, 30),
                           (cx + eye_off, head_cy - 1), 1)
        pygame.draw.circle(surface, accent,
                           (cx + 3.0 * face, head_cy + 2), 1)


def _thick_line(surface, fill, outline, x1, y1, x2, y2, width):
    """A smoother thick line: filled core + AA edges.

    pygame's wide `draw.line` is a clean rectangle but pixel-snapped at both
    ends; surrounding it with two parallel aalines softens the silhouette.
    """
    pygame.draw.line(surface, fill, (x1, y1), (x2, y2), int(width))
    pygame.draw.aaline(surface, outline, (x1, y1), (x2, y2))
