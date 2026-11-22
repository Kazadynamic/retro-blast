"""Game entities: Hammy, enemies, items, platforms, particles, floating text."""
from __future__ import annotations

import math
import random

import pygame

from .assets import Assets
from .config import (GRAVITY, JUMP_BUFFER, JUMP_CUT, JUMP_VEL, KNOCKBACK,
                     MAX_FALL, MAX_RUN, MOVE_ACCEL, MOVE_DECEL, COYOTE_TIME,
                     PLAYER_H, PLAYER_W, STOMP_BOUNCE, TILE, T_LAVA, T_SPIKE,
                     clamp)
from .physics import move_x, move_y, tile_overlap

GRAVITY = GRAVITY


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
class Player:
    def __init__(self, x, y, save, abilities=None):
        self.rect = [float(x), float(y), PLAYER_W, PLAYER_H]
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1
        self.on_ground = False
        self.coyote = 0.0
        self.jump_buffer = 0.0
        self.jumps_left = 1
        self.health = 3
        self.max_health = 3
        self.invuln = 0.0
        self.hurt_timer = 0.0
        self.state = "idle"
        self.anim = 0.0
        self.dead = False
        self.dead_timer = 0.0
        self.dash_cd = 0.0
        self.dash_time = 0.0
        self.magnet = 0.0
        self.star = 0.0
        self.shield = False
        self.abilities = abilities or {}
        self.land_timer = 0.0
        self.collect_timer = 0.0
        self.skin = "classic"
        self.pack = "blue"
        self.acc = "none"
        self.idle_time = 0.0

    # -- properties --------------------------------------------------------
    @property
    def x(self):
        return self.rect[0]

    @property
    def y(self):
        return self.rect[1]

    @property
    def cx(self):
        return self.rect[0] + self.rect[2] / 2

    @property
    def cy(self):
        return self.rect[1] + self.rect[3] / 2

    def apply_loadout(self, save):
        eq = save["equipped"]
        self.skin = eq.get("skin", "classic")
        self.pack = eq.get("backpack", "blue")
        self.acc = eq.get("accessory", "none")
        ability = eq.get("ability", "none")
        self.abilities = {"double": ability == "double",
                          "high": ability == "high",
                          "shield": ability == "shield",
                          "dash": ability == "dash"}

    # -- update ------------------------------------------------------------
    def update(self, dt, inp, world, game):
        if self.dead:
            self.dead_timer += dt
            self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)
            self.rect[1] += self.vy * dt
            return

        ability = self.abilities
        jump_vel = JUMP_VEL * (1.25 if ability.get("high") else 1.0)
        max_jumps = 2 if ability.get("double") else 1

        left = inp.held_action("left")
        right = inp.held_action("right")
        move = (1 if right else 0) - (1 if left else 0)
        if self.dash_time > 0:
            move = self.facing
        if move:
            self.facing = move
            self.idle_time = 0.0
        else:
            self.idle_time += dt

        # horizontal acceleration
        if self.dash_time > 0:
            self.dash_time -= dt
            self.vx = self.facing * 320.0
        else:
            target = move * MAX_RUN
            if move:
                if self.vx < target:
                    self.vx = min(target, self.vx + MOVE_ACCEL * dt)
                else:
                    self.vx = max(target, self.vx - MOVE_ACCEL * dt)
            else:
                dec = MOVE_DECEL * dt
                if abs(self.vx) <= dec:
                    self.vx = 0.0
                else:
                    self.vx -= dec if self.vx > 0 else -dec

        # dash
        self.dash_cd = max(0.0, self.dash_cd - dt)
        if ability.get("dash") and inp.pressed_action("dash") and self.dash_cd <= 0:
            self.dash_time = 0.16
            self.dash_cd = 0.9
            game.audio.play("dash")
            game.world.spawn_particles(self.cx, self.cy, 8, (120, 220, 255))

        # jumping
        self.coyote = max(0.0, self.coyote - dt)
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if inp.pressed_action("jump"):
            self.jump_buffer = JUMP_BUFFER
        if self.jump_buffer > 0:
            if self.on_ground or self.coyote > 0:
                self.vy = jump_vel
                self.on_ground = False
                self.coyote = 0.0
                self.jump_buffer = 0.0
                self.jumps_left = max_jumps - 1
                game.audio.play("jump")
                game.save["stats"]["jumps"] = int(game.save["stats"]["jumps"]) + 1
                game.world.spawn_particles(self.cx, self.rect[1] + self.rect[3],
                                           5, (220, 220, 220))
            elif self.jumps_left > 0:
                self.vy = jump_vel * 0.92
                self.jumps_left -= 1
                self.jump_buffer = 0.0
                game.audio.play("jump")
                game.world.spawn_particles(self.cx, self.rect[1] + self.rect[3],
                                           6, (255, 226, 92))
        if inp.released_action("jump") and self.vy < 0:
            self.vy *= JUMP_CUT

        # gravity
        self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)
        prev_bottom = self.rect[1] + self.rect[3]
        hit_x = move_x(world, self.rect, self.vx * dt)
        if hit_x:
            self.vx = 0.0
        hit_y, on_platform = move_y(world, self.rect, self.vy * dt, prev_bottom)
        was_air = not self.on_ground
        if hit_y:
            if self.vy > 120 and was_air:
                game.audio.play("land")
                self.land_timer = 0.14
                game.world.spawn_particles(self.cx, self.rect[1] + self.rect[3],
                                           6, (200, 180, 150))
            self.vy = 0.0
            self.on_ground = True
            self.jumps_left = max_jumps - 1
            self.coyote = COYOTE_TIME
        else:
            if self.on_ground:
                self.coyote = COYOTE_TIME
            self.on_ground = False

        # hazards
        for tx, ty, tile in tile_overlap(world, self.rect):
            if tile == T_SPIKE:
                if self.rect[1] + self.rect[3] > ty * TILE + 8:
                    game.hurt_player(1, tx * TILE + 8)
            elif tile == T_LAVA:
                game.hurt_player(1, tx * TILE + 8, lava=True)

        # fell out of the world
        if self.rect[1] > world.level.height * TILE + 40:
            self.die(game)

        # timers
        self.invuln = max(0.0, self.invuln - dt)
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.land_timer = max(0.0, self.land_timer - dt)
        self.collect_timer = max(0.0, self.collect_timer - dt)
        self.magnet = max(0.0, self.magnet - dt)
        self.star = max(0.0, self.star - dt)
        self.anim += dt * (1.0 + abs(self.vx) / MAX_RUN)

        # animation state
        if self.hurt_timer > 0:
            self.state = "hurt"
        elif self.collect_timer > 0:
            self.state = "collect"
        elif self.land_timer > 0:
            self.state = "land"
        elif not self.on_ground:
            self.state = "jump" if self.vy < 0 else "fall"
        elif abs(self.vx) > 12:
            self.state = "run" if abs(self.vx) > 90 else "walk"
        else:
            self.state = "idle"

    def die(self, game):
        if self.dead:
            return
        self.dead = True
        self.dead_timer = 0.0
        self.vy = -260.0
        self.health = 0
        game.audio.play("die")
        game.on_player_death()

    def draw(self, surf, assets: Assets, cam, time):
        if self.dead and self.dead_timer > 1.6:
            return
        if self.invuln > 0 and int(time * 18) % 2 == 0 and not self.dead:
            return
        pose = self.state
        if pose in ("walk", "run") and abs(self.vx) < 12:
            pose = "idle"
        frame = int(self.anim * (6 if pose in ("walk", "run") else 4)) % 4
        img = assets.hammy(pose, frame, self.skin, self.pack, self.acc)
        if self.star > 0:
            img = img.copy()
            tint = pygame.Surface(img.get_size(), pygame.SRCALPHA)
            tint.fill((255, 240, 150, 110))
            img.blit(tint, (0, 0))
        x = int(self.rect[0]) - cam[0] - 6
        y = int(self.rect[1]) - cam[1] - 8
        if self.facing < 0:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (x, y))


# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------
class Enemy:
    SIZES = {"slime": (14, 12), "walker": (14, 14), "flyer": (14, 12),
             "boss": (28, 26)}

    def __init__(self, kind, tx, ty, world):
        self.kind = kind
        self.world = world
        w, h = self.SIZES[kind]
        self.rect = [tx * TILE + (TILE - w) / 2, ty * TILE + (TILE - h), w, h]
        self.vx = 0.0
        self.vy = 0.0
        self.dir = -1 if random.random() < 0.5 else 1
        self.on_ground = False
        self.t = random.random() * 6.0
        self.home_y = self.rect[1]
        self.range = 3 * TILE
        self.origin_x = self.rect[0]
        self.alive = True
        self.hp = 8 if kind == "boss" else 1
        self.hit_flash = 0.0
        self.anim = 0.0
        self.speed = {"slime": 42, "walker": 74, "flyer": 60, "boss": 60}[kind]
        self.hop_timer = random.random() * 2.0

    @property
    def cx(self):
        return self.rect[0] + self.rect[2] / 2

    @property
    def cy(self):
        return self.rect[1] + self.rect[3] / 2

    def update(self, dt, world, player, game):
        if not self.alive:
            return
        if self.rect[1] > world.level.height * TILE + 64:
            self.alive = False   # fell into a pit: remove instead of simulating
            return
        self.t += dt
        self.anim += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.kind == "flyer":
            self.vx = self.dir * self.speed
            self.rect[0] += self.vx * dt
            self.rect[1] = self.home_y + math.sin(self.t * 3.0) * 12
            if abs(self.rect[0] - self.origin_x) > self.range:
                self.dir = -1 if self.rect[0] > self.origin_x else 1
        else:
            self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)
            self.hop_timer -= dt
            if self.kind == "slime":
                self.vx = self.dir * self.speed
                if self.on_ground and self.hop_timer <= 0:
                    self.vy = -190.0
                    self.hop_timer = 1.4 + random.random() * 1.6
            elif self.kind == "walker":
                self.vx = self.dir * self.speed
            else:  # boss
                self.vx = self.dir * self.speed * 0.7
                if self.on_ground and self.hop_timer <= 0:
                    self.vy = -360.0
                    self.dir = 1 if player.cx > self.cx else -1
                    self.hop_timer = 1.1
            prev_bottom = self.rect[1] + self.rect[3]
            hit_x = move_x(world, self.rect, self.vx * dt)
            if hit_x:
                self.dir = -self.dir
            hit_y, _ = move_y(world, self.rect, self.vy * dt, prev_bottom)
            if hit_y:
                self.vy = 0.0
                self.on_ground = True
            else:
                self.on_ground = False
            if self.kind in ("slime", "walker") and self.on_ground:
                ahead_x = self.rect[0] + (self.rect[2] + 2) * \
                    (1 if self.dir > 0 else -1)
                feet_y = self.rect[1] + self.rect[3] + 2
                # turn at walls and at ledges so ground enemies stay on their
                # platform instead of marching into a pit
                if not world.solid_at_px(ahead_x, feet_y):
                    self.dir = -self.dir
                elif world.tile_at(int(ahead_x // TILE),
                                   int((self.rect[1] + self.rect[3] - 2)
                                       // TILE)) in SOLID_TILES:
                    self.dir = -self.dir

    def damage(self, amount, game, player):
        self.hp -= amount
        self.hit_flash = 0.12
        game.audio.play("stomp" if self.kind != "boss" else "boss_hit")
        game.world.spawn_particles(self.cx, self.cy, 8, (255, 255, 255))
        if self.hp <= 0:
            self.alive = False
            game.world.spawn_particles(self.cx, self.cy, 18,
                                       (255, 208, 48) if self.kind == "boss"
                                       else (200, 220, 255))
            game.on_enemy_killed(self)

    def draw(self, surf, assets: Assets, cam):
        if not self.alive:
            return
        img = assets.enemy(self.kind, int(self.anim * 6) % 2, self.world)
        if self.hit_flash > 0:
            img = img.copy()
            flash = pygame.Surface(img.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, 200))
            img.blit(flash, (0, 0))
        x = int(self.rect[0]) - cam[0] - (img.get_width() - self.rect[2]) // 2
        y = int(self.rect[1]) - cam[1] - (img.get_height() - self.rect[3])
        if self.dir > 0:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (x, y))


SOLID_TILES = (1, 6, 7)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
class Item:
    def __init__(self, name, tx, ty):
        self.name = name
        self.rect = [tx * TILE + 2, ty * TILE + 2, 12, 12]
        self.t = random.random() * 6.0
        self.collected = False
        self.vx = 0.0
        self.vy = 0.0

    @property
    def cx(self):
        return self.rect[0] + self.rect[2] / 2

    @property
    def cy(self):
        return self.rect[1] + self.rect[3] / 2

    def update(self, dt, world, player, game):
        if self.collected:
            return
        self.t += dt
        if player.magnet > 0 and self.name in ("coin", "gem", "diamond"):
            dx = player.cx - self.cx
            dy = player.cy - self.cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 90:
                self.rect[0] += dx / max(1.0, dist) * 190 * dt
                self.rect[1] += dy / max(1.0, dist) * 190 * dt

    def draw(self, surf, assets: Assets, cam, time):
        if self.collected:
            return
        frame = int(time * 8 + self.t) % 4
        img = assets.item(self.name, frame)
        bob = math.sin(self.t * 4.0) * 1.5
        x = int(self.rect[0]) - cam[0] - 2
        y = int(self.rect[1]) - cam[1] - 2 + int(bob)
        surf.blit(img, (x, y))


# ---------------------------------------------------------------------------
# Moving platform
# ---------------------------------------------------------------------------
class MovingPlatform:
    def __init__(self, tx, ty, length, axis, rng):
        self.rect = [tx * TILE, ty * TILE + 4, length * TILE, 8]
        self.axis = axis
        self.range = rng * TILE
        self.origin = self.rect[0] if axis == "h" else self.rect[1]
        self.t = random.random() * 6.0
        self.speed = 1.4
        self.dx = 0.0
        self.dy = 0.0

    def update(self, dt):
        self.t += dt * self.speed
        off = math.sin(self.t) * self.range
        if self.axis == "h":
            new_x = self.origin + off
            self.dx = new_x - self.rect[0]
            self.dy = 0.0
            self.rect[0] = new_x
        else:
            new_y = self.origin + off
            self.dy = new_y - self.rect[1]
            self.dx = 0.0
            self.rect[1] = new_y

    def draw(self, surf, assets, cam, world):
        img = assets.tile("platform", world)
        for i in range(int(self.rect[2] // TILE)):
            surf.blit(img, (int(self.rect[0]) - cam[0] + i * TILE,
                            int(self.rect[1]) - cam[1]))


# ---------------------------------------------------------------------------
# Particles / floating text
# ---------------------------------------------------------------------------
class Particle:
    def __init__(self, x, y, color, count=1):
        self.x = x
        self.y = y
        self.vx = random.uniform(-70, 70)
        self.vy = random.uniform(-160, -20)
        self.life = random.uniform(0.3, 0.7)
        self.color = color
        self.size = random.choice((2, 2, 3))

    def update(self, dt):
        self.life -= dt
        self.vy += 520 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surf, cam):
        if self.life <= 0:
            return
        pygame.draw.rect(surf, self.color,
                         (int(self.x) - cam[0], int(self.y) - cam[1],
                          self.size, self.size))


class FloatText:
    def __init__(self, x, y, text, color=(255, 255, 255), size=8):
        from .assets import render_text
        self.x = x
        self.y = y
        self.life = 1.1
        self.surf = render_text(text, size, color, shadow=(20, 16, 30))

    def update(self, dt):
        self.life -= dt
        self.y -= 26 * dt

    def draw(self, surf, cam):
        if self.life <= 0:
            return
        surf.blit(self.surf, (int(self.x) - cam[0] - self.surf.get_width() // 2,
                              int(self.y) - cam[1]))
