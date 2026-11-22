"""RETRO BLAST! - global configuration, constants and palette."""
from __future__ import annotations

import os

GAME_TITLE = "RETRO BLAST!"
GAME_SUBTITLE = "EXPLORE THE PIXELVERSE WITH HAMMY"
VERSION = "1.0.0"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
SPRITE_DIR = os.path.join(ASSET_DIR, "sprites")
BG_DIR = os.path.join(ASSET_DIR, "bg")
AUDIO_DIR = os.path.join(ASSET_DIR, "audio")
FONT_PATH = os.path.join(ASSET_DIR, "fonts", "PressStart2P.ttf")
SAVE_PATH = os.path.join(BASE_DIR, "save.json")
ASSET_STAMP = os.path.join(ASSET_DIR, "stamp.txt")

# Internal render resolution (pixel perfect) and window scale.
SCREEN_W, SCREEN_H = 512, 288
SCALE_DEFAULT = 3
FPS = 60

TILE = 16
LEVEL_ROWS = SCREEN_H // TILE  # 18 tile rows

# Physics (pixels / seconds)
GRAVITY = 1500.0
MAX_FALL = 620.0
MOVE_ACCEL = 1600.0
MOVE_DECEL = 2200.0
MAX_RUN = 150.0
JUMP_VEL = -445.0
JUMP_CUT = 0.45
COYOTE_TIME = 0.09
JUMP_BUFFER = 0.12
PLAYER_W, PLAYER_H = 12, 16
STOMP_BOUNCE = -330.0
KNOCKBACK = 190.0

# Tile codes
T_EMPTY = 0
T_SOLID = 1
T_PLATFORM = 2   # one-way
T_SPIKE = 3      # damage
T_LAVA = 4       # damage + knock up
T_SECRET = 5     # looks solid, walk through, reveals secret
T_DOOR = 6       # locked door (needs key)
T_GATE = 7       # boss gate (opens when boss dies)

SOLID_TILES = (T_SOLID, T_DOOR, T_GATE)

# Game states
ST_MENU = "MENU"
ST_INFO = "INFO"
ST_LEVELS = "LEVELS"
ST_SHOP = "SHOP"
ST_PLAY = "PLAY"
ST_PAUSE = "PAUSE"
ST_COMPLETE = "COMPLETE"
ST_GAMEOVER = "GAMEOVER"
ST_SETTINGS = "SETTINGS"
ST_ACHIEVEMENTS = "ACHIEVEMENTS"
ST_VICTORY = "VICTORY"

# Palette ------------------------------------------------------------------
PAL = {
    "sky_top": (88, 180, 232),
    "sky_bot": (176, 236, 244),
    "orange": (244, 132, 32),
    "orange_dk": (188, 84, 20),
    "cyan": (44, 196, 214),
    "blue": (48, 104, 214),
    "blue_dk": (28, 58, 132),
    "purple": (128, 72, 196),
    "purple_dk": (72, 40, 120),
    "yellow": (250, 214, 64),
    "green": (96, 200, 84),
    "green_dk": (44, 128, 52),
    "red": (224, 60, 56),
    "white": (252, 250, 240),
    "grey": (140, 148, 160),
    "grey_dk": (72, 78, 92),
    "black": (18, 16, 26),
    "panel": (36, 30, 58),
    "panel_lt": (64, 54, 96),
    "brown": (120, 76, 44),
    "brown_dk": (74, 46, 28),
    "cream": (255, 238, 214),
    "fur": (232, 150, 60),
    "fur_dk": (176, 104, 40),
    "gold": (255, 208, 48),
    "gem_blue": (86, 200, 255),
    "gem_yellow": (255, 226, 92),
    "gem_pink": (255, 120, 190),
    "lava": (244, 84, 28),
    "lava_hot": (255, 190, 40),
}

WORLD_THEMES = [
    dict(name="PIXEL GRASSLAND", short="GRASSLAND", music="world1",
         sky=(96, 196, 240, 190, 240, 248), ground=(96, 200, 84), dirt=(128, 82, 48),
         dirt_dk=(84, 52, 32), accent=(250, 214, 64), enemy_set=("slime", "walker"),
         boss="slime"),
    dict(name="CRYSTAL CAVERNS", short="CAVERNS", music="world2",
         sky=(26, 20, 52, 48, 34, 78), ground=(92, 78, 140), dirt=(52, 42, 88),
         dirt_dk=(32, 24, 56), accent=(120, 220, 255), enemy_set=("walker", "flyer"),
         boss="walker"),
    dict(name="NEON CITY", short="NEON CITY", music="world3",
         sky=(20, 16, 44, 52, 30, 84), ground=(70, 78, 120), dirt=(40, 44, 72),
         dirt_dk=(24, 26, 44), accent=(255, 72, 200), enemy_set=("walker", "flyer"),
         boss="flyer"),
    dict(name="LAVA FORTRESS", short="FORTRESS", music="world4",
         sky=(44, 18, 30, 84, 28, 34), ground=(110, 70, 66), dirt=(64, 38, 40),
         dirt_dk=(38, 22, 26), accent=(255, 150, 40), enemy_set=("slime", "flyer"),
         boss="slime"),
]


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def frect(x: float, y: float, w: float, h: float):
    """Float rect -> int rect tuple."""
    return (int(round(x)), int(round(y)), int(round(w)), int(round(h)))


def aabb(a, b) -> bool:
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and \
           a[1] < b[1] + b[3] and a[1] + a[3] > b[1]
