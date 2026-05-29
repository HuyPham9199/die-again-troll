"""Finite State Machine — GDD §2.2.

Every state implements enter/update/exit/draw. The machine itself owns no game
logic; states push new states or pop themselves via `change_to` / `pop`.
"""
from __future__ import annotations

from typing import Optional


class State:
    """Base State. Subclasses override the four lifecycle hooks."""

    def __init__(self, machine: "StateMachine"):
        self.machine = machine

    # Called once when the state becomes current.
    def enter(self, **kwargs) -> None: ...

    # Called once when leaving — release timers, stop sounds, etc.
    def exit(self) -> None: ...

    # `dt` is seconds since last frame.
    def update(self, dt: float) -> None: ...

    # `surface` is the back buffer; draw absolute (post-camera) here.
    def draw(self, surface) -> None: ...

    # Optional: receive pygame events the engine has already polled.
    def handle_event(self, event) -> None: ...


class StateMachine:
    """Stack-based FSM.

    Most transitions use `change_to` (replace top). `push` / `pop` are for
    overlays such as a pause menu over Play.
    """

    def __init__(self, engine=None):
        self._stack: list[State] = []
        # Back-reference for states that need access to shared services
        # (fonts, particle pool, save data). Set by Engine on construction.
        self.engine = engine

    @property
    def current(self) -> Optional[State]:
        return self._stack[-1] if self._stack else None

    def change_to(self, state: State, **kwargs) -> None:
        if self._stack:
            self._stack[-1].exit()
            self._stack.pop()
        self._stack.append(state)
        state.enter(**kwargs)

    def push(self, state: State, **kwargs) -> None:
        self._stack.append(state)
        state.enter(**kwargs)

    def pop(self) -> None:
        if self._stack:
            self._stack[-1].exit()
            self._stack.pop()

    def update(self, dt: float) -> None:
        if self.current:
            self.current.update(dt)

    def draw(self, surface) -> None:
        if self.current:
            self.current.draw(surface)

    def handle_event(self, event) -> None:
        if self.current:
            self.current.handle_event(event)
