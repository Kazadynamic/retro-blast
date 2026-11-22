"""Reachability proof: BFS over standable tiles from spawn to exit.

Complements the physics bot with a deterministic answer to "can this level
actually be finished?".  Spots are tiles the player can stand on; moves model a
walk step and a running jump (up to 4 tiles up / 5 across), with intermediate
columns acting as blockers when they rise above the jump arc.  Locked doors are
treated as walls unless the key is reachable first.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from retroblast.config import (LEVEL_ROWS, SURFACE_ROW, T_DOOR, T_GATE,
                               T_PLATFORM, T_SOLID)
from retroblast.levels import build_level

REACH_UP = 4
REACH_ACROSS = 5
FALL_DOWN = 8
BLOCKING = (T_SOLID, T_DOOR, T_GATE)


def column_has_door(level, x):
    for y in range(level.height):
        if level.tile_at(x, y) == T_DOOR:
            return True
    return False


def ground_top(level, x, doors_block):
    if doors_block and column_has_door(level, x):
        return 2
    for y in range(level.height):
        if level.tile_at(x, y) == T_SOLID:
            return y
    return None


def stand_spots(level, doors_block):
    spots = set()
    for x in range(level.width):
        if doors_block and column_has_door(level, x):
            continue
        for y in range(level.height):
            if level.tile_at(x, y) in (T_SOLID, T_PLATFORM):
                if level.tile_at(x, y - 1) in BLOCKING:
                    continue
                if level.tile_at(x, y - 2) in BLOCKING:
                    continue
                spots.add((x, y))
    # moving platforms sweep a range of columns: the player can board them
    for (tx, ty, plen, axis, rng) in level.platforms:
        if axis == "h":
            for x in range(tx - rng, tx + plen + rng):
                spots.add((x, ty))
        else:
            for y in range(ty - rng, ty + rng + 1):
                spots.add((tx, y))
    return spots


def platform_near(level, x, y0, y1):
    for y in range(max(0, y0), min(LEVEL_ROWS, y1 + 1)):
        if level.tile_at(x, y) == T_PLATFORM:
            return True
    return False


def neighbours(level, spots, node, doors_block):
    x, y = node
    for (x2, y2) in spots:
        d = abs(x2 - x)
        if d > REACH_ACROSS or d == 0:
            if d == 0 and y2 != y and y - REACH_UP <= y2 <= y + FALL_DOWN:
                yield (x2, y2)
            continue
        if y2 < y - REACH_UP or y2 > y + FALL_DOWN:
            continue
        if d == 1 and y2 == y:
            yield (x2, y2)
            continue
        lo, hi = min(x, x2), max(x, x2)
        blocked = False
        for c in range(lo + 1, hi):
            h = ground_top(level, c, doors_block)
            if h is not None and h < y - REACH_UP:
                if not platform_near(level, c, y - REACH_UP, y):
                    blocked = True
                    break
        if not blocked:
            yield (x2, y2)


def reachable(level, doors_block, start):
    spots = stand_spots(level, doors_block)
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for nxt in neighbours(level, spots, node, doors_block):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen, spots


def analyse(level):
    start = (level.spawn[0] // 16, SURFACE_ROW)
    if start not in stand_spots(level, True):
        # spawn tile blocked: fall back to any spot in that column
        col = level.spawn[0] // 16
        cands = [(col, y) for y in range(LEVEL_ROWS)
                 if (col, y) in stand_spots(level, True)]
        if not cands:
            return False, "spawn column has no standable tile"
        start = cands[0]

    seen_blocked, _ = reachable(level, True, start)
    key_ok = True
    if level.doors:
        key_cols = {tx for name, tx, ty in level.items if name == "key"}
        key_ok = any(x in key_cols and any((x, y) in seen_blocked
                                          for y in range(LEVEL_ROWS))
                     for x in key_cols)
        if not key_ok:
            return False, "key is unreachable while the door is locked"

    seen, _ = reachable(level, False, start)
    ex = level.exit[0] if level.exit else None
    if ex is None:
        return False, "level has no exit"
    if any(abs(x - ex) <= 1 for (x, y) in seen):
        return True, "exit reachable"
    return False, (f"exit column {ex} unreachable "
                   f"(reached {max(x for x, _ in seen)})")


def main():
    print("REACHABILITY (BFS over standable tiles, jump 4 up / 5 across)")
    bad = []
    for w in range(4):
        for i in range(2):
            level = build_level(w, i)
            ok, msg = analyse(level)
            print(f"  {level.name:<16} {'OK  ' if ok else 'FAIL'} {msg}")
            if not ok:
                bad.append((level.name, msg))
    print()
    if bad:
        print(f"{len(bad)} unreachable level(s)")
        return False
    print("all 8 levels are traversable start -> exit")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
