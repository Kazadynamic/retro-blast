"""Procedural pixel-art generation (PIL) + asset loading for RETRO BLAST!.

All artwork is generated with code: no external images are required.  The
generator writes PNG sheets into assets/ on first run; the loader slices them
into pygame surfaces and keeps an in-memory cache for every visual variant
(skins / backpacks / accessories / world tints).
"""
from __future__ import annotations

import os
from functools import lru_cache

import pygame
from PIL import Image, ImageDraw

from .config import (ASSET_DIR, ASSET_STAMP, AUDIO_DIR, BG_DIR, FONT_PATH,
                     SPRITE_DIR, WORLD_THEMES)

# ---------------------------------------------------------------------------
# Hammy variants
# ---------------------------------------------------------------------------
SKINS = {
    "classic": ((232, 150, 60), (176, 104, 40), (255, 238, 214)),
    "shadow": ((150, 110, 210), (96, 62, 150), (226, 214, 246)),
    "mint": ((110, 214, 170), (62, 150, 116), (232, 252, 240)),
    "gold": ((255, 208, 84), (196, 146, 40), (255, 246, 214)),
}
PACKS = {
    "blue": ((64, 128, 224), (36, 78, 150)),
    "red": ((224, 72, 72), (150, 36, 40)),
    "jet": ((70, 74, 96), (40, 42, 60)),
    "gold": ((250, 200, 60), (176, 128, 28)),
}
ACCESSORIES = ("none", "band", "cape", "hat")

POSE_ORDER = ["idle", "walk", "run", "jump", "fall", "land", "hurt",
              "victory", "collect", "dash"]
POSE_COUNT = {"idle": 2, "walk": 4, "run": 4, "jump": 1, "fall": 1, "land": 1,
              "hurt": 1, "victory": 2, "collect": 1, "dash": 1}
HAMMY_W, HAMMY_H = 24, 24
HAMMY_FRAMES = sum(POSE_COUNT[p] for p in POSE_ORDER)
POSE_START = {}
_i = 0
for _p in POSE_ORDER:
    POSE_START[_p] = _i
    _i += POSE_COUNT[_p]

OUTLINE = (74, 44, 26)


def _pose_params(pose: str, frame: int) -> dict:
    p = dict(bob=0, foot_l=(0, 0), foot_r=(0, 0), arm="down", squash=1.0,
             eye="open", lean=0, mouth="smile")
    if pose == "idle":
        p["bob"] = 1 if frame else 0
        p["eye"] = "blink" if frame else "open"
    elif pose == "walk":
        seq = [(-1, 0), (0, -1), (1, 0), (0, 0)]
        p["foot_l"] = seq[frame % 4]
        p["foot_r"] = (-seq[frame % 4][0], seq[(frame + 2) % 4][1])
        p["bob"] = 1 if frame % 2 else 0
    elif pose == "run":
        seq = [(-2, 0), (0, -2), (2, 0), (0, -1)]
        p["foot_l"] = seq[frame % 4]
        p["foot_r"] = (-seq[frame % 4][0], seq[(frame + 2) % 4][1])
        p["bob"] = 1 if frame % 2 else 0
        p["lean"] = 2
        p["arm"] = "pump"
    elif pose == "jump":
        p["foot_l"] = (0, -2)
        p["foot_r"] = (0, -2)
        p["arm"] = "up"
        p["bob"] = -1
    elif pose == "fall":
        p["foot_l"] = (-1, 1)
        p["foot_r"] = (1, 1)
        p["arm"] = "out"
    elif pose == "land":
        p["squash"] = 0.78
        p["arm"] = "out"
    elif pose == "hurt":
        p["eye"] = "x"
        p["lean"] = -3
        p["arm"] = "out"
        p["mouth"] = "ouch"
    elif pose == "victory":
        p["arm"] = "up"
        p["eye"] = "happy"
        p["bob"] = -2 if frame else 0
    elif pose == "collect":
        p["arm"] = "forward"
        p["eye"] = "happy"
    elif pose == "dash":
        p["lean"] = 4
        p["foot_l"] = (-2, 0)
        p["foot_r"] = (2, -1)
        p["arm"] = "back"
    return p


def _hammy_image(pose: str, frame: int, skin: str = "classic",
                 pack: str = "blue", acc: str = "none") -> Image.Image:
    fur, fur_dk, cream = SKINS.get(skin, SKINS["classic"])
    pk, pk_dk = PACKS.get(pack, PACKS["blue"])
    p = _pose_params(pose, frame)
    img = Image.new("RGBA", (HAMMY_W, HAMMY_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bob = p["bob"]
    sq = p["squash"]
    lean = p["lean"]

    def R(x0, y0, x1, y1, c):
        d.rectangle([x0, y0 + bob, x1, y1 + bob], fill=c)

    def E(x0, y0, x1, y1, c):
        d.ellipse([x0, y0 + bob, x1, y1 + bob], fill=c)

    body_h = int(11 * sq)
    body_top = 21 - body_h
    if acc == "cape":
        d.polygon([(8, 11 + bob), (20, 11 + bob), (23, 22 + bob), (6, 22 + bob)],
                  fill=(44, 196, 214))
    # backpack (behind body, on the back = left side)
    d.rounded_rectangle([2, 11 + bob, 7, 20 + bob], radius=2, fill=pk,
                        outline=pk_dk)
    R(3, 14 + bob, 6, 18 + bob, pk_dk)
    R(3, 14 + bob, 6, 15 + bob, (255, 255, 255, 160))
    # shoulder strap so the pack reads as a backpack
    R(6, 10 + bob, 11, 12 + bob, pk_dk)
    R(7, 12 + bob, 8, 18 + bob, pk_dk)
    # body
    d.rounded_rectangle([6, body_top + bob, 18, 21 + bob], radius=4, fill=fur,
                        outline=fur_dk)
    # belly
    d.rounded_rectangle([8, 14 + bob, 16, 20 + bob], radius=3, fill=cream)
    # head
    d.ellipse([5, 2 + bob, 19, 14 + bob], fill=fur, outline=fur_dk)
    # ears
    E(5, 1 + bob, 9, 5 + bob, fur)
    E(5, 1 + bob, 9, 5 + bob, fur_dk)
    E(6, 2 + bob, 8, 4 + bob, (244, 160, 170))
    E(15, 1 + bob, 19, 5 + bob, fur)
    E(15, 1 + bob, 19, 5 + bob, fur_dk)
    E(16, 2 + bob, 18, 4 + bob, (244, 160, 170))
    # goggles strap + lenses
    R(5, 5 + bob, 19, 7 + bob, (240, 140, 30))
    for cx in (9, 15):
        E(cx - 3, 3 + bob, cx + 3, 9 + bob, (240, 140, 30))
        E(cx - 2, 4 + bob, cx + 2, 8 + bob, (120, 220, 235))
        E(cx - 1, 5 + bob, cx + 1, 7 + bob, (200, 246, 252))
    # eyes
    if p["eye"] == "open":
        for cx in (9, 15):
            R(cx - 1, 5 + bob, cx, 7 + bob, (28, 22, 30))
            R(cx - 1, 5 + bob, cx, 5 + bob, (255, 255, 255))
    elif p["eye"] == "blink":
        for cx in (9, 15):
            R(cx - 1, 6 + bob, cx + 1, 7 + bob, (28, 22, 30))
    elif p["eye"] == "happy":
        for cx in (9, 15):
            d.arc([cx - 2, 4 + bob, cx + 2, 8 + bob], 180, 360,
                  fill=(28, 22, 30))
    else:  # x
        for cx in (9, 15):
            R(cx - 1, 5 + bob, cx + 1, 6 + bob, (28, 22, 30))
            R(cx - 1, 7 + bob, cx + 1, 8 + bob, (28, 22, 30))
    # nose + mouth
    R(11, 9 + bob, 13, 10 + bob, (244, 130, 150))
    if p["mouth"] == "smile":
        R(11, 11 + bob, 12, 11 + bob, OUTLINE)
        R(13, 11 + bob, 14, 11 + bob, OUTLINE)
    else:
        E(11, 10 + bob, 13, 12 + bob, OUTLINE)
    # arms
    arm = p["arm"]
    if arm == "up":
        R(3, 6 + bob, 5, 11 + bob, fur)
        R(19, 6 + bob, 21, 11 + bob, fur)
    elif arm == "out":
        R(2, 11 + bob, 6, 13 + bob, fur)
        R(18, 11 + bob, 22, 13 + bob, fur)
    elif arm == "forward":
        R(16, 12 + bob, 22, 14 + bob, fur)
        R(2, 12 + bob, 6, 14 + bob, fur)
    elif arm == "back":
        R(1, 11 + bob, 5, 13 + bob, fur)
        R(19, 11 + bob, 23, 13 + bob, fur)
    elif arm == "pump":
        R(3, 9 + bob, 6, 13 + bob, fur)
        R(18, 12 + bob, 21, 15 + bob, fur)
    else:
        R(4, 11 + bob, 6, 15 + bob, fur)
        R(18, 11 + bob, 20, 15 + bob, fur)
    # legs then feet / shoes
    fl = p["foot_l"]
    fr = p["foot_r"]
    R(7 + fl[0], 18 + fl[1] + bob, 9 + fl[0], 21 + fl[1] + bob, fur_dk)
    R(14 + fr[0], 18 + fr[1] + bob, 16 + fr[0], 21 + fr[1] + bob, fur_dk)
    d.rounded_rectangle([6 + fl[0], 20 + fl[1] + bob, 10 + fl[0],
                         22 + fl[1] + bob], radius=1, fill=(64, 128, 224))
    d.rounded_rectangle([14 + fr[0], 20 + fr[1] + bob, 18 + fr[0],
                         22 + fr[1] + bob], radius=1, fill=(64, 128, 224))
    # accessory
    if acc == "band":
        R(5, 4 + bob, 19, 6 + bob, (224, 60, 56))
        R(17, 2 + bob, 20, 6 + bob, (224, 60, 56))
    elif acc == "hat":
        d.polygon([(9, 4 + bob), (15, 4 + bob), (12, -1 + bob)],
                  fill=(250, 214, 64))
        R(8, 3 + bob, 16, 5 + bob, (224, 60, 56))
    if lean:
        img = img.transform((HAMMY_W, HAMMY_H), Image.AFFINE,
                            (1, 0, -lean * 0.3, 0, 1, 0))
    return img


@lru_cache(maxsize=512)
def hammy_frame(pose: str, frame: int, skin: str, pack: str,
                acc: str) -> pygame.Surface:
    img = _hammy_image(pose, frame, skin, pack, acc)
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


@lru_cache(maxsize=256)
def hammy_big(pose: str, frame: int, skin: str, pack: str, acc: str,
              factor: int = 3) -> pygame.Surface:
    """Nearest-neighbour upscale so the pixel art stays crisp in menus."""
    surf = hammy_frame(pose, frame, skin, pack, acc)
    img = Image.frombytes("RGBA", surf.get_size(), pygame.image.tobytes(surf, "RGBA"))
    img = img.resize((surf.get_width() * factor, surf.get_height() * factor),
                     Image.NEAREST)
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------
ENEMY_KINDS = ("slime", "walker", "flyer", "boss")
ENEMY_TINTS = {
    0: {"slime": (110, 214, 96), "walker": (224, 120, 60), "flyer": (190, 120, 230),
        "boss": (110, 214, 96)},
    1: {"slime": (150, 110, 220), "walker": (90, 200, 220), "flyer": (220, 100, 180),
        "boss": (90, 200, 220)},
    2: {"slime": (250, 110, 190), "walker": (120, 220, 220), "flyer": (250, 200, 80),
        "boss": (250, 200, 80)},
    3: {"slime": (250, 150, 60), "walker": (230, 80, 70), "flyer": (250, 190, 60),
        "boss": (230, 80, 70)},
}


def _enemy_image(kind: str, frame: int, world: int) -> Image.Image:
    tint = ENEMY_TINTS[world][kind]
    dark = tuple(max(0, c - 70) for c in tint)
    light = tuple(min(255, c + 60) for c in tint)
    size = 32 if kind == "boss" else 16
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if kind == "slime":
        sq = 2 if frame else 0
        d.rounded_rectangle([2, 6 + sq, 14, 15], radius=4, fill=tint,
                            outline=dark)
        d.rounded_rectangle([4, 4 + sq, 12, 8 + sq], radius=3, fill=tint,
                            outline=dark)
        d.ellipse([5, 5 + sq, 8, 8 + sq], fill=(255, 255, 255))
        d.ellipse([9, 5 + sq, 12, 8 + sq], fill=(255, 255, 255))
        d.rectangle([6, 6 + sq, 7, 8 + sq], fill=(28, 22, 30))
        d.rectangle([10, 6 + sq, 11, 8 + sq], fill=(28, 22, 30))
        d.rectangle([6, 11 + sq, 10, 12 + sq], fill=dark)
        d.ellipse([4, 6 + sq, 6, 8 + sq], fill=light)
    elif kind == "walker":
        d.rounded_rectangle([2, 3, 14, 13], radius=2, fill=tint, outline=dark)
        d.rectangle([3, 1, 6, 4], fill=dark)
        d.rectangle([10, 1, 13, 4], fill=dark)
        d.rectangle([5, 6, 8, 9], fill=(255, 255, 255))
        d.rectangle([9, 6, 12, 9], fill=(255, 255, 255))
        d.rectangle([6, 7, 7, 8], fill=(28, 22, 30))
        d.rectangle([10, 7, 11, 8], fill=(28, 22, 30))
        d.rectangle([6, 11, 10, 12], fill=dark)
        off = 1 if frame else 0
        d.rectangle([3, 13, 5, 15 - off], fill=dark)
        d.rectangle([11, 13, 13, 14 + off], fill=dark)
    elif kind == "flyer":
        wing = 2 if frame else 5
        d.polygon([(1, 8), (5, 8), (5, 8 - wing)], fill=light)
        d.polygon([(15, 8), (11, 8), (11, 8 - wing)], fill=light)
        d.ellipse([4, 4, 12, 12], fill=tint, outline=dark)
        d.rectangle([6, 6, 8, 8], fill=(28, 22, 30))
        d.rectangle([7, 6, 8, 7], fill=(255, 255, 255))
        d.rectangle([9, 10, 11, 11], fill=dark)
        d.polygon([(7, 12), (9, 12), (8, 14)], fill=(250, 214, 64))
    else:  # boss
        sq = 3 if frame else 0
        d.rounded_rectangle([2, 8 + sq, 30, 30], radius=8, fill=tint,
                            outline=dark)
        d.rounded_rectangle([5, 3 + sq, 27, 12 + sq], radius=6, fill=tint,
                            outline=dark)
        for cx in (10, 20):
            d.ellipse([cx - 4, 6 + sq, cx + 4, 14 + sq], fill=(255, 255, 255))
            d.rectangle([cx - 1, 8 + sq, cx + 2, 12 + sq], fill=(200, 30, 30))
        d.rectangle([10, 18 + sq, 22, 20 + sq], fill=dark)
        for tx in (11, 15, 19):
            d.polygon([(tx, 18 + sq), (tx + 3, 18 + sq), (tx + 1, 22 + sq)],
                      fill=(255, 255, 255))
        d.polygon([(6, 3 + sq), (9, -2 + sq), (12, 3 + sq)], fill=(250, 214, 64))
        d.polygon([(14, 3 + sq), (17, -3 + sq), (20, 3 + sq)], fill=(250, 214, 64))
        d.polygon([(20, 3 + sq), (23, -2 + sq), (26, 3 + sq)], fill=(250, 214, 64))
        d.ellipse([5, 9 + sq, 9, 13 + sq], fill=light)
    return img


@lru_cache(maxsize=128)
def enemy_frame(kind: str, frame: int, world: int) -> pygame.Surface:
    img = _enemy_image(kind, frame, world)
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


# ---------------------------------------------------------------------------
# Items / collectibles
# ---------------------------------------------------------------------------
ITEM_DEFS = [
    ("coin", 6, 12), ("diamond", 2, 12), ("gem", 2, 12), ("key", 2, 12),
    ("box", 2, 14), ("heart", 1, 12), ("star", 1, 12), ("magnet", 1, 12),
    ("spring", 1, 12),
]
ITEM_START = {}
_i = 0
for _name, _n, _s in ITEM_DEFS:
    ITEM_START[_name] = (_i, _n, _s)
    _i += _n


def _item_image(name: str, frame: int) -> Image.Image:
    size = ITEM_START[name][2]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size // 2
    if name == "coin":
        ph = [6, 4, 2, 4, 6, 4][frame % 6]
        d.ellipse([c - ph, 1, c + ph, size - 1], fill=(255, 208, 48),
                  outline=(176, 128, 20))
        if ph > 3:
            d.rectangle([c - 1, 3, c + 1, size - 3], fill=(255, 240, 170))
    elif name == "diamond":
        w = 5 if frame else 4
        d.polygon([(c, 1), (c + w, c), (c, size - 1), (c - w, c)],
                  fill=(86, 200, 255), outline=(30, 110, 190))
        d.polygon([(c, 3), (c + 2, c), (c, size - 3), (c - 2, c)],
                  fill=(190, 240, 255))
    elif name == "gem":
        col = (255, 226, 92) if frame == 0 else (255, 120, 190)
        d.polygon([(c, 1), (size - 2, c), (c, size - 1), (1, c)], fill=col,
                  outline=(140, 90, 20))
        d.line([(1, c), (size - 2, c)], fill=(255, 255, 255))
    elif name == "key":
        d.ellipse([2, 2, 8, 8], outline=(255, 208, 48), width=2)
        d.rectangle([7, 4, size - 2, 6], fill=(255, 208, 48))
        d.rectangle([size - 5, 6, size - 3, 9], fill=(255, 208, 48))
        d.rectangle([size - 8, 6, size - 6, 8], fill=(255, 208, 48))
    elif name == "box":
        d.rounded_rectangle([1, 1, size - 2, size - 2], radius=2,
                            fill=(196, 138, 74), outline=(120, 76, 40))
        d.line([(1, c), (size - 2, c)], fill=(120, 76, 40))
        d.rectangle([c - 2, c - 2, c + 2, c + 2], fill=(250, 214, 64))
        if frame:
            d.line([(2, 2), (size - 3, size - 3)], fill=(120, 76, 40))
    elif name == "heart":
        d.polygon([(c, size - 2), (1, c - 1), (1, 3), (c - 2, 1), (c, 3),
                   (c + 2, 1), (size - 2, 3), (size - 2, c - 1)],
                  fill=(232, 60, 70), outline=(150, 24, 36))
    elif name == "star":
        import math
        pts = []
        for k in range(10):
            r = 6 if k % 2 == 0 else 3
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        d.polygon(pts, fill=(255, 226, 92), outline=(196, 150, 20))
    elif name == "magnet":
        d.arc([2, 2, size - 3, size - 4], 0, 180, fill=(224, 60, 56), width=3)
        d.rectangle([2, c, 5, size - 2], fill=(224, 60, 56))
        d.rectangle([size - 6, c, size - 3, size - 2], fill=(224, 60, 56))
        d.rectangle([2, size - 4, 5, size - 2], fill=(200, 200, 210))
        d.rectangle([size - 6, size - 4, size - 3, size - 2],
                    fill=(200, 200, 210))
    elif name == "spring":
        d.rectangle([2, size - 4, size - 3, size - 2], fill=(140, 148, 160))
        for k in range(3):
            d.line([(3, size - 6 - k * 3), (size - 4, size - 6 - k * 3)],
                   fill=(200, 206, 216))
        d.rectangle([1, 1, size - 2, 4], fill=(250, 214, 64))
    return img


@lru_cache(maxsize=128)
def item_frame(name: str, frame: int) -> pygame.Surface:
    img = _item_image(name, frame)
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


def _door_image(open_: bool) -> pygame.Surface:
    img = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 15, 31], radius=3, fill=(120, 76, 44),
                        outline=(74, 46, 28))
    if open_:
        d.rectangle([3, 3, 12, 28], fill=(28, 22, 40))
        d.rectangle([3, 3, 12, 5], fill=(120, 220, 235))
    else:
        d.rectangle([3, 3, 12, 28], fill=(196, 138, 74))
        d.rectangle([9, 15, 12, 18], fill=(255, 208, 48))
        d.rectangle([3, 3, 12, 5], fill=(160, 106, 56))
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


@lru_cache(maxsize=4)
def door_frame(open_: bool) -> pygame.Surface:
    return _door_image(open_)


def _gate_image() -> pygame.Surface:
    img = Image.new("RGBA", (16, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 15, 47], fill=(90, 92, 110), outline=(40, 42, 60))
    for y in range(4, 48, 8):
        d.rectangle([2, y, 13, y + 4], fill=(140, 148, 168))
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


def gate_frame() -> pygame.Surface:
    return _gate_image()


def _checkpoint_image(lit: bool) -> pygame.Surface:
    img = Image.new("RGBA", (16, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([6, 4, 8, 23], fill=(90, 92, 110))
    col = (250, 214, 64) if lit else (120, 124, 140)
    d.polygon([(8, 4), (15, 7), (8, 11)], fill=col)
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


@lru_cache(maxsize=4)
def checkpoint_frame(lit: bool) -> pygame.Surface:
    return _checkpoint_image(lit)


# ---------------------------------------------------------------------------
# Tiles
# ---------------------------------------------------------------------------
TILE_ORDER = ["ground_top", "ground_fill", "platform", "spike", "lava0", "lava1",
              "secret_top", "door_tile", "gate_tile", "crate", "torch0", "torch1",
              "decor_grass", "decor_flower", "decor_crystal", "decor_neon",
              "decor_rock", "decor_chain"]


def _tile_image(name: str, theme: dict) -> Image.Image:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    g = theme["ground"]
    dirt = theme["dirt"]
    dirt_dk = theme["dirt_dk"]
    acc = theme["accent"]
    if name in ("ground_top", "secret_top"):
        d.rectangle([0, 0, 15, 15], fill=dirt)
        d.rectangle([0, 0, 15, 4], fill=g)
        d.rectangle([0, 4, 15, 5], fill=tuple(max(0, c - 40) for c in g))
        for x in range(0, 16, 4):
            d.rectangle([x + 1, 1, x + 2, 3], fill=tuple(min(255, c + 30) for c in g))
        d.rectangle([2, 8, 3, 9], fill=dirt_dk)
        d.rectangle([10, 12, 12, 13], fill=dirt_dk)
    elif name == "ground_fill":
        d.rectangle([0, 0, 15, 15], fill=dirt)
        d.rectangle([1, 3, 3, 5], fill=dirt_dk)
        d.rectangle([8, 9, 11, 11], fill=dirt_dk)
        d.rectangle([4, 12, 6, 14], fill=tuple(min(255, c + 20) for c in dirt))
    elif name == "platform":
        d.rounded_rectangle([0, 2, 15, 8], radius=2, fill=g, outline=dirt_dk)
        d.rectangle([2, 4, 13, 6], fill=tuple(min(255, c + 30) for c in g))
        d.rectangle([0, 8, 15, 9], fill=dirt_dk)
    elif name == "spike":
        d.rectangle([0, 13, 15, 15], fill=(90, 92, 110))
        for x in (1, 6, 11):
            d.polygon([(x, 13), (x + 3, 3), (x + 6, 13)], fill=(200, 206, 216),
                      outline=(110, 116, 132))
    elif name in ("lava0", "lava1"):
        d.rectangle([0, 0, 15, 15], fill=(244, 84, 28))
        d.rectangle([0, 0, 15, 3], fill=(255, 190, 40))
        for x in range(2, 16, 6):
            yy = 5 if (x + (0 if name == "lava0" else 3)) % 12 else 8
            d.rectangle([x, yy, x + 2, yy + 2], fill=(255, 226, 92))
        d.rectangle([0, 13, 15, 15], fill=(160, 40, 20))
    elif name == "door_tile":
        d.rectangle([0, 0, 15, 15], fill=(120, 76, 44))
        d.rectangle([2, 2, 13, 15], fill=(196, 138, 74))
        d.rectangle([7, 7, 9, 11], fill=(255, 208, 48))
        d.rectangle([0, 0, 15, 1], fill=(74, 46, 28))
    elif name == "gate_tile":
        d.rectangle([0, 0, 15, 15], fill=(90, 92, 110))
        d.rectangle([2, 0, 4, 15], fill=(140, 148, 168))
        d.rectangle([11, 0, 13, 15], fill=(140, 148, 168))
    elif name == "crate":
        d.rectangle([1, 1, 14, 14], fill=(196, 138, 74), outline=(120, 76, 40))
        d.line([(1, 1), (14, 14)], fill=(120, 76, 40))
        d.line([(14, 1), (1, 14)], fill=(120, 76, 40))
    elif name in ("torch0", "torch1"):
        d.rectangle([7, 8, 8, 15], fill=(120, 76, 44))
        h = 2 if name == "torch1" else 0
        d.ellipse([5, 3 - h, 10, 9], fill=(255, 190, 40))
        d.ellipse([6, 4 - h, 9, 8], fill=(255, 240, 150))
    elif name == "decor_grass":
        for x, h in ((2, 5), (5, 7), (9, 4), (12, 6)):
            d.rectangle([x, 15 - h, x + 1, 15], fill=g)
    elif name == "decor_flower":
        d.rectangle([7, 8, 8, 15], fill=g)
        d.ellipse([5, 4, 10, 9], fill=acc)
        d.ellipse([6, 5, 9, 8], fill=(255, 255, 255))
    elif name == "decor_crystal":
        d.polygon([(8, 1), (12, 8), (8, 15), (4, 8)], fill=acc,
                  outline=tuple(max(0, c - 60) for c in acc))
        d.line([(8, 2), (8, 14)], fill=(255, 255, 255))
    elif name == "decor_neon":
        d.rectangle([2, 3, 13, 12], fill=(30, 28, 52))
        d.rectangle([3, 4, 12, 11], outline=acc)
        d.rectangle([5, 6, 10, 7], fill=acc)
        d.rectangle([7, 8, 8, 9], fill=(255, 255, 255))
    elif name == "decor_rock":
        d.ellipse([3, 8, 13, 15], fill=dirt)
        d.ellipse([5, 6, 11, 10], fill=tuple(min(255, c + 26) for c in dirt))
    elif name == "decor_chain":
        for y in range(0, 16, 4):
            d.rectangle([7, y, 8, y + 3], fill=(180, 186, 198))
    return img


@lru_cache(maxsize=64)
def tile_image(name: str, world: int) -> pygame.Surface:
    theme = WORLD_THEMES[world]
    img = _tile_image(name, theme)
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


# ---------------------------------------------------------------------------
# Backgrounds (512x288 parallax layers)
# ---------------------------------------------------------------------------
def _gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def _cloud(d, x, y, s, col=(255, 255, 255)):
    d.ellipse([x, y, x + 26 * s, y + 10 * s], fill=col)
    d.ellipse([x + 8 * s, y - 5 * s, x + 20 * s, y + 8 * s], fill=col)
    d.rectangle([x + 4 * s, y + 4 * s, x + 22 * s, y + 9 * s], fill=col)


def background_far(world: int) -> pygame.Surface:
    import random
    rng = random.Random(100 + world)
    w, h = 512, 288
    if world == 0:
        img = _gradient((w, h), (86, 178, 238), (186, 238, 246))
        d = ImageDraw.Draw(img)
        d.ellipse([400, 26, 456, 82], fill=(255, 246, 190))
        d.ellipse([408, 34, 448, 74], fill=(255, 252, 220))
        for _ in range(7):
            _cloud(d, rng.randint(-20, w), rng.randint(10, 130), rng.choice([1, 1, 2]))
        d.polygon([(0, 288), (60, 210), (140, 288)], fill=(150, 120, 190))
        d.polygon([(90, 288), (190, 190), (300, 288)], fill=(128, 96, 176))
        d.polygon([(240, 288), (340, 216), (460, 288)], fill=(150, 120, 190))
        d.polygon([(400, 288), (480, 226), (560, 288)], fill=(128, 96, 176))
    elif world == 1:
        img = _gradient((w, h), (18, 14, 40), (44, 30, 72))
        d = ImageDraw.Draw(img)
        for _ in range(60):
            x, y = rng.randint(0, w), rng.randint(0, 150)
            v = 160 + rng.randint(0, 80)
            d.point((x, y), fill=(v, v, v))
        for _ in range(9):
            x = rng.randint(0, w)
            hh = rng.randint(50, 150)
            col = rng.choice([(90, 60, 160), (60, 90, 190), (140, 70, 180)])
            d.polygon([(x, 288), (x + 16, 288 - hh), (x + 34, 288)], fill=col)
            d.polygon([(x + 16, 288 - hh), (x + 24, 288 - hh - 26), (x + 34, 288)],
                      fill=(180, 140, 240))
    elif world == 2:
        img = _gradient((w, h), (12, 10, 30), (40, 22, 66))
        d = ImageDraw.Draw(img)
        for _ in range(70):
            v = rng.randint(140, 255)
            d.point((rng.randint(0, w), rng.randint(0, 120)), fill=(v, v, v))
        x = -10
        while x < w + 20:
            bh = rng.randint(70, 190)
            bw = rng.randint(28, 52)
            d.rectangle([x, 288 - bh, x + bw, 288], fill=(26, 24, 48))
            for wy in range(288 - bh + 8, 280, 12):
                for wx in range(x + 4, x + bw - 4, 9):
                    if rng.random() < 0.45:
                        d.rectangle([wx, wy, wx + 4, wy + 5],
                                    fill=rng.choice([(255, 72, 200), (44, 196, 214),
                                                     (250, 214, 64)]))
            x += bw + rng.randint(4, 14)
    else:
        img = _gradient((w, h), (30, 12, 22), (86, 26, 26))
        d = ImageDraw.Draw(img)
        for _ in range(50):
            d.point((rng.randint(0, w), rng.randint(0, 200)),
                    fill=(255, rng.randint(120, 200), 40))
        x = -10
        while x < w + 20:
            bw = rng.randint(36, 70)
            bh = rng.randint(60, 170)
            d.rectangle([x, 288 - bh, x + bw, 288], fill=(64, 32, 34))
            d.rectangle([x - 3, 288 - bh, x + bw + 3, 288 - bh + 8], fill=(96, 46, 44))
            for k in range(0, bw, 12):
                d.rectangle([x + k, 288 - bh - 8, x + k + 6, 288 - bh],
                            fill=(96, 46, 44))
            x += bw + rng.randint(8, 20)
        d.rectangle([0, 268, w, 288], fill=(150, 48, 20))
        d.rectangle([0, 268, w, 272], fill=(255, 150, 40))
        d.rectangle([0, 208, w, 240], fill=(200, 60, 20))
        d.rectangle([0, 208, w, 214], fill=(255, 180, 60))
    return pygame.image.fromstring(img.tobytes(), img.size, "RGB").convert()


def background_mid(world: int) -> pygame.Surface:
    import random
    rng = random.Random(200 + world)
    w, h = 512, 288
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    g = WORLD_THEMES[world]["ground"]
    if world == 0:
        for i in range(4):
            x = i * 150 - 30
            d.ellipse([x, 220, x + 220, 330], fill=(86, 168, 78))
            d.ellipse([x + 40, 200, x + 180, 300], fill=(104, 190, 92))
        for _ in range(6):
            x = rng.randint(0, w)
            d.rectangle([x, 236, x + 6, 262], fill=(96, 62, 36))
            d.ellipse([x - 10, 214, x + 16, 244], fill=(72, 150, 66))
    elif world == 1:
        for i in range(5):
            x = i * 120 + rng.randint(-20, 20)
            d.polygon([(x, 288), (x + 26, 190), (x + 54, 288)], fill=(40, 30, 70))
            d.polygon([(x + 26, 190), (x + 34, 150), (x + 54, 288)],
                      fill=(90, 70, 160))
        for _ in range(14):
            x = rng.randint(0, w)
            d.polygon([(x, 288), (x + 8, 236), (x + 16, 288)],
                      fill=rng.choice([(120, 220, 255), (200, 140, 255)]))
    elif world == 2:
        for i in range(6):
            x = i * 96 + rng.randint(-10, 10)
            bh = rng.randint(90, 170)
            d.rectangle([x, 288 - bh, x + 70, 288], fill=(20, 18, 38))
            d.rectangle([x + 4, 288 - bh + 6, x + 66, 288 - bh + 12],
                        fill=rng.choice([(255, 72, 200), (44, 196, 214)]))
            for wy in range(288 - bh + 22, 278, 16):
                for wx in range(x + 8, x + 62, 14):
                    d.rectangle([wx, wy, wx + 6, wy + 7],
                                fill=rng.choice([(255, 72, 200), (44, 196, 214),
                                                 (250, 214, 64)]))
    else:
        for i in range(5):
            x = i * 120 + rng.randint(-16, 16)
            d.rectangle([x, 190, x + 90, 288], fill=(48, 26, 28))
            d.rectangle([x + 6, 196, x + 84, 204], fill=(70, 36, 34))
            for wy in range(198, 234, 16):
                d.rectangle([x + 10, wy, x + 80, wy + 7], fill=(255, 120, 30))
        # distant lava horizon, visible above the ground line
        d.rectangle([0, 206, w, 238], fill=(255, 92, 20))
        d.rectangle([0, 206, w, 212], fill=(255, 200, 70))
        for i in range(20):
            lx = rng.randint(0, w)
            d.polygon([(lx, 212), (lx + 12, 212), (lx + 6, 212 - rng.randint(4, 14))],
                      fill=(255, 190, 60))
    return pygame.image.fromstring(img.tobytes(), img.size, "RGBA")


# ---------------------------------------------------------------------------
# Fonts + asset manager
# ---------------------------------------------------------------------------
_font_cache: dict = {}


def get_font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        try:
            _font_cache[size] = pygame.font.Font(FONT_PATH, size)
        except (OSError, IOError):
            _font_cache[size] = pygame.font.SysFont("courier", size, bold=True)
    return _font_cache[size]


def text_size(text: str, size: int) -> tuple:
    return get_font(size).size(text)


def render_text(text: str, size: int, color=(255, 255, 255),
                shadow=None) -> pygame.Surface:
    label = str(text).upper()
    surf = get_font(size).render(label, False, color)
    if shadow is not None:
        base = get_font(size).render(label, False, shadow)
        out = pygame.Surface((base.get_width() + 2, base.get_height() + 2),
                             pygame.SRCALPHA)
        out.blit(base, (1, 1))
        out.blit(surf, (0, 0))
        return out
    return surf


class Assets:
    """Loaded artwork + convenience accessors."""

    def __init__(self):
        self.bg_far = [background_far(w) for w in range(4)]
        self.bg_mid = [background_mid(w) for w in range(4)]

    def hammy(self, pose: str, frame: int, skin: str, pack: str,
              acc: str) -> pygame.Surface:
        frame = frame % max(1, POSE_COUNT.get(pose, 1))
        return hammy_frame(pose, frame, skin, pack, acc)

    def enemy(self, kind: str, frame: int, world: int) -> pygame.Surface:
        return enemy_frame(kind, frame % 2, world)

    def item(self, name: str, frame: int = 0) -> pygame.Surface:
        count = ITEM_START[name][1]
        return item_frame(name, frame % count)

    def tile(self, name: str, world: int) -> pygame.Surface:
        return tile_image(name, world)

    def tile_name(self, code: int) -> str:
        return {
            1: "ground_fill",
            2: "platform",
            3: "spike",
            4: "lava0",
            5: "secret_top",
            6: "door_tile",
            7: "gate_tile",
        }.get(code, "ground_fill")


def ensure_assets() -> None:
    """Pre-render sheets to disk so the project ships real asset files."""
    os.makedirs(SPRITE_DIR, exist_ok=True)
    os.makedirs(BG_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)
    stamp = "retro-blast-assets-v1"
    if os.path.exists(ASSET_STAMP):
        with open(ASSET_STAMP, "r", encoding="utf-8") as fh:
            if fh.read().strip() == stamp:
                return
    pygame.init()
    pygame.display.set_mode((64, 64))
    for skin in SKINS:
        sheet = Image.new("RGBA", (HAMMY_W * HAMMY_FRAMES, HAMMY_H), (0, 0, 0, 0))
        for pose in POSE_ORDER:
            for f in range(POSE_COUNT[pose]):
                x = (POSE_START[pose] + f) * HAMMY_W
                sheet.paste(_hammy_image(pose, f, skin, "blue", "none"), (x, 0))
        sheet.save(os.path.join(SPRITE_DIR, f"hammy_{skin}.png"))
    for kind in ENEMY_KINDS:
        for world in range(4):
            size = 32 if kind == "boss" else 16
            sheet = Image.new("RGBA", (size * 2, size), (0, 0, 0, 0))
            for f in range(2):
                sheet.paste(_enemy_image(kind, f, world), (f * size, 0))
            sheet.save(os.path.join(SPRITE_DIR, f"enemy_{kind}_w{world}.png"))
    items = Image.new("RGBA", (16 * sum(n for _, n, _ in ITEM_DEFS), 16),
                      (0, 0, 0, 0))
    for name, n, size in ITEM_DEFS:
        idx, _, _ = ITEM_START[name]
        for f in range(n):
            items.paste(_item_image(name, f),
                        ((idx + f) * 16 + (16 - size) // 2, (16 - size) // 2))
    items.save(os.path.join(SPRITE_DIR, "items.png"))
    for world in range(4):
        tiles = Image.new("RGBA", (16 * len(TILE_ORDER), 16), (0, 0, 0, 0))
        for i, name in enumerate(TILE_ORDER):
            tiles.paste(_tile_image(name, WORLD_THEMES[world]), (i * 16, 0))
        tiles.save(os.path.join(SPRITE_DIR, f"tiles_w{world}.png"))
        pygame.image.save(background_far(world),
                          os.path.join(BG_DIR, f"far_w{world}.png"))
        pygame.image.save(background_mid(world),
                          os.path.join(BG_DIR, f"mid_w{world}.png"))
    pygame.display.quit()
    with open(ASSET_STAMP, "w", encoding="utf-8") as fh:
        fh.write(stamp)
