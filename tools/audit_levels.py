"""Level audit: enemy/item placement + traversability, per level.

Checks, for every one of the 8 generated levels:
  * enemies are not embedded in solid tiles and are not floating over pits
  * items are not inside solid tiles
  * pits are jumpable (<=4 tiles) or have a platform over them
  * no unclimbable wall (>4 tiles up) without a nearby platform
  * exit / checkpoint / key / secret tiles sit on real ground
Prints a compact report so generator bugs are visible with real numbers.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from retroblast.config import (LEVEL_ROWS, T_DOOR, T_GATE, T_PLATFORM,
                               T_SECRET, T_SOLID, T_SPIKE)
from retroblast.levels import build_level

SURFACE = 14
REACH_UP = 4        # jump height in tiles
REACH_ACROSS = 5    # running jump distance in tiles

ISSUES = []


def note(level, kind, msg):
    ISSUES.append((level, kind, msg))


def ground_top(grid, width, x):
    """Row of the topmost real ground tile in column x, or None for a pit."""
    for y in range(LEVEL_ROWS):
        if grid[y][x] == T_SOLID:
            return y
    return None


def platforms_in(grid, width, x0, x1, y0, y1):
    """Any one-way platform tile in the column/row window."""
    for x in range(max(0, x0), min(width, x1 + 1)):
        for y in range(max(0, y0), min(LEVEL_ROWS, y1 + 1)):
            if grid[y][x] == T_PLATFORM:
                return True
    return False


def audit(level):
    name = level.name
    grid = level.tiles
    width = level.width
    tag = f"{name}"

    # --- enemies ----------------------------------------------------------
    sizes = {"slime": (14, 12), "walker": (14, 14), "flyer": (14, 12),
             "boss": (28, 26)}
    for kind, tx, ty in level.enemies:
        w, h = sizes[kind]
        rx0 = int((tx * 16 + (16 - w) / 2) // 16)
        rx1 = int((tx * 16 + (16 - w) / 2 + w - 1) // 16)
        ry0 = int((ty * 16 + (16 - h)) // 16)
        ry1 = int((ty * 16 + 15) // 16)
        for x in range(rx0, rx1 + 1):
            for y in range(ry0, ry1 + 1):
                if level.tile_at(x, y) in (T_SOLID, T_DOOR, T_GATE):
                    note(tag, "enemy-stuck",
                         f"{kind} at tile ({tx},{ty}) overlaps solid tile")
        if kind != "flyer":
            if ground_top(grid, width, tx) is None:
                note(tag, "enemy-pit",
                     f"{kind} at tile ({tx},{ty}) has no ground under it")
    if level.boss:
        kind, tx, ty = level.boss
        w, h = sizes[kind]
        if ground_top(grid, width, tx) is None:
            note(tag, "boss-pit", f"boss at tile ({tx},{ty}) has no ground")
        if level.tile_at(tx, ty) in (T_SOLID, T_DOOR, T_GATE):
            note(tag, "boss-stuck", f"boss at tile ({tx},{ty}) inside a solid")

    # --- items ------------------------------------------------------------
    for item, tx, ty in level.items:
        tile = level.tile_at(tx, ty)
        if tile in (T_SOLID, T_DOOR, T_GATE):
            note(tag, "item-stuck", f"{item} at tile ({tx},{ty}) inside solid")
        if tile == T_SPIKE:
            note(tag, "item-spike", f"{item} at tile ({tx},{ty}) sits on spikes")

    # --- exit / checkpoints / key / secret --------------------------------
    if level.exit:
        ex, ey = level.exit
        if level.tile_at(ex, ey) in (T_SOLID, T_DOOR, T_GATE):
            note(tag, "exit-stuck", f"exit at ({ex},{ey}) inside solid")
        below = level.tile_at(ex, ey + 1)
        if below not in (T_SOLID,):
            note(tag, "exit-float", f"exit at ({ex},{ey}) has no floor")
    for tx, ty in level.checkpoints:
        if ground_top(grid, width, tx) is None:
            note(tag, "checkpoint-pit",
                 f"checkpoint at ({tx},{ty}) floats over a pit (respawn loop)")
    for tx, ty, tw, th in level.secrets:
        for x in range(tx, tx + tw):
            if level.tile_at(x, ty - 1) != T_SECRET:
                note(tag, "secret-floor",
                     f"secret ({tx},{ty}) has no false floor at column {x}")

    # --- pits -------------------------------------------------------------
    x = 0
    while x < width:
        if ground_top(grid, width, x) is None:
            start = x
            while x < width and ground_top(grid, width, x) is None:
                x += 1
            run = x - start
            plat = platforms_in(grid, width, start, x - 1,
                                SURFACE - 5, SURFACE)
            if not plat:
                # a moving platform may cover the pit even with no tile there
                for ptx, pty, plen, paxis, prange in level.platforms:
                    lo = ptx - (prange if paxis == "h" else 0)
                    hi = ptx + plen - 1 + (prange if paxis == "h" else 0)
                    if paxis == "h" and lo <= start and hi >= x - 3 and \
                            abs(pty - SURFACE) <= 3:
                        plat = True
                        break
                    if paxis == "v" and lo <= start <= hi and \
                            abs(pty - SURFACE) <= 6:
                        plat = True
                        break
            if run > REACH_ACROSS and not plat:
                note(tag, "pit-uncrossable",
                     f"pit columns {start}..{x - 1} is {run} tiles wide, "
                     f"no platform")
        x += 1

    # --- walls ------------------------------------------------------------
    for x in range(width - 1):
        h0 = ground_top(grid, width, x)
        h1 = ground_top(grid, width, x + 1)
        if h0 is None or h1 is None:
            continue
        rise = h0 - h1 > 0
        if rise and (h0 - h1) > REACH_UP:
            # a platform within jumping reach of the lower column makes it
            # climbable, otherwise it is a wall
            plat = platforms_in(grid, width, x, x + 1,
                                h1 - 1, h0 + 1)
            if not plat:
                note(tag, "wall-unclimbable",
                     f"columns {x}->{x + 1} rise {h0 - h1} tiles "
                     f"({h0} -> {h1}) with no platform")

    # --- locked doors must be reachable and block a full wall -------------
    if level.doors:
        dx = level.doors[0][0]
        wall_top = min(y for _, y in level.doors)
        if wall_top > SURFACE - REACH_UP - 1:
            note(tag, "door-jumpable",
                 f"locked door top at row {wall_top} can be jumped over")
        key_tiles = [(tx, ty) for item, tx, ty in level.items if item == "key"]
        for ktx, kty in key_tiles:
            if ground_top(grid, width, ktx) is None and \
                    not platforms_in(grid, width, ktx, ktx, kty, SURFACE):
                note(tag, "key-unreachable",
                     f"key at ({ktx},{kty}) floats over a pit")


def main():
    print("LEVEL AUDIT")
    for world in range(4):
        for index in range(2):
            audit(build_level(world, index))
    if not ISSUES:
        print("  no placement or traversability problems found")
        return True
    by_level = {}
    for level, kind, msg in ISSUES:
        by_level.setdefault(level, []).append((kind, msg))
    for level, items in by_level.items():
        print(f"\n{level}: {len(items)} issue(s)")
        for kind, msg in items:
            print(f"  [{kind}] {msg}")
    print(f"\nTOTAL {len(ISSUES)} issue(s) across {len(by_level)} level(s)")
    return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
