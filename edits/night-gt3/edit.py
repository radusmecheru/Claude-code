#!/usr/bin/env python3
"""Four night edits of the blue GT3 + black GT3 RS footage (IMG_0854-0893, 07162), each in a learned style
on that style's own sound.

  e1  Night ritual walkaround      (Style C, ref4 reggaeton 112 BPM, 13.7 s)
  e2  Red night glitch-cut         (Style F, r3 phonk 129 BPM, 14.3 s)
  e3  Light-bar wake-up -> drop    (Style H, r5 161 BPM, 11.45 s)
  e4  Glide + roll, early cuts     (Styles J + I, r7 129 BPM, 15.1 s)

Shots are given in ORIGINAL clip time. 30 fps clips were prepped to 60 fps with tools/prep60.sh into
work/ed3/prep (offset = prep start). Footage analysis (sharpness / motion / junk ranges) is in
work/ed3/ana/metrics.txt; only ranges with low motion blur and the cars framed whole are used, and no
range repeats inside an edit (checked). No people are in the footage (YuNet hits were wheels/flowers).

  python3 edits/night-gt3/edit.py work/ed3 e1 [--target-mb 29] [--check]
"""
import argparse
import functools
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from carfx import camera  # noqa: E402
import editkit as ek  # noqa: E402
import looks  # noqa: E402
import transitions as tr  # noqa: E402

# name: (file in work dir, original time of its first frame, available until (original time), audio source)
SRC = {
    '0855': ('src/IMG_0855.mov', 0.0, 5.0, 'src/IMG_0855.mov'),
    '0856': ('src/IMG_0856.mov', 0.0, 2.45, 'src/IMG_0856.mov'),
    '0858': ('src/IMG_0858.mov', 0.0, 3.85, 'src/IMG_0858.mov'),
    '0859': ('src/IMG_0859.mov', 0.0, 6.6, 'src/IMG_0859.mov'),
    '0860': ('src/IMG_0860.mov', 0.0, 4.4, 'src/IMG_0860.mov'),
    '0893': ('src/IMG_0893.mov', 0.0, 7.0, 'src/IMG_0893.mov'),
    '07162': ('src/07162.mp4', 0.0, 15.0, 'src/07162.mp4'),
    '0862': ('prep/0862.mkv', 0.0, 4.06, 'src/IMG_0862.mov'),
    '0866': ('prep/0866.mkv', 0.0, 3.6, 'src/IMG_0866.mov'),
    '0867': ('prep/0867.mkv', 1.5, 5.1, 'src/IMG_0867.mov'),
    '0868': ('prep/0868.mkv', 2.3, 7.1, 'src/IMG_0868.mov'),
    '0873a': ('prep/0873a.mkv', 1.7, 4.2, 'src/IMG_0873.mov'),
    '0873b': ('prep/0873b.mkv', 9.2, 10.3, 'src/IMG_0873.mov'),
}
# 07162 is a compilation; never let a shot cross one of its internal cuts.
CUTS_07162 = [2.967, 4.367, 6.067, 7.433, 8.9, 10.2, 12.2, 13.433, 15.033]
MASKS = {'0893': ('masks/0893.npy', 2.8), '0866': ('masks/0866.npy', 2.3)}

SONGS = {'e1': '../ref4/song.wav', 'e2': '../refs/r3/song.wav', 'e3': '../refs/r5/song.wav', 'e4': '../refs/r7/song.wav'}

BEATS = {
    'e1': [0.12, 0.65, 1.14, 1.63, 2.11, 2.6, 3.11, 3.67, 4.23, 4.78, 5.32, 5.87, 6.39, 6.94, 7.5, 8.03, 8.57,
           9.06, 9.54, 10.05, 10.5, 11.03, 11.56, 12.12, 12.65, 13.21],
    'e2': [0.49, 0.95, 1.42, 1.88, 2.39, 2.88, 3.39, 3.88, 4.34, 4.78, 5.27, 5.76, 6.25, 6.66, 7.11, 7.55, 8.01,
           8.48, 8.94, 9.4, 9.87, 10.33, 10.77, 11.17, 11.59, 12.0, 12.47, 12.93, 13.4, 13.86, 14.33],
    'e3': [0.33, 0.7, 1.07, 1.44, 1.81, 2.21, 2.58, 2.97, 3.34, 3.72, 4.09, 4.44, 4.81, 5.18, 5.55, 5.92, 6.29,
           6.66, 7.04, 7.41, 7.8, 8.17, 8.57, 8.94, 9.33, 9.71, 10.08, 10.45, 10.84, 11.22],
    'e4': [0.07, 0.49, 0.93, 1.3, 1.67, 2.14, 2.6, 3.07, 3.55, 3.99, 4.46, 4.95, 5.41, 5.85, 6.34, 6.8, 7.27,
           7.73, 8.2, 8.66, 9.15, 9.61, 10.08, 10.57, 11.03, 11.49, 11.96, 12.42, 12.89, 13.35, 13.82, 14.28, 14.77],
}
# Zoom punches only on the strong hits (bass), never shake.
HITS = {
    'e1': [9.64, 10.72, 11.26, 11.82, 12.35, 12.9, 13.44],
    'e2': [6.42, 8.835, 9.4, 9.87, 10.33, 11.297, 12.0, 12.47, 12.93, 13.653],
    'e3': [5.91, 7.05, 7.81, 8.95, 10.09, 10.84],
    'e4': [2.14, 2.6, 3.07, 3.99, 4.95, 5.85, 6.8, 7.73, 8.66, 9.61, 10.57, 11.49, 12.42, 13.35, 13.82, 14.77],
}
END = {'e1': 13.72, 'e2': 14.33, 'e3': 11.45, 'e4': 15.1}
EARLY = {'e4': 1}  # frames each cut lands before the beat (Style J)

# (song start, song end, source, in-point (orig clip time), fx, clip-audio gain)
SHOTS = {
    'e1': [
        (0.00, 1.14, '07162', 10.25, {'fadein'}, 0),
        (1.14, 2.11, '0856', 1.20, {'jump'}, 0),
        (2.11, 3.11, '0855', 1.30, set(), 0),
        (3.11, 4.23, '0859', 2.80, {'jump'}, 0),
        (4.23, 5.32, '0860', 2.45, set(), 0),
        (5.32, 6.39, '0893', 0.85, {'glow'}, 0),
        (6.39, 7.50, '0862', 1.00, {'glow'}, 0),
        (7.50, 8.57, '07162', 7.45, set(), 0),
        (8.57, 9.54, '0867', 1.60, set(), 0),
        (9.54, 10.50, '07162', 6.10, {'glow'}, 0),
        (10.50, 11.56, '0868', 5.95, set(), 0),
        (11.56, 12.65, '0866', 2.00, {'glow', 'jump'}, 0),
        (12.65, 13.72, '07162', 8.95, {'push', 'fadeout'}, 0),
    ],
    'e2': [
        (0.00, 0.95, '0859', 1.60, {'blink'}, 0),
        (0.95, 1.88, '0855', 3.00, {'blink'}, 0),
        (1.88, 2.39, '07162', 3.10, {'blink'}, 0),
        (2.39, 4.78, '0862', 0.00, {'push', 'dark'}, 0.5),
        (4.78, 6.42, '07162', 10.30, {'dark'}, 0.3),
        (6.42, 7.11, '0893', 0.85, {'flashin'}, 0),
        (7.11, 7.55, '0856', 1.30, set(), 0),
        (7.55, 8.48, '0858', 1.50, set(), 0),
        (8.48, 8.835, '0893', 3.00, {'silhouette'}, 0),
        (8.835, 9.87, '07162', 6.10, {'whipin'}, 0),
        (9.87, 10.77, '0855', 1.20, set(), 0),
        (10.77, 11.297, '0866', 2.40, {'xray'}, 0),
        (11.297, 12.00, '0873a', 3.30, {'arrive'}, 0),
        (12.00, 12.93, '0867', 3.00, set(), 0),
        (12.93, 13.653, '0859', 4.60, {'glitch'}, 0),
        (13.653, 14.33, '07162', 9.00, {'final'}, 0),
    ],
    'e3': [
        (0.00, 2.97, '0862', 0.00, {'fadein', 'push'}, 0.55),
        (2.97, 4.81, '07162', 10.25, set(), 0.3),
        (4.81, 5.91, '0866', 0.00, set(), 0.3),
        (5.91, 7.05, '0868', 2.40, {'arrive'}, 0),
        (7.05, 7.81, '0893', 0.90, {'arrive', 'flash'}, 0),
        (7.81, 8.95, '0859', 3.60, {'arrive'}, 0),
        (8.95, 10.09, '0856', 1.25, {'arrive'}, 0),
        (10.09, 10.84, '0867', 4.30, {'arrive'}, 0),
        (10.84, 11.45, '07162', 6.20, {'final'}, 0),
    ],
    'e4': [
        (0.00, 2.14, '0893', 0.85, {'fadein', 'pushfast', 'zoomout'}, 0.4),
        (2.14, 3.07, '0873a', 1.75, {'zoomin'}, 0),
        (3.07, 3.99, '0868', 2.40, set(), 0),
        (3.99, 4.95, '0860', 2.60, set(), 0),
        (4.95, 5.85, '0858', 2.30, set(), 0),
        (5.85, 6.80, '0893', 3.20, set(), 0),
        (6.80, 7.73, '0873b', 9.30, set(), 0),
        (7.73, 8.66, '0868', 4.30, set(), 0),
        (8.66, 9.61, '0868', 6.00, {'roll'}, 0),
        (9.61, 10.57, '0893', 4.30, set(), 0),
        (10.57, 11.49, '0859', 4.50, set(), 0),
        (11.49, 12.42, '0862', 2.00, set(), 0),
        (12.42, 13.35, '07162', 8.95, {'punchout'}, 0),
        (13.35, 13.82, '0866', 3.00, set(), 0),
        (13.82, 15.10, '07162', 6.10, {'final2'}, 0),
    ],
}

D = None
V = None


def look(img):
    if V == 'e1':
        return looks.night_ritual(img, strength=0.6)
    if V == 'e2':
        return looks.night_ritual(img, strength=0.75)
    if V == 'e3':
        return looks.clean_night(img)
    return looks.punchy(img)


def env(t, times, decay):
    since = min((t - b for b in times if b <= t + 1e-6), default=99)
    return math.exp(-max(since, 0) * decay)


def timeline(v):
    e = EARLY.get(v, 0) / ek.FPS
    shots = SHOTS[v]
    out = []
    for i, s in enumerate(shots):
        a = s[0] - (e if i else 0)
        b = s[1] - e if i + 1 < len(shots) else s[1]
        out.append((round(a, 4), round(b, 4), s))
    return out


def source_times(v, s0, at, n, fx):
    """Original clip time of each output frame; 'jump' skips 0.2 s at every beat inside the shot."""
    inner = [b for b in BEATS[v] if s0 + 0.05 < b < s0 + n / ek.FPS - 0.05]
    out = []
    for i in range(n):
        t = s0 + i / ek.FPS
        skips = sum(1 for b in inner if b <= t) if 'jump' in fx else 0
        out.append(at + i / ek.FPS + 0.2 * skips)
    return out


def check(v):
    used = {}
    prev = 0.0
    for s0, s1, (_, _, src, at, fx, _) in timeline(v):
        assert abs(s0 - prev) < 1e-3, f'{v}: gap at {s0}'
        prev = s1
        n = ek.fr(s1) - ek.fr(s0)
        times = source_times(v, s0, at, n, fx)
        a, b = times[0], times[-1] + 1 / ek.FPS
        _, first, last, _ = SRC[src]
        assert a >= first - 1e-3 and b <= last + 0.025, f'{v}: {src}@{at} needs {a:.2f}-{b:.2f}, has {first}-{last}'
        if src == '07162':
            assert not any(a + 0.02 < c < b - 0.02 for c in CUTS_07162), f'{v}: 07162@{at} crosses a cut'
        key = src.rstrip('ab')
        for u0, u1 in used.get(key, []):
            assert a >= u1 - 0.02 or b <= u0 + 0.02, f'{v}: {src}@{at} repeats footage'
        used.setdefault(key, []).append((a, b))
    assert abs(prev - END[v]) < 1e-3


def render(item, out, t0, n):
    s0, s1, (_, _, src, at, fx, _) = item
    path, first, _, _ = SRC[src]
    times = source_times(V, s0, at, n, fx)
    span = times[-1] - at + 1 / ek.FPS
    raw = ek.read(os.path.join(D, path), at - first, int(round(span * ek.FPS)) + 1)
    mk = MASKS.get(src)
    masks = ek.Masks(os.path.join(D, mk[0]), mk[1]) if mk and fx & {'silhouette', 'xray'} else None
    beats, hits = BEATS[V], HITS[V]
    last_angle = None
    for i, ct in enumerate(times):
        t = t0 + i / ek.FPS
        k = t - s0
        p = i / max(1, n - 1)
        img = raw[min(int(round((ct - at) * ek.FPS)), len(raw) - 1)].astype(np.float32)
        if 'push' in fx:
            img = camera(img, zoom=1.0 + 0.06 * p ** 1.3)
        if 'pushfast' in fx:
            img = camera(img, zoom=1.0 + 0.03 * p + 0.12 * p ** 6)
        if 'punchout' in fx:  # Style J pull-back: one jump per beat, tighter -> wider
            jumps = sum(1 for b in beats if s0 + 0.05 < b <= t)
            img = camera(img, zoom=[1.18, 1.08, 1.0][min(jumps, 2)])
        if 'roll' in fx:
            ang = -10 * (1 - (1 - min(1.0, i / 20)) ** 3)
            img = tr.roll(img, ang, last_angle)
            last_angle = ang
        if 'zoomout' in fx and i >= n - 8:
            img = tr.zoom_blur(img, (i - (n - 8)) / 7, out=True)
        if 'zoomin' in fx and i < 6:
            img = tr.zoom_blur(img, i / 5, out=False)
        if 'whipin' in fx and i < 5:
            img = tr.whip(img, -(1 - i / 5), direction=1)
        if 'arrive' in fx:
            img = tr.arrive(img, max(0.0, 1 - i / 6))
        if masks is not None:
            m = masks(ct)
            if 'silhouette' in fx and (i // 2) % 2 == 0:
                img = tr.silhouette(img, m, 'car')
            if 'xray' in fx and k > n / ek.FPS - 0.3:
                img = tr.silhouette(img, m, 'xray')
        img = look(img)
        if 'dark' in fx:
            img *= 0.7
        if 'glow' in fx:
            img = looks.lamp_glow(img, 0.3 + 0.9 * env(t, beats, 10))
        if V == 'e1' and t > 1.0:  # ritual exposure pump on every beat
            img = img * (1 + 0.22 * env(t, beats, 12))
        if 'blink' in fx:
            img = tr.blink(img, t, [b for b in beats if b < 2.39], hold=0.2)
        if 'glitch' in fx and k > n / ek.FPS - 0.28:
            img = tr.box_glitch(img, i, seed=7)
        if 'flashin' in fx:
            img = tr.flash_in(img, 0.85 * math.exp(-k * 14))
        if 'flash' in fx:
            img = tr.flash(img, math.exp(-k * 18), gain=0.25)
        if 'fadein' in fx:
            img *= min(1.0, k / 0.4)
        if 'fadeout' in fx:
            img *= max(0.0, min(1.0, (s1 - t) / 0.4))
        if 'final' in fx:
            img = tr.flash_in(img, 0.8 * math.exp(-k * 9))
            if k > 0.25:
                img = tr.fade(img, (k - 0.25) / max(0.1, (s1 - s0) - 0.3))
        if 'final2' in fx:
            hit = 14.77
            if t >= hit:
                img = tr.flash_in(img, 0.8 * math.exp(-(t - hit) * 9))
                img = tr.fade(img, (t - hit - 0.08) / 0.22) if t > hit + 0.08 else img
        e = env(t + EARLY.get(V, 0) / ek.FPS, hits, 11)
        img = camera(img, zoom=1 + 0.04 * e) if e > 0.01 else img
        out.write(img)


def main():
    global D, V
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('variant', choices=list(SHOTS))
    ap.add_argument('--target-mb', type=float)
    ap.add_argument('--seg', action='append')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    D, V = a.workdir, a.variant
    check(V)
    if a.check:
        print(f'{V}: {len(SHOTS[V])} shots OK')
        return
    items = timeline(V)
    segs = {f'{V}_{i:02d}': (it[0], it[1]) for i, it in enumerate(items)}
    fns = {f'{V}_{i:02d}': functools.partial(render, it) for i, it in enumerate(items)}
    extra = [{'path': os.path.join(D, SRC[src][3]), 'src_in': at, 'at': s0, 'dur': s1 - s0, 'gain': g, 'duck': False}
             for s0, s1, (_, _, src, at, fx, g) in items if g]
    ek.run(D, segs, fns, os.path.join(D, SONGS[V]), END[V], f'night_{V}', only=a.seg, target_mb=a.target_mb,
           grade='unsharp=5:5:0.3:5:5:0,format=yuv420p', extra_audio=extra)


if __name__ == '__main__':
    main()
