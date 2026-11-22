"""Physics playthrough bot v2: can a simple controller finish each level?

Uses the real World/Player physics (no teleporting, no cheats).  The controller
holds RIGHT and jumps at walls, pits, spikes, lava and enemies, and WAITS for a
moving platform instead of leaping into the pit.  It reports the furthest x
reached, where it got stuck, and whether it reached the exit.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from retroblast.config import (LEVEL_ROWS, SOLID_TILES, TILE, T_LAVA,
                               T_SPIKE)  # noqa: E402
from retroblast.game import Game  # noqa: E402
from retroblast.levels import build_level  # noqa: E402
from retroblast.world import World  # noqa: E402
from tests.test_headless import FakeInput  # noqa: E402

MAX_FRAMES = 60 * 120
SOLID = SOLID_TILES
PLATFORM_TILE = 2


class Bot:
    def __init__(self, world: World):
        self.world = world
        self.input = FakeInput()
        self.stale = 0
        self.best_x = 0.0
        self.last_x = 0.0
        self.stuck_spots = []
        self.waited = 0

    def tick(self):
        w = self.world
        p = w.player
        self.input.tick()
        self.input._held.discard("right")

        tx = int((p.cx + 12) // TILE)
        foot_ty = int((p.rect[1] + p.rect[3] - 2) // TILE)
        ahead_tile = w.tile_at(tx, foot_ty)
        blocked = any(w.tile_at(tx, foot_ty - k) in SOLID for k in (0, 1))
        pit = not any(w.tile_at(tx, y) in SOLID
                      for y in range(foot_ty, min(LEVEL_ROWS, foot_ty + 4)))
        hazard = ahead_tile in (T_SPIKE, T_LAVA) or \
            w.tile_at(tx, foot_ty + 1) in (T_SPIKE, T_LAVA)
        enemy_ahead = any(e.alive and 0 < e.cx - p.cx < 30 for e in w.enemies)
        pit_within = any(
            not any(w.tile_at(c, y) in SOLID
                    for y in range(foot_ty, min(LEVEL_ROWS, foot_ty + 4)))
            for c in range(tx, min(self.world.level.width, tx + 6)))

        jump = blocked or hazard
        if not jump and enemy_ahead and not pit_within:
            jump = True              # only bunny-hop an enemy on safe ground
        if pit:
            run = 0
            c = tx
            while c < self.world.level.width and not any(
                    w.tile_at(c, y) in SOLID
                    for y in range(foot_ty, min(LEVEL_ROWS, foot_ty + 4))):
                run += 1
                c += 1
            if run <= 4:
                jump = True          # short pit: just jump it
                self.waited = 0
            elif self._platform_near() is None:
                self.waited += 1
                if self.waited > 150:
                    jump = True      # stop waiting, try the leap anyway
            else:
                jump = True
                self.waited = 0
                # a bridge platform overhangs the edge: jump straight up onto
                # it instead of drifting over the pit
                if self._platform_overhead(tx, foot_ty):
                    self.input._held.discard("right")
        else:
            self.waited = 0

        if jump and (p.on_ground or p.coyote > 0):
            self.input.press("jump")
        self.input.hold("right")

        w.update(1.0 / 60.0, self.input, w.game)
        x = p.cx
        self.best_x = max(self.best_x, x)
        if x - self.last_x < 0.5:
            self.stale += 1
        else:
            self.stale = 0
            self.last_x = x
        if self.stale == 45:
            self.stuck_spots.append(int(x // TILE))
            self.input.press("jump")
        return p

    def _platform_overhead(self, tx, foot_ty):
        for c in range(tx - 1, tx + 2):
            for r in range(max(0, foot_ty - 4), foot_ty):
                if self.world.tile_at(c, r) == PLATFORM_TILE:
                    return True
        return False

    def _platform_near(self):
        p = self.world.player
        feet = p.rect[1] + p.rect[3]
        for plat in self.world.platforms:
            if plat.rect[0] - p.cx < 44 and plat.rect[0] > p.cx - 24 and \
                    abs(plat.rect[1] - feet) < 48:
                return plat
        tx = int((p.cx + 12) // TILE)
        row = int((feet + 4) // TILE)
        for k in range(0, 6):
            for r in range(max(0, row - 4), row + 1):
                if self.world.tile_at(tx + k, r) == PLATFORM_TILE:
                    return True
        return None


def run_level(game, world_idx, level_idx, verbose=True):
    level = build_level(world_idx, level_idx)
    world = World(level, game.save, game.assets, game.audio)
    world.game = game
    game.world = world
    bot = Bot(world)
    frames = 0
    result = "timeout"
    while frames < MAX_FRAMES:
        p = bot.tick()
        frames += 1
        if world.finished:
            result = "finished"
            break
        if p.dead:
            col = int(p.cx // TILE)
            if level.is_pit(col):
                cause = "pit"
            else:
                t = level.tile_at(col, int((p.rect[1] + p.rect[3]) // TILE))
                cause = {3: "spikes", 4: "lava"}.get(t, "hazard")
            result = f"died at tile {col} ({cause})"
            break
    if verbose:
        pct = 100 * bot.best_x / max(1, level.world_px)
        print(f"  {level.name:<16} {result:<22} {pct:5.1f}%  "
              f"x={bot.best_x:.0f}/{level.world_px}  "
              f"stuck={sorted(set(bot.stuck_spots))[:5]}  "
              f"enemies={len(level.enemies)} items={len(level.items)}")
    return result, bot, level


def main():
    game = Game(headless=True)
    game.input = FakeInput()
    print("PLAYTHROUGH BOT v2 (real physics: right + jump at wall/pit/hazard, "
          "waits for moving platforms)")
    failed = []
    for w in range(4):
        for i in range(2):
            result, bot, level = run_level(game, w, i)
            if result != "finished":
                failed.append((level.name, result))
    print()
    if failed:
        print(f"{len(failed)} level(s) NOT completed by the bot:")
        for name, result in failed:
            print(f"  - {name}: {result}")
        return False
    print("every level was completed by the bot")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
