"""Deep level check: runtime fuzz + monster placement report + level maps.

1. Fuzzes every level with random input for thousands of frames, catching
   exceptions and counting player deaths / enemy leaks (enemies that fall out
   of the world and never despawn).
2. Prints every monster spawn (kind, tile x, ground row, distance from the
   player's natural path) so bad placement is visible with real numbers.
3. Renders a full-level overview PNG per level with markers, so placement can
   be eyeballed: red = enemy, magenta = boss, yellow = item, green = spawn,
   cyan = secret, grey = gate, white = exit.
"""
from __future__ import annotations

import os
import random
import sys
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from retroblast.config import LEVEL_ROWS, TILE, T_DOOR, T_GATE, T_LAVA  # noqa: E402
from retroblast.config import T_PLATFORM, T_SECRET, T_SOLID, T_SPIKE  # noqa: E402
from retroblast.game import Game  # noqa: E402
from retroblast.levels import build_level  # noqa: E402
from tests.test_headless import FakeInput  # noqa: E402

OUT = os.path.join(ROOT, "tests", "maps")
os.makedirs(OUT, exist_ok=True)

TILE_COLORS = {
    T_SOLID: (96, 64, 40),
    T_PLATFORM: (150, 200, 90),
    T_SPIKE: (220, 70, 70),
    T_LAVA: (244, 84, 28),
    T_SECRET: (96, 64, 40),
    T_DOOR: (196, 138, 74),
    T_GATE: (150, 156, 176),
}


def render_map(level, path, scale=4):
    w = level.width * scale
    h = LEVEL_ROWS * scale
    img = pygame.Surface((w, h))
    img.fill((24, 22, 34))
    for y in range(LEVEL_ROWS):
        for x in range(level.width):
            t = level.tiles[y][x]
            if t:
                img.fill(TILE_COLORS.get(t, (255, 255, 255)),
                         (x * scale, y * scale, scale, scale))
    def mark(tx, ty, color, size=None):
        s = size or scale
        img.fill(color, (tx * scale, ty * scale, s, s))
    for name, tx, ty in level.items:
        mark(tx, ty, (255, 226, 92))
    for kind, tx, ty in level.enemies:
        mark(tx, ty, (255, 40, 40), scale)
    if level.boss:
        mark(level.boss[1], level.boss[2], (255, 0, 255), scale * 2)
    for tx, ty, tw, th in level.secrets:
        for x in range(tx, tx + tw):
            mark(x, ty - 1, (80, 220, 255))
    for tx, ty in level.checkpoints:
        mark(tx, ty, (120, 120, 120))
    if level.exit:
        mark(level.exit[0], level.exit[1], (255, 255, 255), scale * 2)
    sx, sy = level.spawn[0] // TILE, level.spawn[1] // TILE
    mark(sx, sy, (60, 255, 120), scale)
    pygame.image.save(img, path)


def fuzz(game, world, index, steps=3000, seed=0):
    rng = random.Random(seed)
    game.start_level(world, index)
    inp = game.input
    deaths = 0
    leaks = 0
    max_x = 0.0
    for _ in range(steps):
        inp._held = set()
        r = rng.random()
        if r < 0.75:
            inp.hold("right")
        elif r < 0.9:
            inp.hold("left")
        if rng.random() < 0.08:
            inp.press("jump")
        if rng.random() < 0.02:
            inp.press("dash")
        try:
            game.update(1.0 / 60.0)
            game.draw()
        except Exception:
            print(f"  CRASH {world}:{index}")
            traceback.print_exc()
            return False, deaths, leaks, max_x
        inp.tick()
        p = game.world.player
        max_x = max(max_x, p.cx)
        if p.dead:
            deaths += 1
            game.activate("restart")
            inp = game.input
        for e in game.world.enemies:
            if e.alive and e.rect[1] > game.world.level.height * TILE + 80:
                leaks += 1
                e.alive = False
        if game.state == "GAMEOVER":
            game.activate("restart")
            inp = game.input
    return True, deaths, leaks, max_x


def main():
    game = Game(headless=True)
    game.input = FakeInput()
    print("=== fuzz + leak check (3000 frames per level) ===")
    bad = 0
    for w in range(4):
        for i in range(2):
            ok, deaths, leaks, max_x = fuzz(game, w, i, seed=7 + w * 10 + i)
            lvl = build_level(w, i)
            reach = max_x / TILE
            flag = "" if ok else "  <-- CRASH"
            print(f"  {w}:{i} {lvl.name:<16} ok={ok} deaths={deaths:<3} "
                  f"leaked_enemies={leaks:<3} furthest_x={reach:.0f} tiles "
                  f"of {lvl.width}{flag}")
            if not ok:
                bad += 1

    print("\n=== monster placement ===")
    for w in range(4):
        for i in range(2):
            lvl = build_level(w, i)
            counts = {}
            for kind, tx, ty in lvl.enemies:
                counts[kind] = counts.get(kind, 0) + 1
            boss = lvl.boss[0] if lvl.boss else "-"
            items = len(lvl.items)
            kinds = ", ".join(f"{k}x{v}" for k, v in sorted(counts.items()))
            print(f"  {lvl.name:<16} enemies={len(lvl.enemies):<3} ({kinds or 'none'})"
                  f"  boss={boss:<6} items={items:<3} secrets={len(lvl.secrets)}"
                  f" doors={len(lvl.doors)} gates={len(lvl.gates)}"
                  f" moving={len(lvl.platforms)}")
            for kind, tx, ty in lvl.enemies:
                below = lvl.tile_at(tx, ty + 1)
                ground = "ground" if below in (T_SOLID, T_PLATFORM) else "PIT/AIR"
                print(f"      {kind:<7} tile x={tx:<4} y={ty:<3} under={ground}")

    print("\n=== rendering level maps ===")
    for w in range(4):
        for i in range(2):
            lvl = build_level(w, i)
            path = os.path.join(OUT, f"level_{w}_{i}.png")
            render_map(lvl, path)
            print("  wrote", path)
    print("\nresult:", "FAIL" if bad else "CLEAN")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
