"""ASCII map of a generated level, with a window around a given tile.

Used to diagnose why the playthrough bot gets stuck: shows terrain, pits,
platforms, hazards, enemies, items, doors and the segment trace side by side.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from retroblast.config import T_DOOR, T_GATE, T_LAVA, T_PLATFORM, T_SECRET, T_SOLID, T_SPIKE  # noqa: E402
from retroblast.levels import build_level  # noqa: E402

CHARS = {
    T_SOLID: "#", T_PLATFORM: "=", T_SPIKE: "^", T_LAVA: "~",
    T_SECRET: "s", T_DOOR: "D", T_GATE: "G",
}


def render(level, x0=0, x1=None, mark=None):
    x1 = level.width - 1 if x1 is None else x1
    item_map = {}
    for name, tx, ty in level.items:
        item_map.setdefault((tx, ty), name[0].upper())
    enemy_map = {}
    for kind, tx, ty in level.enemies:
        enemy_map.setdefault((tx, ty), "e")
    if level.boss:
        enemy_map[(level.boss[1], level.boss[2])] = "B"
    exit_t = level.exit if level.exit else (None, None)
    out = []
    header = "     " + "".join(str((x // 10) % 10) for x in range(x0, x1 + 1))
    header2 = "     " + "".join(str(x % 10) for x in range(x0, x1 + 1))
    out.append(header)
    out.append(header2)
    for y in range(level.height):
        row = f"{y:>3} |"
        for x in range(x0, x1 + 1):
            tile = level.tile_at(x, y)
            ch = CHARS.get(tile, " ")
            if (x, y) in item_map and tile == 0:
                ch = item_map[(x, y)].lower()
            if (x, y) in enemy_map:
                ch = enemy_map[(x, y)]
            if (x, y) == exit_t:
                ch = "X"
            if (x, y) == (level.spawn[0] // 16, level.spawn[1] // 16):
                ch = "P"
            if mark and x == mark:
                ch = "|"
            row += ch
        out.append(row)
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    world = int(args[0]) if args else 0
    index = int(args[1]) if len(args) > 1 else 0
    level = build_level(world, index)
    x0 = int(args[2]) if len(args) > 2 else 0
    width = int(args[3]) if len(args) > 3 else 90
    mark = int(args[4]) if len(args) > 4 else None
    print(f"{level.name}  width={level.width}  exit={level.exit}  "
          f"boss={level.boss}")
    print("segments:", " ".join(level.trace))
    print(f"enemies: {level.enemies}")
    print(f"platforms: {level.platforms}")
    print(f"checkpoints: {level.checkpoints}  doors: {len(level.doors)}  "
          f"secrets: {level.secrets}")
    print()
    print(render(level, x0, min(level.width - 1, x0 + width - 1), mark))
    print()
    tops = []
    for x in range(x0, min(level.width, x0 + width)):
        top = None
        for y in range(level.height):
            if level.tile_at(x, y) == T_SOLID:
                top = y
                break
        tops.append("." if top is None else str(top % 10))
    print("ground  " + "".join(tops))


if __name__ == "__main__":
    main()
