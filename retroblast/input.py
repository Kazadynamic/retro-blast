"""Unified keyboard + gamepad input with menu navigation."""
from __future__ import annotations

import pygame

from .config import clamp

KEYMAP = {
    "left": (pygame.K_a, pygame.K_LEFT),
    "right": (pygame.K_d, pygame.K_RIGHT),
    "up": (pygame.K_w, pygame.K_UP),
    "down": (pygame.K_s, pygame.K_DOWN),
    "jump": (pygame.K_SPACE, pygame.K_z, pygame.K_k),
    "interact": (pygame.K_e, pygame.K_RETURN),
    "dash": (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_x),
    "pause": (pygame.K_ESCAPE, pygame.K_p),
}

# Standard mapping buttons: A=0 B=1 X=2 Y=3 LB=4 RB=5 BACK=6 START=9
PAD_JUMP = (0, 2)
PAD_INTERACT = (1, 3)
PAD_DASH = (4, 5)
PAD_PAUSE = (9, 6)

AXIS_DEADZONE = 0.35


class Input:
    def __init__(self):
        self.held = set()
        self.pressed = set()
        self.released = set()
        self.pad_held = set()
        self.pad_pressed = set()
        self.pad_released = set()
        self.axis = (0.0, 0.0)
        self.joystick = None
        self.mouse_pos = (0, 0)
        self.mouse_pressed = False
        self.mouse_held = False
        self._prev_mouse = False
        self.wheel = 0
        self._prev_keys = set()
        self._prev_buttons = set()
        self._prev_axis = (0.0, 0.0)
        self.any_key = False
        self._scan()

    # -- lifecycle ---------------------------------------------------------
    def _scan(self):
        if pygame.joystick.get_count() > 0 and self.joystick is None:
            try:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
            except pygame.error:
                self.joystick = None

    def begin_frame(self):
        keys = pygame.key.get_pressed()
        self.held = {name for name, codes in KEYMAP.items()
                     if any(keys[c] for c in codes if c is not None)}
        for name, codes in KEYMAP.items():
            for c in codes:
                if c is None:
                    continue
                if keys[c] and c not in self._prev_keys:
                    self.pressed.add(name)
                elif not keys[c] and c in self._prev_keys:
                    self.released.add(name)
        self._prev_keys = {c for codes in KEYMAP.values() for c in codes
                           if c is not None and keys[c]}

        if self.joystick is not None:
            ax = self.joystick.get_axis(0)
            ay = self.joystick.get_axis(1)
            mag = (ax * ax + ay * ay) ** 0.5
            if mag < AXIS_DEADZONE:
                ax = ay = 0.0
            self.axis = (ax, ay)
            buttons = set()
            for i in range(self.joystick.get_numbuttons()):
                if self.joystick.get_button(i):
                    buttons.add(i)
            if self.joystick.get_numhats() > 0:
                hx, hy = self.joystick.get_hat(0)
                if hx < 0:
                    buttons.add(100)
                if hx > 0:
                    buttons.add(101)
                if hy > 0:
                    buttons.add(102)
                if hy < 0:
                    buttons.add(103)
            self.pad_pressed = buttons - self._prev_buttons
            self.pad_released = self._prev_buttons - buttons
            self.pad_held = buttons
            self._prev_buttons = buttons
            if ax or ay:
                self.axis = (ax, ay)
            # analogue stick edge detection for menu navigation
            if ax < -0.6 and self._prev_axis[0] >= -0.6:
                self.pressed.add("left")
            if ax > 0.6 and self._prev_axis[0] <= 0.6:
                self.pressed.add("right")
            if ay < -0.6 and self._prev_axis[1] >= -0.6:
                self.pressed.add("up")
            if ay > 0.6 and self._prev_axis[1] <= 0.6:
                self.pressed.add("down")
            self._prev_axis = (ax, ay)
        else:
            self.axis = (0.0, 0.0)

        surf = pygame.display.get_surface()
        scale = max(1, surf.get_width() // 512) if surf is not None else 1
        mx, my = pygame.mouse.get_pos()
        self.mouse_pos = (mx // scale, my // scale)
        self.mouse_held = pygame.mouse.get_pressed()[0]
        self.mouse_pressed = self.mouse_held and not self._prev_mouse
        self._prev_mouse = self.mouse_held
        self.any_key = bool(self.pressed) or bool(self.pad_pressed)

    def tick(self):
        """Called at the end of a frame: clears per-frame events."""
        self.pressed.clear()
        self.released.clear()
        self.pad_pressed.clear()
        self.pad_released.clear()
        self.mouse_pressed = False
        self.any_key = False
        self.wheel = 0

    def consume(self, name: str):
        """Drop a pending press so it is not handled twice in one frame."""
        self.pressed.discard(name)
        self.pad_pressed.discard(name)

    # -- queries -----------------------------------------------------------
    def held_action(self, name: str) -> bool:
        if name == "left":
            return "left" in self.held or self.axis[0] < -AXIS_DEADZONE or 100 in self.pad_held
        if name == "right":
            return "right" in self.held or self.axis[0] > AXIS_DEADZONE or 101 in self.pad_held
        if name == "up":
            return "up" in self.held or self.axis[1] < -AXIS_DEADZONE or 102 in self.pad_held
        if name == "down":
            return "down" in self.held or self.axis[1] > AXIS_DEADZONE or 103 in self.pad_held
        if name in self.held:
            return True
        if name == "jump":
            return bool(self.pad_held & set(PAD_JUMP))
        if name == "interact":
            return bool(self.pad_held & set(PAD_INTERACT))
        if name == "dash":
            return bool(self.pad_held & set(PAD_DASH))
        if name == "pause":
            return bool(self.pad_held & set(PAD_PAUSE))
        return False

    def pressed_action(self, name: str) -> bool:
        if name in self.pressed:
            return True
        if name == "jump":
            return bool(self.pad_pressed & set(PAD_JUMP))
        if name == "interact":
            return bool(self.pad_pressed & set(PAD_INTERACT))
        if name == "dash":
            return bool(self.pad_pressed & set(PAD_DASH))
        if name == "pause":
            return bool(self.pad_pressed & set(PAD_PAUSE))
        if name == "up":
            return 102 in self.pad_pressed
        if name == "down":
            return 103 in self.pad_pressed
        if name == "left":
            return 100 in self.pad_pressed
        if name == "right":
            return 101 in self.pad_pressed
        return False

    def confirm(self) -> bool:
        return self.pressed_action("interact") or self.pressed_action("jump")

    def back(self) -> bool:
        return self.pressed_action("pause") or (1 in self.pad_pressed)

    def released_action(self, name: str) -> bool:
        if name in self.released:
            return True
        if name == "jump":
            return bool(self.pad_released & set(PAD_JUMP))
        return False
