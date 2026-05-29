"""SettingsState — account, audio, display.

Layout uses externally-positioned panels (no inner title) plus separate
section headers so labels never collide with a panel's title underline.
"""
from __future__ import annotations

import pygame

import config
from core.fsm import State
from systems import audio, auth_db, save_mgr
from ui.widgets import Button, Slider, draw_panel, draw_starfield


# Vertical anchors for the page — change ONE place, layout reflows.
PAGE_TITLE_Y = 24
SECT_ACCOUNT_Y = 74
SECT_AUDIO_Y = 174
SECT_DISPLAY_Y = 320
BACK_Y = 502

PANEL_X = 80
PANEL_W = 800
# Distance from a section header's top to the panel start.
HEADER_TO_PANEL = 22
# Panel heights tuned to fit content + breathing room.
AUDIO_PANEL_H = 116
DISPLAY_PANEL_H = 144  # holds 3 toggle rows


class SettingsState(State):
    def __init__(self, machine, back_to):
        super().__init__(machine)
        self._back_to = back_to
        self._anim_t = 0.0

    def enter(self, **kwargs):
        self.engine = self.machine.engine
        self.settings = save_mgr.get_settings(self.engine.save_data)
        audio.play_music("background_music")  # ensures BGM resumes if we got here from PlayState
        self._build_widgets()

    # ------------------------------------------------------------------
    def _build_widgets(self):
        cx = config.SCREEN_WIDTH // 2

        # --- Account panel ----------------------------------------------
        # y range derived from SECT_ACCOUNT_Y + HEADER_TO_PANEL down 72 px.
        acct_top = SECT_ACCOUNT_Y + HEADER_TO_PANEL
        # Sign-in / Sign-out button (right side, vertically centred to panel).
        self.login_btn = Button(
            pygame.Rect(PANEL_X + PANEL_W - 184, acct_top + 18, 168, 36),
            "Sign in",
            on_click=self._login_clicked,
        )

        # --- Audio sliders (Music + SFX only) --------------------------
        audio_top = SECT_AUDIO_Y + HEADER_TO_PANEL
        slider_w = 280
        slider_x = cx - 50
        slider_y0 = audio_top + 34
        gap = 56
        s_music = Slider(
            pygame.Rect(slider_x, slider_y0, slider_w, 14),
            "MUSIC",
            int(self.settings.get("music_volume", 60)),
            on_change=lambda v: self._set_setting("music_volume", v),
        )
        s_sfx = Slider(
            pygame.Rect(slider_x, slider_y0 + gap, slider_w, 14),
            "SFX",
            int(self.settings.get("sfx_volume", 80)),
            on_change=lambda v: self._set_setting("sfx_volume", v),
        )
        self.sliders = [s_music, s_sfx]

        # --- Display: 3 stacked rows -----------------------------------
        # row1 = resolution mode, row2 = FPS, row3 = touch.
        disp_top = SECT_DISPLAY_Y + HEADER_TO_PANEL
        row_y0 = disp_top + 14
        row_h = 36
        # Buttons sit right-aligned inside the panel.
        btn_w = 220
        btn_x = PANEL_X + PANEL_W - 20 - btn_w
        self.mode_btn = Button(
            pygame.Rect(btn_x, row_y0, btn_w, 32),
            self._mode_label(),
            on_click=self._toggle_mode,
        )
        self.fps_btn = Button(
            pygame.Rect(btn_x, row_y0 + row_h, btn_w, 32),
            self._fps_label(),
            on_click=self._toggle_fps,
        )
        self.mobile_btn = Button(
            pygame.Rect(btn_x, row_y0 + row_h * 2, btn_w, 32),
            self._mobile_label(),
            on_click=self._toggle_mobile,
        )

        # --- Back -------------------------------------------------------
        cx = config.SCREEN_WIDTH // 2
        self.back_btn = Button(
            pygame.Rect(cx - 90, BACK_Y, 180, 36),
            "Back",
            on_click=self._back,
        )

    # ------------------------------------------------------------------
    def _fps_label(self) -> str:
        return "ON" if self.settings.get("show_fps", True) else "OFF"

    def _mobile_label(self) -> str:
        return "ON" if self.settings.get("show_mobile_controls", False) else "OFF"

    def _mode_label(self) -> str:
        m = self.settings.get("display_mode", "windowed")
        return "FULLSCREEN" if m == "fullscreen" else "WINDOWED 16:9"

    def _toggle_fps(self):
        self._set_setting("show_fps", not self.settings.get("show_fps", True))
        self.fps_btn.text = self._fps_label()

    def _toggle_mobile(self):
        self._set_setting("show_mobile_controls",
                          not self.settings.get("show_mobile_controls", False))
        self.mobile_btn.text = self._mobile_label()

    def _toggle_mode(self):
        cur = self.settings.get("display_mode", "windowed")
        new = "fullscreen" if cur == "windowed" else "windowed"
        self._set_setting("display_mode", new)
        self.engine.set_display_mode(new)
        self.mode_btn.text = self._mode_label()

    def _login_clicked(self):
        if self.engine.save_data.get("username"):
            auth_db.logout(self.engine.save_data)
            save_mgr.save(self.engine.save_data)
            self.login_btn.text = "Sign in"
            return
        from ui.auth_state import AuthState
        self.machine.change_to(AuthState(self.machine,
                                         back_to=SettingsState._reentry))

    @staticmethod
    def _reentry(machine):
        from ui.menus import MainMenuState
        return SettingsState(machine, back_to=MainMenuState)

    def _set_setting(self, key: str, value):
        self.settings[key] = value
        save_mgr.save(self.engine.save_data)
        # Re-apply volumes immediately so the slider gives instant feedback.
        if key in ("master_volume", "music_volume", "sfx_volume"):
            audio.apply_settings(self.settings)

    def _back(self):
        self.machine.change_to(self._back_to(self.machine))

    # ------------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()
            return
        self.login_btn.handle_event(event)
        self.mode_btn.handle_event(event)
        self.fps_btn.handle_event(event)
        self.mobile_btn.handle_event(event)
        self.back_btn.handle_event(event)
        for s in self.sliders:
            s.handle_event(event)

    def update(self, dt):
        self._anim_t += dt

    # ------------------------------------------------------------------
    def draw(self, surface):
        draw_starfield(surface, self._anim_t)
        engine = self.engine
        cx = config.SCREEN_WIDTH // 2

        # Page title.
        title = engine.font_lg.render("SETTINGS", True, config.COLOR_PLAYER)
        surface.blit(title, title.get_rect(center=(cx, PAGE_TITLE_Y + 26)))

        # ---- ACCOUNT section ----
        self._draw_section_header(surface, "ACCOUNT", SECT_ACCOUNT_Y)
        acct_top = SECT_ACCOUNT_Y + HEADER_TO_PANEL
        acct_rect = pygame.Rect(PANEL_X, acct_top, PANEL_W, 72)
        draw_panel(surface, acct_rect)   # no title arg → no overlap risk
        sd = engine.save_data
        if sd.get("username"):
            who = engine.font_md.render(sd["username"], True, config.COLOR_TEXT)
            email_text = sd.get("email") or "—"
            email = engine.font_sm.render(email_text, True, config.COLOR_TEXT_DIM)
            surface.blit(who, (acct_rect.x + 20, acct_rect.y + 12))
            surface.blit(email, (acct_rect.x + 20, acct_rect.y + 42))
            self.login_btn.text = "Sign out"
        else:
            note = engine.font_sm.render(
                "Not signed in — progress saves locally only.",
                True, config.COLOR_TEXT_DIM,
            )
            surface.blit(note, (acct_rect.x + 20,
                                acct_rect.y + (acct_rect.height - note.get_height()) // 2))
            self.login_btn.text = "Sign in"
        self.login_btn.draw(surface, engine.font_md)

        # ---- AUDIO section ----
        self._draw_section_header(surface, "AUDIO", SECT_AUDIO_Y)
        audio_top = SECT_AUDIO_Y + HEADER_TO_PANEL
        audio_rect = pygame.Rect(PANEL_X, audio_top, PANEL_W, AUDIO_PANEL_H)
        draw_panel(surface, audio_rect)
        for s in self.sliders:
            s.draw(surface, engine.font_sm, engine.font_sm)

        # ---- DISPLAY section ----
        self._draw_section_header(surface, "DISPLAY", SECT_DISPLAY_Y)
        disp_top = SECT_DISPLAY_Y + HEADER_TO_PANEL
        disp_rect = pygame.Rect(PANEL_X, disp_top, PANEL_W, DISPLAY_PANEL_H)
        draw_panel(surface, disp_rect)

        rows = (
            ("Resolution",        self.mode_btn),
            ("Show FPS counter",  self.fps_btn),
            ("Touch controls",    self.mobile_btn),
        )
        for label_text, btn in rows:
            lbl = engine.font_sm.render(label_text, True, config.COLOR_TEXT)
            surface.blit(lbl, (disp_rect.x + 22,
                               btn.rect.centery - lbl.get_height() // 2))
            btn.draw(surface, engine.font_md)

        # Back button.
        self.back_btn.draw(surface, engine.font_md)

    # ------------------------------------------------------------------
    def _draw_section_header(self, surface, text: str, y: int) -> None:
        engine = self.engine
        lbl = engine.font_md.render(text, True, (180, 220, 230))
        surface.blit(lbl, (PANEL_X, y))
        # Cyan accent underline that stretches a fixed length, like a tab indicator.
        underline_y = y + lbl.get_height() + 2
        pygame.draw.line(
            surface, (60, 220, 200),
            (PANEL_X, underline_y),
            (PANEL_X + lbl.get_width() + 12, underline_y), 2,
        )
