#!/usr/bin/env python3
"""
ABOVE THE NOISE — a 9:16 social video, generated entirely in Python.

Concept (my spin): being the most hated man on the internet, told as a
launch. On the pad, the screen swarms with the things people say. The
engines light. The higher the rocket climbs, the more the words physically
fall away — hate has weight, and it can't reach orbit. Up in the silence,
only the work remains. Build anyway.

Everything is procedural: starfield, launch tower, Starship-style vehicle,
exhaust plume, camera shake, film grain, captions, and a synthesized
rumble/drone soundtrack. Frames are piped raw to ffmpeg (libx264 + aac).

Usage:  python3 spacex_video.py [out.mp4]
Needs:  numpy, pillow, ffmpeg on PATH.
"""

import math
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
DUR = 34.0
N_FRAMES = int(DUR * FPS)
SR = 44100

# Timeline (seconds)
T_IGNITE = 7.0      # engine glow builds, countdown
T_LIFTOFF = 10.0    # vehicle leaves the pad
T_SPACE = 22.0      # plume dies, coast in silence
T_CARD = 30.0       # final title card

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
FONT_REG = f"{FONT_DIR}/DejaVuSans.ttf"

rng = random.Random(42)

# ---------------------------------------------------------------- utilities

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def smooth(a, b, t):
    """Smoothstep of t between edges a..b."""
    if a == b:
        return 1.0 if t >= b else 0.0
    x = clamp((t - a) / (b - a))
    return x * x * (3 - 2 * x)


def font(path, size):
    return ImageFont.truetype(path, size)


# ------------------------------------------------------------- world pieces

STARS = [(rng.random(), rng.random(), rng.random()) for _ in range(420)]

HATE = [
    "FRAUD", "HE WILL FAIL", "OVERRATED", "IT'LL BLOW UP AGAIN",
    "DELUSIONAL", "NOBODY ASKED", "SELL IT ALL", "WORST PERSON ALIVE",
    "GIVE UP", "JOKE", "WASTE OF MONEY", "GO AWAY",
    "CRINGE", "LIAR", "HAS-BEEN", "IT WILL NEVER FLY",
    "RICH CLOWN", "WHO HURT YOU", "RATIO", "BLOCKED",
]
# (x frac, base y frac, font size, drift speed, phase)
HATE_POS = []
for i, _ in enumerate(HATE):
    side = -1 if i % 2 == 0 else 1
    x = 0.5 + side * (0.16 + 0.30 * rng.random())
    y = 0.08 + 0.78 * rng.random()
    HATE_POS.append((x, y, rng.randint(34, 72), 0.4 + rng.random(),
                     rng.random() * math.tau))

CAPTIONS = [
    (1.5, 6.2, "Imagine a hundred million\npeople hoping you fail."),
    (6.6, 9.6, "They cheered when the\nearly ones exploded."),
    (12.0, 16.0, "But hate has never\nreached orbit."),
    (16.6, 21.4, "Engines don't read\nthe comments."),
    (23.5, 29.0, "Up here it's quiet.\nOnly the work remains."),
]


def altitude(t):
    """0 on the pad -> 1 in space, eased acceleration after liftoff."""
    if t <= T_LIFTOFF:
        return 0.0
    x = (t - T_LIFTOFF) / (T_SPACE - T_LIFTOFF)
    return clamp(x * x * (3 - 2 * x))


def sky(t):
    """Vertical gradient background as float array (H, W, 3)."""
    alt = altitude(t)
    # Pad: deep navy with sodium-light haze at the horizon. Space: black.
    top = np.array([4, 5, 14]) * (1 - alt) + np.array([0, 0, 2]) * alt
    bot = np.array([26, 22, 38]) * (1 - alt) + np.array([2, 2, 6]) * alt
    g = np.linspace(0, 1, H)[:, None, None]
    img = top[None, None, :] * (1 - g) + bot[None, None, :] * g
    return np.repeat(img, W, axis=1)


def draw_stars(arr, t, scroll):
    alt = altitude(t)
    vis = 0.35 + 0.65 * alt          # stars brighten away from city glow
    for sx, sy, ph in STARS:
        x = int(sx * W)
        y = int((sy * H + scroll * (0.15 + 0.5 * ph)) % H)
        tw = 0.6 + 0.4 * math.sin(t * 2.2 + ph * 9)
        b = int(255 * vis * tw * (0.3 + 0.7 * ph))
        arr[y:y + 2, x:x + 2] = np.maximum(arr[y:y + 2, x:x + 2], b)


def draw_streaks(d, t, speed):
    """Velocity star-streaks during ascent."""
    if speed <= 0.05:
        return
    n = int(40 * speed)
    r = random.Random(int(t * 7))
    for _ in range(n):
        x = r.randrange(W)
        y = r.randrange(H)
        ln = int(12 + 90 * speed * r.random())
        a = int(90 * speed * r.random())
        d.line([(x, y), (x, y + ln)], fill=(200, 210, 255, a), width=2)


def draw_pad(d, t, scroll, ox, oy):
    """Launch tower + ground; slides off-screen as we climb."""
    gy = int(H * 0.86 + scroll) + oy
    if gy > H + 400:
        return
    d.rectangle([0, gy, W, H + 600], fill=(8, 7, 10, 255))
    # Tower with chopstick arms
    tx = int(W * 0.30) + ox
    d.rectangle([tx, gy - 950, tx + 46, gy], fill=(14, 13, 18, 255))
    for i in range(9):
        yy = gy - 90 - i * 100
        d.line([(tx, yy), (tx + 46, yy - 36)], fill=(20, 19, 26, 255), width=7)
    d.line([(tx + 46, gy - 760), (tx + 210, gy - 740)],
           fill=(16, 15, 21, 255), width=16)
    # Floodlights
    for fx in (0.12, 0.85):
        lx, ly = int(W * fx) + ox, gy - 26
        glow = 0.5 + 0.5 * math.sin(t * 3 + fx * 10)
        d.ellipse([lx - 60, ly - 18, lx + 60, ly + 18],
                  fill=(255, 220, 160, int(38 * glow)))
        d.ellipse([lx - 8, ly - 8, lx + 8, ly + 8], fill=(255, 235, 200, 230))


def rocket_geometry(t):
    """Screen-space center x, base y, scale of the vehicle."""
    alt = altitude(t)
    cx = W * 0.5
    base = H * 0.84 - alt * H * 0.30          # eases up toward center
    if t > T_SPACE:                            # gentle coast drift
        base += (t - T_SPACE) * 14
    scale = 1.0 - 0.25 * alt
    return cx, base, scale


def draw_rocket(d, t, ox, oy):
    cx, base, s = rocket_geometry(t)
    cx += ox
    base += oy
    bw = 110 * s          # body half-width
    bh = 760 * s          # body height
    top = base - bh
    body = (208, 211, 218)
    shade = (148, 152, 162)
    # Stainless body, simple side shading
    d.rectangle([cx - bw, top + bw, cx + bw, base], fill=body)
    d.rectangle([cx + bw * 0.35, top + bw, cx + bw, base], fill=shade)
    # Nose cone
    d.pieslice([cx - bw, top, cx + bw, top + bw * 2.4], 180, 360, fill=body)
    # Forward + aft flaps
    fl = (120, 124, 134)
    d.polygon([(cx - bw, top + bw * 1.2), (cx - bw - 52 * s, top + bw * 2.6),
               (cx - bw, top + bw * 3.0)], fill=fl)
    d.polygon([(cx + bw, top + bw * 1.2), (cx + bw + 52 * s, top + bw * 2.6),
               (cx + bw, top + bw * 3.0)], fill=fl)
    d.polygon([(cx - bw, base - 240 * s), (cx - bw - 84 * s, base - 20 * s),
               (cx - bw, base)], fill=fl)
    d.polygon([(cx + bw, base - 240 * s), (cx + bw + 84 * s, base - 20 * s),
               (cx + bw, base)], fill=fl)
    # Tiny window of the one human aboard
    d.ellipse([cx - 14 * s, top + bw * 1.5, cx + 14 * s, top + bw * 1.5 + 28 * s],
              fill=(40, 60, 90))
    return cx, base, s


def draw_flame(d, t, cx, base, s):
    """Layered flickering exhaust plume."""
    if t < T_IGNITE:
        return
    build = smooth(T_IGNITE, T_LIFTOFF, t)
    die = 1.0 - smooth(T_SPACE - 1.0, T_SPACE + 0.8, t)
    power = build * die
    if power <= 0.01:
        return
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
    # Pad-level blast glow before/at liftoff
    gw = 420 * power
    if altitude(t) < 0.12:
        d.ellipse([cx - gw, base - 40, cx + gw, base + 170],
                  fill=(255, 170, 70, int(70 * power)))


def draw_hate(layer, d, t, scroll):
    """The comment storm. It cannot follow the vehicle up."""
    alt = altitude(t)
    fade_world = 1.0 - smooth(0.05, 0.75, alt)     # words die with altitude
    intro = smooth(0.3, 1.6, t)
    if fade_world <= 0.01:
        return
    for word, (fx, fy, size, spd, ph) in zip(HATE, HATE_POS):
        x = fx * W + math.sin(t * spd + ph) * 26
        y = fy * H + math.cos(t * spd * 0.7 + ph) * 18 + scroll * (1.5 + spd)
        if y > H + 60:
            continue
        pulse = 0.55 + 0.45 * math.sin(t * 1.8 + ph * 5)
        a = int(165 * intro * fade_world * pulse)
        if a <= 4:
            continue
        f = font(FONT_BOLD, size)
        tw = d.textlength(word, font=f)
        d.text((x - tw / 2 + 3, y + 3), word, font=f, fill=(0, 0, 0, a // 2))
        d.text((x - tw / 2, y), word, font=f, fill=(190, 40, 48, a))


def draw_earth(d, t):
    """Blue limb of Earth rising into frame during the coast."""
    vis = smooth(T_SPACE - 0.5, T_SPACE + 3.0, t)
    if vis <= 0.01:
        return
    r = W * 2.2
    cy = H + r - vis * 360
    for rr, col, a in [(r + 90, (90, 160, 255), 26), (r + 40, (120, 185, 255), 48),
                       (r, (38, 90, 170), 235)]:
        d.ellipse([W / 2 - rr, cy - rr, W / 2 + rr, cy + rr],
                  fill=col + (int(a * vis),))
    d.arc([W / 2 - r, cy - r, W / 2 + r, cy + r], 180, 360,
          fill=(200, 230, 255, int(120 * vis)), width=6)


def draw_caption(d, t):
    for t0, t1, text in CAPTIONS:
        a = smooth(t0, t0 + 0.6, t) * (1 - smooth(t1 - 0.6, t1, t))
        if a <= 0.01:
            continue
        lines = text.split("\n")
        size = 64
        f = font(FONT_BOLD, size)
        widest = max(d.textlength(ln, font=f) for ln in lines)
        if widest > W * 0.92:                  # shrink to fit the frame
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
    d.text(((W - tw) / 2, H * 0.36), s, font=f, fill=(255, 200, 120, a))


def draw_card(d, t):
    a = smooth(T_CARD, T_CARD + 1.0, t)
    if a <= 0.01:
        return
    d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * a)))
    f1 = font(FONT_BOLD, 110)
    f2 = font(FONT_REG, 46)
    for txt, f, y, col in [("BUILD", f1, H * 0.40, (240, 242, 248)),
                           ("ANYWAY.", f1, H * 0.40 + 130, (240, 242, 248)),
                           ("per aspera ad astra", f2, H * 0.40 + 320,
                            (130, 135, 150))]:
        tw = d.textlength(txt, font=f)
        d.text(((W - tw) / 2, y), txt, font=f, fill=col + (int(255 * a),))


# ----------------------------------------------------------------- vignette

yy, xx = np.mgrid[0:H, 0:W]
_r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
VIGNETTE = (1.0 - 0.38 * np.clip(_r - 0.45, 0, 1) ** 2)[:, :, None]


def render_frame(i, scroll):
    t = i / FPS
    arr = sky(t)
    star_layer = np.zeros((H, W), dtype=np.float64)
    draw_stars(star_layer, t, scroll)
    arr = np.maximum(arr, star_layer[:, :, None] * np.array([0.86, 0.9, 1.0]))
    img = Image.fromarray(arr.astype(np.uint8))

    # camera shake around liftoff
    shake = smooth(T_IGNITE + 1.5, T_LIFTOFF, t) * (1 - smooth(14.0, 18.0, t))
    ox = int(rng.uniform(-8, 8) * shake)
    oy = int(rng.uniform(-8, 8) * shake)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    speed = altitude(t) * (1 - smooth(T_SPACE - 1, T_SPACE + 2, t) * 0.85)
    draw_streaks(d, t, speed)
    draw_earth(d, t)
    draw_pad(d, t, scroll, ox, oy)
    flame_d = ImageDraw.Draw(ov)
    cx, base, s = draw_rocket(flame_d, t, ox, oy)
    draw_flame(flame_d, t, cx, base, s)
    draw_hate(ov, d, t, scroll)
    draw_caption(d, t)
    draw_countdown(d, t)
    draw_card(d, t)
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    out = np.asarray(img, dtype=np.float64)
    grain = np.random.default_rng(i).normal(0, 3.5, (H, W, 1))
    out = np.clip(out * VIGNETTE + grain, 0, 255)
    # global fade in/out
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

    # Engine rumble: lowpassed noise with the launch envelope
    e = (0.08
         + 0.55 * np.interp(t, [T_IGNITE - 0.5, T_LIFTOFF], [0, 1],
                            left=0, right=1)
         * np.interp(t, [T_SPACE - 2, T_SPACE + 2], [1, 0.05],
                     left=1, right=0.05))
    rumble = lowpass(r.normal(0, 1, n), 90) * 6.0 * e
    crackle = lowpass(r.normal(0, 1, n), 800) * 0.8 * np.maximum(e - 0.2, 0)

    # Drone: dread on the pad resolving to a calm space pad
    dread = np.sin(2 * np.pi * 55 * t) * 0.22 * np.interp(
        t, [0, T_LIFTOFF, T_SPACE], [1, 1, 0], right=0)
    calm = (np.sin(2 * np.pi * 220 * t) + 0.6 * np.sin(2 * np.pi * 277.18 * t)
            + 0.5 * np.sin(2 * np.pi * 329.63 * t))
    calm *= 0.085 * np.interp(t, [T_SPACE - 1, T_SPACE + 4], [0, 1],
                              left=0, right=1)
    calm *= 0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * t)

    mix = rumble + crackle + dread + calm
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
    out_path = sys.argv[1] if len(sys.argv) > 1 else "above_the_noise.mp4"
    audio_path = "/tmp/atn_audio.wav"
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

    scroll = 0.0
    for i in range(N_FRAMES):
        t = i / FPS
        scroll += altitude(t) * 2200 / FPS   # world falls away as we climb
        proc.stdin.write(render_frame(i, scroll).tobytes())
        if i % 120 == 0:
            print(f"  frame {i}/{N_FRAMES} ({t:4.1f}s)", flush=True)

    proc.stdin.close()
    proc.wait()
    print(f"done -> {out_path}")


if __name__ == "__main__":
    main()
