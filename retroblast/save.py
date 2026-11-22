"""Save / load system: coins, gems, progression, shop, achievements, settings."""
from __future__ import annotations

import json
import os

from .config import SAVE_PATH

DEFAULT_SAVE = {
    "coins": 0,
    "diamonds": 0,
    "gems": 0,
    "keys": 0,
    "xp": 0,
    "player_level": 1,
    "progress": {},          # "w:l" -> True when completed
    "unlocked_worlds": 1,
    "shop": {},              # item id -> True (owned)
    "equipped": {"skin": "classic", "backpack": "blue", "ability": "none",
                 "accessory": "none"},
    "achievements": [],
    "stats": {"plays": 0, "secrets": 0, "bosses": 0, "deaths": 0, "jumps": 0},
    "settings": {"music": 0.8, "sfx": 0.9, "scale": 3, "screen_shake": True},
}

# Shop catalogue -----------------------------------------------------------
SHOP_ITEMS = [
    # id, name, desc, price, slot, data
    ("skin_classic", "CLASSIC COAT", "ORANGE ADVENTURER FUR", 0, "skin", "classic"),
    ("skin_shadow", "SHADOW COAT", "PURPLE NIGHT FUR", 150, "skin", "shadow"),
    ("skin_mint", "MINT COAT", "COOL MINT FUR", 250, "skin", "mint"),
    ("skin_gold", "GOLDEN COAT", "SHINY GOLDEN FUR", 600, "skin", "gold"),
    ("pack_blue", "BLUE PACK", "TRUSTY BLUE BACKPACK", 0, "backpack", "blue"),
    ("pack_red", "RED PACK", "HERO RED BACKPACK", 120, "backpack", "red"),
    ("pack_jet", "JET PACK", "DARK JET BACKPACK", 300, "backpack", "jet"),
    ("pack_gold", "GOLD PACK", "ROYAL GOLD BACKPACK", 700, "backpack", "gold"),
    ("acc_none", "NO GEAR", "BARE HAMSTER", 0, "accessory", "none"),
    ("acc_band", "HEADBAND", "RED HERO HEADBAND", 200, "accessory", "band"),
    ("acc_cape", "CAPE", "CYAN HERO CAPE", 350, "accessory", "cape"),
    ("acc_hat", "PARTY HAT", "FESTIVE PARTY HAT", 500, "accessory", "hat"),
    ("ab_none", "NO SKILL", "STANDARD HAMSTER", 0, "ability", "none"),
    ("ab_double", "DOUBLE JUMP", "JUMP AGAIN IN MID AIR", 400, "ability", "double"),
    ("ab_high", "SUPER JUMP", "+25% JUMP HEIGHT", 350, "ability", "high"),
    ("ab_shield", "SHIELD", "BLOCK ONE HIT PER LEVEL", 450, "ability", "shield"),
    ("ab_dash", "DASH", "PRESS SHIFT TO DASH", 500, "ability", "dash"),
    ("pu_magnet", "COIN MAGNET", "ATTRACTS NEARBY COINS", 100, "powerup", "magnet"),
    ("pu_star", "STAR POWER", "8S INVINCIBILITY", 150, "powerup", "star"),
    ("pu_heart", "EXTRA HEART", "+1 MAX HEALTH", 200, "powerup", "heart"),
]

ACHIEVEMENTS = [
    ("first_coin", "FIRST COIN", "COLLECT YOUR FIRST COIN"),
    ("coin_100", "COIN COLLECTOR", "HOLD 100 COINS AT ONCE"),
    ("secret_1", "SECRET FINDER", "DISCOVER A HIDDEN AREA"),
    ("boss_1", "BOSS SLAYER", "DEFEAT A BOSS"),
    ("level_5", "RISING HERO", "REACH PLAYER LEVEL 5"),
    ("world_4", "DEEP DIVER", "REACH LAVA FORTRESS"),
    ("all_clear", "PIXEL MASTER", "COMPLETE EVERY LEVEL"),
    ("gem_50", "GEM HUNTER", "COLLECT 50 GEMS"),
]


class SaveData(dict):
    """Dictionary with the default schema underneath."""

    def __init__(self):
        super().__init__(DEFAULT_SAVE)
        for key, value in DEFAULT_SAVE.items():
            if isinstance(value, (dict, list)):
                self[key] = json.loads(json.dumps(value))

    def add(self, **kwargs):
        for key, value in kwargs.items():
            if key in ("coins", "diamonds", "gems", "xp", "keys"):
                self[key] = max(0, int(self.get(key, 0)) + int(value))
            else:
                self[key] = value

    def level_xp(self):
        xp = int(self["xp"])
        lvl = 1
        while xp >= level_cost(lvl):
            xp -= level_cost(lvl)
            lvl += 1
        return lvl, xp


def level_cost(lvl: int) -> int:
    return 60 + (lvl - 1) * 45


def load_save(path: str = SAVE_PATH) -> SaveData:
    data = SaveData()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            for key, value in loaded.items():
                if key in data and type(value) is type(DEFAULT_SAVE.get(key)):
                    data[key] = value
        except (OSError, ValueError):
            pass
    return data


def write_save(data: dict, path: str = SAVE_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def reset_save(path: str = SAVE_PATH) -> None:
    data = SaveData()
    write_save(dict(data), path)
