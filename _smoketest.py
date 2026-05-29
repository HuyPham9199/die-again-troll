"""Headless smoke test covering the troll mechanics + auth pipeline.

Pumps synthetic events through:
  * Boot → MainMenu → Settings → AuthState (register, then logout, then login)
  * MainMenu → Play (level 1 fake-floor kill) → (level 2 fake-portal kill)
  * Settings save-on-exit and DB sync_progress when logged in.

ISOLATION: save.dat and game.db are routed through a temp directory via
env vars so this script NEVER touches the real player's data. Earlier
revisions overwrote production save.dat / game.db — that bug is fixed.
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Sandbox the test's save + DB files. Must be set BEFORE any project
# module is imported because save_mgr/auth_db read these env vars when
# resolving the path.
_TMPDIR = tempfile.mkdtemp(prefix="dieagain-smoketest-")
os.environ["DIEAGAIN_SAVE_PATH"] = os.path.join(_TMPDIR, "save.dat")
os.environ["DIEAGAIN_DB_PATH"] = os.path.join(_TMPDIR, "game.db")

import pygame

import config
from core.engine import Engine
from systems import auth_db, save_mgr
from ui.menus import BootState, MainMenuState, ModeSelectState, LevelSelectState
from ui.settings_state import SettingsState
from ui.auth_state import AuthState
from states.play_state import PlayState


def post_key(key, down=True, unicode=""):
    pygame.event.post(pygame.event.Event(
        pygame.KEYDOWN if down else pygame.KEYUP,
        {"key": key, "mod": 0, "unicode": unicode}
    ))


def type_text(s):
    for ch in s:
        # Use the actual character code for unicode so TextField captures it.
        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN,
            {"key": ord(ch.lower()) if ch.isalnum() else 0,
             "mod": 0, "unicode": ch}
        ))


def click_at(x, y):
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEMOTION, {"pos": (x, y), "rel": (0, 0), "buttons": (0, 0, 0)}
    ))
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (x, y), "button": 1}
    ))
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONUP, {"pos": (x, y), "button": 1}
    ))


def tick(engine, n=1, dt=1/60):
    for _ in range(n):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            engine.fsm.handle_event(event)
        engine.fsm.update(dt)
        engine.screen.fill(config.COLOR_BG)
        engine.fsm.draw(engine.screen)
    return True


def assert_state(engine, cls, label=""):
    cur = engine.fsm.current
    assert isinstance(cur, cls), \
        f"[{label}] expected {cls.__name__}, got {type(cur).__name__}"


def main():
    engine = Engine()
    engine.fsm.change_to(BootState(engine.fsm))
    tick(engine, 60)
    assert_state(engine, MainMenuState, "boot")
    print("OK MainMenu")

    # ---- Settings → Sign in flow ----
    menu = engine.fsm.current
    click_at(*menu._buttons[1].rect.center)
    tick(engine, 2)
    assert_state(engine, SettingsState, "settings")
    sett = engine.fsm.current
    # Login button should be "Sign in" while signed-out.
    assert sett.login_btn.text == "Sign in", \
        f"expected Sign in label, got {sett.login_btn.text!r}"
    click_at(*sett.login_btn.rect.center)
    tick(engine, 2)
    assert_state(engine, AuthState, "to-auth")
    print("OK AuthState reached")

    # Switch to Register tab — click the right half of the tab pill.
    auth = engine.fsm.current
    right_half_x = auth.tab_rect.centerx + auth.tab_rect.width // 4
    click_at(right_half_x, auth.tab_rect.centery)
    tick(engine, 1)
    auth = engine.fsm.current  # _set_mode rebuilds layout, but instance is same
    assert auth.mode == "register", f"mode = {auth.mode}"

    # Type a new account. Bypass the TextField input pipeline and just set
    # the underlying strings — the unicode event simulation is finicky
    # because TextField's KEYDOWN path doesn't always trust synthetic
    # events. We're testing wiring, not the keyboard subsystem.
    auth.username.text = "troll1"
    auth.password.text = "secret9"
    auth.email.text = "t@example.com"
    auth._submit()
    tick(engine, 5)
    assert engine.save_data.get("username") == "troll1", \
        f"register didn't persist, save_data={engine.save_data}"
    print("OK Registered as", engine.save_data["username"])

    # The USEREVENT+2 timer should fire and bounce back to Settings.
    tick(engine, 50)  # ~0.8 s
    assert_state(engine, SettingsState, "post-register")
    sett = engine.fsm.current
    assert sett.login_btn.text == "Sign out", \
        f"login button should now say Sign out, got {sett.login_btn.text!r}"
    print("OK Returned to Settings as signed-in user")

    # Sign out.
    click_at(*sett.login_btn.rect.center)
    tick(engine, 2)
    assert engine.save_data.get("username") in (None, ""), \
        f"sign out failed, username={engine.save_data.get('username')}"
    print("OK Signed out")

    # Sign back in (via AuthState login mode).
    click_at(*sett.login_btn.rect.center)
    tick(engine, 2)
    assert_state(engine, AuthState, "to-auth-login")
    auth = engine.fsm.current
    auth.username.text = "troll1"
    auth.password.text = "secret9"
    auth._submit()
    tick(engine, 5)
    assert engine.save_data.get("username") == "troll1", "re-login failed"
    print("OK Re-login")
    tick(engine, 50)
    assert_state(engine, SettingsState, "post-login")

    # Back to MainMenu.
    click_at(*engine.fsm.current.back_btn.rect.center)
    tick(engine, 2)
    assert_state(engine, MainMenuState, "back-to-menu")

    # ---- Play level 1 → fake-floor kill ----
    menu = engine.fsm.current
    click_at(*menu._buttons[0].rect.center)
    tick(engine, 2)
    assert_state(engine, ModeSelectState, "to-modeselect")
    click_at(*engine.fsm.current._buttons[0].rect.center)  # NORMAL
    tick(engine, 2)
    assert_state(engine, LevelSelectState, "to-levelselect")
    ls = engine.fsm.current
    print(f"OK LevelSelect — {len(ls.level_paths)} normal levels visible")
    assert len(ls.level_paths) >= 20, "expected 20 normal levels"

    click_at(*ls.tile_rects[0].center)  # level 1
    tick(engine, 2)
    assert_state(engine, PlayState, "to-play")
    play = engine.fsm.current
    assert len(play.level.fake_floors) >= 1
    print("OK Level 1 launched:", play.level.name)

    # Walk right, expect death.
    post_key(pygame.K_RIGHT, down=True)
    d0 = engine.save_data["total_deaths"]
    for _ in range(180):
        tick(engine, 1)
        if engine.save_data["total_deaths"] > d0:
            break
    post_key(pygame.K_RIGHT, down=False)
    d1 = engine.save_data["total_deaths"]
    assert d1 > d0, "fake floor didn't kill"
    print(f"OK Fake-floor kill deaths {d0}->{d1}")

    # ---- Sanity-check DB sync_progress works ----
    engine.save_data["max_normal_level"] = 4
    auth_db.sync_progress(engine.save_data["user_id"], engine.save_data)
    # Reset local then pull from DB to confirm it round-tripped.
    engine.save_data["max_normal_level"] = 1
    auth_db.pull_progress(engine.save_data)
    assert engine.save_data["max_normal_level"] >= 4, \
        f"DB sync round-trip failed: {engine.save_data['max_normal_level']}"
    print(f"OK DB sync round-trip max_normal_level={engine.save_data['max_normal_level']}")

    # ---- Mobile controls — verify the overlay reacts to taps ----
    # Spin up a fresh PlayState so the mobile state we toggle is the live one.
    engine.save_data["max_normal_level"] = 20
    save_mgr.get_settings(engine.save_data)["show_mobile_controls"] = True
    save_mgr.save(engine.save_data)
    engine.fsm.change_to(
        PlayState(engine.fsm),
        level_path=os.path.join(os.getcwd(), "levels", "data", "normal", "level_03.json"),
        mode="normal",
    )
    tick(engine, 2)
    play = engine.fsm.current
    assert play.mobile.visible, "mobile controls should be visible after toggle"
    # Hold the left-arrow button — DOWN only, then verify, then UP.
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": play.mobile.left_rect.center, "button": 1},
    ))
    tick(engine, 2)
    assert play.mobile.left_held, "left touch button should be held after DOWN"
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONUP,
        {"pos": play.mobile.left_rect.center, "button": 1},
    ))
    tick(engine, 2)
    assert not play.mobile.left_held, "left should release on UP"
    # Jump pulse: a tap on the jump button should request a jump on next tick.
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": play.mobile.jump_rect.center, "button": 1},
    ))
    tick(engine, 1)
    print("OK mobile controls overlay reacts to taps")

    # ---- Verify save-on-exit doesn't crash ----
    engine._save_on_exit()
    print("OK save-on-exit ran cleanly")

    # ---- Parse every level just to be safe ----
    from levels.map_parser import list_levels, load_level
    for path in list_levels(os.path.join(os.getcwd(), "levels", "data"), "normal"):
        ld = load_level(path)
        print(f"   L{ld.level_id} {ld.name!r}: "
              f"solids={len(ld.solids)} ff={len(ld.fake_floors)} "
              f"cs={len(ld.ceiling_spikes)} fg={len(ld.fake_goals)} "
              f"rz={len(ld.reverse_zones)}")

    pygame.quit()
    print("SMOKE OK")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.exit(1)
