"""Level audit: structural checks + a real physics bot playthrough.

Structural pass
  - spawn / exit / checkpoint / enemy / item tiles are sane (nothing embedded
    in solid rock, nothing floating over a pit unless it is a flyer).
  - every gap in the ground is <= MAX_GAP tiles (jump range).
  - no pit deeper than MAX_PIT next to a wall the player cannot jump out of.

Bot pass
  - runs the actual game physics: hold RIGHT, jump when blocked or when the
    ground disappears ahead, then reports how far Hammy got as a % of the
    level width.  A soft-lock (unclimbable pit, unreachable platform) shows up
    as a low percentage.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from retroblast.config import (SOLID_TILES, TILE, T_EMPTY, T_LAVA, T_PLATFORM,
                               T_SECRET, T_SPIKE, T_DOOR, T_GATE)  # noqa: E402
from retroblast.game import Game  # noqa: E402
from retroblast.levels import build_level  # noqa: E402
from tests.test_headless import FakeInput  # noqa: E402

FAILS = []
WARN = []
MAX_GAP = 5
MAX_PIT = 3


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def warn(cond, msg):
    if not cond:
        print("  WARN " + msg)
        WARN.append(msg)


def col_has_ground(lvl, tx):
    """True when column tx has any solid-ish tile in the lower half."""
    for ty in range(lvl.height):
        if lvl.tile_at(tx, ty) in (1, 2, 5, 6, 7):
            return True
    return False


def ground_top(lvl, tx):
    for ty in range(lvl.height):
        if lvl.tile_at(tx, ty) in SOLID_TILES:
            return ty
    return None


def structural(lvl, label):
    print(f"structural {label}: {lvl.width} tiles, "
          f"{len(lvl.items)} items, {len(lvl.enemies)} enemies, "
          f"{len(lvl.secrets)} secrets, {len(lvl.doors)} door tiles, "
          f"{len(lvl.gates)} gate tiles, {len(lvl.checkpoints)} checkpoints")
    # spawn
    sx, sy = lvl.spawn[0] // TILE, lvl.spawn[1] // TILE
    check(lvl.tile_at(sx, sy) not in SOLID_TILES, f"{label}: spawn tile is free")
    check(lvl.tile_at(sx, sy + 1) in SOLID_TILES, f"{label}: spawn has floor")
    # exit
    if lvl.exit:
        ex, ey = lvl.exit
        check(lvl.tile_at(ex, ey) not in SOLID_TILES, f"{label}: exit tile free")
        check(lvl.tile_at(ex, ey + 1) in SOLID_TILES, f"{label}: exit has floor")
    # enemies
    for kind, tx, ty in lvl.enemies:
        here = lvl.tile_at(tx, ty)
        check(here not in SOLID_TILES, f"{label}: {kind} not inside a wall @({tx},{ty})")
        if kind != "flyer":
            check(lvl.tile_at(tx, ty + 1) in SOLID_TILES,
                  f"{label}: {kind} stands on ground @({tx},{ty})")
    # checkpoints
    for tx, ty in lvl.checkpoints:
        check(lvl.tile_at(tx, ty + 1) in SOLID_TILES,
              f"{label}: checkpoint on solid ground @({tx},{ty})")
    # items (secret-pocket items live underground by design)
    secret_cells = set()
    for sx0, sy0, sw, sh in lvl.secrets:
        for xx in range(sx0, sx0 + sw):
            for yy in range(sy0, sy0 + sh):
                secret_cells.add((xx, yy))
    for name, tx, ty in lvl.items:
        if (tx, ty) in secret_cells:
            continue
        check(lvl.tile_at(tx, ty) not in SOLID_TILES,
              f"{label}: item {name} not buried @({tx},{ty})")
    # gaps in the ground along the surface
    gaps = []
    run = 0
    for tx in range(lvl.width):
        top = ground_top(lvl, tx)
        if top is None:
            run += 1
        else:
            if run:
                gaps.append((tx - run, run))
            run = 0
    if run:
        gaps.append((lvl.width - run, run))
    for start, length in gaps:
        # a pit with a one-way platform bridge over it is a designed crossing
        bridged = any(lvl.tile_at(tx, y) == T_PLATFORM
                      for tx in range(start, start + length)
                      for y in range(14 - 4, 14))
        warn(length <= MAX_GAP or bridged,
             f"{label}: ground gap of {length} tiles at x={start} "
             f"with no platform bridge")
    # walls: the ground RISING more than 3 tiles in one column is unclimbable
    # (a drop is fine - the player just falls)
    for tx in range(1, lvl.width):
        if any(lvl.tile_at(tx, y) in (T_DOOR, T_GATE) for y in range(14)):
            continue        # locked door / boss gate: meant to block until opened
        prev = ground_top(lvl, tx - 1)
        cur = ground_top(lvl, tx)
        if prev is not None and cur is not None:
            warn(prev - cur <= MAX_PIT,
                 f"{label}: unclimbable wall of {prev - cur} tiles at x={tx}")


def bot_play(game, w, i, frames=9000):
    import random
    random.seed(1000 + w * 10 + i)   # enemy facing / platform phase is random
    game.start_level(w, i)
    inp = FakeInput()
    game.input = inp
    inp.hold("right")
    world = game.world
    max_x = 0.0
    deaths = 0
    stall = 0
    cause = "timeout"
    blocked_frames = 0
    jump_cd = 0
    backtrack = 0
    last_back = -9999
    for step in range(frames):
        p = world.player
        p.invuln = 1.0          # god mode: measure geometry, not combat skill
        if p.dead:
            deaths += 1
            cause = "died"
            break
        if backtrack > 0:
            backtrack -= 1
            inp._held.discard("right")
            inp.hold("left")
        else:
            inp._held.discard("left")
            inp.hold("right")
        ahead_x = p.cx + 18
        feet_y = p.rect[1] + p.rect[3] + 6
        ground_ahead = world.tile_at_px(ahead_x, feet_y) in (1, 2, 5, 6, 7)
        if p.on_ground and abs(p.vx) < 8:
            blocked_frames += 1
        else:
            blocked_frames = 0
        # pressed against a locked door with no key: walk back to look for it
        door_ahead = world.tile_at_px(p.rect[0] + p.rect[2] + 2, feet_y) == 6
        if blocked_frames > 15 and world.keys_held == 0 and backtrack == 0 \
                and door_ahead and step - last_back > 200:
            backtrack = 45
            last_back = step
        # a key just ahead on the ground: stop bouncing so we actually grab it
        key_near = any(it.name == "key" and not it.collected and
                       0 < it.cx - p.cx < 90 for it in world.items)
        jump_cd = max(0, jump_cd - 1)
        if p.on_ground and jump_cd == 0 and \
                (blocked_frames > 15 or (not ground_ahead and not key_near)):
            inp.press("jump")
            jump_cd = 10
        game.update(1.0 / 60.0)
        inp.tick()
        if p.cx > max_x + 1:
            max_x = p.cx
            stall = 0
        else:
            stall += 1
            if stall == 240:
                cause = f"stuck@{int(p.cx // 16)}"
                break
        if game.state != "PLAY":
            cause = f"state={game.state}"
            break
    pct = 100.0 * max_x / world.level.world_px
    lvl = world.level
    if cause == "died":
        col = int(world.player.cx // 16)
        tiles = "".join(str(lvl.tile_at(col + k, 13)) for k in range(-3, 4))
        cause += f" near x={col} row13[{tiles}]"
    return pct, deaths, cause


def main():
    game = Game(headless=True)
    print("LEVEL AUDIT")
    for w in range(4):
        for i in range(2):
            lvl = build_level(w, i)
            structural(lvl, f"{w}:{i}")
    print()
    print("BOT PLAYTHOLD (hold right + auto jump)")
    for w in range(4):
        for i in range(2):
            pct, deaths, cause = bot_play(game, w, i)
            flag = "OK  " if pct >= 95 else "FAIL"
            print(f"  {flag} {w}:{i} reached {pct:5.1f}%  {cause}")
            if pct < 95:
                FAILS.append(f"bot only reached {pct:.0f}% on level {w}:{i}")
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S), {len(WARN)} warning(s)")
        return False
    print("LEVELS OK")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
