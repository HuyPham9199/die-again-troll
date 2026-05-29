"""Entry point. Boots the engine and pushes the first state."""
from __future__ import annotations

from core.engine import Engine
from ui.menus import BootState


def main() -> None:
    engine = Engine()
    engine.run(BootState(engine.fsm))


if __name__ == "__main__":
    main()
