"""Pre-allocated particle pool — GDD §6.1.

Avoid Python GC stalls when 200 particles spawn at once. Particles are simple
data containers; the pool itself owns the array. Dead particles are reused.
"""
from __future__ import annotations

import math
import random

import pygame

import config


class Particle:
    __slots__ = ("dead", "x", "y", "vx", "vy", "life", "max_life", "color", "size")

    def __init__(self):
        self.dead = True
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.life = 0.0
        self.max_life = 1.0
        self.color = config.COLOR_PLAYER
        self.size = 3


class ParticlePool:
    def __init__(self, size: int = config.PARTICLE_POOL_SIZE):
        self._pool: list[Particle] = [Particle() for _ in range(size)]

    def _acquire(self) -> Particle | None:
        for p in self._pool:
            if p.dead:
                return p
        return None  # pool exhausted — drop the request, don't grow

    def burst(self, x: float, y: float, count: int = 24,
              color: tuple[int, int, int] = config.COLOR_PLAYER,
              speed: float = 320.0, life: float = 0.6) -> None:
        for _ in range(count):
            p = self._acquire()
            if p is None:
                return
            angle = random.uniform(0, math.tau)
            v = random.uniform(0.3, 1.0) * speed
            p.dead = False
            p.x = x
            p.y = y
            p.vx = math.cos(angle) * v
            p.vy = math.sin(angle) * v
            p.life = life
            p.max_life = life
            p.color = color
            p.size = random.randint(2, 4)

    def update(self, dt: float) -> None:
        for p in self._pool:
            if p.dead:
                continue
            p.life -= dt
            if p.life <= 0:
                p.dead = True
                continue
            p.vy += config.GRAVITY * 0.4 * dt   # mild gravity
            p.x += p.vx * dt
            p.y += p.vy * dt

    def draw(self, surface: pygame.Surface, camera) -> None:
        for p in self._pool:
            if p.dead:
                continue
            sx, sy = camera.world_to_screen(p.x, p.y)
            fade = max(0.0, p.life / p.max_life)
            c = (
                int(p.color[0] * fade),
                int(p.color[1] * fade),
                int(p.color[2] * fade),
            )
            pygame.draw.rect(surface, c, (int(sx), int(sy), p.size, p.size))
