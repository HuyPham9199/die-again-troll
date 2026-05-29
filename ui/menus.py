"""Boot / MainMenu / ModeSelect / LevelSelect states.

All menus are mouse-first (click) but also fully keyboard-navigable.
"""
from __future__ import annotations

import os

import pygame

import config
from core.fsm import State
from systems import audio, save_mgr
from systems.particle_pool import ParticlePool
from ui.branding import make_logo
from ui.widgets import Button, draw_panel, draw_starfield, draw_lock, draw_check


_LEVELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "levels", "data",
)


# ----------------------------------------------------------------------------
class BootState(State):
    DURATION = 0.8

    def enter(self, **kwargs):
        self.elapsed = 0.0
        engine = self.machine.engine
        if engine.particle_pool is None:
            engine.particle_pool = ParticlePool()
        if not engine.save_data:
            engine.save_data = save_mgr.load()
        # Apply saved audio volumes now that save_data is loaded — the
        # rest of the game can play sounds at the user's chosen level
        # from the very first frame.
        settings = save_mgr.get_settings(engine.save_data)
        audio.apply_settings(settings)
        # Apply the saved display mode (fullscreen / windowed).
        engine.set_display_mode(settings.get("display_mode", "windowed"))
        # If a user is logged in, pull the latest progress from DB so the
        # local cache reflects whatever happened on another device.
        if engine.save_data.get("user_id"):
            try:
                from systems import auth_db
                auth_db.pull_progress(engine.save_data)
            except Exception:
                pass
        self._title_surf = engine.font_lg.render(
            "DIE AGAIN", True, config.COLOR_PLAYER
        )
        self._sub_surf = engine.font_sm.render(
            "loading…", True, config.COLOR_TEXT_DIM
        )
        self._logo = make_logo(72)

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.DURATION:
            self.machine.change_to(MainMenuState(self.machine))

    def draw(self, surface):
        cx, cy = config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2
        surface.blit(self._logo,
                     self._logo.get_rect(center=(cx, cy - 80)))
        surface.blit(self._title_surf,
                     self._title_surf.get_rect(center=(cx, cy - 10)))
        surface.blit(self._sub_surf,
                     self._sub_surf.get_rect(center=(cx, cy + 40)))


# ----------------------------------------------------------------------------
class _MenuBase(State):
    """Shared scaffolding for click-and-keyboard menus."""

    def __init__(self, machine):
        super().__init__(machine)
        self._buttons: list[Button] = []
        self._selected_idx: int = 0
        self._anim_t: float = 0.0

    def update(self, dt):
        self._anim_t += dt

    def _set_selected(self, idx: int) -> None:
        if not self._buttons:
            return
        self._selected_idx = idx % len(self._buttons)

    def _activate_selected(self) -> None:
        if self._buttons and self._buttons[self._selected_idx].enabled:
            b = self._buttons[self._selected_idx]
            if b.on_click:
                b.on_click()

    def handle_event(self, event):
        # Mouse: dispatch to every button.
        for b in self._buttons:
            b.handle_event(event)
        # Mouse hover also moves keyboard selection — keeps both in sync.
        if event.type == pygame.MOUSEMOTION:
            for i, b in enumerate(self._buttons):
                if b.enabled and b.rect.collidepoint(event.pos):
                    self._selected_idx = i
                    break
        if event.type == pygame.KEYDOWN:
            self._on_key(event.key)

    def _on_key(self, key: int) -> None:
        if key in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB):
            self._step_selection(+1)
        elif key in (pygame.K_UP, pygame.K_w):
            self._step_selection(-1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate_selected()

    def _step_selection(self, delta: int) -> None:
        if not self._buttons:
            return
        n = len(self._buttons)
        i = self._selected_idx
        for _ in range(n):
            i = (i + delta) % n
            if self._buttons[i].enabled:
                self._selected_idx = i
                return

    def _draw_background(self, surface: pygame.Surface,
                         title: str, subtitle: str | None = None) -> None:
        draw_starfield(surface, self._anim_t)
        engine = self.machine.engine
        cx = config.SCREEN_WIDTH // 2
        title_surf = engine.font_lg.render(title, True, config.COLOR_PLAYER)
        surface.blit(title_surf, title_surf.get_rect(center=(cx, 70)))
        if subtitle:
            sub_surf = engine.font_sm.render(subtitle, True, config.COLOR_TEXT_DIM)
            surface.blit(sub_surf, sub_surf.get_rect(center=(cx, 105)))

    def _draw_buttons(self) -> None:
        surface = pygame.display.get_surface()
        font = self.machine.engine.font_md
        for i, b in enumerate(self._buttons):
            b.draw(surface, font, selected=(i == self._selected_idx))


# ----------------------------------------------------------------------------
class MainMenuState(_MenuBase):
    def enter(self, **kwargs):
        self.engine = self.machine.engine
        self._logo = make_logo(96)
        audio.play_music("background_music")
        cx = config.SCREEN_WIDTH // 2
        bw, bh = 240, 52
        x = cx - bw // 2
        self._buttons = [
            Button(pygame.Rect(x, 260, bw, bh), "Play",
                   on_click=self._go_modes),
            Button(pygame.Rect(x, 320, bw, bh), "Settings",
                   on_click=self._go_settings),
            Button(pygame.Rect(x, 380, bw, bh), "Quit",
                   on_click=self.engine.quit),
        ]
        self._selected_idx = 0

    def _go_modes(self):
        self.machine.change_to(ModeSelectState(self.machine))

    def _go_settings(self):
        from ui.settings_state import SettingsState
        self.machine.change_to(SettingsState(self.machine,
                                             back_to=MainMenuState))

    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            self.engine.quit()
            return
        super()._on_key(key)

    def draw(self, surface):
        draw_starfield(surface, self._anim_t)
        cx = config.SCREEN_WIDTH // 2

        # Pre-render the title segments so we can measure and centre the
        # whole row as a single block — logo + "DIE AGAIN : TROLL".
        font_lg = self.engine.font_lg
        title_p1 = font_lg.render("DIE AGAIN", True, config.COLOR_PLAYER)
        title_sep = font_lg.render(":", True, (255, 220, 60))
        title_p2 = font_lg.render("TROLL", True, (255, 220, 60))

        seg_gap = 14
        title_w = (title_p1.get_width() + seg_gap
                   + title_sep.get_width() + seg_gap
                   + title_p2.get_width())
        logo_w = self._logo.get_width()
        logo_gap = 24
        block_w = logo_w + logo_gap + title_w

        start_x = cx - block_w // 2
        row_center_y = 130

        # Logo on the left of the row, vertically centred to the row.
        logo_rect = self._logo.get_rect(
            midleft=(start_x, row_center_y)
        )
        surface.blit(self._logo, logo_rect)

        # Title segments — all on the SAME baseline.
        text_y = row_center_y - title_p1.get_height() // 2
        x = logo_rect.right + logo_gap
        surface.blit(title_p1, (x, text_y))
        x += title_p1.get_width() + seg_gap
        surface.blit(title_sep, (x, text_y))
        x += title_sep.get_width() + seg_gap
        surface.blit(title_p2, (x, text_y))

        tagline = self.engine.font_sm.render(
            "trust nothing — not even the gate.",
            True, config.COLOR_TEXT_DIM,
        )
        surface.blit(tagline, tagline.get_rect(
            midtop=(cx, row_center_y + logo_w // 2 + 4)
        ))

        # Account chip — small label top-right if signed in.
        sd = self.engine.save_data
        if sd.get("username"):
            chip_label = self.engine.font_sm.render(
                f"@ {sd['username']}", True, (160, 220, 200)
            )
            cw = chip_label.get_width() + 20
            chip_rect = pygame.Rect(config.SCREEN_WIDTH - cw - 14, 14, cw, 26)
            pygame.draw.rect(surface, (22, 24, 36), chip_rect, border_radius=13)
            pygame.draw.rect(surface, (60, 220, 200), chip_rect, 1, border_radius=13)
            surface.blit(chip_label,
                         chip_label.get_rect(center=chip_rect.center))

        self._draw_buttons()
        hint = self.engine.font_sm.render(
            "Click or use UP/DOWN + ENTER", True, config.COLOR_TEXT_DIM,
        )
        surface.blit(hint, hint.get_rect(
            center=(cx, config.SCREEN_HEIGHT - 32)
        ))


# ----------------------------------------------------------------------------
class ModeSelectState(_MenuBase):
    """Normal / Nightmare. Nightmare locked until 5 normal levels cleared."""

    def enter(self, **kwargs):
        self.engine = self.machine.engine
        audio.play_music("background_music")  # no-op if already playing
        cleared_normal = max(0, self.engine.save_data.get("max_normal_level", 1) - 1)
        self._nightmare_unlocked = cleared_normal >= 5

        cx = config.SCREEN_WIDTH // 2
        bw, bh = 320, 90
        gap = 30
        total_w = bw * 2 + gap
        start_x = cx - total_w // 2
        y = 230
        self._buttons = [
            Button(pygame.Rect(start_x, y, bw, bh), "NORMAL",
                   on_click=lambda: self._launch("normal"),
                   accent=(60, 220, 200)),
            Button(pygame.Rect(start_x + bw + gap, y, bw, bh), "NIGHTMARE",
                   on_click=lambda: self._launch("nightmare"),
                   accent=(255, 80, 120),
                   enabled=self._nightmare_unlocked),
        ]
        # Bottom Back button.
        self._buttons.append(
            Button(pygame.Rect(cx - 90, 420, 180, 40), "Back",
                   on_click=self._back)
        )
        self._selected_idx = 0

    def _launch(self, mode: str):
        self.machine.change_to(LevelSelectState(self.machine), mode=mode)

    def _back(self):
        self.machine.change_to(MainMenuState(self.machine))

    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            self._back()
            return
        # Map LEFT/RIGHT to selection on this screen.
        if key in (pygame.K_LEFT, pygame.K_a):
            self._step_selection(-1)
            return
        if key in (pygame.K_RIGHT, pygame.K_d):
            self._step_selection(+1)
            return
        super()._on_key(key)

    def draw(self, surface):
        self._draw_background(surface, "SELECT MODE")
        self._draw_buttons()

        # Subtle blurb under each mode.
        engine = self.engine
        cx = config.SCREEN_WIDTH // 2
        bw, gap = 320, 30
        start_x = cx - (bw * 2 + gap) // 2
        y = 335
        normal_blurb = engine.font_sm.render(
            "20 hand-crafted levels.", True, config.COLOR_TEXT_DIM
        )
        surface.blit(normal_blurb,
                     normal_blurb.get_rect(center=(start_x + bw // 2, y)))

        if self._nightmare_unlocked:
            night_blurb = engine.font_sm.render(
                "Unforgiving. Bring patience.", True, (200, 100, 130)
            )
        else:
            night_blurb = engine.font_sm.render(
                "Clear 5 normal levels to unlock.", True, config.COLOR_TEXT_DIM
            )
        surface.blit(night_blurb,
                     night_blurb.get_rect(center=(start_x + bw + gap + bw // 2, y)))

        # Lock icon on top-right of Nightmare button if locked.
        if not self._nightmare_unlocked:
            night_btn = self._buttons[1].rect
            draw_lock(surface, (night_btn.right - 18, night_btn.top + 18), 18)


# ----------------------------------------------------------------------------
class LevelSelectState(_MenuBase):
    def enter(self, **kwargs):
        from levels.map_parser import list_levels
        self.engine = self.machine.engine
        audio.play_music("background_music")  # resume BGM after coming back from a level
        self.mode = kwargs.get("mode", "normal")
        self.level_paths = list_levels(_LEVELS_DIR, self.mode)
        self.max_unlocked = self._compute_max_unlocked()

        cx = config.SCREEN_WIDTH // 2
        # Back button only — level tiles are custom-drawn (not Buttons).
        self._buttons = [
            Button(pygame.Rect(cx - 90, 478, 180, 36), "Back",
                   on_click=self._back)
        ]
        # Custom tile state.
        n = max(1, len(self.level_paths))
        self.tile_selected = 0
        self._build_tile_rects()
        self._selected_idx = 0  # 0 = tile area (handled separately), else Back

    def _compute_max_unlocked(self) -> int:
        if self.mode == "normal":
            return self.engine.save_data.get("max_normal_level", 1)
        # nightmare: GDD §5.3
        return save_mgr.nightmare_unlocked_count(self.engine.save_data)

    def _build_tile_rects(self) -> None:
        n = len(self.level_paths)
        if n == 0:
            self.tile_rects = []
            self.tile_font_size = 22
            return
        cols = min(n, 6)
        rows = (n + cols - 1) // cols

        # Available vertical space between the header area and the Back
        # button. Tile size shrinks automatically once we exceed 12 levels
        # so a full 6x4 grid (24 tiles) still fits on screen.
        available_h = 250
        gap = 10
        tile_h = min(80, (available_h - (rows - 1) * gap) // rows)
        tile_size = max(44, tile_h)
        # Pick a readable label size for the chosen tile size.
        self.tile_font_size = 22 if tile_size >= 70 else 18 if tile_size >= 56 else 14

        cx = config.SCREEN_WIDTH // 2
        total_w = cols * tile_size + (cols - 1) * gap
        start_x = cx - total_w // 2
        # Vertically anchor the grid so it stays roughly centred regardless of row count.
        total_h = rows * tile_size + (rows - 1) * gap
        start_y = 200 + max(0, (available_h - total_h) // 2)

        self.tile_rects: list[pygame.Rect] = []
        for i in range(n):
            r = i // cols
            c = i % cols
            x = start_x + c * (tile_size + gap)
            y = start_y + r * (tile_size + gap)
            self.tile_rects.append(pygame.Rect(x, y, tile_size, tile_size))

    def _back(self):
        self.machine.change_to(ModeSelectState(self.machine))

    def _launch(self, idx: int) -> None:
        if not self.level_paths or idx >= len(self.level_paths):
            return
        if idx + 1 > self.max_unlocked:
            return  # locked
        # Dedicated "match-starting" sting that replaces the generic UI click
        # whenever a level tile is the trigger.
        audio.play_sfx("game-start")
        from states.play_state import PlayState
        self.machine.change_to(
            PlayState(self.machine),
            level_path=self.level_paths[idx],
            mode=self.mode,
        )

    def handle_event(self, event):
        # Pass-through to Back button.
        super().handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.tile_rects):
                if rect.collidepoint(event.pos):
                    self._launch(i)
                    return
        if event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.tile_rects):
                if rect.collidepoint(event.pos):
                    self.tile_selected = i
                    return

    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            self._back()
            return
        n = len(self.tile_rects)
        if n and key in (pygame.K_LEFT, pygame.K_a):
            self.tile_selected = (self.tile_selected - 1) % n
        elif n and key in (pygame.K_RIGHT, pygame.K_d):
            self.tile_selected = (self.tile_selected + 1) % n
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._launch(self.tile_selected)

    def draw(self, surface):
        mode_label = "NORMAL" if self.mode == "normal" else "NIGHTMARE"
        self._draw_background(surface, "LEVEL SELECT", mode_label)

        if not self.level_paths:
            msg = self.engine.font_sm.render(
                f"No levels found in levels/data/{self.mode}/",
                True, config.COLOR_SPIKE
            )
            surface.blit(msg, msg.get_rect(
                center=(config.SCREEN_WIDTH // 2, 260)
            ))
            self._draw_buttons()
            return

        for i, rect in enumerate(self.tile_rects):
            level_id = i + 1
            unlocked = level_id <= self.max_unlocked
            # "Cleared" = beaten this level. max_unlocked tracks the *next*
            # level the player still has to clear, so anything strictly
            # below it is already cleared.
            cleared = level_id < self.max_unlocked
            is_sel = (i == self.tile_selected)
            if cleared:
                bg = (24, 36, 28)
                border = (90, 230, 130)
            elif unlocked:
                bg = (22, 24, 38)
                border = (60, 220, 200)
            else:
                bg = (18, 18, 26)
                border = (90, 90, 110)
            if is_sel:
                border = (255, 220, 60)
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, border, rect, 2, border_radius=6)
            pygame.draw.rect(surface, (10, 10, 18),
                             rect.inflate(-6, -6), 1, border_radius=4)
            if unlocked:
                tile_font = (self.engine.font_md if self.tile_font_size >= 22
                             else self.engine.font_sm)
                label = tile_font.render(
                    str(level_id), True, config.COLOR_TEXT
                )
                surface.blit(label, label.get_rect(center=rect.center))
                # Green check tucked into the top-right corner. The size
                # tracks tile width / 6 so it never crowds the level number
                # on small tiles (we saw "20" + check touching at 55 px).
                if cleared:
                    check_size = max(8, min(14, rect.width // 6))
                    cx_pos = rect.right - check_size // 2 - 4
                    cy_pos = rect.top + check_size // 2 + 4
                    draw_check(surface, (cx_pos, cy_pos), size=check_size)
            else:
                lock_size = max(14, min(22, rect.width // 3))
                draw_lock(surface, rect.center, lock_size,
                          color=(160, 160, 190))

        self._draw_buttons()
        hint = self.engine.font_sm.render(
            "Click a tile or LEFT/RIGHT + ENTER   |   ESC back",
            True, config.COLOR_TEXT_DIM,
        )
        surface.blit(hint, hint.get_rect(
            center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT - 28)
        ))
