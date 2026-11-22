"""RETRO BLAST! - entry point."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    parser = argparse.ArgumentParser(description="RETRO BLAST! - Explore the Pixelverse with Hammy")
    parser.add_argument("--headless", action="store_true",
                        help="run without a window (verification mode)")
    parser.add_argument("--test", action="store_true",
                        help="run the headless smoke test and exit")
    args = parser.parse_args()

    if args.test:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        from tests.test_headless import run_tests
        return 0 if run_tests() else 1

    from retroblast.assets import ensure_assets
    from retroblast.audio import ensure_audio
    from retroblast.game import Game

    ensure_assets()
    ensure_audio()
    game = Game(headless=args.headless)
    if args.headless:
        # render a few frames then quit (used by CI / verification)
        for _ in range(20):
            game.input.begin_frame()
            game.update(1.0 / 60.0)
            game.draw()
            game.input.tick()
        return 0
    game.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
