"""LevelData: parse JSON layout (GDD §4.1) into world rects + trap objects.

Schema (any field marked optional defaults sensibly):
    level_id        int
    grid_size       int (px per tile)
    player_spawn    [col, row]
    goal_pos        [col, row]
    layout          2D matrix of tile codes
    name            optional display name
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import pygame

import config
from entities.traps import (
    HiddenSpike,
    InvisibleBlock,
    FakeFloor,
    CeilingSpike,
    Crusher,
    FakeGoal,
    ReverseZone,
)


@dataclass
class LevelData:
    level_id: int
    name: str
    grid_size: int
    cols: int
    rows: int
    player_spawn_px: tuple[int, int]
    goal_rect: pygame.Rect
    solids: list[pygame.Rect] = field(default_factory=list)
    hidden_spikes: list[HiddenSpike] = field(default_factory=list)
    invisible_blocks: list[InvisibleBlock] = field(default_factory=list)
    fake_floors: list[FakeFloor] = field(default_factory=list)
    ceiling_spikes: list[CeilingSpike] = field(default_factory=list)
    crushers: list[Crusher] = field(default_factory=list)
    fake_goals: list[FakeGoal] = field(default_factory=list)
    reverse_zones: list[ReverseZone] = field(default_factory=list)

    @property
    def world_w(self) -> int:
        return self.cols * self.grid_size

    @property
    def world_h(self) -> int:
        return self.rows * self.grid_size


def _validate(d: dict[str, Any], path: str) -> None:
    for key in ("level_id", "grid_size", "player_spawn", "goal_pos", "layout"):
        if key not in d:
            raise ValueError(f"{path}: missing required key {key!r}")
    if not isinstance(d["layout"], list) or not d["layout"]:
        raise ValueError(f"{path}: 'layout' must be a non-empty 2D list")
    row0_len = len(d["layout"][0])
    for i, row in enumerate(d["layout"]):
        if len(row) != row0_len:
            raise ValueError(
                f"{path}: layout row {i} length {len(row)} != row 0 length {row0_len}"
            )


def load_level(path: str) -> LevelData:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    _validate(raw, path)

    grid = int(raw["grid_size"])
    layout = raw["layout"]
    rows = len(layout)
    cols = len(layout[0])

    spawn_c, spawn_r = raw["player_spawn"]
    goal_c, goal_r = raw["goal_pos"]

    data = LevelData(
        level_id=int(raw["level_id"]),
        name=str(raw.get("name", f"Level {raw['level_id']}")),
        grid_size=grid,
        cols=cols,
        rows=rows,
        player_spawn_px=(spawn_c * grid + grid // 2 - 14, spawn_r * grid),
        goal_rect=pygame.Rect(goal_c * grid, goal_r * grid, grid, grid),
    )

    for r, row in enumerate(layout):
        for c, code in enumerate(row):
            rect = pygame.Rect(c * grid, r * grid, grid, grid)
            if code == config.TILE_SOLID:
                data.solids.append(rect)
            elif code == config.TILE_HIDDEN_SPIKE:
                data.hidden_spikes.append(HiddenSpike(rect, grid))
            elif code == config.TILE_INVISIBLE_BLOCK:
                data.invisible_blocks.append(InvisibleBlock(rect))
            elif code == config.TILE_FAKE_FLOOR:
                data.fake_floors.append(FakeFloor(rect))
            elif code == config.TILE_CEILING_SPIKE:
                data.ceiling_spikes.append(CeilingSpike(rect, grid))
            elif code == config.TILE_CRUSHER:
                data.crushers.append(Crusher(rect))
            # TILE_AIR → nothing

    # Optional extras keyed by name. Coords are tile units, converted to px.
    for col, row in raw.get("decoy_goals", []):
        gr = pygame.Rect(col * grid, row * grid, grid, grid)
        data.fake_goals.append(FakeGoal(gr))
    for z in raw.get("reverse_zones", []):
        # Accepts [c0, r0, c1, r1] (inclusive on both ends).
        c0, r0, c1, r1 = z
        rect = pygame.Rect(c0 * grid, r0 * grid,
                           (c1 - c0 + 1) * grid, (r1 - r0 + 1) * grid)
        data.reverse_zones.append(ReverseZone(rect))

    return data


def list_levels(data_root: str, mode: str = "normal") -> list[str]:
    """Return sorted absolute paths of level_*.json files for the given mode.

    `data_root` should be the .../levels/data directory; mode names a subfolder
    underneath it ("normal" or "nightmare").
    """
    mode_dir = os.path.join(data_root, mode)
    if not os.path.isdir(mode_dir):
        return []
    files = [f for f in os.listdir(mode_dir)
             if f.startswith("level_") and f.endswith(".json")]
    files.sort()
    return [os.path.join(mode_dir, f) for f in files]
