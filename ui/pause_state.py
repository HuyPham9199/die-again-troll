"""In-game pause overlay.

Pushed on top of PlayState when the player presses ESC during gameplay.
While this state is current the FSM doesn't tick PlayState, so the level
freezes — the snapshot captured in `enter()` is used as a dimmed backdrop.

Contents (no auth here — that lives in SettingsState):
  * Read-only "Playing as …" line so the player sees whose progress is being
    saved.
  * Music + SFX sliders (live preview, so volume tweaks are audible).
  * Show/Hide FPS toggle.
  * Resume button (also ESC).
  * Exit Level — pops the pause overlay AND replaces PlayState with the
    Level Select for the current mode.
"""
from __future__ import annotations

import pygame

import config
from core.fsm import State
from systems import audio, save_mgr
from ui.widgets import Button, Slider, draw_card


CARD_W = 460
CARD_H = 400


class PauseState(State):
    def enter(self, **kwargs):
        self.engine = self.machine.engine
        self.settings = save_mgr.get_settings(self.engine.save_data)
        # Snapshot the last gameplay frame to use as a frozen backdrop.
        # `engine.screen` still holds the previous flip's content at this
        # point — we copy it before the next fill().
        self.snapshot = self.engine.screen.copy()

        cx = config.SCREEN_WIDTH // 2
        self.card_top = (config.SCREEN_HEIGHT - CARD_H) // 2
        self.card_rect = pygame.Rect(
            cx - CARD_W // 2, self.card_top, CARD_W, CARD_H,
        )

        self._build_widgets(cx)

        # While paused we let the lobby BGM play so the player can hear
        # volume changes while sliding. On resume we silence it again so
        # gameplay stays tense.
        audio.play_music("background_music")

    # ------------------------------------------------------------------
    def _build_widgets(self, cx: int) -> None:
        ct = self.card_top

        # Audio sliders inside the card. Track centerx == card centerx so
        # the (- track +) assembly *and* the centred label both line up
        # vertically with the rest of the card content. Width is tuned so
        # the value readout on the right still fits inside the card.
        slider_w = 200
        slider_x = cx - slider_w // 2
        self.music_slider = Slider(
            pygame.Rect(slider_x, ct + 142, slider_w, 14),
            "MUSIC",
            int(self.settings.get("music_volume", 60)),
            on_change=lambda v: self._set_setting("music_volume", v),
        )
        self.sfx_slider = Slider(
            pygame.Rect(slider_x, ct + 192, slider_w, 14),
            "SFX",
            int(self.settings.get("sfx_volume", 80)),
            on_change=lambda v: self._set_setting("sfx_volume", v),
        )

        # FPS toggle row.
        self.fps_btn = Button(
            pygame.Rect(cx + 80, ct + 244, 130, 32),
            self._fps_label(),
            on_click=self._toggle_fps,
        )

        # Bottom buttons: Resume left, Exit Level right.
        btn_w = 180
        btn_h = 42
        gap = 16
        total_w = btn_w * 2 + gap
        start_x = cx - total_w // 2
        self.resume_btn = Button(
            pygame.Rect(start_x, ct + CARD_H - btn_h - 24, btn_w, btn_h),
            "Resume", on_click=self._resume,
            accent=(60, 220, 200),
        )
        self.exit_btn = Button(
            pygame.Rect(start_x + btn_w + gap,
                        ct + CARD_H - btn_h - 24, btn_w, btn_h),
            "Exit Level", on_click=self._exit_level,
            accent=(255, 120, 140),
        )

    def _fps_label(self) -> str:
        return "FPS: ON" if self.settings.get("show_fps", True) else "FPS: OFF"

    # ------------------------------------------------------------------
    def _set_setting(self, key: str, value):
        self.settings[key] = value
        save_mgr.save(self.engine.save_data)
        if key in ("music_volume", "sfx_volume"):
            audio.apply_settings(self.settings)

    def _toggle_fps(self):
        self._set_setting("show_fps",
                          not self.settings.get("show_fps", True))
        self.fps_btn.text = self._fps_label()

    def _resume(self):
        # Drop the lobby BGM we started for the pause, then pop back to
        # PlayState (which is still alive underneath).
        audio.stop_music(fade_ms=200)
        self.machine.pop()

    def _exit_level(self):
        # Pop pause first so the FSM is back on PlayState briefly, then
        # ask the play state for the mode we were running, then switch
        # to the matching LevelSelect.
        self.machine.pop()
        play = self.machine.current
        mode = getattr(play, "mode", "normal")
        from ui.menus import LevelSelectState
        self.machine.change_to(LevelSelectState(self.machine), mode=mode)

    # ------------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._resume()
            return
        self.music_slider.handle_event(event)
        self.sfx_slider.handle_event(event)
        self.fps_btn.handle_event(event)
        self.resume_btn.handle_event(event)
        self.exit_btn.handle_event(event)

    def update(self, dt):
        # Update widget caret/animations only; gameplay is frozen.
        pass

    # ------------------------------------------------------------------
    def draw(self, surface):
        # Frozen gameplay frame as the backdrop, dimmed.
        surface.blit(self.snapshot, (0, 0))
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((6, 8, 16, 175))
        surface.blit(dim, (0, 0))

        engine = self.engine
        cx = config.SCREEN_WIDTH // 2
        draw_card(surface, self.card_rect)

        # Title
        title = engine.font_lg.render("PAUSED", True, config.COLOR_PLAYER)
        surface.blit(title, title.get_rect(
            center=(cx, self.card_top + 46)
        ))

        # Divider under the title.
        pygame.draw.line(
            surface, (70, 90, 130),
            (self.card_rect.left + 28, self.card_top + 82),
            (self.card_rect.right - 28, self.card_top + 82), 1,
        )

        # "Playing as @username" / "Playing as guest"
        sd = engine.save_data
        who = sd.get("username")
        if who:
            line = f"Playing as @{who}"
            color = (160, 220, 200)
        else:
            line = "Playing as guest — progress saves locally only"
            color = config.COLOR_TEXT_DIM
        who_surf = engine.font_sm.render(line, True, color)
        surface.blit(who_surf, who_surf.get_rect(
            center=(cx, self.card_top + 105)
        ))

        # Sliders
        self.music_slider.draw(surface, engine.font_sm, engine.font_sm)
        self.sfx_slider.draw(surface, engine.font_sm, engine.font_sm)

        # FPS toggle row — label on left, button on right.
        fps_label_surf = engine.font_sm.render(
            "Show FPS counter", True, config.COLOR_TEXT,
        )
        surface.blit(fps_label_surf, (
            self.card_rect.left + 28,
            self.fps_btn.rect.centery - fps_label_surf.get_height() // 2,
        ))
        self.fps_btn.draw(surface, engine.font_md)

        # Bottom buttons.
        self.resume_btn.draw(surface, engine.font_md)
        self.exit_btn.draw(surface, engine.font_md)
