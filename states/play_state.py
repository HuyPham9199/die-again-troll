"""PlayState — the actual game.

Runs the player update loop, trap checks, camera, particles. Owns the
current `LevelData`. Transitions out to GameOver or Victory.
"""
from __future__ import annotations

import pygame

import config
from core.camera import Camera
from core.fsm import State
from entities.player import Player
from entities.portal import Portal
from levels.map_parser import LevelData, load_level
from systems import audio, save_mgr
from ui.mobile_controls import MobileControls


class PlayState(State):
    def enter(self, **kwargs):
        self.engine = self.machine.engine
        self.level_path: str = kwargs["level_path"]
        self.mode: str = kwargs.get("mode", "normal")
        self.level: LevelData = load_level(self.level_path)

        self.player = Player(*self.level.player_spawn_px)
        self.portal = Portal(self.level.goal_rect)
        self.camera = Camera(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.camera.world_bounds = pygame.Rect(
            0, 0, self.level.world_w, self.level.world_h
        )
        self.camera.set_target(*self.player.rect.center, snap=True)

        self.deaths_this_level = 0
        self.input_left = False
        self.input_right = False
        self.show_debug = False   # F1 toggles trigger overlay
        self.paused = False
        self.victory = False
        self.victory_timer = 0.0
        # dt-counted; ticks down in update() while the player is dead.
        self.respawn_timer = 0.0

        # Touch controls — visibility driven by the settings flag.
        self.mobile = MobileControls()
        settings = save_mgr.get_settings(self.engine.save_data)
        self.mobile.visible = bool(settings.get("show_mobile_controls", False))

        # No music during gameplay — silence keeps the troll moments tense.
        # Lobby BGM resumes when the player returns to LevelSelect / Menu.
        audio.stop_music(fade_ms=300)

    # ---------------------------------------------------------------- input
    def handle_event(self, event):
        # Touch buttons take priority — they swallow the mouse event if
        # one fired, so a tap doesn't accidentally trip a UI button below.
        if self.mobile.handle_event(event):
            if self.mobile.consume_jump():
                self.player.request_jump()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # ESC opens the in-game pause overlay. PlayState stays on
                # the stack underneath, frozen — pressing ESC again (or
                # clicking Resume) pops the overlay back to gameplay.
                from ui.pause_state import PauseState
                self.machine.push(PauseState(self.machine))
                return
            if event.key == pygame.K_F1:
                self.show_debug = not self.show_debug
            if event.key == pygame.K_r:
                self._reset_player(count_death=False)
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.input_left = True
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.input_right = True
            elif event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                self.player.request_jump()
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.input_left = False
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.input_right = False

    # --------------------------------------------------------------- update
    def update(self, dt):
        # Respawn countdown ticks even when the player is dead.
        if self.respawn_timer > 0:
            self.respawn_timer -= dt
            if self.respawn_timer <= 0 and not self.player.alive and not self.victory:
                self._reset_player(count_death=False)

        if self.victory:
            self.victory_timer += dt
            self.camera.update(dt)
            self.engine.particle_pool.update(dt)
            self.portal.update(dt)
            for fg in self.level.fake_goals:
                fg.update(dt)
            if self.victory_timer > 1.6:
                self._on_victory_finished()
            return

        # ---- Build current solids list (rebuilt each tick) ---------------
        active_solids = list(self.level.solids)
        for ib in self.level.invisible_blocks:
            if ib.solid:
                active_solids.append(ib.rect)
        for ff in self.level.fake_floors:
            if ff.is_solid:
                active_solids.append(ff.rect)
        for cr in self.level.crushers:
            if cr.is_solid:
                active_solids.append(cr.rect)

        # ---- Input vector + reverse-zone flip ----------------------------
        left = self.input_left or self.mobile.left_held
        right = self.input_right or self.mobile.right_held
        ix = (-1 if left else 0) + (1 if right else 0)
        # Touch jump pulse — also accepted here in case it fired during a
        # frame the player wasn't ready (e.g., mid-respawn).
        if self.mobile.consume_jump():
            self.player.request_jump()
        in_reverse = any(rz.active_for(self.player.rect)
                         for rz in self.level.reverse_zones)
        if in_reverse:
            ix = -ix

        # ---- Pre-collision: invisible block head-bump --------------------
        if self.player.vy < 0:
            anticipated = self.player.rect.move(0, int(self.player.vy * dt))
            for ib in self.level.invisible_blocks:
                if not ib.solid and anticipated.colliderect(ib.rect):
                    ib.trigger()
                    active_solids.append(ib.rect)
                    self.camera.add_trauma(0.25)

        # ---- Player tick ------------------------------------------------
        self.player.update(dt, ix, active_solids)

        # ---- Trap triggers + lethal checks ------------------------------
        # Fake floors crumble on first overlap.
        for ff in self.level.fake_floors:
            ff.check(self.player.rect)
            ff.update(dt)

        # Hidden spikes reveal then kill.
        for sp in self.level.hidden_spikes:
            sp.check_reveal(self.player.rect)
            if sp.kills(self.player.rect) and self.player.alive:
                self._kill_player()
                break

        # Ceiling spikes — trigger + fall + kill on contact.
        for cs in self.level.ceiling_spikes:
            cs.maybe_trigger(self.player.rect)
            cs.update(dt, self.level.solids)
            if self.player.alive and cs.kills(self.player.rect):
                self._kill_player()
                break

        # Crushers — wind up, slam, kill if mid-fall on player.
        for cr in self.level.crushers:
            cr.maybe_trigger(self.player.rect)
            cr.update(dt, self.level.solids)
            if self.player.alive and cr.kills(self.player.rect):
                self._kill_player()
                break

        # Fake goals — instant kill on touch.
        for fg in self.level.fake_goals:
            fg.update(dt)
            if self.player.alive and fg.kills(self.player.rect):
                fg.mark_triggered()
                self._kill_player(cause="fake_portal")
                break

        # Fell off the bottom of the world → die.
        if self.player.alive and self.player.rect.top > self.level.world_h + 200:
            self._kill_player()

        # Real goal.
        if self.player.alive and self.player.rect.colliderect(self.level.goal_rect):
            self._on_goal_reached()

        self.camera.set_target(*self.player.rect.center)
        self.camera.update(dt)
        self.engine.particle_pool.update(dt)
        self.portal.update(dt)

    # ----------------------------------------------------------------- draw
    def draw(self, surface):
        # Subtle grid backdrop (only over the visible window).
        self._draw_grid(surface)

        # Tiles — frustum-culled (GDD §6.2).
        c0, c1, r0, r1 = self.camera.visible_tile_range(
            self.level.grid_size, self.level.cols, self.level.rows
        )
        gs = self.level.grid_size
        for s in self.level.solids:
            tc = s.x // gs
            tr = s.y // gs
            if not (c0 <= tc < c1 and r0 <= tr < r1):
                continue
            r = self.camera.apply_rect(s)
            pygame.draw.rect(surface, config.COLOR_SOLID, r)
            pygame.draw.rect(surface, config.COLOR_SOLID_EDGE, r, 1)

        # Fake floors — draw before invisible blocks so a crumble doesn't
        # cover a triggered ib visually.
        for ff in self.level.fake_floors:
            ff.draw(surface, self.camera, debug=self.show_debug)

        # Invisible blocks (drawn only once solid, or in debug).
        for ib in self.level.invisible_blocks:
            ib.draw(surface, self.camera, debug=self.show_debug)

        # Reverse zones — invisible in normal play, tinted overlay in debug.
        for rz in self.level.reverse_zones:
            rz.draw(surface, self.camera, debug=self.show_debug)

        # Hidden spikes (reveal themselves).
        for sp in self.level.hidden_spikes:
            sp.draw(surface, self.camera, debug=self.show_debug)

        # Ceiling spikes + crushers — drawn over tiles, under player.
        for cs in self.level.ceiling_spikes:
            cs.draw(surface, self.camera, debug=self.show_debug)
        for cr in self.level.crushers:
            cr.draw(surface, self.camera, debug=self.show_debug)

        # Fake goals first so the real portal sparkles draw on top of them
        # (gives the real one a *slight* edge on close inspection).
        for fg in self.level.fake_goals:
            fg.draw(surface, self.camera, debug=self.show_debug)
        self.portal.draw(surface, self.camera)

        # Particles, then player.
        self.engine.particle_pool.draw(surface, self.camera)
        self.player.draw(surface, self.camera)

        # HUD.
        self._draw_hud(surface)

        # Mobile controls on top of HUD (never on top of the victory banner).
        self.mobile.draw(surface)

        if self.victory:
            self._draw_victory(surface)

    def _draw_grid(self, surface):
        gs = self.level.grid_size
        ox = -int(self.camera.x) % gs
        oy = -int(self.camera.y) % gs
        for x in range(ox, config.SCREEN_WIDTH, gs):
            pygame.draw.line(surface, config.COLOR_GRID, (x, 0),
                             (x, config.SCREEN_HEIGHT))
        for y in range(oy, config.SCREEN_HEIGHT, gs):
            pygame.draw.line(surface, config.COLOR_GRID, (0, y),
                             (config.SCREEN_WIDTH, y))

    def _draw_hud(self, surface):
        sd = self.engine.save_data
        settings = save_mgr.get_settings(sd)
        mode_tag = "[N]" if self.mode == "normal" else "[!]"
        # Two-line HUD: level info on top, controls hint on a dimmer second
        # line. Splitting prevents a long level name from butting into the
        # FPS counter at top-right.
        line1 = self.engine.font_sm.render(
            f"{mode_tag} Level {self.level.level_id} — {self.level.name}"
            f"   deaths {sd.get('total_deaths', 0)}",
            True, config.COLOR_TEXT,
        )
        line2 = self.engine.font_sm.render(
            "R restart   ESC menu   F1 debug",
            True, config.COLOR_TEXT_DIM,
        )
        surface.blit(line1, (12, 8))
        surface.blit(line2, (12, 30))

        if settings.get("show_fps", True):
            fps_txt = self.engine.font_sm.render(
                f"{self.engine.display_fps:3d} fps",
                True, config.COLOR_GOAL,
            )
            surface.blit(fps_txt,
                         (config.SCREEN_WIDTH - fps_txt.get_width() - 12, 10))

    def _draw_victory(self, surface):
        overlay = pygame.Surface(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 140))
        surface.blit(overlay, (0, 0))
        msg = self.engine.font_lg.render("LEVEL CLEAR", True, config.COLOR_GOAL)
        surface.blit(msg, msg.get_rect(
            center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)
        ))

    # ----------------------------------------------------------------- ops
    def _kill_player(self, cause: str = "generic"):
        if not self.player.alive:
            return
        self.player.kill()
        save_mgr.record_death(self.engine.save_data)
        save_mgr.save(self.engine.save_data)
        self.deaths_this_level += 1
        self.engine.particle_pool.burst(
            self.player.rect.centerx, self.player.rect.centery,
            count=32, color=config.COLOR_PLAYER, speed=420.0, life=0.7,
        )
        self.camera.add_trauma(0.85)
        # Single death cue regardless of cause — matches the user's
        # supplied `die.mp3`. Fake-portal-specific sting can be added
        # later by dropping `fake_portal.mp3` into the sfx folder and
        # branching on `cause` here.
        audio.play_sfx("die")
        self.respawn_timer = 0.6

    def _reset_player(self, count_death: bool):
        self.player.respawn()
        # Reset every trigger so the level is fully replayable.
        for ib in self.level.invisible_blocks:
            ib.solid = False
            ib.state = ib.STATE_IDLE
        for sp in self.level.hidden_spikes:
            sp.revealed = False
            sp.state = sp.STATE_IDLE
        for ff in self.level.fake_floors:
            ff.reset()
        for cs in self.level.ceiling_spikes:
            cs.reset()
        for cr in self.level.crushers:
            cr.reset()
        for fg in self.level.fake_goals:
            fg.reset()
        if count_death:
            save_mgr.record_death(self.engine.save_data)

    def _on_goal_reached(self):
        if self.victory:
            return
        self.victory = True
        self.victory_timer = 0.0
        audio.play_sfx("winner")
        save_mgr.record_level_complete(self.engine.save_data, self.level.level_id,
                                       mode=self.mode)
        save_mgr.save(self.engine.save_data)
        # Push to cloud DB if signed in. Best-effort: a network/DB error
        # mustn't ruin the level-clear moment.
        uid = self.engine.save_data.get("user_id")
        if uid:
            try:
                from systems import auth_db
                auth_db.sync_progress(uid, self.engine.save_data)
            except Exception:
                pass
        self.engine.particle_pool.burst(
            self.level.goal_rect.centerx, self.level.goal_rect.centery,
            count=48, color=config.COLOR_GOAL, speed=380.0, life=0.9,
        )
        self.camera.add_trauma(0.4)

    def _on_victory_finished(self):
        from ui.menus import LevelSelectState
        self.machine.change_to(LevelSelectState(self.machine))
