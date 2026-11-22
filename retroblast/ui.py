"""All screens and widgets: menus, HUD, shop, panels, buttons."""
from __future__ import annotations

import pygame

from .assets import get_font, hammy_big, render_text, text_size
from .config import PAL, SCREEN_H, SCREEN_W, aabb, clamp
from .save import ACHIEVEMENTS, SHOP_ITEMS

FONT = get_font


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def label(surf, text, x, y, size=8, color=(255, 255, 255), shadow=None,
          align="left"):
    surf_s = render_text(text, size, color, shadow)
    if align == "center":
        x -= surf_s.get_width() // 2
    elif align == "right":
        x -= surf_s.get_width()
    surf.blit(surf_s, (int(x), int(y)))
    return surf_s


def panel(surf, rect, fill=None, border=None, radius=4):
    fill = fill or PAL["panel"]
    border = border or PAL["panel_lt"]
    pygame.draw.rect(surf, border, rect, border_radius=radius)
    inner = rect.inflate(-4, -4)
    pygame.draw.rect(surf, fill, inner, border_radius=max(1, radius - 1))


STYLES = {
    "orange": (PAL["orange"], PAL["orange_dk"], (255, 240, 200)),
    "cyan": (PAL["cyan"], (20, 120, 150), (230, 252, 255)),
    "green": (PAL["green"], PAL["green_dk"], (235, 255, 220)),
    "red": (PAL["red"], (140, 28, 30), (255, 220, 220)),
    "purple": (PAL["purple"], PAL["purple_dk"], (240, 225, 255)),
    "grey": (PAL["grey"], PAL["grey_dk"], (230, 232, 236)),
    "blue": (PAL["blue"], PAL["blue_dk"], (225, 240, 255)),
    "gold": (PAL["gold"], (176, 128, 20), (255, 248, 210)),
}


class Button:
    def __init__(self, rect, text, style="orange", size=8, action=None,
                 sub=None, disabled=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.style = style
        self.size = size
        self.action = action
        self.sub = sub
        self.disabled = disabled
        self.hover = False
        self.press = False

    def draw(self, surf):
        main, dark, light = STYLES.get(self.style, STYLES["orange"])
        if self.disabled:
            main, dark, light = PAL["grey_dk"], (40, 42, 52), (150, 154, 164)
        rect = self.rect
        if self.press:
            rect = rect.move(0, 2)
        pygame.draw.rect(surf, dark, rect, border_radius=4)
        inner = rect.inflate(-4, -4)
        pygame.draw.rect(surf, main, inner, border_radius=3)
        pygame.draw.line(surf, light, (inner.x + 2, inner.y + 1),
                         (inner.right - 2, inner.y + 1), 1)
        col = (30, 22, 18) if self.style in ("orange", "gold", "green") else \
            (16, 20, 34)
        label(surf, self.text, rect.centerx, rect.y + rect.height // 2 - self.size // 2 - 1,
              self.size, col, align="center")
        if self.sub:
            label(surf, self.sub, rect.centerx, rect.bottom - self.size - 3,
                  max(6, self.size - 2), light, align="center")

    def hit(self, pos):
        return not self.disabled and self.rect.collidepoint(pos)


# ---------------------------------------------------------------------------
# shared chrome
# ---------------------------------------------------------------------------
def draw_checker_floor(surf, y=272, square=8, col_a=(44, 38, 66),
                       col_b=(58, 50, 84)):
    for row in range((SCREEN_H - y) // square):
        for col in range(SCREEN_W // square + 1):
            colr = col_a if (row + col) % 2 == 0 else col_b
            pygame.draw.rect(surf, colr,
                             (col * square, y + row * square, square, square))


def draw_crt(surf, x, y, w=132, h=100, title="HAMMY'S HQ", time=0.0):
    pygame.draw.rect(surf, (58, 54, 70), (x - 4, y - 4, w + 8, h + 8),
                     border_radius=6)
    pygame.draw.rect(surf, (30, 28, 42), (x, y, w, h), border_radius=4)
    screen = pygame.Rect(x + 10, y + 10, w - 20, h - 34)
    pygame.draw.rect(surf, (16, 60, 74), screen, border_radius=3)
    pygame.draw.rect(surf, (8, 34, 44), screen.inflate(2, 2), 1, border_radius=3)
    # CRT scanlines
    for yy in range(screen.y, screen.bottom, 3):
        pygame.draw.line(surf, (10, 44, 56), (screen.x, yy),
                         (screen.right, yy), 1)
    label(surf, title, screen.centerx, screen.y + 6, 8, (120, 220, 235),
          align="center")
    # fake screen content
    for i in range(4):
        yy = screen.y + 22 + i * 7
        pygame.draw.line(surf, (40, 120, 140),
                         (screen.x + 8, yy), (screen.x + 8 + (30 + i * 8), yy), 2)
    blink = int(time * 2) % 2 == 0
    if blink:
        pygame.draw.rect(surf, (120, 220, 235),
                         (screen.x + 8, screen.bottom - 12, 5, 6))
    label(surf, "HAMMY OS v1.0", x + w // 2, y + h - 18, 6, (150, 150, 170),
          align="center")
    pygame.draw.rect(surf, (20, 18, 30), (x + w // 2 - 14, y + h - 6, 28, 3),
                     border_radius=1)


def draw_navbar(surf, game, buttons):
    pygame.draw.rect(surf, (22, 18, 38), (0, 0, SCREEN_W, 18))
    pygame.draw.line(surf, PAL["purple"], (0, 18), (SCREEN_W, 18))
    x = SCREEN_W - 8
    for btn in reversed(buttons):
        x -= btn.rect.width + 6
        btn.rect.x = x
        btn.rect.y = 3
        btn.draw(surf)


def draw_info_panel(surf, game, rect):
    panel(surf, rect)
    save = game.save
    lvl, xp = save.level_xp()
    label(surf, f"LV {lvl}", rect.x + 10, rect.y + 6, 10, PAL["yellow"])
    label(surf, f"XP {xp}", rect.x + 10, rect.y + 20, 6, PAL["grey"])
    label(surf, f"COINS {save['coins']}", rect.x + 70, rect.y + 6, 8,
          PAL["gold"])
    label(surf, f"GEMS {save['gems']}", rect.x + 70, rect.y + 18, 8,
          PAL["gem_pink"])
    label(surf, f"DIAMONDS {save['diamonds']}", rect.x + 70, rect.y + 30, 6,
          PAL["gem_blue"])
    done = sum(1 for key in save["progress"] if save["progress"][key])
    label(surf, f"PROGRESS {done}/8", rect.x + 160, rect.y + 6, 6,
          PAL["cyan"])
    bar = pygame.Rect(rect.x + 160, rect.y + 16, 66, 6)
    pygame.draw.rect(surf, (30, 26, 48), bar)
    pygame.draw.rect(surf, PAL["cyan"],
                     (bar.x, bar.y, int(bar.width * done / 8), bar.height))
    # settings button
    btn = Button((rect.right - 26, rect.y + rect.height - 22, 20, 16), "S",
                 "grey", 8, action="settings")
    btn.draw(surf)
    return btn


# ---------------------------------------------------------------------------
# MAIN MENU
# ---------------------------------------------------------------------------
def draw_main_menu(game, surf, time):
    assets = game.assets
    surf.fill(PAL["sky_top"])
    fx = -(int(time * 6) % SCREEN_W)
    surf.blit(assets.bg_far[0], (fx, 0))
    surf.blit(assets.bg_far[0], (fx + SCREEN_W, 0))
    mx = -(int(time * 14) % SCREEN_W)
    surf.blit(assets.bg_mid[0], (mx, 0))
    surf.blit(assets.bg_mid[0], (mx + SCREEN_W, 0))
    draw_checker_floor(surf, 272)

    # logo
    label(surf, "RETRO BLAST!", 12, 24, 22, PAL["orange"],
          shadow=(90, 30, 10))
    label(surf, "RETRO BLAST!", 10, 22, 22, PAL["yellow"])
    label(surf, "EXPLORE THE PIXELVERSE WITH HAMMY", 12, 50, 8, PAL["cyan"],
          shadow=(10, 40, 60))

    # Hammy standing on the left, clear of the info panel
    pose = "idle"
    frame = int(time * 3) % 2
    img = assets.hammy(pose, frame, game.save["equipped"]["skin"],
                       game.save["equipped"]["backpack"],
                       game.save["equipped"]["accessory"])
    surf.blit(hammy_big(pose, frame, game.save["equipped"]["skin"],
                        game.save["equipped"]["backpack"],
                        game.save["equipped"]["accessory"], 3), (18, 116))
    pygame.draw.ellipse(surf, (0, 0, 0, 60), (24, 182, 60, 6))

    draw_crt(surf, 118, 94, 132, 100, "HAMMY'S HQ", time)

    # buttons
    start = Button((300, 84, 176, 28), "START ADVENTURE", "orange", 10,
                   action="start")
    learn = Button((300, 118, 176, 22), "LEARN MORE", "cyan", 8, action="info")
    shop = Button((300, 146, 176, 20), "SHOP", "purple", 8, action="shop")
    for btn in (start, learn, shop):
        btn.hover = btn.hit(game.input.mouse_pos)
        btn.draw(surf)

    label(surf, "ARROWS/WASD MOVE  SPACE JUMP", 300, 178, 6, (255, 255, 255))
    label(surf, "E INTERACT   ESC PAUSE", 300, 188, 6, (220, 226, 240))

    info_btn = draw_info_panel(surf, game, pygame.Rect(12, 210, 280, 56))
    info_btn.hover = info_btn.hit(game.input.mouse_pos)
    info_btn.draw(surf)

    label(surf, f"V{game.version}", SCREEN_W - 8, SCREEN_H - 12, 6,
          PAL["grey"], align="right")
    nav = [
        Button((0, 3, 44, 13), "HOME", "purple", 6, action="menu"),
        Button((0, 3, 50, 13), "GAMES", "cyan", 6, action="levels"),
        Button((0, 3, 46, 13), "SHOP", "gold", 6, action="shop"),
        Button((0, 3, 72, 13), "COMMUNITY", "green", 6, action="community"),
    ]
    for btn in nav:
        btn.hover = btn.hit(game.input.mouse_pos)
    draw_navbar(surf, game, nav)
    return [start, learn, shop, info_btn] + nav


# ---------------------------------------------------------------------------
# GAME INFO / LEARN MORE
# ---------------------------------------------------------------------------
def draw_info(game, surf, time):
    surf.fill(PAL["panel"])
    label(surf, "ABOUT RETRO BLAST!", 16, 18, 14, PAL["orange"])
    label(surf, "EXPLORE THE PIXELVERSE WITH HAMMY", 16, 38, 8, PAL["cyan"])
    lines = [
        "HAMMY IS A BRAVE LITTLE HAMSTER WITH A BIG",
        "BACKPACK AND AN EVEN BIGGER HEART. RUN, JUMP",
        "AND COLLECT COINS, GEMS AND DIAMONDS ACROSS",
        "4 WORLDS: GRASSLAND, CAVERNS, NEON CITY AND",
        "THE LAVA FORTRESS.",
        "",
        "CONTROLS:",
        "  A/D OR ARROWS ... MOVE",
        "  SPACE ............ JUMP (HOLD = HIGHER)",
        "  E OR ENTER ....... INTERACT / CONFIRM",
        "  SHIFT ............ DASH (IF BOUGHT)",
        "  ESC OR P ......... PAUSE",
        "  GAMEPAD .......... STICK + A JUMP + B INTERACT",
        "",
        "STOMP ENEMIES, FIND SECRET ROOMS, GRAB KEYS",
        "TO OPEN LOCKED DOORS AND BEAT THE BOSS GATE.",
    ]
    y = 58
    for line in lines:
        label(surf, line, 16, y, 6, PAL["white"] if line else PAL["grey"])
        y += 10
    back = Button((SCREEN_W // 2 - 40, SCREEN_H - 30, 80, 20), "BACK", "red", 8,
                  action="back")
    back.hover = back.hit(game.input.mouse_pos)
    back.draw(surf)
    return [back]


# ---------------------------------------------------------------------------
# LEVEL SELECT
# ---------------------------------------------------------------------------
def draw_level_select(game, surf, time):
    surf.fill((18, 16, 34))
    label(surf, "SELECT LEVEL", 16, 14, 14, PAL["orange"])
    label(surf, "COMPLETE A LEVEL TO UNLOCK THE NEXT", 16, 32, 6, PAL["grey"])
    buttons = []
    col_x = (16, 262)
    row_y = (46, 170)
    for world in range(4):
        cx = col_x[world % 2]
        cy = row_y[world // 2]
        unlocked_world = world < game.save["unlocked_worlds"]
        label(surf, f"WORLD {world + 1}: {game.worlds[world]['name']}", cx, cy,
              8, PAL["cyan"] if unlocked_world else PAL["grey_dk"])
        for idx in range(2):
            lvl_id = f"{world}:{idx}"
            unlocked = world < game.save["unlocked_worlds"] or \
                (world == game.save["unlocked_worlds"] - 1 and idx == 0)
            done = bool(game.save["progress"].get(lvl_id))
            name = game.level_names[world][idx]
            style = "green" if done else ("orange" if unlocked else "grey")
            by = cy + 14 + idx * 26
            btn = Button((cx, by, 118, 22), name, style, 7,
                         action=f"play:{world}:{idx}", disabled=not unlocked)
            btn.hover = btn.hit(game.input.mouse_pos)
            btn.draw(surf)
            if done:
                label(surf, "CLEAR", cx + 124, by + 8, 6, PAL["green"])
            buttons.append(btn)
    back = Button((SCREEN_W - 80, SCREEN_H - 26, 64, 16), "BACK", "red", 8,
                  action="back")
    back.hover = back.hit(game.input.mouse_pos)
    back.draw(surf)
    buttons.append(back)
    return buttons


# ---------------------------------------------------------------------------
# SHOP
# ---------------------------------------------------------------------------
SLOTS = [("skin", "SKINS"), ("backpack", "BACKPACKS"), ("accessory", "GEAR"),
         ("ability", "SKILLS"), ("powerup", "POWER-UPS")]


def shop_preview(surf, game, item, x, y):
    assets = game.assets
    item_id, name, desc, price, slot, data = item
    if slot == "skin":
        img = assets.hammy("idle", 0, data, "blue", "none")
    elif slot == "backpack":
        img = assets.hammy("idle", 0, "classic", data, "none")
    elif slot == "accessory":
        img = assets.hammy("idle", 0, "classic", "blue", data)
    elif slot == "powerup":
        img = assets.item(data)
    else:
        img = render_text(data[:2].upper(), 12, PAL["cyan"])
    surf.blit(pygame.transform.scale(img, (24, 24))
              if img.get_width() <= 24 else img, (x, y))


def draw_shop(game, surf, time):
    surf.fill((20, 16, 38))
    label(surf, "HAMMY'S SHOP", 16, 14, 14, PAL["gold"])
    label(surf, f"COINS {game.save['coins']}", SCREEN_W - 16, 18, 10,
          PAL["gold"], align="right")
    buttons = []
    tab_w = 92
    tab_x = 16
    for slot, title in SLOTS:
        active = game.shop_tab == slot
        btn = Button((tab_x, 34, tab_w - 4, 18), title,
                     "cyan" if active else "grey", 6, action=f"tab:{slot}")
        btn.hover = btn.hit(game.input.mouse_pos)
        btn.draw(surf)
        buttons.append(btn)
        tab_x += tab_w

    items = [it for it in SHOP_ITEMS if it[4] == game.shop_tab]
    row_h = 30
    list_rect = pygame.Rect(16, 58, SCREEN_W - 32, SCREEN_H - 58 - 40)
    surf.set_clip(list_rect)
    y = list_rect.y - game.shop_scroll
    for item in items:
        item_id, name, desc, price, slot, data = item
        owned = game.is_owned(item_id)
        equipped = game.save["equipped"].get(slot) == data
        rect = pygame.Rect(list_rect.x, y, list_rect.width, row_h - 4)
        if rect.bottom > list_rect.y and rect.top < list_rect.bottom:
            pygame.draw.rect(surf, (32, 26, 52), rect, border_radius=3)
            shop_preview(surf, game, item, rect.x + 4, rect.y + 3)
            label(surf, name, rect.x + 34, rect.y + 3, 8,
                  PAL["white"] if not owned else PAL["cyan"])
            label(surf, desc, rect.x + 34, rect.y + 14, 6, PAL["grey"])
            if equipped:
                label(surf, "EQUIPPED", rect.right - 8, rect.y + 10, 6,
                      PAL["green"], align="right")
                y += row_h
                continue
            if owned:
                btn = Button((rect.right - 78, rect.y + 9, 70, 13), "EQUIP",
                             "blue", 6, action=f"equip:{item_id}")
            else:
                btn = Button((rect.right - 78, rect.y + 9, 70, 13),
                             f"BUY {price}",
                             "orange" if game.save["coins"] >= price
                             else "grey", 6, action=f"buy:{item_id}",
                             disabled=game.save["coins"] < price)
            btn.hover = btn.hit(game.input.mouse_pos) and \
                list_rect.collidepoint(game.input.mouse_pos)
            btn.draw(surf)
            buttons.append(btn)
        y += row_h
    surf.set_clip(None)
    content_h = len(items) * row_h
    max_scroll = max(0, content_h - list_rect.height)
    game.shop_scroll = max(0, min(max_scroll, game.shop_scroll))
    if max_scroll > 0:
        thumb_h = max(10, int(list_rect.height * list_rect.height / content_h))
        thumb_y = list_rect.y + int(game.shop_scroll / max_scroll *
                                    (list_rect.height - thumb_h))
        pygame.draw.rect(surf, PAL["grey"],
                         (list_rect.right + 2, thumb_y, 3, thumb_h))
    back = Button((SCREEN_W - 80, SCREEN_H - 26, 64, 16), "BACK", "red", 8,
                  action="back")
    back.hover = back.hit(game.input.mouse_pos)
    back.draw(surf)
    buttons.append(back)
    return buttons


# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
def draw_settings(game, surf, time):
    surf.fill(PAL["panel"])
    label(surf, "SETTINGS", 16, 18, 14, PAL["cyan"])
    buttons = []
    y = 50
    for name, key in (("MUSIC", "music"), ("SFX", "sfx")):
        label(surf, name, 20, y, 8, PAL["white"])
        for i in range(5):
            on = game.save["settings"][key] >= (i + 1) * 0.2 - 0.01
            btn = Button((80 + i * 26, y - 4, 22, 14), str(i + 1),
                         "cyan" if on else "grey", 6,
                         action=f"vol:{key}:{i + 1}")
            btn.hover = btn.hit(game.input.mouse_pos)
            btn.draw(surf)
            buttons.append(btn)
        y += 24
    label(surf, "SCREEN SCALE", 20, y, 8, PAL["white"])
    for i, scale in enumerate((2, 3, 4)):
        on = game.save["settings"]["scale"] == scale
        btn = Button((120 + i * 34, y - 4, 30, 14), f"{scale}X",
                     "cyan" if on else "grey", 6, action=f"scale:{scale}")
        btn.hover = btn.hit(game.input.mouse_pos)
        btn.draw(surf)
        buttons.append(btn)
    y += 26
    shake = game.save["settings"].get("screen_shake", True)
    btn = Button((20, y, 120, 16), f"SCREEN SHAKE: {'ON' if shake else 'OFF'}",
                 "cyan" if shake else "grey", 6, action="shake")
    btn.hover = btn.hit(game.input.mouse_pos)
    btn.draw(surf)
    buttons.append(btn)
    y += 26
    btn = Button((20, y, 120, 16), "RESET SAVE DATA", "red", 6, action="reset")
    btn.hover = btn.hit(game.input.mouse_pos)
    btn.draw(surf)
    buttons.append(btn)
    back = Button((SCREEN_W - 80, SCREEN_H - 28, 64, 18), "BACK", "red", 8,
                  action="back")
    back.hover = back.hit(game.input.mouse_pos)
    back.draw(surf)
    buttons.append(back)
    return buttons


# ---------------------------------------------------------------------------
# ACHIEVEMENTS
# ---------------------------------------------------------------------------
def draw_achievements(game, surf, time):
    surf.fill((20, 16, 38))
    label(surf, "ACHIEVEMENTS", 16, 16, 14, PAL["gold"])
    buttons = []
    y = 44 - game.ach_scroll
    for ach_id, name, desc in ACHIEVEMENTS:
        got = ach_id in game.save["achievements"]
        rect = pygame.Rect(16, y, SCREEN_W - 32, 24)
        pygame.draw.rect(surf, (32, 26, 52), rect, border_radius=3)
        label(surf, name, rect.x + 8, rect.y + 3, 8,
              PAL["gold"] if got else PAL["grey"])
        label(surf, desc, rect.x + 8, rect.y + 14, 6, PAL["white"] if got
              else PAL["grey_dk"])
        label(surf, "DONE" if got else "LOCKED", rect.right - 8, rect.y + 8, 6,
              PAL["green"] if got else PAL["grey_dk"], align="right")
        y += 28
    content_h = len(ACHIEVEMENTS) * 28
    max_scroll = max(0, content_h - (SCREEN_H - 80))
    game.ach_scroll = max(0, min(max_scroll, game.ach_scroll))
    back = Button((SCREEN_W - 80, SCREEN_H - 28, 64, 18), "BACK", "red", 8,
                  action="back")
    back.hover = back.hit(game.input.mouse_pos)
    back.draw(surf)
    buttons.append(back)
    return buttons


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
def draw_hud(game, surf):
    world = game.world
    p = world.player
    surf.fill((0, 0, 0), (0, 0, SCREEN_W, 20))
    pygame.draw.line(surf, (40, 34, 60), (0, 20), (SCREEN_W, 20))
    # health
    for i in range(p.max_health):
        img = game.assets.item("heart" if i < p.health else "heart")
        if i >= p.health:
            dark = pygame.Surface(img.get_size(), pygame.SRCALPHA)
            dark.fill((40, 30, 40, 200))
            img = img.copy()
            img.blit(dark, (0, 0))
        surf.blit(img, (6 + i * 14, 4))
    label(surf, f"{world.coins}", 96, 6, 8, PAL["gold"], shadow=(20, 16, 10))
    surf.blit(game.assets.item("coin", 0), (84, 4))
    label(surf, f"{world.gems}", 152, 6, 8, PAL["gem_pink"], shadow=(20, 16, 10))
    surf.blit(game.assets.item("gem", 0), (140, 4))
    label(surf, f"{world.diamonds}", 208, 6, 8, PAL["gem_blue"],
          shadow=(20, 16, 10))
    surf.blit(game.assets.item("diamond", 0), (196, 4))
    if world.keys_held > 0:
        label(surf, f"KEY x{world.keys_held}", 264, 6, 8, PAL["yellow"],
              shadow=(20, 16, 10))
        surf.blit(game.assets.item("key", 0), (252, 4))
    # level name + progress
    label(surf, world.level.name, SCREEN_W - 8, 4, 6, PAL["cyan"],
          align="right")
    if world.level.width > 0:
        prog = clamp(p.cx / world.level.world_px, 0, 1)
        bar = pygame.Rect(SCREEN_W - 108, 13, 100, 4)
        pygame.draw.rect(surf, (40, 34, 60), bar)
        pygame.draw.rect(surf, PAL["cyan"], (bar.x, bar.y, int(bar.width * prog),
                                             bar.height))
    # power-up timers
    y = 24
    if p.star > 0:
        label(surf, f"STAR {p.star:.0f}", 8, y, 6, PAL["yellow"])
        y += 9
    if p.magnet > 0 and p.magnet < 9000:
        label(surf, f"MAGNET {p.magnet:.0f}", 8, y, 6, (224, 60, 56))
        y += 9
    if p.shield:
        label(surf, "SHIELD", 8, y, 6, PAL["cyan"])
    boss = getattr(world, "boss", None)
    if boss is not None and boss.alive:
        bar = pygame.Rect(SCREEN_W // 2 - 42, 22, 84, 6)
        pygame.draw.rect(surf, (30, 22, 30), bar)
        pygame.draw.rect(surf, PAL["red"],
                         (bar.x, bar.y, int(bar.width * max(0, boss.hp) / 8),
                          bar.height))
        pygame.draw.rect(surf, (200, 200, 210), bar, 1)
        label(surf, "BOSS", SCREEN_W // 2, 30, 6, PAL["red"], align="center")


# ---------------------------------------------------------------------------
# PAUSE / COMPLETE / GAME OVER / VICTORY
# ---------------------------------------------------------------------------
def draw_pause(game, surf, time):
    surf.fill((10, 8, 20))
    panel(surf, pygame.Rect(SCREEN_W // 2 - 110, 60, 220, 168))
    label(surf, "PAUSED", SCREEN_W // 2, 74, 16, PAL["orange"], align="center")
    buttons = []
    items = [("RESUME", "resume", "green"), ("SETTINGS", "settings", "cyan"),
             ("RESTART LEVEL", "restart", "orange"),
             ("QUIT TO MENU", "menu", "red")]
    y = 104
    for text, action, style in items:
        btn = Button((SCREEN_W // 2 - 80, y, 160, 20), text, style, 8,
                     action=action)
        btn.hover = btn.hit(game.input.mouse_pos)
        btn.draw(surf)
        buttons.append(btn)
        y += 24
    label(surf, "ESC TO RESUME", SCREEN_W // 2, 214, 6, PAL["grey"],
          align="center")
    return buttons


def draw_complete(game, surf, time):
    surf.fill((10, 20, 14))
    panel(surf, pygame.Rect(SCREEN_W // 2 - 130, 48, 260, 190))
    label(surf, "LEVEL CLEAR!", SCREEN_W // 2, 62, 16, PAL["green"],
          align="center")
    w = game.world
    rows = [("COINS", w.coins, PAL["gold"]), ("GEMS", w.gems, PAL["gem_pink"]),
            ("DIAMONDS", w.diamonds, PAL["gem_blue"]),
            ("SECRETS", w.secrets_found, PAL["cyan"])]
    y = 92
    for name, value, col in rows:
        label(surf, name, SCREEN_W // 2 - 100, y, 8, col)
        label(surf, str(value), SCREEN_W // 2 + 100, y, 8, PAL["white"],
              align="right")
        y += 16
    lvl, xp = game.save.level_xp()
    label(surf, f"PLAYER LV {lvl}  XP {game.last_xp}", SCREEN_W // 2, y + 6,
          8, PAL["yellow"], align="center")
    buttons = []
    next_btn = None
    if game.has_next_level():
        next_btn = Button((SCREEN_W // 2 - 110, y + 24, 100, 20), "NEXT LEVEL",
                          "orange", 7, action="next")
    menu_btn = Button((SCREEN_W // 2 + 10, y + 24, 100, 20), "MENU", "red", 7,
                      action="menu")
    for btn in (next_btn, menu_btn):
        if btn:
            btn.hover = btn.hit(game.input.mouse_pos)
            btn.draw(surf)
            buttons.append(btn)
    return buttons


def draw_gameover(game, surf, time):
    surf.fill((24, 8, 10))
    label(surf, "GAME OVER", SCREEN_W // 2, 70, 20, PAL["red"], align="center")
    label(surf, "HAMMY WILL TRY AGAIN!", SCREEN_W // 2, 100, 8, PAL["grey"],
          align="center")
    buttons = []
    retry = Button((SCREEN_W // 2 - 110, 140, 100, 22), "RETRY", "orange", 8,
                   action="restart")
    menu = Button((SCREEN_W // 2 + 10, 140, 100, 22), "MENU", "red", 8,
                  action="menu")
    for btn in (retry, menu):
        btn.hover = btn.hit(game.input.mouse_pos)
        btn.draw(surf)
        buttons.append(btn)
    return buttons


def draw_victory(game, surf, time):
    surf.fill((16, 12, 34))
    label(surf, "PIXEL MASTER!", SCREEN_W // 2, 60, 18, PAL["gold"],
          align="center")
    label(surf, "YOU CONQUERED THE PIXELVERSE!", SCREEN_W // 2, 88, 8,
          PAL["cyan"], align="center")
    img = hammy_big("victory", int(time * 4) % 2,
                    game.save["equipped"]["skin"],
                    game.save["equipped"]["backpack"],
                    game.save["equipped"]["accessory"], 3)
    surf.blit(img, (SCREEN_W // 2 - 36, 110))
    lvl, xp = game.save.level_xp()
    label(surf, f"PLAYER LV {lvl}", SCREEN_W // 2, 190, 8, PAL["yellow"],
          align="center")
    label(surf, f"COINS {game.save['coins']}  GEMS {game.save['gems']}",
          SCREEN_W // 2, 204, 8, PAL["white"], align="center")
    btn = Button((SCREEN_W // 2 - 60, 226, 120, 20), "MENU", "orange", 8,
                 action="menu")
    btn.hover = btn.hit(game.input.mouse_pos)
    btn.draw(surf)
    return [btn]


# ---------------------------------------------------------------------------
# community screen (stats + achievements shortcut)
# ---------------------------------------------------------------------------
def draw_community(game, surf, time):
    surf.fill((18, 16, 38))
    label(surf, "COMMUNITY HUB", 16, 16, 14, PAL["purple"])
    stats = game.save["stats"]
    rows = [("PLAYS", stats["plays"]), ("SECRETS FOUND", stats["secrets"]),
            ("BOSSES BEATEN", stats["bosses"]), ("DEATHS", stats["deaths"]),
            ("JUMPS", stats["jumps"]),
            ("ACHIEVEMENTS", f"{len(game.save['achievements'])}/"
                             f"{len(ACHIEVEMENTS)}")]
    y = 48
    for name, value in rows:
        label(surf, name, 20, y, 8, PAL["cyan"])
        label(surf, str(value), SCREEN_W - 20, y, 8, PAL["white"], align="right")
        y += 18
    buttons = []
    btn = Button((20, y + 6, 160, 20), "VIEW ACHIEVEMENTS", "gold", 7,
                 action="achievements")
    btn.hover = btn.hit(game.input.mouse_pos)
    btn.draw(surf)
    buttons.append(btn)
    back = Button((SCREEN_W - 80, SCREEN_H - 28, 64, 18), "BACK", "red", 8,
                  action="back")
    back.hover = back.hit(game.input.mouse_pos)
    back.draw(surf)
    buttons.append(back)
    return buttons
