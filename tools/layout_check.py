"""Programmatic UI layout checks: bounds + overlap for every screen.

Complements screenshot review: asserts every button lives inside the internal
512x288 frame, that the nav bar fits on the right, and that no two buttons on
the same screen overlap (which is what made the shop's equipped row look
broken).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from retroblast.config import SCREEN_H, SCREEN_W  # noqa: E402
from retroblast.game import Game  # noqa: E402
from tests.test_headless import FakeInput, frames  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def verify_layout(game, where):
    buttons = [b for b in game.buttons if b.action]
    for btn in buttons:
        r = btn.rect
        check(r.left >= 0 and r.top >= 0 and r.right <= SCREEN_W
              and r.bottom <= SCREEN_H,
              f"{where}: '{btn.text}' inside frame {tuple(r)}")
    for i in range(len(buttons)):
        for j in range(i + 1, len(buttons)):
            a, b = buttons[i], buttons[j]
            if a.rect.colliderect(b.rect):
                check(False, f"{where}: '{a.text}' overlaps '{b.text}'")
    check(True, f"{where}: {len(buttons)} buttons laid out")


def main():
    game = Game(headless=True)
    game.input = FakeInput()
    inp = game.input
    print("UI layout verification")

    frames(game, 5)
    verify_layout(game, "menu")

    inp.press("interact")
    frames(game, 3)
    verify_layout(game, "level select")

    inp.press("interact")
    frames(game, 5)
    inp.press("pause")
    frames(game, 3)
    verify_layout(game, "pause")

    game.activate("shop")
    frames(game, 3)
    verify_layout(game, "shop:skins")
    for slot in ("backpack", "accessory", "ability", "powerup"):
        game.activate(f"tab:{slot}")
        frames(game, 3)
        verify_layout(game, f"shop:{slot}")

    game.activate("back")
    frames(game, 2)
    game.activate("settings")
    frames(game, 3)
    verify_layout(game, "settings")

    game.activate("back")
    frames(game, 2)
    game.activate("community")
    frames(game, 3)
    verify_layout(game, "community")

    game.activate("achievements")
    frames(game, 3)
    verify_layout(game, "achievements")

    print()
    if FAILS:
        print(f"{len(FAILS)} LAYOUT FAILURE(S)")
        return False
    print("LAYOUT OK")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
