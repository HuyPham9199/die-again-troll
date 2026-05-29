"""Game engine — main loop, fixed-clock dt, event pumping.

The engine owns the StateMachine and shared services (asset cache, particle
pool, save manager). States read these via `engine.<service>`.
"""
from __future__ import annotations

import sys

import pygame

import config
from core.fsm import StateMachine
from systems import audio, save_mgr
from ui.branding import make_logo


class Engine:
    def __init__(self):
        pygame.init()
        audio.init()
        pygame.display.set_caption(config.TITLE)
        try:
            pygame.display.set_icon(make_logo(32))
        except Exception:
            pass
        # Display starts windowed; BootState reads the saved setting and
        # may switch to fullscreen once save.dat is loaded.
        self.display_mode = "windowed"
        self.screen = self._make_display(self.display_mode)
        self.clock = pygame.time.Clock()
        self.running = True

        self.fsm = StateMachine(engine=self)
        # Slot for save data loaded by BootState.
        self.save_data: dict = {}

        # Services attached lazily by states that need them, to keep imports
        # cheap during Boot.
        self.particle_pool = None
        self.save_mgr = None
        # Two FPS values: a live one (updated every frame) used internally
        # and a smoothed integer that refreshes only every FPS_REFRESH_SECONDS
        # so the HUD doesn't flicker.
        self.current_fps = 0.0
        self.display_fps = 0
        self._fps_acc = 0.0
        self._fps_sample_t = 0.0

        # Fonts — single sans-serif, two sizes is enough for now.
        self.font_lg = pygame.font.SysFont("Consolas", 42, bold=True)
        self.font_md = pygame.font.SysFont("Consolas", 22, bold=True)
        self.font_sm = pygame.font.SysFont("Consolas", 16)

    def quit(self) -> None:
        self.running = False

    # ----- Display mode --------------------------------------------------
    def _make_display(self, mode: str):
        """Create the display surface for the requested mode.

        Both modes use a fixed 960x540 logical resolution; fullscreen lets
        pygame's SCALED flag upscale to the native monitor resolution while
        keeping coordinates inside the game unchanged.
        """
        size = (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        if mode == "fullscreen":
            try:
                return pygame.display.set_mode(
                    size, pygame.FULLSCREEN | pygame.SCALED
                )
            except pygame.error:
                # Some SDL backends (e.g. the dummy driver used in CI) don't
                # support SCALED — fall back to a normal window.
                return pygame.display.set_mode(size)
        return pygame.display.set_mode(size)

    def set_display_mode(self, mode: str) -> None:
        if mode not in ("windowed", "fullscreen"):
            return
        if mode == self.display_mode:
            return
        self.display_mode = mode
        self.screen = self._make_display(mode)

    def toggle_fullscreen(self) -> None:
        new = "fullscreen" if self.display_mode == "windowed" else "windowed"
        self.set_display_mode(new)
        # Persist so the choice survives the next launch.
        if self.save_data:
            save_mgr.get_settings(self.save_data)["display_mode"] = new
            save_mgr.save(self.save_data)

    def run(self, initial_state) -> None:
        self.fsm.change_to(initial_state)

        while self.running:
            # Cap dt to 50ms — prevents tunneling after a window-drag pause.
            dt = min(self.clock.tick(config.FPS_CAP) / 1000.0, 0.05)
            self.current_fps = self.clock.get_fps()

            # Accumulate FPS samples and refresh the HUD readout every
            # FPS_REFRESH_SECONDS — keeps the number stable enough to read.
            self._fps_sample_t += dt
            self._fps_acc += self.current_fps
            samples = max(1, int(self._fps_sample_t * config.FPS_CAP))
            if self._fps_sample_t >= config.FPS_REFRESH_SECONDS:
                self.display_fps = int(round(self._fps_acc / samples))
                self._fps_sample_t = 0.0
                self._fps_acc = 0.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif (event.type == pygame.KEYDOWN
                      and event.key == pygame.K_F11):
                    # F11 toggles fullscreen at engine level — works in
                    # any state, doesn't need each State to wire it.
                    self.toggle_fullscreen()
                else:
                    self.fsm.handle_event(event)

            self.fsm.update(dt)

            self.screen.fill(config.COLOR_BG)
            self.fsm.draw(self.screen)
            pygame.display.flip()

        # Final save on exit. Covers both the X-button (pygame.QUIT) and
        # the Quit menu option — anything that drops out of the loop.
        self._save_on_exit()
        pygame.quit()
        sys.exit(0)

    def _save_on_exit(self) -> None:
        """Persist save_data, and push to cloud DB if a user is logged in."""
        if not self.save_data:
            return
        try:
            save_mgr.save(self.save_data)
        except Exception:
            return  # disk full / permission denied — nothing useful we can do
        user_id = self.save_data.get("user_id")
        if user_id:
            try:
                from systems import auth_db
                auth_db.sync_progress(user_id, self.save_data)
            except Exception:
                # Cloud DB is optional. If sync fails (no network, schema
                # mismatch, etc.) we keep the local save and move on.
                pass
