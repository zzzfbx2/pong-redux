#!/usr/bin/env python3
"""
DON'T BUY THE HYPE — a 9:16 social video, generated entirely in Python.

Concept: an overpriced IPO told as a rocket launch. On the pad, the frame
swarms with FOMO ("TO THE MOON", "OVERSUBSCRIBED 20x", "CAN'T LOSE"). The
ticker pops at the open and climbs — priced for a perfect future, sold to
retail at the top. At the apex the lockup ends: insiders eject under golden
parachutes, the flame dies, and the rocket — with the one little retail
window still aboard — falls all the way back to the pad while the comment
storm turns red ("BAGHOLDER", "CAN'T SELL", "WHO COULD'VE KNOWN").
Up only in the prospectus. Don't buy the hype.

Everything is procedural: starfield, tower, vehicle, plume, parachutes,
live price ticker, camera shake, grain, and a synthesized soundtrack
(hype arpeggio -> engine rumble -> the cutoff -> falling whoosh -> impact
-> somber minor pad). Frames are piped raw to ffmpeg (libx264 + aac).

Usage:  python3 ipo_video.py [out.mp4]
Needs:  numpy, pillow, ffmpeg on PATH.
"""

import math
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
DUR = 34.0
N_FRAMES = int(DUR * FPS)
SR = 44100

# Timeline (seconds)
T_IGNITE = 7.0      # engine glow builds, countdown
T_LIFTOFF = 10.0    # the open: ticker leaves the pad
T_APEX = 18.0       # all-time high
T_STALL = 19.5      # hangs there for a heartbeat
T_CRASH = 26.5      # back on the pad
T_CARD = 30.0       # final title card

IPO_PRICE = 45.00

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
FONT_REG = f"{FONT_DIR}/DejaVuSans.ttf"

rng = random.Random(42)

# ---------------------------------------------------------------- utilities

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def smooth(a, b, t):
    if a == b:
        return 1.0 if t >= b else 0.0
    x = clamp((t - a) / (b - a))
    return x * x * (3 - 2 * x)


def font(path, size):
    return ImageFont.truetype(path, size)


# ------------------------------------------------------------- world pieces

STARS = [(rng.random(), rng.random(), rng.random()) for _ in range(420)]

HYPE = [
    "TO THE MOON", "GUARANTEED POP", "CAN'T LOSE", "GET IN NOW",
    "100x", "NEXT BIG THING", "FOMO", "PRICED FOR PERFECTION",
    "EVERYONE'S BUYING", "OVERSUBSCRIBED 20x", "IT ONLY GOES UP",
    "TRUST ME BRO", "ALLOCATION SECURED", "YOLO", "ROAD SHOW MAGIC",
    "ONCE IN A LIFETIME",
]
TRAP = [
    "BAGHOLDER", "TRAPPED", "DOWN 62%", "CAN'T SELL",
    "MARGIN CALL", "HALTED", "LOCKUP EXPIRED", "INSIDERS SOLD",
    "WHO COULD'VE KNOWN", "AVERAGING DOWN", "IT'LL COME BACK",
    "HOPE ISN'T A STRATEGY",
]


def scatter(words):
    pos = []
    for i, _ in enumerate(words):
        side = -1 if i % 2 == 0 else 1
        x = 0.5 + side * (0.16 + 0.30 * rng.random())
        y = 0.08 + 0.78 * rng.random()
        pos.append((x, y, rng.randint(34, 68), 0.4 + rng.random(),
                    rng.random() * math.tau))
    return pos


HYPE_POS = scatter(HYPE)
TRAP_POS = scatter(TRAP)

CAPTIONS = [
    (1.5, 6.4, "Every overpriced IPO\nbegins with a countdown."),
    (6.8, 9.8, "Priced for a perfect future.\nSold to you at the top."),
    (11.5, 15.5, "The pop is\nfor the insiders."),
    (16.0, 19.4, "Lockup ends.\nInsiders eject."),
    (20.5, 25.5, "Retail rides it\nall the way down."),
    (27.0, 29.6, "Up only\nin the prospectus."),
]

# (drift dx, sway speed, phase) for the three golden parachutes
CHUTES = [(-1.4, 1.7, 0.0), (0.3, 2.1, 2.1), (1.5, 1.5, 4.2)]


def arc(t):
    """Stock-as-altitude: 0 pad -> 1 apex -> 0 back on the pad."""
    if t <= T_LIFTOFF:
        return 0.0
    if t <= T_APEX:
        return smooth(T_LIFTOFF, T_APEX, t)
    if t <= T_STALL:
        return 1.0
    if t <= T_CRASH:
        x = (t - T_STALL) / (T_CRASH - T_STALL)
        return 1.0 - x * x          # gravity wins, accelerating
    return 0.0


def velocity(t):
    return (arc(t) - arc(t - 1 / FPS)) * FPS


def price(t):
    return float(np.interp(
        t,
        [0, T_LIFTOFF, 12.0, T_APEX, T_STALL, 21.0, 23.5, T_CRASH, DUR],
        [IPO_PRICE, IPO_PRICE, 67.0, 98.0, 96.0, 74.0, 38.0, 11.8, 11.8]))


def sky(t):
    alt = arc(t)
    top = np.array([4, 5, 14]) * (1 - alt) + np.array([0, 0, 2]) * alt
    bot = np.array([26, 22, 38]) * (1 - alt) + np.array([2, 2, 6]) * alt
    g = np.linspace(0, 1, H)[:, None, None]
    img = top[None, None, :] * (1 - g) + bot[None, None, :] * g
    return np.repeat(img, W, axis=1)


def draw_stars(arr, t, scroll):
    vis = 0.35 + 0.65 * arc(t)
    for sx, sy, ph in STARS:
        x = int(sx * W)
        y = int((sy * H + scroll * (0.15 + 0.5 * ph)) % H)
        tw = 0.6 + 0.4 * math.sin(t * 2.2 + ph * 9)
        b = int(255 * vis * tw * (0.3 + 0.7 * ph))
        arr[y:y + 2, x:x + 2] = np.maximum(arr[y:y + 2, x:x + 2], b)


def draw_streaks(d, t):
    vel = velocity(t)
    speed = clamp(abs(vel) * 3.0)
    if speed <= 0.05:
        return
    sign = 1 if vel > 0 else -1     # streaks trail opposite to motion
    n = int(40 * speed)
    r = random.Random(int(t * 7))
    for _ in range(n):
        x = r.randrange(W)
        y = r.randrange(H)
        ln = int(12 + 90 * speed * r.random()) * sign
        a = int(90 * speed * r.random())
        col = (200, 210, 255, a) if sign > 0 else (255, 160, 150, a)
        d.line([(x, y), (x, y + ln)], fill=col, width=2)


def draw_pad(d, t, scroll, ox, oy):
    gy = int(H * 0.86 + scroll) + oy
    if gy > H + 400:
        return
    d.rectangle([0, gy, W, H + 600], fill=(8, 7, 10, 255))
    tx = int(W * 0.30) + ox
    d.rectangle([tx, gy - 950, tx + 46, gy], fill=(14, 13, 18, 255))
    for i in range(9):
        yy = gy - 90 - i * 100
        d.line([(tx, yy), (tx + 46, yy - 36)], fill=(20, 19, 26, 255), width=7)
    d.line([(tx + 46, gy - 760), (tx + 210, gy - 740)],
           fill=(16, 15, 21, 255), width=16)
    for fx in (0.12, 0.85):
        lx, ly = int(W * fx) + ox, gy - 26
        glow = 0.5 + 0.5 * math.sin(t * 3 + fx * 10)
        d.ellipse([lx - 60, ly - 18, lx + 60, ly + 18],
                  fill=(255, 220, 160, int(38 * glow)))
        d.ellipse([lx - 8, ly - 8, lx + 8, ly + 8], fill=(255, 235, 200, 230))


def rocket_geometry(t):
    a = arc(t)
    cx = W * 0.5
    base = H * 0.84 - a * H * 0.34
    scale = 1.0 - 0.22 * a
    return cx, base, scale


# Vehicle is drawn into its own sprite so the whole thing (flame included)
# can tip over during the fall.
SPR_W, SPR_H = 560, 2100
SPR_BASE = 1150


def flame_power(t):
    build = smooth(T_IGNITE, T_LIFTOFF, t)
    die = 1.0 - smooth(T_APEX - 0.6, T_APEX + 0.5, t)   # hype runs out
    return build * die


def rocket_sprite(t, s):
    spr = Image.new("RGBA", (SPR_W, SPR_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(spr)
    cx, base = SPR_W / 2, SPR_BASE
    bw = 110 * s
    bh = 760 * s
    top = base - bh
    body = (208, 211, 218)
    shade = (148, 152, 162)
    d.rectangle([cx - bw, top + bw, cx + bw, base], fill=body)
    d.rectangle([cx + bw * 0.35, top + bw, cx + bw, base], fill=shade)
    d.pieslice([cx - bw, top, cx + bw, top + bw * 2.4], 180, 360, fill=body)
    fl = (120, 124, 134)
    d.polygon([(cx - bw, top + bw * 1.2), (cx - bw - 52 * s, top + bw * 2.6),
               (cx - bw, top + bw * 3.0)], fill=fl)
    d.polygon([(cx + bw, top + bw * 1.2), (cx + bw + 52 * s, top + bw * 2.6),
               (cx + bw, top + bw * 3.0)], fill=fl)
    d.polygon([(cx - bw, base - 240 * s), (cx - bw - 84 * s, base - 20 * s),
               (cx - bw, base)], fill=fl)
    d.polygon([(cx + bw, base - 240 * s), (cx + bw + 84 * s, base - 20 * s),
               (cx + bw, base)], fill=fl)
    # Ticker painted on the hull — this rocket IS the stock
    tf = font(FONT_BOLD, int(64 * s))
    tw = d.textlength("$IPO", font=tf)
    d.text((cx - tw / 2, top + bw * 3.4), "$IPO", font=tf, fill=(60, 64, 74))
    # The one little retail window, still aboard on the way down
    d.ellipse([cx - 14 * s, top + bw * 1.5, cx + 14 * s,
               top + bw * 1.5 + 28 * s], fill=(40, 60, 90))

    power = flame_power(t)
    if power > 0.01:
        r = random.Random(int(t * 31))
        flick = 0.85 + 0.3 * r.random()
        ln = (180 + 620 * power) * s * flick
        wd = 95 * s * (0.6 + 0.5 * power)
        layers = [(1.00, 1.00, (255, 120, 30, 110)),
                  (0.72, 0.66, (255, 190, 60, 170)),
                  (0.42, 0.38, (255, 245, 215, 235))]
        for lw, ll, col in layers:
            d.polygon([(cx - wd * lw, base), (cx + wd * lw, base),
                       (cx + wd * lw * 0.25, base + ln * ll),
                       (cx - wd * lw * 0.25, base + ln * ll)], fill=col)
    return spr


def draw_rocket(ov, t, ox, oy):
    cx, base, s = rocket_geometry(t)
    spr = rocket_sprite(t, s)
    tilt = smooth(T_STALL, T_CRASH, t) * 16          # noses over as it falls
    if tilt > 0.1:
        spr = spr.rotate(tilt, resample=Image.BILINEAR,
                         center=(SPR_W / 2, SPR_BASE - 380 * s))
    ov.paste(spr, (int(cx - SPR_W / 2) + ox, int(base - SPR_BASE) + oy), spr)
    return cx + ox, base - 760 * s + oy, s          # nose position


def draw_pad_glow(d, t, ox, oy):
    power = flame_power(t)
    if power <= 0.01 or arc(t) > 0.12:
        return
    cx, base, _ = rocket_geometry(t)
    gw = 420 * power
    d.ellipse([cx - gw + ox, base - 40 + oy, cx + gw + ox, base + 170 + oy],
              fill=(255, 170, 70, int(70 * power)))


def draw_chutes(d, t, nx, ny):
    """Golden parachutes leaving the vehicle at the top."""
    a0 = smooth(17.6, 18.3, t) * (1 - smooth(22.5, 23.5, t))
    if a0 <= 0.01:
        return
    tt = t - 17.6
    for dx, sway, ph in CHUTES:
        # leave from the vehicle body, clear of the caption block
        x = nx + dx * (60 + tt * 110)
        y = ny + 260 - 40 * tt + 14 * math.sin(t * sway + ph)
        a = int(255 * a0)
        d.pieslice([x - 46, y - 46, x + 46, y + 10], 180, 360,
                   fill=(255, 205, 90, a))
        for lx in (-40, 0, 40):
            d.line([(x + lx, y - 16), (x, y + 46)],
                   fill=(220, 180, 90, a), width=3)
        d.rectangle([x - 11, y + 44, x + 11, y + 64], fill=(255, 205, 90, a))


def draw_words(d, t, scroll, words, positions, color, mode):
    """mode 'hype': swarm on the pad, can't follow the pop up.
       mode 'trap': stream past as everything falls, then linger."""
    if mode == "hype":
        gate = (1.0 - smooth(0.05, 0.75, arc(t))) * smooth(0.3, 1.6, t)
        if t > T_APEX:
            gate = 0.0
    else:
        gate = smooth(T_STALL, T_STALL + 1.2, t) * (1 - smooth(T_CARD - 0.8,
                                                               T_CARD, t))
    if gate <= 0.01:
        return
    fall = smooth(T_STALL, T_CRASH, t)
    for word, (fx, fy, size, spd, ph) in zip(words, positions):
        x = fx * W + math.sin(t * spd + ph) * 26
        if mode == "hype":
            y = fy * H + math.cos(t * spd * 0.7 + ph) * 18 + scroll * (1.5 + spd)
        else:
            y = fy * H + (1 - fall) * H * 0.9 * (0.5 + 0.5 * spd)
        if not -60 < y < H + 60:
            continue
        pulse = 0.55 + 0.45 * math.sin(t * 1.8 + ph * 5)
        a = int(170 * gate * pulse)
        if a <= 4:
            continue
        f = font(FONT_BOLD, size)
        tw = d.textlength(word, font=f)
        d.text((x - tw / 2 + 3, y + 3), word, font=f, fill=(0, 0, 0, a // 2))
        d.text((x - tw / 2, y), word, font=f, fill=color + (a,))


def draw_ticker(d, t):
    vis = smooth(9.0, 9.8, t) * (1 - smooth(28.0, 28.8, t))
    if vis <= 0.01:
        return
    p = price(t)
    rising = p - price(t - 0.2) > 0.005      # flat-after-crash stays red
    col = (90, 230, 130) if rising else (240, 80, 80)
    arrow = "▲" if rising else "▼"
    pct = (p / IPO_PRICE - 1) * 100
    txt = f"$IPO  {p:.2f} {arrow} {pct:+.0f}%"
    f = font(FONT_BOLD, 54)
    tw = d.textlength(txt, font=f)
    x, y = (W - tw) / 2, H * 0.272
    a = int(255 * vis)
    d.text((x + 3, y + 3), txt, font=f, fill=(0, 0, 0, a // 2))
    d.text((x, y), txt, font=f, fill=col + (a,))


def draw_impact(d, t):
    if not T_CRASH <= t < T_CRASH + 0.8:
        return
    k = 1 - (t - T_CRASH) / 0.8
    cx, base, _ = rocket_geometry(T_CRASH)
    gw = 300 + 260 * (1 - k)
    d.ellipse([cx - gw, base - 30, cx + gw, base + 120],
              fill=(180, 160, 150, int(110 * k)))


def draw_caption(d, t):
    for t0, t1, text in CAPTIONS:
        a = smooth(t0, t0 + 0.6, t) * (1 - smooth(t1 - 0.6, t1, t))
        if a <= 0.01:
            continue
        lines = text.split("\n")
        size = 64
        f = font(FONT_BOLD, size)
        widest = max(d.textlength(ln, font=f) for ln in lines)
        if widest > W * 0.92:
            size = int(size * W * 0.92 / widest)
            f = font(FONT_BOLD, size)
        y = H * 0.150
        for ln in lines:
            tw = d.textlength(ln, font=f)
            x = (W - tw) / 2
            d.text((x + 4, y + 4), ln, font=f, fill=(0, 0, 0, int(200 * a)))
            d.text((x, y), ln, font=f, fill=(240, 242, 248, int(255 * a)))
            y += size * 1.34


def draw_countdown(d, t):
    if not (T_IGNITE <= t < T_LIFTOFF):
        return
    n = int(T_LIFTOFF - t) + 1
    frac = (T_LIFTOFF - t) % 1.0
    a = int(255 * smooth(0.0, 0.15, frac) * (0.4 + 0.6 * frac))
    f = font(FONT_BOLD, 220)
    s = str(n)
    tw = d.textlength(s, font=f)
    d.text(((W - tw) / 2 + 5, H * 0.36 + 5), s, font=f, fill=(0, 0, 0, a // 2))
    d.text(((W - tw) / 2, H * 0.36), s, font=f, fill=(120, 235, 150, a))


def draw_card(d, t):
    a = smooth(T_CARD, T_CARD + 1.0, t)
    if a <= 0.01:
        return
    d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * a)))
    f1 = font(FONT_BOLD, 110)
    f2 = font(FONT_REG, 42)
    for txt, f, y, col in [("DON'T BUY", f1, H * 0.40, (240, 242, 248)),
                           ("THE HYPE.", f1, H * 0.40 + 130, (240, 242, 248)),
                           ("not financial advice — do your own research",
                            f2, H * 0.40 + 320, (130, 135, 150))]:
        tw = d.textlength(txt, font=f)
        d.text(((W - tw) / 2, y), txt, font=f, fill=col + (int(255 * a),))


# ----------------------------------------------------------------- vignette

yy, xx = np.mgrid[0:H, 0:W]
_r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
VIGNETTE = (1.0 - 0.38 * np.clip(_r - 0.45, 0, 1) ** 2)[:, :, None]


def render_frame(i):
    t = i / FPS
    scroll = arc(t) * 1400
    arr = sky(t)
    star_layer = np.zeros((H, W), dtype=np.float64)
    draw_stars(star_layer, t, scroll)
    arr = np.maximum(arr, star_layer[:, :, None] * np.array([0.86, 0.9, 1.0]))
    img = Image.fromarray(arr.astype(np.uint8))

    # shake at liftoff and again on impact
    shake = (smooth(T_IGNITE + 1.5, T_LIFTOFF, t) * (1 - smooth(14, 18, t))
             + smooth(T_CRASH - 0.1, T_CRASH, t) * (1 - smooth(T_CRASH + 0.2,
                                                               T_CRASH + 0.9, t)))
    ox = int(rng.uniform(-8, 8) * clamp(shake))
    oy = int(rng.uniform(-8, 8) * clamp(shake))

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    draw_streaks(d, t)
    draw_pad(d, t, scroll, ox, oy)
    draw_pad_glow(d, t, ox, oy)
    nx, ny, _ = draw_rocket(ov, t, ox, oy)
    d = ImageDraw.Draw(ov)                 # paste invalidates the old draw
    draw_chutes(d, t, nx, ny)
    draw_impact(d, t)
    draw_words(d, t, scroll, HYPE, HYPE_POS, (90, 200, 120), "hype")
    draw_words(d, t, scroll, TRAP, TRAP_POS, (190, 40, 48), "trap")
    draw_ticker(d, t)
    draw_caption(d, t)
    draw_countdown(d, t)
    draw_card(d, t)
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    out = np.asarray(img, dtype=np.float64)
    grain = np.random.default_rng(i).normal(0, 3.5, (H, W, 1))
    out = np.clip(out * VIGNETTE + grain, 0, 255)
    fade = smooth(0, 0.8, t) * (1 - smooth(DUR - 0.8, DUR, t))
    return (out * fade).astype(np.uint8)


# -------------------------------------------------------------------- audio

def lowpass(x, cutoff_hz):
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1 / (1 + (freqs / cutoff_hz) ** 4)
    return np.fft.irfft(spec, len(x))


def make_audio(path):
    n = int(DUR * SR)
    t = np.arange(n) / SR
    r = np.random.default_rng(7)

    # Hype arpeggio, climbing and accelerating until the music stops
    step = np.floor(t * 4) % 8
    freq = 220 * 2 ** (step / 8 + t / 14)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    gate = 0.25 + 0.75 * (np.sin(2 * np.pi * 4 * t) > 0)
    arp = (np.sin(phase) + 0.3 * np.sin(2 * phase)) * gate
    arp *= np.interp(t, [0, 2, T_LIFTOFF, T_APEX - 0.3, T_APEX],
                     [0.02, 0.10, 0.13, 0.11, 0], right=0)

    # Engine rumble — dies abruptly at the apex
    e = np.interp(t, [T_IGNITE - 0.5, T_LIFTOFF, T_APEX, T_APEX + 0.3],
                  [0, 0.6, 0.6, 0], left=0, right=0)
    rumble = lowpass(r.normal(0, 1, n), 90) * 6.0 * e
    crackle = lowpass(r.normal(0, 1, n), 800) * 0.8 * np.maximum(e - 0.2, 0)

    # The fall: descending glide + rising wind
    fmask = np.interp(t, [T_STALL, T_STALL + 0.5, T_CRASH, T_CRASH + 0.1],
                      [0, 1, 1, 0], left=0, right=0)
    gl_f = np.interp(t, [T_STALL, T_CRASH], [520, 52])
    glide = np.sin(2 * np.pi * np.cumsum(gl_f) / SR) * 0.16 * fmask
    wind = lowpass(r.normal(0, 1, n), 1600) * 1.1 * fmask \
        * np.interp(t, [T_STALL, T_CRASH], [0.1, 1], left=0, right=0)

    # Impact thud
    tt = np.maximum(t - T_CRASH, 0)
    thud = np.exp(-tt * 6) * np.sin(2 * np.pi * 52 * tt) * 0.6 * (t >= T_CRASH)
    thud += lowpass(r.normal(0, 1, n), 200) * np.exp(-tt * 9) * (t >= T_CRASH)

    # Somber A-minor pad for the aftermath
    pad = (np.sin(2 * np.pi * 220 * t) + 0.6 * np.sin(2 * np.pi * 261.63 * t)
           + 0.5 * np.sin(2 * np.pi * 329.63 * t))
    pad *= 0.075 * np.interp(t, [T_CRASH + 0.8, T_CRASH + 3.5], [0, 1],
                             left=0, right=1)
    pad *= 0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * t)

    mix = arp + rumble + crackle + glide + wind + thud + pad
    mix *= np.interp(t, [0, 1, DUR - 1.5, DUR], [0, 1, 1, 0])
    mix = np.tanh(mix * 1.2) * 0.85
    pcm = (mix * 32767).astype(np.int16)
    stereo = np.column_stack([pcm, np.roll(pcm, 220)]).ravel()

    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


# ------------------------------------------------------------------- render

def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "dont_buy_the_hype.mp4"
    audio_path = "/tmp/ipo_audio.wav"
    make_audio(audio_path)

    cmd = ["ffmpeg", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-",
           "-i", audio_path,
           "-vf", "hqdn3d=1.5:1:3:2",
           "-c:v", "libx264", "-preset", "medium", "-crf", "24",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-shortest", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)

    for i in range(N_FRAMES):
        proc.stdin.write(render_frame(i).tobytes())
        if i % 120 == 0:
            print(f"  frame {i}/{N_FRAMES} ({i / FPS:4.1f}s)", flush=True)

    proc.stdin.close()
    proc.wait()
    print(f"done -> {out_path}")


if __name__ == "__main__":
    main()
