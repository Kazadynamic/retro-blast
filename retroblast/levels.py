"""Level construction: 4 worlds x 2 levels, assembled from seeded segments.

Levels are built as tile grids (16px tiles, 18 rows) plus object lists.
Everything is deterministic for a given (world, index) so the game is the same
on every machine and tests are reproducible.
"""
from __future__ import annotations

import random

from .config import (LEVEL_ROWS, SOLID_TILES, SURFACE_ROW, T_DOOR, T_EMPTY,
                     T_GATE, T_LAVA, T_PLATFORM, T_SECRET, T_SOLID, T_SPIKE,
                     TILE, WORLD_THEMES)

LEVEL_NAMES = [
    ("GRASSLAND 1-1", "GRASSLAND 1-2"),
    ("CAVERNS 2-1", "CAVERNS 2-2"),
    ("NEON CITY 3-1", "NEON CITY 3-2"),
    ("FORTRESS 4-1", "FORTRESS 4-2"),
]

SURFACE = SURFACE_ROW  # row of the ground surface


class Level:
    def __init__(self, world: int, index: int):
        self.world = world
        self.index = index
        self.theme = WORLD_THEMES[world]
        self.name = LEVEL_NAMES[world][index]
        self.tiles = []
        self.width = 0
        self.height = LEVEL_ROWS
        self.spawn = (3 * TILE, (SURFACE - 1) * TILE)
        self.exit = None           # (tx, ty)
        self.items = []            # (name, tx, ty)
        self.enemies = []          # (kind, tx, ty)
        self.platforms = []        # (tx, ty, length, axis, range)
        self.secrets = []          # (tx, ty, tw, th)
        self.doors = []            # [(tx, ty), ...]
        self.gates = []            # [(tx, ty), ...]
        self.boss = None           # (kind, tx, ty)
        self.checkpoints = []      # [(tx, ty), ...]
        self.world_px = 0
        self.trace = []            # segment names, for audits

    # -- helpers -----------------------------------------------------------
    def tile_at(self, tx: int, ty: int) -> int:
        # invisible walls left/right and a floor under the world keep the
        # player and the enemies inside the level
        if ty >= self.height:
            return T_SOLID
        if tx < 0 or tx >= self.width:
            return T_SOLID
        if ty < 0:
            return T_EMPTY
        return self.tiles[ty][tx]

    def set_tile(self, tx: int, ty: int, value: int) -> None:
        if 0 <= tx < self.width and 0 <= ty < self.height:
            self.tiles[ty][tx] = value

    def solid_at_px(self, x: float, y: float) -> bool:
        tx, ty = int(x // TILE), int(y // TILE)
        return self.tile_at(tx, ty) in (T_SOLID, T_DOOR, T_GATE)

    def is_pit(self, tx: int) -> bool:
        """True when the column has no real ground anywhere (a death pit)."""
        if tx < 0 or tx >= self.width:
            return False
        for y in range(SURFACE, self.height):
            if self.tiles[y][tx] == T_SOLID:
                return False
        return True


def build_level(world: int, index: int) -> Level:
    rng = random.Random(7000 + world * 100 + index * 7)
    theme = WORLD_THEMES[world]
    rows = LEVEL_ROWS
    nominal = 150 + index * 34 + world * 10   # planned playable length
    cols = nominal + 120                      # headroom so segments never overflow
    lvl = Level(world, index)
    lvl.tiles = [[T_EMPTY] * cols for _ in range(rows)]

    items, enemies, platforms, secrets, doors, gates, checkpoints = (
        [], [], [], [], [], [], [])
    boss = [None]
    exit_tile = [None]

    def ground(x0, x1, top=SURFACE):
        for x in range(max(0, x0), min(cols, x1)):
            for y in range(top, rows):
                lvl.tiles[y][x] = T_SOLID

    def platform(tx, ty, length):
        for x in range(tx, min(cols, tx + length)):
            if 0 <= ty < rows:
                lvl.tiles[ty][x] = T_PLATFORM

    def coin_row(tx, ty, n):
        for i in range(n):
            items.append(("coin", tx + i, ty))

    def coin_arc(tx, ty, n):
        for i in range(n):
            items.append(("coin", tx + i, ty - (1 if 0 < i < n - 1 else 0)))

    def add_enemy(kind, tx, ty=SURFACE - 1):
        """Only place a ground enemy on real, hazard-free ground.

        Reads the grid directly: lvl.width is still 0 while the level is being
        built, so Level.tile_at() would report every tile as empty.
        """
        if 1 < tx < cols - 1 and lvl.tiles[SURFACE][tx] in SOLID_TILES:
            enemies.append((kind, tx, ty))

    # -- segments ----------------------------------------------------------
    def seg_flat(x):
        ln = rng.randint(6, 11)
        ground(x, x + ln)
        if rng.random() < 0.75:
            coin_row(x + 1, SURFACE - 2, min(4, ln - 2))
        if rng.random() < 0.4:
            add_enemy(rng.choice(theme["enemy_set"]), x + ln // 2)
        if rng.random() < 0.25:
            items.append(("box", x + rng.randint(1, ln - 2), SURFACE - 1))
        return x + ln

    def seg_gap(x):
        gap = rng.randint(3, 4)
        coin_arc(x, SURFACE - 3, gap)
        return x + gap

    def seg_platforms(x):
        # a bridge of one-way platforms over the pit; the first one overhangs
        # the near edge so the player can jump straight up onto it
        gap = rng.randint(5, 6)
        for i in range((gap + 3) // 2 + 1):
            px = x - 1 + i * 2
            platform(px, SURFACE - 2, 2)
        coin_arc(x, SURFACE - 3, gap)
        return x + gap

    def seg_stairs(x):
        ln = rng.randint(3, 5)
        for i in range(ln):
            h = i + 1
            for y in range(SURFACE - h, rows):
                lvl.tiles[y][x + i] = T_SOLID
            items.append(("coin", x + i, SURFACE - h - 1))
        return x + ln

    def seg_spikes(x):
        ln = rng.randint(5, 8)
        ground(x, x + ln)
        for i in range(1, ln - 1):
            lvl.tiles[SURFACE][x + i] = T_SPIKE
        platform(x + 1, SURFACE - 3, ln - 2)
        return x + ln

    def seg_lava(x):
        ln = rng.randint(4, 6)
        for i in range(ln):
            lvl.tiles[SURFACE][x + i] = T_LAVA
            for y in range(SURFACE + 1, rows):
                lvl.tiles[y][x + i] = T_SOLID
        # stepping platforms every 2 tiles, the first overhangs the near edge
        for px in range(x - 1, x + ln + 1, 2):
            platform(px, SURFACE - 3, 2)
        return x + ln

    def seg_enemies(x):
        ln = rng.randint(7, 12)
        ground(x, x + ln)
        for _ in range(rng.randint(1, 2 + index)):
            add_enemy(rng.choice(theme["enemy_set"]),
                      x + rng.randint(2, ln - 2))
        if rng.random() < 0.4:
            items.append(("heart", x + ln // 2, SURFACE - 2))
        return x + ln

    def seg_secret(x):
        ln = 9
        ground(x, x + ln)
        # shallow 3-tile pocket; the false floor spans the whole pocket so the
        # player can always jump straight back out
        for yy in (SURFACE + 1, SURFACE + 2):
            for xx in range(x + 3, x + 6):
                lvl.tiles[yy][xx] = T_EMPTY
        for xx in (x + 3, x + 4, x + 5):
            lvl.tiles[SURFACE][xx] = T_SECRET
        secrets.append((x + 3, SURFACE + 1, 3, 2))
        items.append(("gem", x + 3, SURFACE + 1))
        items.append(("gem", x + 4, SURFACE + 1))
        items.append(("diamond", x + 5, SURFACE + 1))
        items.append(("coin", x + 1, SURFACE - 1))
        return x + ln

    def seg_keydoor(x):
        ln = 15
        ground(x, x + ln)
        door_x = x + 8
        for yy in range(2, SURFACE):
            lvl.tiles[yy][door_x] = T_DOOR
            doors.append((door_x, yy))
        # the key sits on the ground in plain sight, just before the door
        items.append(("key", door_x - 3, SURFACE - 1))
        platform(x + 4, SURFACE - 3, 3)
        coin_arc(x + 4, SURFACE - 4, 3)
        coin_row(x + 11, SURFACE - 2, 3)
        return x + ln

    def seg_moving(x):
        # short enough to jump even when the platform is on the far side
        gap = rng.randint(3, 4)
        platforms.append((x + 1, SURFACE - 2, 3, "h", 2))
        coin_arc(x, SURFACE - 3, gap)
        return x + gap

    def seg_drop(x):
        # short descent (max 2 tiles) so it can never open a pit or leave a
        # wall the player cannot climb back up
        ln = rng.randint(4, 6)
        for i in range(ln):
            top = SURFACE + min(i, 2)
            for y in range(top, rows):
                lvl.tiles[y][x + i] = T_SOLID
        coin_row(x, SURFACE - 1, ln)
        return x + ln

    def seg_boss(x):
        ln = 26
        ground(x - 3, x +ln)   # flat run-up: never a pit right at the gate
        gate_x = x + ln - 3
        for yy in range(2, SURFACE):
            lvl.tiles[yy][gate_x] = T_GATE
            gates.append((gate_x, yy))
        boss[0] = ("boss", x + ln // 2, SURFACE - 2)
        exit_tile[0] = (x + ln - 2, SURFACE - 1)
        items.append(("heart", x + 2, SURFACE - 1))
        return x + ln
    def has_surface(tx):
        return 0 <= tx < cols and lvl.tiles[SURFACE][tx] == T_SOLID

    # -- assemble ----------------------------------------------------------
    ground(0, 12)
    lvl.spawn = (3 * TILE, (SURFACE - 1) * TILE)
    x = 12
    pool = [seg_flat, seg_gap, seg_platforms, seg_stairs, seg_enemies]
    if world >= 1:
        pool += [seg_spikes]
    if world >= 2:
        pool += [seg_moving, seg_drop]
    if world >= 3:
        pool += [seg_lava]
    if index >= 1:
        pool += [seg_secret, seg_keydoor]
        pool += [seg_flat, seg_gap]  # weight the easy ones a bit more
    pit_segments = (seg_gap, seg_platforms, seg_moving)
    # pit/stairs/drop/hazard segments change the ground or punish a missed
    # landing, so two of them in a row would create an island, a wall, or a
    # jump out of a pit that lands straight on spikes
    edge_sensitive = (seg_gap, seg_platforms, seg_moving, seg_stairs, seg_drop,
                      seg_spikes, seg_lava)
    easy_segments = (seg_flat, seg_enemies)
    last_sensitive = False
    warmup = 2          # the first segments are always gentle
    keydoors = 0        # one locked door per level: one key is enough
    target = nominal - 36
    guard = 0
    while x < target and guard < 200:
        guard += 1
        if warmup > 0:
            choices = [s for s in easy_segments if s in pool] or [seg_flat]
            warmup -= 1
        else:
            choices = [s for s in pool
                       if not (last_sensitive and s in edge_sensitive)
                       and not (s is seg_keydoor and keydoors >= 1)]
        if not choices:
            choices = [seg_flat]
        seg = rng.choice(choices)
        if seg is seg_keydoor:
            keydoors += 1
        start = x
        new_x = seg(x)
        if new_x <= x:
            new_x = x + 4
        x = new_x
        last_sensitive = seg in edge_sensitive
        lvl.trace.append((seg.__name__, start, x - 1))
        if rng.random() < 0.25:
            cx = max(2, x - 4)
            if has_surface(cx):
                checkpoints.append((cx, SURFACE - 1))

    if index == 1:
        x = seg_boss(x)
        width = x + 4
    else:
        ground(x, x + 12)
        exit_tile[0] = (x + 8, SURFACE - 1)
        coin_row(x + 2, SURFACE - 2, 3)
        width = x + 12

    lvl.width = width
    lvl.tiles = [row[:width] for row in lvl.tiles]
    lvl.world_px = width * TILE
    lvl.items = items
    lvl.enemies = enemies
    lvl.platforms = platforms
    lvl.secrets = secrets
    lvl.doors = doors
    lvl.gates = gates
    lvl.boss = boss[0]
    lvl.checkpoints = checkpoints
    lvl.exit = exit_tile[0]
    return lvl


def level_list():
    """All 8 levels as (world, index, name)."""
    out = []
    for w in range(4):
        for i in range(2):
            out.append((w, i, LEVEL_NAMES[w][i]))
    return out
