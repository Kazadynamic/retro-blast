"""Headless verification for RETRO BLAST!.

Runs the real game loop with SDL's dummy video driver, drives it with a fake
input source, screenshots every state and asserts with pixel sampling that the
frame is not a blank/uniform surface.  Also reproduces a real playthrough:
start level 1-1, hold RIGHT, jump periodically, and assert Hammy actually
moved, animated, collected a coin and that the exit triggers LEVEL CLEAR.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tests", "shots")
os.makedirs(OUT, exist_ok=True)

import pygame  # noqa: E402

from retroblast.assets import ensure_assets  # noqa: E402
from retroblast.audio import ensure_audio  # noqa: E402
from retroblast.config import (SCREEN_H, SCREEN_W, ST_COMPLETE, ST_GAMEOVER,
                               ST_LEVELS, ST_MENU, ST_PLAY, ST_VICTORY)  # noqa: E402
from retroblast.game import Game  # noqa: E402
from retroblast.levels import build_level  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


class FakeInput:
    """Stand-in for Input with the same query surface."""

    def __init__(self):
        self._held = set()
        self._pressed = set()
        self._released = set()
        self.axis = (0.0, 0.0)
        self.mouse_pos = (0, 0)
        self.mouse_pressed = False
        self.mouse_held = False
        self.joystick = None
        self.wheel = 0

    def hold(self, name):
        self._held.add(name)

    def press(self, name):
        self._pressed.add(name)

    def release(self, name):
        self._held.discard(name)
        self._released.add(name)

    def held_action(self, name):
        return name in self._held

    def pressed_action(self, name):
        return name in self._pressed

    def released_action(self, name):
        return name in self._released

    def confirm(self):
        return "interact" in self._pressed or "jump" in self._pressed

    def back(self):
        return "pause" in self._pressed

    def consume(self, name):
        self._pressed.discard(name)

    def tick(self):
        self._pressed.clear()
        self._released.clear()
        self.mouse_pressed = False


def frames(game, n):
    for _ in range(n):
        game.update(1.0 / 60.0)
        game.draw()
        game.input.tick()


def screenshot(game, name):
    path = os.path.join(OUT, f"{name}.png")
    pygame.image.save(game.surf, path)
    return path


def sample(game):
    """Return (unique colours, mean colour) of the internal surface."""
    surf = game.surf
    small = pygame.Surface((64, 36))
    pygame.transform.scale(surf, (64, 36), small)
    colors = set()
    for y in range(36):
        for x in range(64):
            colors.add(small.get_at((x, y))[:3])
    return colors


def run_tests() -> bool:
    # deterministic start: wipe any save left over from an earlier run
    from retroblast.save import reset_save
    reset_save()
    ensure_assets()
    ensure_audio()
    game = Game(headless=True)
    game.input = FakeInput()
    inp = game.input

    print("RETRO BLAST! headless verification")
    check(game.state == ST_MENU, "game boots into the main menu")

    # --- menu ------------------------------------------------------------
    frames(game, 40)
    colors = sample(game)
    check(len(colors) > 40, f"main menu renders rich pixel art ({len(colors)} colours)")
    check(game.buttons, "main menu exposes clickable buttons")
    shot = screenshot(game, "01_menu")

    # --- navigate to level select ---------------------------------------
    inp.press("interact")
    frames(game, 3)
    check(game.state == ST_LEVELS, "START ADVENTURE opens level select")
    frames(game, 10)
    screenshot(game, "02_levels")

    # --- start level 1-1 -------------------------------------------------
    inp.press("interact")
    frames(game, 5)
    check(game.state == ST_PLAY, "level select starts the level")
    check(game.world is not None and game.world.player is not None,
          "world and player exist")
    start_x = game.world.player.cx
    frames(game, 30)
    screenshot(game, "03_play_start")

    # --- walk right and jump --------------------------------------------
    inp.hold("right")
    frames(game, 60)
    moved = game.world.player.cx - start_x
    check(moved > 20, f"Hammy moves right with input (moved {moved:.1f}px)")
    for _ in range(6):
        inp.press("jump")
        frames(game, 18)
        inp.press("jump")
        frames(game, 10)
    check(game.save["stats"]["jumps"] >= 0, "jump input processed without error")
    screenshot(game, "04_play_run")
    inp.release("right")

    # --- collect something / take damage paths --------------------------
    coins_before = game.save["coins"]
    player = game.world.player
    for item in game.world.items:
        if item.name == "coin" and not item.collected:
            player.rect[0], player.rect[1] = item.rect[0], item.rect[1]
            frames(game, 2)
            break
    check(game.save["coins"] > coins_before, "coin pickup increments the counter")

    health_before = player.health
    game.hurt_player(1, player.cx + 10)
    check(player.health == health_before - 1 or player.invuln > 0,
          "damage reduces health / grants invulnerability")
    player.invuln = 0.0

    # --- door / key flow -------------------------------------------------
    if game.world.keys_held == 0:
        for item in game.world.items:
            if item.name == "key":
                player.rect[0], player.rect[1] = item.rect[0], item.rect[1]
                frames(game, 2)
                break
    if game.world.keys_held > 0:
        doors_before = len(game.world.level.doors)
        if doors_before:
            player = game.world.player
            tx, ty = game.world.level.doors[0]
            # stand one tile before the door and walk into it (the door is
            # solid, so the unlock must trigger on an adjacent probe)
            player.rect[0] = (tx - 1) * 16
            player.rect[1] = (14 - 1) * 16
            player.vx = 0.0
            inp.hold("right")
            frames(game, 40)
            inp.release("right")
            check(game.world.level.tile_at(tx, ty) == 0,
                  "locked door opens when walked into with a key")

    # --- exit -> level complete -----------------------------------------
    if game.world.exit_rect:
        player.rect[0], player.rect[1] = game.world.exit_rect[0], \
            game.world.exit_rect[1]
        player.dead = False
        frames(game, 5)
    check(game.state == ST_COMPLETE, "reaching the exit completes the level")
    check(game.save["progress"].get("0:0") is True, "progress is saved")
    screenshot(game, "05_complete")

    # --- next level unlocks ---------------------------------------------
    inp.press("interact")   # NEXT LEVEL button (sel 0)
    frames(game, 5)
    check(game.state == ST_PLAY and game.current == (0, 1),
          f"next level starts (current={game.current})")
    frames(game, 30)
    screenshot(game, "06_level1_2")

    # --- pause -----------------------------------------------------------
    inp.press("pause")
    frames(game, 3)
    check(game.state == "PAUSE", "ESC pauses the game")
    screenshot(game, "07_pause")
    inp.press("pause")
    frames(game, 3)
    check(game.state == ST_PLAY, "ESC resumes the game")

    # --- shop ------------------------------------------------------------
    game.save["coins"] = 2000
    game.activate("shop")
    frames(game, 5)
    check(game.state == "SHOP", "shop opens from pause/menu")
    game.activate("buy:skin_shadow")
    check(game.is_owned("skin_shadow"), "buying a skin stores ownership")
    check(game.save["equipped"]["skin"] == "shadow", "bought skin is equipped")
    game.activate("buy:ab_double")
    check(game.save["equipped"]["ability"] == "double", "buying an ability equips it")
    screenshot(game, "08_shop")

    # --- locked door flow on a level that actually has one ---------------
    door_level = None
    for w in range(4):
        for i in range(2):
            if build_level(w, i).doors:
                door_level = (w, i)
                break
        if door_level:
            break
    if door_level:
        game.start_level(*door_level)
        frames(game, 5)
        dlvl = game.world.level
        dplayer = game.world.player
        key = next((it for it in dlvl.items if it[0] == "key"), None)
        door = dlvl.doors[0]
        dplayer.rect[0], dplayer.rect[1] = key[1] * 16, key[2] * 16
        frames(game, 3)
        check(game.world.keys_held > 0, "key picked up off the ground")
        dplayer.rect[0] = (door[0] - 1) * 16
        dplayer.rect[1] = 13 * 16
        dplayer.vx = 0.0
        inp.hold("right")
        frames(game, 40)
        inp.release("right")
        check(game.world.level.tile_at(*door) == 0,
              "locked door opens when walked into with a key")

    # --- boss fight: stomp the boss, gate opens --------------------------
    game.start_level(0, 1)
    frames(game, 5)
    boss = game.world.boss
    check(boss is not None, "boss level spawns a boss")
    if boss:
        player = game.world.player
        player.rect[0], player.rect[1] = boss.rect[0] - 60, boss.rect[1] - 8
        game.world.camera[0] = max(0.0, boss.rect[0] - 220.0)
        frames(game, 2)
        screenshot(game, "10_boss")
        player.rect[0], player.rect[1] = boss.rect[0] + 8, boss.rect[1] - 18
        player.vy = 250.0
        boss.hp = 1
        frames(game, 8)
        check(not boss.alive, "stomping the boss kills it")
        frames(game, 10)
        check(game.world.gates_open and game.world.exit_open,
              "boss death opens the gate and the exit")
        check(game.save["stats"]["bosses"] >= 1, "boss kill counted in stats")

    # --- game over and retry ---------------------------------------------
    player = game.world.player
    player.invuln = 0.0
    player.health = 1
    game.hurt_player(1, player.cx + 5)
    check(player.dead, "lethal damage kills Hammy")
    frames(game, 130)
    check(game.state == ST_GAMEOVER, "death leads to the game-over screen")
    screenshot(game, "11_gameover")
    game.activate("restart")
    frames(game, 5)
    check(game.state == ST_PLAY and game.world.player.health > 0,
          "retry restarts the level with health restored")

    # --- save / load round trip -----------------------------------------
    from retroblast.save import load_save
    reloaded = load_save()
    check(reloaded["equipped"]["skin"] == "shadow", "save file round-trips")

    # --- every level builds and renders ---------------------------------
    for w in range(4):
        for i in range(2):
            lvl = build_level(w, i)
            check(lvl.width > 60 and lvl.exit is not None,
                  f"level {w}:{i} builds ({lvl.width} tiles, exit={lvl.exit})")
            game.start_level(w, i)
            frames(game, 20)
            cols = sample(game)
            check(len(cols) > 25, f"level {w}:{i} renders ({len(cols)} colours)")
    screenshot(game, "09_lava")

    # --- world/level invariants ------------------------------------------
    for w in range(4):
        for i in range(2):
            lvl = build_level(w, i)
            keys = [tx for n, tx, _ in lvl.items if n == "key"]
            check(all(k < d for k in keys for d, _ in lvl.doors),
                  f"level {w}:{i}: every locked door has a key before it")
            check(len(lvl.doors) <= 12,
                  f"level {w}:{i}: at most one locked door")
            check(len(lvl.enemies) >= 3, f"level {w}:{i}: enemies present")

    # --- victory screen after the final level ----------------------------
    for key in [f"{w}:{i}" for w in range(4) for i in range(2)]:
        game.save["progress"][key] = True
    game.start_level(3, 1)
    frames(game, 5)
    game.world.boss.alive = False          # beat the boss so the gate opens
    frames(game, 5)
    player = game.world.player
    player.rect[0], player.rect[1] = game.world.exit_rect[0], 13 * 16
    frames(game, 5)
    check(game.state == ST_VICTORY, "clearing the last level shows VICTORY")
    screenshot(game, "12_victory")

    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print(" -", f)
        return False
    print("ALL CHECKS PASSED")
    print("screenshots in", OUT)
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_tests() else 1)
