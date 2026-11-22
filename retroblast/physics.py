"""Tile collision helpers shared by the player, enemies and platforms."""
from __future__ import annotations

from .config import SOLID_TILES, TILE


def move_x(world, r, dx) -> bool:
    """Move rect r=[x,y,w,h] horizontally, resolving against solid tiles."""
    r[0] += dx
    ty0 = int(r[1] // TILE)
    ty1 = int((r[1] + r[3] - 1) // TILE)
    if dx > 0:
        tx = int((r[0] + r[2]) // TILE)
        for ty in range(ty0, ty1 + 1):
            if world.tile_at(tx, ty) in SOLID_TILES:
                r[0] = tx * TILE - r[2] - 0.01
                return True
    elif dx < 0:
        tx = int(r[0] // TILE)
        for ty in range(ty0, ty1 + 1):
            if world.tile_at(tx, ty) in SOLID_TILES:
                r[0] = (tx + 1) * TILE + 0.01
                return True
    return False


def move_y(world, r, dy, prev_bottom) -> tuple:
    """Move rect vertically. Returns (hit_solid, hit_one_way)."""
    r[1] += dy
    tx0 = int(r[0] // TILE)
    tx1 = int((r[0] + r[2] - 1) // TILE)
    if dy > 0:
        ty = int((r[1] + r[3]) // TILE)
        for tx in range(tx0, tx1 + 1):
            tile = world.tile_at(tx, ty)
            if tile in SOLID_TILES or (tile == 2 and prev_bottom <= ty * TILE + 0.6):
                r[1] = ty * TILE - r[3] - 0.01
                return True, tile == 2
        return False, False
    if dy < 0:
        ty = int(r[1] // TILE)
        for tx in range(tx0, tx1 + 1):
            if world.tile_at(tx, ty) in SOLID_TILES:
                r[1] = (ty + 1) * TILE + 0.01
                return True, False
    return False, False


def tile_overlap(world, r):
    """Yield (tx, ty, tile) for every tile the rect touches."""
    tx0 = int(r[0] // TILE)
    tx1 = int((r[0] + r[2] - 1) // TILE)
    ty0 = int(r[1] // TILE)
    ty1 = int((r[1] + r[3] - 1) // TILE)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            tile = world.tile_at(tx, ty)
            if tile:
                yield tx, ty, tile
