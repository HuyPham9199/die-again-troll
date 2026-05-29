"""AuthState — Sign in / Register form backed by systems.auth_db.

Card-based modern layout: single centred card with a pill-style tab toggle,
tightly-spaced label/input pairs and a full-width Submit. The legacy starfield
backdrop still drifts behind but is dimmed so the card is clearly the focus.
"""
from __future__ import annotations

import pygame

import config
from core.fsm import State
from systems import audio, auth_db, save_mgr
from ui.branding import make_logo
from ui.widgets import Button, TextField, draw_card, draw_starfield


CARD_W = 460
# Heights are derived from internal padding constants; recompute if FIELD_GAP
# changes. Login is 2 fields, register is 3.
CARD_H_LOGIN = 320
CARD_H_REGISTER = 396
CARD_TOP = 100


class AuthState(State):
    def __init__(self, machine, back_to):
        super().__init__(machine)
        self._back_to = back_to
        self._anim_t = 0.0
        self.mode = "login"
        self.message = ""
        self.message_ok = False
        self._auto_back_in = 0.0

    # ------------------------------------------------------------------
    def enter(self, **kwargs):
        self.engine = self.machine.engine
        self._logo = make_logo(48)
        audio.play_music("background_music")
        # Pull the last-used username from local save so the form is
        # pre-filled and the user only has to type their password.
        last = self.engine.save_data.get("last_username") or ""
        self._carry_username = last
        self._carry_password = ""
        self._carry_email = ""
        self._build_layout()
        # If we pre-filled the username, focus the password field so the
        # user can just start typing instead of arrowing past the name.
        if last:
            self.username.set_focus(False)
            self.password.set_focus(True)

    def _build_layout(self):
        cx = config.SCREEN_WIDTH // 2
        card_h = CARD_H_REGISTER if self.mode == "register" else CARD_H_LOGIN
        # Fixed top anchor — switching modes shouldn't make the card jump.
        self.card_rect = pygame.Rect(
            cx - CARD_W // 2, CARD_TOP, CARD_W, card_h,
        )

        pad = 28
        inner_x = self.card_rect.left + pad
        inner_w = CARD_W - pad * 2

        # Tab pill (single rounded rect split in two halves).
        self.tab_y = self.card_rect.top + pad
        self.tab_rect = pygame.Rect(
            self.card_rect.centerx - 120, self.tab_y, 240, 36,
        )

        # Form fields. Each label occupies ~24px above its input; the gap
        # constant below is the spacing between one input's bottom and the
        # next input's top (covers the next field's label).
        FIELD_H = 40
        # Each label is ~19 px high + 8 px breathing room, so the gap
        # between the previous input's bottom and the next input's top
        # has to be at least 27 px or the label clips into the field above.
        FIELD_GAP = 36
        y = self.tab_y + 36 + 32  # tab height + gap to first field
        self.username = TextField(
            pygame.Rect(inner_x, y, inner_w, FIELD_H),
            label="USERNAME", max_len=24, on_submit=self._submit,
        )
        y += FIELD_H + FIELD_GAP
        self.password = TextField(
            pygame.Rect(inner_x, y, inner_w, FIELD_H),
            label="PASSWORD", max_len=32, password=True,
            on_submit=self._submit,
        )
        y += FIELD_H            # bottom of password
        if self.mode == "register":
            y += FIELD_GAP
            self.email = TextField(
                pygame.Rect(inner_x, y, inner_w, FIELD_H),
                label="EMAIL (optional)", max_len=64,
                on_submit=self._submit,
            )
            y += FIELD_H
        else:
            # Still construct an off-screen email field so handle_event/draw
            # code paths that touch it don't have to special-case None.
            self.email = TextField(
                pygame.Rect(-9999, -9999, 1, 1), label="", on_submit=self._submit,
            )

        # Message line + submit, anchored to where the fields actually end.
        self.message_y = y + 18
        self.submit_btn = Button(
            pygame.Rect(inner_x, y + 32, inner_w, 44),
            "Submit", on_click=self._submit, accent=(60, 220, 200),
        )

        # Small ghost Back at top-left — doubles as "continue as guest".
        self.back_btn = Button(
            pygame.Rect(28, 24, 100, 32), "← Back",
            on_click=self._back, accent=(120, 130, 170),
        )

        # Preserve any in-progress field state across mode switches.
        if hasattr(self, "_carry_username"):
            self.username.text = self._carry_username
            self.password.text = self._carry_password
            self.email.text = self._carry_email

        self.username.set_focus(True)
        self._fields = [self.username, self.password, self.email]

    # ------------------------------------------------------------------
    def _set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        # Carry the typed values across the rebuild.
        self._carry_username = self.username.text
        self._carry_password = self.password.text
        self._carry_email = self.email.text if mode == "register" else ""
        self.mode = mode
        self.message = ""
        self._build_layout()

    def _submit(self) -> None:
        u = self.username.text.strip()
        p = self.password.text
        e = self.email.text.strip() or None
        if self.mode == "login":
            user, err = auth_db.login(u, p)
            if err or not user:
                self.message = err or "Login failed."
                self.message_ok = False
                return
            auth_db.apply_login_to_save(self.engine.save_data, user)
            save_mgr.save(self.engine.save_data)
            self.message = f"Welcome back, {user['username']}."
            self.message_ok = True
            self._auto_back_in = 0.7
        else:
            user, err = auth_db.register(u, p, e)
            if err or not user:
                self.message = err or "Registration failed."
                self.message_ok = False
                return
            auth_db.apply_login_to_save(self.engine.save_data, user)
            save_mgr.save(self.engine.save_data)
            self.message = f"Account created — welcome, {user['username']}."
            self.message_ok = True
            self._auto_back_in = 0.8

    def _back(self) -> None:
        self.machine.change_to(self._back_to(self.machine))

    def _focus_next(self) -> None:
        visible = self._fields if self.mode == "register" else self._fields[:2]
        try:
            idx = next(i for i, f in enumerate(visible) if f.focused)
        except StopIteration:
            idx = -1
        for f in visible:
            f.set_focus(False)
        visible[(idx + 1) % len(visible)].set_focus(True)

    # ------------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._back()
                return
            if event.key == pygame.K_TAB:
                self._focus_next()
                return
        # Tab clicks first — clicking a tab shouldn't also focus a field.
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.tab_rect.collidepoint(event.pos):
                if event.pos[0] < self.tab_rect.centerx:
                    self._set_mode("login")
                else:
                    self._set_mode("register")
                return
        for f in (self._fields if self.mode == "register" else self._fields[:2]):
            if f.handle_event(event):
                for other in self._fields:
                    if other is not f:
                        other.set_focus(False)
        self.submit_btn.handle_event(event)
        self.back_btn.handle_event(event)

    def update(self, dt):
        self._anim_t += dt
        for f in self._fields:
            f.update(dt)
        if self._auto_back_in > 0:
            self._auto_back_in -= dt
            if self._auto_back_in <= 0:
                self._back()

    # ------------------------------------------------------------------
    def draw(self, surface):
        # Dimmed starfield behind everything — set the focus on the card.
        draw_starfield(surface, self._anim_t)
        overlay = pygame.Surface(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA
        )
        overlay.fill((10, 12, 20, 140))
        surface.blit(overlay, (0, 0))

        engine = self.engine
        # Title row above the card — small logo + "ACCOUNT" label.
        # Title position is *fixed* (not tied to card top) so the layout
        # doesn't shift on tab switch.
        title_baseline_y = 56
        title_surf = engine.font_lg.render("ACCOUNT", True, config.COLOR_TEXT)
        title_x = config.SCREEN_WIDTH // 2 - title_surf.get_width() // 2 + 26
        logo_rect = self._logo.get_rect(
            midright=(title_x - 12, title_baseline_y + title_surf.get_height() // 2)
        )
        surface.blit(self._logo, logo_rect)
        surface.blit(title_surf, (title_x, title_baseline_y))

        # The card itself.
        draw_card(surface, self.card_rect)

        # Tab pill.
        self._draw_tab_pill(surface)

        # Form fields.
        self.username.draw(surface, engine.font_sm, engine.font_md)
        self.password.draw(surface, engine.font_sm, engine.font_md)
        if self.mode == "register":
            self.email.draw(surface, engine.font_sm, engine.font_md)

        # Message line — placed just above the submit button.
        if self.message:
            color = (90, 230, 130) if self.message_ok else (255, 110, 130)
            ms = engine.font_sm.render(self.message, True, color)
            surface.blit(ms, ms.get_rect(
                center=(self.card_rect.centerx,
                        self.submit_btn.rect.top - 14)
            ))

        self.submit_btn.draw(surface, engine.font_md)
        self.back_btn.draw(surface, engine.font_sm)

    def _draw_tab_pill(self, surface):
        engine = self.engine
        # Background pill — full rounded rect, slightly inset border.
        pygame.draw.rect(surface, (16, 18, 28), self.tab_rect, border_radius=18)
        pygame.draw.rect(surface, (70, 76, 100), self.tab_rect, 1, border_radius=18)

        # Active half — fill in accent.
        half_w = self.tab_rect.width // 2
        active_rect = pygame.Rect(
            self.tab_rect.left + (0 if self.mode == "login" else half_w),
            self.tab_rect.top,
            half_w, self.tab_rect.height,
        )
        accent = (60, 220, 200) if self.mode == "login" else (255, 120, 160)
        pygame.draw.rect(surface, accent, active_rect, border_radius=18)

        # Labels.
        for i, (label, mode) in enumerate(
            (("SIGN IN", "login"), ("REGISTER", "register"))
        ):
            half_center = (
                self.tab_rect.left + half_w // 2 + i * half_w,
                self.tab_rect.centery,
            )
            color = (10, 10, 18) if mode == self.mode else (180, 190, 220)
            ts = engine.font_md.render(label, True, color)
            surface.blit(ts, ts.get_rect(center=half_center))
