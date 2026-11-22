"""Dump a generated level as ASCII so the segment layout is readable."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from retroblast.levels import build_level  # noqa: E402

SYM = {0: " ", 1: "#", 2: "=", 3: "^", 4: "~", 5: "S", 6: "D", 7: "G"}
OBJ = {"coin": "o", "diamond": "D", "gem": "*", "key": "k", "box": "b",
       "heart": "h", "star": "s", "magnet": "m", "spring": "p"}


def dump(w, i):
    lvl = build_level(w, i)
    print(f"=== level {w}:{i} {lvl.name}  width={lvl.width} ===")
    print("spawn", lvl.spawn, "exit", lvl.exit, "boss", lvl.boss)
    grid = [[SYM[lvl.tile_at(x, y)] for x in range(lvl.width)]
            for y in range(lvl.height)]
    for name, tx, ty in lvl.items:
        if 0 <= tx < lvl.width and 0 <= ty < lvl.height:
            grid[ty][tx] = OBJ.get(name, "?")
    for kind, tx, ty in lvl.enemies:
        grid[ty][tx] = {"slime": "x", "walker": "w", "flyer": "f",
                        "boss": "B"}.get(kind, "X")
    for tx, ty in lvl.checkpoints:
        grid[ty][tx] = "c"
    if lvl.exit:
        grid[lvl.exit[1]][lvl.exit[0]] = "E"
    for plat in lvl.platforms:
        print("moving platform:", plat)
    # ruler
    print("    " + "".join(str((x // 10) % 10) if x % 10 == 0 else " "
                           for x in range(lvl.width)))
    print("    " + "".join(str(x % 10) for x in range(lvl.width)))
    for y, row in enumerate(grid):
        print(f"{y:2d}  " + "".join(row))
    print()


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        w, i = (int(v) for v in arg.split(":"))
        dump(w, i)
