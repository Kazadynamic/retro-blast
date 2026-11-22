"""Game state machine: menu flow, level flow, progression, shop, achievements."""
from __future__ import annotations

import pygame

from .assets import Assets, render_text
from .audio import Audio
from .config import (FPS, SCREEN_H, SCREEN_W, ST_ACHIEVEMENTS, ST_COMPLETE,
                     ST_GAMEOVER, ST_INFO, ST_LEVELS, ST_MENU, ST_PAUSE,
                     ST_PLAY, ST_SETTINGS, ST_SHOP, ST_VICTORY, VERSION,
                     WORLD_THEMES, clamp)
from .input import Input
from .levels import LEVEL_NAMES, build_level
from .save import ACHIEVEMENTS, SHOP_ITEMS, load_save, write_save
from .ui import (draw_achievements, draw_community, draw_complete,
                 draw_gameover, draw_hud, draw_info, draw_level_select,
                 draw_main_menu, draw_pause, draw_settings, draw_shop,
                 draw_victory, label, panel)
from .world import World


class Game:
    def __init__(self, headless: bool = False):
        pygame.init()
        self.headless = headless
        self.save = load_save()
        self.scale = int(self.save["settings"].get("scale", 3))
        self.screen = None
        self._surf = None
        self._make_screen()
        self.assets = Assets()
        self.audio = Audio(self.save)
        self.input = Input()
        self.state = ST_MENU
        self.return_to = ST_MENU
        self.world = None
        self.current = (0, 0)
        self.worlds = WORLD_THEMES
        self.level_names = LEVEL_NAMES
        self.version = VERSION
        self.time = 0.0
        self.sel = 0
        self.shop_tab = "skin"
        self.shop_scroll = 0
        self.ach_scroll = 0
        self.last_xp = 0
        self.toast = None
        self.toast_timer = 0.0
        self.buttons = []
        self.audio.play_music("menu")

    # -- display -----------------------------------------------------------
    def _make_screen(self):
        flags = pygame.SCALED | pygame.RESIZABLE
        if self.headless:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        else:
            self.screen = pygame.display.set_mode(
                (SCREEN_W * self.scale, SCREEN_H * self.scale), flags)

    def apply_scale(self):
        self.scale = int(self.save["settings"].get("scale", 3))
        if not self.headless:
            self.screen = pygame.display.set_mode(
                (SCREEN_W * self.scale, SCREEN_H * self.scale),
                pygame.SCALED | pygame.RESIZABLE)

    @property
    def surf(self):
        """Internal 512x288 render surface."""
        if self.headless:
            return self.screen
        if getattr(self, "_surf", None) is None:
            self._surf = pygame.Surface((SCREEN_W, SCREEN_H))
        return self._surf

    # -- state helpers -----------------------------------------------------
    def set_state(self, state):
        self.state = state
        self.sel = 0
        self.buttons = []
        if state == ST_MENU:
            self.audio.play_music("menu")
        elif state == ST_PLAY and self.world is not None:
            self.audio.play_music("boss" if self.world.boss else
                                  WORLD_THEMES[self.world.level.world]["music"])

    def show_toast(self, text, color=(255, 255, 255)):
        self.toast = render_text(text, 8, color, shadow=(16, 12, 26))
        self.toast_timer = 2.4

    def go_back(self):
        if self.state in (ST_INFO, ST_LEVELS, ST_SHOP, ST_SETTINGS,
                         ST_ACHIEVEMENTS, "COMMUNITY"):
            self.set_state(self.return_to)
            self.audio.play("back")
        elif self.state == ST_PAUSE:
            self.set_state(ST_PLAY)
            self.audio.play("back")

    # -- progression -------------------------------------------------------
    def add_xp(self, amount: int):
        self.save["xp"] = max(0, int(self.save["xp"]) + amount)
        lvl, _ = self.save.level_xp()
        if lvl >= 5:
            self.unlock_achievement("level_5")

    def add_coins(self, n: int):
        self.save["coins"] = max(0, int(self.save["coins"]) + n)
        if self.save["coins"] >= 100:
            self.unlock_achievement("coin_100")

    def add_gems(self, n: int):
        self.save["gems"] = max(0, int(self.save["gems"]) + n)
        if self.save["gems"] >= 50:
            self.unlock_achievement("gem_50")

    def add_diamonds(self, n: int):
        self.save["diamonds"] = max(0, int(self.save["diamonds"]) + n)

    def add_keys(self, n: int):
        self.save["keys"] = max(0, int(self.save["keys"]) + n)

    def unlock_achievement(self, ach_id: str):
        if ach_id in self.save["achievements"]:
            return
        self.save["achievements"].append(ach_id)
        name = next((n for i, n, _ in ACHIEVEMENTS if i == ach_id), ach_id)
        self.audio.play("achievement")
        self.show_toast(f"ACHIEVEMENT: {name}", (255, 214, 64))
        write_save(dict(self.save))

    def is_owned(self, item_id: str) -> bool:
        return item_id in self.save["shop"]

    def buy(self, item_id: str):
        item = next((it for it in SHOP_ITEMS if it[0] == item_id), None)
        if item is None or self.is_owned(item_id):
            return
        price = item[3]
        if self.save["coins"] < price:
            self.audio.play("error")
            self.show_toast("NOT ENOUGH COINS", (232, 60, 70))
            return
        self.save["coins"] -= price
        slot = item[4]
        if slot == "powerup":
            pu = self.save.setdefault("powerups", {})
            key = item[5]
            pu[key] = pu.get(key, 0) + 1
            self.show_toast(f"BOUGHT! USED AT NEXT LEVEL START", (255, 214, 64))
        else:
            self.save["shop"][item_id] = True
            self.save["equipped"][slot] = item[5]
            self.show_toast(f"EQUIPPED {item[1]}", (120, 220, 255))
        self.audio.play("buy")
        write_save(dict(self.save))

    def equip(self, item_id: str):
        item = next((it for it in SHOP_ITEMS if it[0] == item_id), None)
        if item is None or not self.is_owned(item_id):
            return
        self.save["equipped"][item[4]] = item[5]
        self.audio.play("confirm")
        write_save(dict(self.save))

    # -- level flow --------------------------------------------------------
    def start_level(self, world: int, index: int):
        self.current = (world, index)
        self.toast = None
        self.toast_timer = 0.0
        level = build_level(world, index)
        self.world = World(level, self.save, self.assets, self.audio)
        self.save["stats"]["plays"] += 1
        write_save(dict(self.save))
        self.set_state(ST_PLAY)
        self.audio.play("confirm")

    def restart_level(self):
        self.start_level(*self.current)

    def has_next_level(self):
        w, i = self.current
        if i == 0:
            return True
        return w < 3

    def next_level(self):
        w, i = self.current
        if i == 0:
            self.start_level(w, 1)
        elif w < 3:
            self.start_level(w + 1, 0)

    def complete_level(self):
        w, i = self.current
        key = f"{w}:{i}"
        first = not self.save["progress"].get(key, False)
        self.save["progress"][key] = True
        xp = 40 + w * 25 + (15 if i == 1 else 0) + self.world.coins + \
            self.world.gems * 3 + self.world.diamonds * 5 + self.world.secrets_found * 10
        if first:
            xp += 25
        self.last_xp = xp
        self.add_xp(xp)
        if i == 1:
            self.save["unlocked_worlds"] = max(self.save["unlocked_worlds"],
                                               min(4, w + 2))
        else:
            self.save["unlocked_worlds"] = max(self.save["unlocked_worlds"],
                                               min(4, w + 1))
        if w == 3:
            self.unlock_achievement("world_4")
        all_clear = all(self.save["progress"].get(f"{ww}:{ii}")
                        for ww in range(4) for ii in range(2))
        if all_clear:
            self.unlock_achievement("all_clear")
        write_save(dict(self.save))
        self.audio.play("win")
        if all_clear and (w, i) == (3, 1):
            self.set_state(ST_VICTORY)
            self.audio.play_music("victory")
        else:
            self.set_state(ST_COMPLETE)

    def hurt_player(self, amount: int, source_x: float, lava: bool = False):
        p = self.world.player
        if p.dead or p.invuln > 0 or self.world.finished:
            return
        if p.shield:
            p.shield = False
            p.invuln = 1.0
            self.audio.play("dash")
            self.world.add_text(p.cx, p.cy - 14, "SHIELD BLOCK", (120, 220, 255))
            return
        p.health -= amount
        p.invuln = 1.3
        p.hurt_timer = 0.4
        self.world.shake = max(self.world.shake, 0.6)
        self.audio.play("hurt")
        if lava:
            p.vy = -380.0
        else:
            p.vx = (1 if p.cx < source_x else -1) * 190.0
            p.vy = min(p.vy, -180.0)
        self.world.spawn_particles(p.cx, p.cy, 10, (232, 60, 70))
        if p.health <= 0:
            p.die(self)

    def on_player_death(self):
        self.save["stats"]["deaths"] += 1
        write_save(dict(self.save))
        self.death_timer = 0.0

    def on_enemy_killed(self, enemy):
        if enemy.kind == "boss":
            self.save["stats"]["bosses"] += 1
            self.unlock_achievement("boss_1")
            self.world.shake = 1.0
            self.add_xp(30)
            self.world.add_text(enemy.cx, enemy.cy - 20, "BOSS DOWN!",
                                (255, 214, 64), 10)
            self.world.spawn_particles(enemy.cx, enemy.cy, 24, (255, 208, 48))
        else:
            self.add_xp(4)
            self.world.spawn_particles(enemy.cx, enemy.cy, 8, (200, 220, 255))
        write_save(dict(self.save))

    def on_secret(self, x, y):
        self.save["stats"]["secrets"] += 1
        self.unlock_achievement("secret_1")
        self.audio.play("secret")
        self.add_xp(15)
        self.world.add_text(x + 16, y - 10, "SECRET FOUND!", (120, 220, 255), 10)
        self.world.spawn_particles(x + 16, y, 16, (120, 220, 255))
        write_save(dict(self.save))

    # -- input / buttons ---------------------------------------------------
    def activate(self, action: str):
        if action == "start":
            self.return_to = ST_MENU
            self.set_state(ST_LEVELS)
            self.audio.play("confirm")
        elif action == "info":
            self.return_to = ST_MENU
            self.set_state(ST_INFO)
            self.audio.play("confirm")
        elif action == "back":
            self.go_back()
        elif action == "settings":
            self.return_to = self.state
            self.set_state(ST_SETTINGS)
            self.audio.play("confirm")
        elif action == "shop":
            self.return_to = ST_MENU if self.state == ST_MENU else self.state
            self.set_state(ST_SHOP)
            self.audio.play("confirm")
        elif action == "levels":
            self.return_to = ST_MENU
            self.set_state(ST_LEVELS)
            self.audio.play("confirm")
        elif action == "community":
            self.return_to = ST_MENU
            self.set_state("COMMUNITY")
            self.audio.play("confirm")
        elif action == "achievements":
            self.return_to = self.state
            self.set_state(ST_ACHIEVEMENTS)
            self.audio.play("confirm")
        elif action == "menu":
            self.world = None
            self.set_state(ST_MENU)
            self.audio.play("back")
        elif action.startswith("play:"):
            _, w, i = action.split(":")
            self.start_level(int(w), int(i))
        elif action.startswith("buy:"):
            self.buy(action[4:])
        elif action.startswith("equip:"):
            self.equip(action[6:])
        elif action.startswith("tab:"):
            self.shop_tab = action[4:]
            self.shop_scroll = 0
            self.audio.play("select")
        elif action.startswith("vol:"):
            _, key, val = action.split(":")
            self.save["settings"][key] = int(val) * 0.2
            if key == "music":
                self.audio.set_music_volume(int(val) * 0.2)
            write_save(dict(self.save))
            self.audio.play("click")
        elif action.startswith("scale:"):
            self.save["settings"]["scale"] = int(action.split(":")[1])
            write_save(dict(self.save))
            self.apply_scale()
            self.audio.play("click")
        elif action == "shake":
            self.save["settings"]["screen_shake"] = \
                not self.save["settings"].get("screen_shake", True)
            write_save(dict(self.save))
            self.audio.play("click")
        elif action == "reset":
            from .save import reset_save
            reset_save()
            self.save = load_save()
            self.audio.play("error")
            self.show_toast("SAVE DATA RESET", (232, 60, 70))
        elif action == "resume":
            self.set_state(ST_PLAY)
            self.audio.play("confirm")
        elif action == "restart":
            self.restart_level()
        elif action == "menu":
            self.world = None
            self.set_state(ST_MENU)
            self.audio.play("back")
        elif action == "next":
            self.next_level()

    def handle_buttons(self, buttons):
        if not buttons:
            return
        self.sel = clamp(self.sel, 0, len(buttons) - 1)
        for i, btn in enumerate(buttons):
            if btn.hit(self.input.mouse_pos):
                self.sel = i
        if self.input.pressed_action("down"):
            self.sel = (self.sel + 1) % len(buttons)
            self.audio.play("select")
        if self.input.pressed_action("up"):
            self.sel = (self.sel - 1) % len(buttons)
            self.audio.play("select")
        if self.input.pressed_action("left") and self.state == ST_SHOP:
            slots = ["skin", "backpack", "accessory", "ability", "powerup"]
            idx = slots.index(self.shop_tab)
            self.shop_tab = slots[(idx - 1) % len(slots)]
            self.shop_scroll = 0
            self.audio.play("select")
        if self.input.pressed_action("right") and self.state == ST_SHOP:
            slots = ["skin", "backpack", "accessory", "ability", "powerup"]
            idx = slots.index(self.shop_tab)
            self.shop_tab = slots[(idx + 1) % len(slots)]
            self.shop_scroll = 0
            self.audio.play("select")
        for i, btn in enumerate(buttons):
            btn.hover = btn.hover or i == self.sel
        if self.input.mouse_pressed:
            for btn in buttons:
                if btn.hit(self.input.mouse_pos):
                    self.activate(btn.action)
                    self.audio.play("click")
                    return
        if self.input.confirm():
            self.activate(buttons[self.sel].action)
        elif self.input.back():
            self.go_back()

    # -- update ------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        inp = self.input
        if self.toast_timer > 0:
            self.toast_timer -= dt
        if self.state == ST_PLAY:
            if inp.pressed_action("pause"):
                self.set_state(ST_PAUSE)
                inp.consume("pause")
                self.audio.play("pause")
            else:
                self.world.update(dt, inp, self)
                if self.world.player.dead:
                    self.death_timer += dt
                    if self.death_timer > 1.8:
                        self.set_state(ST_GAMEOVER)
                        self.audio.play("gameover")
            # scroll panels
        elif self.state == ST_PAUSE:
            if inp.pressed_action("pause"):
                self.set_state(ST_PLAY)
                inp.consume("pause")
        elif self.state == ST_SHOP:
            self.shop_scroll += inp.wheel * 26
        elif self.state == ST_ACHIEVEMENTS:
            self.ach_scroll += inp.wheel * 26

    # -- draw --------------------------------------------------------------
    def draw(self):
        surf = self.surf
        inp = self.input
        if self.state == ST_MENU:
            self.buttons = draw_main_menu(self, surf, self.time)
        elif self.state == ST_INFO:
            self.buttons = draw_info(self, surf, self.time)
        elif self.state == ST_LEVELS:
            self.buttons = draw_level_select(self, surf, self.time)
        elif self.state == ST_SHOP:
            self.buttons = draw_shop(self, surf, self.time)
        elif self.state == ST_SETTINGS:
            self.buttons = draw_settings(self, surf, self.time)
        elif self.state == ST_ACHIEVEMENTS:
            self.buttons = draw_achievements(self, surf, self.time)
        elif self.state == ST_PAUSE:
            if self.world:
                self.world.draw(surf, self)
            draw_pause(self, surf, self.time)
            self.buttons = draw_pause(self, surf, self.time)
        elif self.state == ST_COMPLETE:
            if self.world:
                self.world.draw(surf, self)
            self.buttons = draw_complete(self, surf, self.time)
        elif self.state == ST_GAMEOVER:
            self.buttons = draw_gameover(self, surf, self.time)
        elif self.state == ST_VICTORY:
            self.buttons = draw_victory(self, surf, self.time)
        elif self.state == "COMMUNITY":
            self.buttons = draw_community(self, surf, self.time)
        elif self.state == ST_PLAY:
            if self.world:
                self.world.draw(surf, self)
                draw_hud(self, surf)
            self.buttons = []

        # toast
        if self.toast_timer > 0 and self.toast is not None and \
                self.state not in (ST_PAUSE, ST_COMPLETE, ST_GAMEOVER):
            surf.blit(self.toast, (SCREEN_W // 2 - self.toast.get_width() // 2,
                                   SCREEN_H - 18))
        self.handle_buttons(self.buttons)

        if not self.headless:
            scaled = pygame.transform.scale(surf, self.screen.get_size())
            self.screen.blit(scaled, (0, 0))
        pygame.display.flip()

    # -- main loop ---------------------------------------------------------
    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif event.type == pygame.MOUSEWHEEL:
                    self.input.wheel += event.y
            self.input.begin_frame()
            dt = min(1.0 / 30.0, clock.tick(FPS) / 1000.0)
            self.update(dt)
            self.draw()
            self.input.tick()
        pygame.quit()
