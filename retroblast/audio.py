"""Procedural chiptune audio: SFX and looping music generated with stdlib."""
from __future__ import annotations

import math
import os
import random
import struct
import wave
from array import array

import pygame

from .config import AUDIO_DIR

SR = 16000
STAMP = os.path.join(AUDIO_DIR, "stamp.txt")


# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------
def _osc(kind: str, phase: float) -> float:
    phase -= math.floor(phase)
    if kind == "square":
        return 1.0 if phase < 0.5 else -1.0
    if kind == "triangle":
        return 4.0 * abs(phase - 0.5) - 1.0
    if kind == "saw":
        return 2.0 * phase - 1.0
    return math.sin(2.0 * math.pi * phase)


def _freq(semi: float) -> float:
    return 440.0 * (2.0 ** (semi / 12.0))


def _write_wav(path: str, samples) -> None:
    data = array("h")
    for s in samples:
        data.append(int(max(-1.0, min(1.0, s)) * 30000))
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(data.tobytes())


def _tone(freq: float, dur: float, kind: str = "square", vol: float = 0.3,
          slide: float = 0.0, attack: float = 0.004):
    n = max(1, int(dur * SR))
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        f = freq * (2.0 ** (slide * t / max(1e-6, dur)))
        phase += f / SR
        env = min(1.0, i / (attack * SR)) * (1.0 - t) ** 0.6
        out.append(_osc(kind, phase) * vol * env)
    return out


def _noise(dur: float, vol: float = 0.3, seed: int = 0) -> list:
    rng = random.Random(seed)
    n = max(1, int(dur * SR))
    return [rng.uniform(-1, 1) * vol * (1.0 - i / n) for i in range(n)]


def _mix(*tracks) -> list:
    size = max((len(t) for t in tracks), default=0)
    out = [0.0] * size
    for track in tracks:
        for i, s in enumerate(track):
            out[i] += s
    peak = max((abs(s) for s in out), default=1.0) or 1.0
    if peak > 0.95:
        scale = 0.95 / peak
        out = [s * scale for s in out]
    return out


def _concat(*parts) -> list:
    out = []
    for p in parts:
        out.extend(p)
    return out


def _silence(dur: float) -> list:
    return [0.0] * int(dur * SR)


# ---------------------------------------------------------------------------
# SFX definitions
# ---------------------------------------------------------------------------
def build_sfx() -> dict:
    s = {}
    s["jump"] = _tone(330, 0.16, "square", 0.28, slide=1.6)
    s["coin"] = _concat(_tone(988, 0.06, "square", 0.26),
                        _tone(1319, 0.12, "square", 0.24))
    s["gem"] = _concat(_tone(1175, 0.07, "triangle", 0.3),
                       _tone(1568, 0.14, "triangle", 0.28))
    s["diamond"] = _concat(_tone(1319, 0.06, "triangle", 0.3),
                           _tone(1760, 0.06, "triangle", 0.28),
                           _tone(2093, 0.12, "triangle", 0.26))
    s["key"] = _concat(_tone(784, 0.06, "square", 0.28),
                       _tone(1047, 0.06, "square", 0.26),
                       _tone(1568, 0.14, "square", 0.24))
    s["box"] = _concat(_noise(0.06, 0.25, 1), _tone(523, 0.1, "square", 0.24),
                       _tone(784, 0.12, "square", 0.22))
    s["hurt"] = _concat(_tone(220, 0.12, "saw", 0.3, slide=-0.8),
                        _tone(110, 0.2, "saw", 0.26, slide=-0.5))
    s["die"] = _concat(_tone(440, 0.14, "saw", 0.3, slide=-1.2),
                       _tone(220, 0.2, "saw", 0.28, slide=-1.0),
                       _tone(110, 0.4, "saw", 0.24, slide=-0.6))
    s["stomp"] = _concat(_noise(0.05, 0.3, 2), _tone(180, 0.1, "square", 0.26,
                                                    slide=-0.6))
    s["land"] = _noise(0.05, 0.16, 3)
    s["select"] = _tone(660, 0.05, "square", 0.2)
    s["confirm"] = _concat(_tone(660, 0.06, "square", 0.24),
                           _tone(880, 0.1, "square", 0.22))
    s["back"] = _tone(440, 0.08, "square", 0.2, slide=-0.4)
    s["pause"] = _concat(_tone(523, 0.05, "square", 0.2),
                         _tone(392, 0.08, "square", 0.2))
    s["secret"] = _concat(*[_tone(f, 0.09, "triangle", 0.26)
                            for f in (523, 659, 784, 1047, 1319)])
    s["door"] = _concat(_tone(196, 0.16, "triangle", 0.28),
                        _tone(294, 0.2, "triangle", 0.24))
    s["unlock"] = _concat(_tone(784, 0.07, "square", 0.26),
                          _tone(1175, 0.14, "square", 0.24))
    s["win"] = _concat(*[_tone(f, 0.13, "square", 0.26)
                         for f in (523, 659, 784, 1047, 784, 1047, 1319)])
    s["boss_hit"] = _concat(_noise(0.06, 0.3, 4), _tone(140, 0.12, "saw", 0.28))
    s["boss_die"] = _concat(_noise(0.4, 0.34, 5),
                            _tone(90, 0.5, "saw", 0.3, slide=-0.7),
                            _tone(60, 0.6, "square", 0.24, slide=-0.4))
    s["powerup"] = _concat(*[_tone(f, 0.07, "square", 0.24)
                             for f in (523, 659, 784, 1047)])
    s["spring"] = _tone(240, 0.2, "square", 0.26, slide=2.2)
    s["dash"] = _noise(0.12, 0.2, 6)
    s["splash"] = _noise(0.2, 0.24, 7)
    s["click"] = _tone(880, 0.04, "square", 0.18)
    s["achievement"] = _concat(*[_tone(f, 0.1, "triangle", 0.28)
                                 for f in (784, 988, 1175, 1568)])
    s["buy"] = _concat(_tone(1047, 0.06, "square", 0.26),
                       _tone(1319, 0.12, "square", 0.24))
    s["error"] = _tone(160, 0.16, "saw", 0.26, slide=-0.3)
    s["gameover"] = _concat(*[_tone(f, 0.22, "triangle", 0.26)
                              for f in (392, 330, 262, 196)])
    s["countdown"] = _tone(880, 0.08, "square", 0.24)
    return s


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------
def _render_track(bpm, bars, roots, mode="major", lead_wave="square",
                  bass_wave="triangle", drums=1, lead_vol=0.2, bass_vol=0.22):
    steps = bars * 8
    step_dur = 60.0 / bpm / 2.0
    lead = [None] * steps
    bass = [None] * steps
    drum = [0] * steps
    arp = [0, 4, 7, 12, 7, 4] if mode == "major" else [0, 3, 7, 12, 7, 3]
    for bar in range(bars):
        root = roots[bar % len(roots)]
        base = bar * 8
        for k in range(0, 8, 2):
            bass[base + k] = root - 12
        for k in range(8):
            if k % 2 == 0:
                lead[base + k] = root + 12 + arp[(k // 2 + bar) % len(arp)]
            elif k == 5:
                lead[base + k] = root + 12 + arp[(k // 2 + bar) % len(arp)]
        drum[base] = 1
        drum[base + 4] = 1
        if drums:
            drum[base + 2] = 2
            drum[base + 6] = 2
        if drums >= 2:
            drum[base + 4] = 3
            drum[base + 7] = 2
    lead_samples = [0.0] * int(steps * step_dur * SR)
    bass_samples = [0.0] * len(lead_samples)
    drum_samples = [0.0] * len(lead_samples)
    for idx in range(steps):
        if lead[idx] is not None:
            part = _tone(_freq(lead[idx]), step_dur * 0.92, lead_wave, lead_vol)
            _add(lead_samples, part, int(idx * step_dur * SR))
        if bass[idx] is not None:
            part = _tone(_freq(bass[idx]), step_dur * 0.95, bass_wave, bass_vol)
            _add(bass_samples, part, int(idx * step_dur * SR))
        if drum[idx]:
            if drum[idx] == 1:
                part = _tone(120, 0.09, "sine", 0.5, slide=-0.8)
            elif drum[idx] == 2:
                part = _noise(0.03, 0.12, idx)
            else:
                part = _noise(0.09, 0.24, idx + 50)
            _add(drum_samples, part, int(idx * step_dur * SR))
    return _mix(lead_samples, bass_samples, drum_samples)


def _add(target, part, offset):
    for i, s in enumerate(part):
        j = offset + i
        if 0 <= j < len(target):
            target[j] += s


TRACKS = {
    "menu": dict(bpm=96, bars=4, roots=[0, -3, 5, 7], mode="major", drums=1),
    "world1": dict(bpm=132, bars=8, roots=[0, 5, -3, 7], mode="major", drums=2),
    "world2": dict(bpm=108, bars=8, roots=[-3, -7, -5, -3], mode="minor", drums=1,
                   lead_wave="triangle"),
    "world3": dict(bpm=128, bars=8, roots=[5, 5, -2, 3], mode="minor", drums=2,
                   lead_wave="saw", bass_vol=0.26),
    "world4": dict(bpm=150, bars=8, roots=[-5, -5, -8, -3], mode="minor", drums=2,
                   lead_wave="square"),
    "boss": dict(bpm=152, bars=6, roots=[5, 5, 3, -2], mode="minor", drums=2,
                 lead_wave="saw", bass_vol=0.28),
    "victory": dict(bpm=140, bars=4, roots=[0, 5, -3, 7], mode="major", drums=2),
}


def ensure_audio() -> None:
    os.makedirs(AUDIO_DIR, exist_ok=True)
    stamp = "retro-blast-audio-v1"
    if os.path.exists(STAMP):
        with open(STAMP, "r", encoding="utf-8") as fh:
            if fh.read().strip() == stamp:
                return
    for name, samples in build_sfx().items():
        _write_wav(os.path.join(AUDIO_DIR, f"{name}.wav"), samples)
    for name, cfg in TRACKS.items():
        cfg = dict(cfg)
        track_name = cfg.pop("name", name)
        _write_wav(os.path.join(AUDIO_DIR, f"music_{name}.wav"),
                   _render_track(**cfg))
    with open(STAMP, "w", encoding="utf-8") as fh:
        fh.write(stamp)


class Audio:
    """SFX + music player with a null fallback when no mixer is available."""

    def __init__(self, save=None):
        self.ok = False
        self.sounds = {}
        self.current_music = None
        self.music_vol = 0.8
        self.sfx_vol = 0.9
        if save:
            self.music_vol = float(save["settings"].get("music", 0.8))
            self.sfx_vol = float(save["settings"].get("sfx", 0.9))
        try:
            pygame.mixer.init(frequency=SR, channels=1, buffer=512)
            self.ok = True
        except pygame.error:
            self.ok = False

    # -- sfx ---------------------------------------------------------------
    def _sound(self, name: str):
        if name not in self.sounds:
            path = os.path.join(AUDIO_DIR, f"{name}.wav")
            if not os.path.exists(path):
                return None
            try:
                self.sounds[name] = pygame.mixer.Sound(path)
            except pygame.error:
                return None
        return self.sounds[name]

    def play(self, name: str, volume: float = 1.0):
        if not self.ok:
            return
        snd = self._sound(name)
        if snd is None:
            return
        snd.set_volume(self.sfx_vol * volume)
        snd.play()

    # -- music -------------------------------------------------------------
    def play_music(self, name: str):
        if not self.ok or self.current_music == name:
            return
        path = os.path.join(AUDIO_DIR, f"music_{name}.wav")
        if not os.path.exists(path):
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_vol * 0.6)
            pygame.mixer.music.play(-1)
            self.current_music = name
        except pygame.error:
            pass

    def stop_music(self):
        if self.ok:
            pygame.mixer.music.stop()
        self.current_music = None

    def set_music_volume(self, value: float):
        self.music_vol = value
        if self.ok:
            pygame.mixer.music.set_volume(value * 0.6)

    def set_sfx_volume(self, value: float):
        self.sfx_vol = value
