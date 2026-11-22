"""The playable world: tile rendering, entities, camera and level flow."""
from __future__ import annotations

import random

import pygame

from .assets import Assets, door_frame, checkpoint_frame, render_text
from .config import (SCREEN_H, SCREEN_W, TILE, T_DOOR, T_EMPTY, T_GATE,
                     T_LAVA, T_PLATFORM, T_SECRET, T_SOLID, T_SPIKE, aabb,
                     clamp, lerp)
from .entities import Enemy, FloatText, Item, MovingPlatform, Particle, Player
from .physics import tile_overlap

DECOR_BY_WORLD = {
    0: ["decor_grass", "decor_flower", "decor_rock"],
    1: ["decor_crystal", "decor_rock", "decor_chain"],
    2: ["decor_neon", "decor_chain", "decor_rock"],
    3: ["decor_rock", "decor_chain", "decor_grass"],
}


def _hash2(x: int, y: int) -> int:
    return (x * 73856093) ^ (y * 19349663)


class World:
    def __init__(self, level, save, assets: Assets, audio):
        self.level = level
        self.save = save
        self.assets = assets
        self.audio = audio
        self.player = Player(level.spawn[0], level.spawn[1], save)
        self.player.apply_loadout(save)
        self.player.max_health = 3
        self.player.health = 3
        # consumable power-ups bought in the shop are used at level start
        pu = save.get("powerups", {})
        if pu.get("heart", 0) > 0:
            pu["heart"] -= 1
            self.player.max_health = 4
            self.player.health = 4
        if pu.get("magnet", 0) > 0:
            pu["magnet"] -= 1
            self.player.magnet = 9999
        if pu.get("star", 0) > 0:
            pu["star"] -= 1
            self.player.star = 8

        self.enemies = [Enemy(k, tx, ty, level.world)
                        for (k, tx, ty) in level.enemies]
        if level.boss:
            boss = Enemy(level.boss[0], level.boss[1], level.boss[2], level.world)
            self.enemies.append(boss)
            self.boss = boss
        else:
            self.boss = None
        self.items = [Item(n, tx, ty) for (n, tx, ty) in level.items]
        self.platforms = [MovingPlatform(*p) for p in level.platforms]
        self.particles = []
        self.texts = []
        self.camera = [0.0, 0.0]
        self.shake = 0.0
        self.time = 0.0
        self.coins = 0
        self.gems = 0
        self.diamonds = 0
        self.keys_held = 0
        self.secrets_found = 0
        self.exit_open = level.boss is None
        self.gates_open = False
        self.found_secrets = set()
        self.checkpoint = None
        self.checkpoint_rects = [(tx * TILE, ty * TILE, TILE, TILE)
                                 for tx, ty in level.checkpoints]
        self.exit_rect = None
        if level.exit:
            tx, ty = level.exit
            self.exit_rect = [tx * TILE, ty * TILE - 16, TILE, 32]
        self.finished = False
        self.death_timer = 0.0
        self._death_handled = False

    # -- helpers -----------------------------------------------------------
    def spawn_particles(self, x, y, count, color):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def add_text(self, x, y, text, color=(255, 255, 255), size=8):
        self.texts.append(FloatText(x, y, text, color, size))

    def tile_at_px(self, x, y):
        return self.level.tile_at(int(x // TILE), int(y // TILE))

    def tile_at(self, tx, ty):
        return self.level.tile_at(tx, ty)

    def set_tile(self, tx, ty, value):
        self.level.set_tile(tx, ty, value)

    def solid_at_px(self, x, y):
        return self.level.solid_at_px(x, y)

    # -- update ------------------------------------------------------------
    def update(self, dt, inp, game):
        self.time += dt
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 3.0)

        for plat in self.platforms:
            plat.update(dt)

        if not self.finished:
            self.player.update(dt, inp, self, game)
            self._carry_player()

        # enemies
        for enemy in self.enemies:
            enemy.update(dt, self, self.player, game)
        self._enemy_collisions(game)

        # items
        for item in self.items:
            item.update(dt, self, self.player, game)
            if not item.collected and aabb(self.player.rect, item.rect):
                self._collect(item, game)

        # secrets
        for i, (tx, ty, tw, th) in enumerate(self.level.secrets):
            rect = [tx * TILE, ty * TILE, tw * TILE, th * TILE]
            if i not in self.found_secrets and aabb(self.player.rect, rect):
                self.found_secrets.add(i)
                self.secrets_found += 1
                game.on_secret(tx * TILE, ty * TILE)

        # locked doors
        if self.keys_held > 0:
            for tx, ty, tile in tile_overlap(self.level, self.player.rect):
                if tile == T_DOOR:
                    self._open_doors(game)
                    break

        # boss gate
        if self.boss and not self.boss.alive and not self.gates_open:
            self._open_gates(game)

        # checkpoints
        for cp in self.checkpoint_rects:
            if self.checkpoint is None and aabb(self.player.rect, cp):
                self.checkpoint = cp
                self.audio.play("confirm")
                self.add_text(cp[0] + 8, cp[1] - 6, "CHECKPOINT", (120, 220, 255))

        # exit
        if self.exit_rect and self.exit_open and not self.finished:
            if aabb(self.player.rect, self.exit_rect):
                self.finished = True
                game.complete_level()

        # particles / texts
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        for t in self.texts:
            t.update(dt)
        self.texts = [t for t in self.texts if t.life > 0]

        # camera
        target_x = self.player.cx - SCREEN_W / 2 + self.player.facing * 28
        target_x = clamp(target_x, 0, max(0, self.level.world_px - SCREEN_W))
        self.camera[0] = lerp(self.camera[0], target_x, 1.0 - pow(0.001, dt))
        self.camera[1] = 0.0

    def _carry_player(self):
        p = self.player
        for plat in self.platforms:
            top = plat.rect[1]
            overlap_x = (p.rect[0] + p.rect[2] > plat.rect[0] + 1 and
                         p.rect[0] < plat.rect[0] + plat.rect[2] - 1)
            feet = p.rect[1] + p.rect[3]
            if overlap_x and p.vy >= 0 and feet <= top + 6 and feet >= top - 8:
                p.rect[0] += plat.dx
                p.rect[1] = top - p.rect[3]
                p.vy = 0.0
                p.on_ground = True

    def _enemy_collisions(self, game):
        p = self.player
        if p.dead:
            return
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if not aabb(p.rect, enemy.rect):
                continue
            stomp = (p.vy > 0 and
                     (p.rect[1] + p.rect[3]) - enemy.rect[1] < 14)
            if p.star > 0:
                enemy.damage(1, game, p)
                continue
            if stomp:
                enemy.damage(1, game, p)
                p.vy = -330.0 if enemy.kind != "boss" else -380.0
                p.on_ground = False
                self.shake = max(self.shake, 0.25)
            else:
                game.hurt_player(1, enemy.cx)

    def _collect(self, item, game):
        p = self.player
        name = item.name
        item.collected = True
        if name == "coin":
            self.coins += 1
            game.add_coins(1)
            self.audio.play("coin")
            self.add_text(item.cx, item.cy - 6, "+1", (255, 226, 92))
            self.spawn_particles(item.cx, item.cy, 5, (255, 226, 92))
        elif name == "diamond":
            self.diamonds += 1
            game.add_diamonds(1)
            self.audio.play("diamond")
            self.add_text(item.cx, item.cy - 6, "+1 DIAMOND", (86, 200, 255))
            self.spawn_particles(item.cx, item.cy, 8, (86, 200, 255))
        elif name == "gem":
            self.gems += 1
            game.add_gems(1)
            self.audio.play("gem")
            self.add_text(item.cx, item.cy - 6, "+1 GEM", (255, 120, 190))
            self.spawn_particles(item.cx, item.cy, 8, (255, 120, 190))
        elif name == "key":
            self.keys_held += 1
            game.add_keys(1)
            self.audio.play("key")
            self.add_text(item.cx, item.cy - 6, "KEY GET!", (255, 208, 48))
        elif name == "heart":
            p.max_health = max(p.max_health, p.health + 1)
            p.health = min(p.max_health, p.health + 1)
            self.audio.play("powerup")
            self.add_text(item.cx, item.cy - 6, "+HP", (232, 60, 70))
        elif name == "star":
            p.star = 8.0
            self.audio.play("powerup")
            self.add_text(item.cx, item.cy - 6, "INVINCIBLE!", (255, 240, 150))
        elif name == "magnet":
            p.magnet = 12.0
            self.audio.play("powerup")
            self.add_text(item.cx, item.cy - 6, "MAGNET!", (224, 60, 56))
        elif name == "spring":
            p.vy = -720.0
            p.on_ground = False
            self.audio.play("spring")
        elif name == "box":
            self.audio.play("box")
            roll = random.random()
            if roll < 0.6:
                game.add_coins(3)
                self.add_text(item.cx, item.cy - 6, "+3 COINS", (255, 226, 92))
                self.spawn_particles(item.cx, item.cy, 10, (255, 226, 92))
            elif roll < 0.85:
                p.health = min(p.max_health, p.health + 1)
                self.add_text(item.cx, item.cy - 6, "+HP", (232, 60, 70))
            else:
                p.star = 6.0
                self.add_text(item.cx, item.cy - 6, "STAR!", (255, 240, 150))
            self.spawn_particles(item.cx, item.cy, 12, (196, 138, 74))

    def _open_doors(self, game):
        self.keys_held -= 1
        game.add_keys(-1)
        for tx, ty in self.level.doors:
            self.level.set_tile(tx, ty, T_EMPTY)
        self.audio.play("unlock")
        self.add_text(self.player.cx, self.player.cy - 14, "UNLOCKED!",
                      (255, 208, 48), 10)
        self.spawn_particles(self.player.cx, self.player.cy, 14, (255, 208, 48))

    def _open_gates(self, game):
        self.gates_open = True
        self.exit_open = True
        for tx, ty in self.level.gates:
            self.level.set_tile(tx, ty, T_EMPTY)
        self.audio.play("boss_die")
        self.add_text(self.player.cx, self.player.cy - 20, "GATE OPEN!",
                      (120, 220, 255), 10)

    def respawn_point(self):
        if self.checkpoint:
            return self.checkpoint[0] + 2, self.checkpoint[1] - 16
        return self.level.spawn[0], self.level.spawn[1]

    # -- draw --------------------------------------------------------------
    def draw(self, surf, game):
        cam = [int(self.camera[0]), int(self.camera[1])]
        if self.shake > 0 and self.save["settings"].get("screen_shake", True):
            cam[0] += random.randint(-2, 2)
            cam[1] += random.randint(-2, 2)
        world = self.level.world
        # parallax backgrounds
        far = self.assets.bg_far[world]
        mid = self.assets.bg_mid[world]
        fx = -(int(self.camera[0] * 0.25) % SCREEN_W)
        mx = -(int(self.camera[0] * 0.5) % SCREEN_W)
        for offset in (fx, fx + SCREEN_W):
            surf.blit(far, (offset, 0))
        for offset in (mx, mx + SCREEN_W):
            surf.blit(mid, (offset, 0))

        self._draw_tiles(surf, cam, world)

        # checkpoints
        for cp in self.checkpoint_rects:
            lit = self.checkpoint == cp
            surf.blit(checkpoint_frame(lit),
                      (cp[0] - cam[0], cp[1] - cam[1] - 8))

        # exit door
        if self.exit_rect:
            img = door_frame(self.exit_open)
            surf.blit(img, (self.exit_rect[0] - cam[0], self.exit_rect[1] - cam[1]))
            if self.exit_open and int(self.time * 2) % 2 == 0:
                label = render_text("EXIT", 8, (120, 220, 255))
                surf.blit(label, (self.exit_rect[0] - cam[0] - 2,
                                  self.exit_rect[1] - cam[1] - 12))

        for plat in self.platforms:
            plat.draw(surf, self.assets, cam, world)
        for item in self.items:
            item.draw(surf, self.assets, cam, self.time)
        for enemy in self.enemies:
            enemy.draw(surf, self.assets, cam)
        self.player.draw(surf, self.assets, cam, self.time)
        for p in self.particles:
            p.draw(surf, cam)
        for t in self.texts:
            t.draw(surf, cam)

    def _draw_tiles(self, surf, cam, world):
        x0 = max(0, int(cam[0] // TILE) - 1)
        x1 = min(self.level.width - 1, int((cam[0] + SCREEN_W) // TILE) + 1)
        decors = DECOR_BY_WORLD[world]
        for ty in range(self.level.height):
            for tx in range(x0, x1 + 1):
                tile = self.level.tiles[ty][tx]
                if tile == T_EMPTY:
                    continue
                px = tx * TILE - cam[0]
                py = ty * TILE - cam[1]
                if tile == T_SOLID:
                    above = self.level.tile_at(tx, ty - 1)
                    name = "ground_top" if above not in (T_SOLID, T_DOOR,
                                                         T_GATE) else "ground_fill"
                    surf.blit(self.assets.tile(name, world), (px, py))
                    if name == "ground_top":
                        h = _hash2(tx, ty) % 100
                        if h < 22:
                            decor = decors[h % len(decors)]
                            surf.blit(self.assets.tile(decor, world),
                                      (px, py - 8))
                        elif h < 30 and world >= 1:
                            torch = "torch0" if int(self.time * 6) % 2 == 0 \
                                else "torch1"
                            surf.blit(self.assets.tile(torch, world),
                                      (px, py - 16))
                elif tile == T_PLATFORM:
                    surf.blit(self.assets.tile("platform", world), (px, py))
                elif tile == T_SPIKE:
                    surf.blit(self.assets.tile("spike", world), (px, py))
                elif tile == T_LAVA:
                    name = "lava0" if int(self.time * 4 + tx) % 2 == 0 else "lava1"
                    surf.blit(self.assets.tile(name, world), (px, py))
                elif tile == T_SECRET:
                    surf.blit(self.assets.tile("secret_top", world), (px, py))
                elif tile == T_DOOR:
                    surf.blit(self.assets.tile("door_tile", world), (px, py))
                elif tile == T_GATE:
                    surf.blit(self.assets.tile("gate_tile", world), (px, py))
