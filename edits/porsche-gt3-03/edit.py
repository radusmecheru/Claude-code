#!/usr/bin/env python3
"""Porsche 911 GT3 - three full-song variants (21.95 s each) with different hooks.

Rules from the user: one full-screen 9:16 picture per frame, the car fully in frame (only vertical
sources - no crops of the landscape clip), 60 fps, the whole sound, engine noise audible on fly-bys,
mostly static (locked-off) shots, and the driver's face never visible (tools/privacy.py, *_faces.json).

Sources in the work dir (prepped with tools/prep60.sh: 1080x1920, RIFE 60 fps), with the original
clip + in-point used for engine audio:
  A  2079 @ 5.00 approach from the horizon   B  2077 @15.30 fly-by        C  2078 @ 8.45 sunset fly-by
  D  2079 @10.45 face to the lens            E  2079 @13.00 parked hero   P1 2077 @12.00 approach
  P2 2077 @16.55 driving away                P3 2078 @ 3.00 pan + approach P4 2078 @ 9.85 away (sunset)
  P5 2079 @11.70 settling, 3/4 front         P6 2079 @14.80 parked hero (continues E)
  c2 = IMG_2084 (vertical 60 fps, front 3/4 at sunset, swing to the sun)
Masks (tools/masks.py on the prepped files): E, P5, P6, A (from 3.5 s), c2 (0-3.6 s).

  python3 edits/porsche-gt3-03/edit.py work/ed2 v1|v2|v3 [--target-mb 29]
"""
import argparse
import functools
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from carfx import camera, hex_bgr, neon_layer, trace_light  # noqa: E402
import editkit as ek  # noqa: E402
from privacy import FaceTrack  # noqa: E402

BLUE = hex_bgr('#2A8CFF')
WHITE = np.array([255, 255, 255], np.float32)
HITS = [5.383, 6.56, 7.883, 9.217, 10.70, 11.90, 13.22, 14.55, 16.04, 17.23, 18.66, 19.04, 19.89, 20.32, 21.37]
END = 21.95
FOOTAGE = '../dl1/files'

# name: (file, length s, original clip for audio, original in-point, mask file, mask t0)
SRC = {
    'A': ('A.mkv', 5.45, 'IMG_2079.mov', 5.00, 'A_mask.npy', 3.5),
    'B': ('B.mkv', 1.25, 'IMG_2077.mov', 15.30, None, 0),
    'C': ('C.mkv', 1.40, 'IMG_2078.mov', 8.45, None, 0),
    'D': ('D.mkv', 1.25, 'IMG_2079.mov', 10.45, None, 0),
    'E': ('E.mkv', 1.80, 'IMG_2079.mov', 13.00, 'E_mask.npy', 0),
    'P1': ('P1.mkv', 3.30, 'IMG_2077.mov', 12.00, None, 0),
    'P2': ('P2.mkv', 1.75, 'IMG_2077.mov', 16.55, None, 0),
    'P3': ('P3.mkv', 5.45, 'IMG_2078.mov', 3.00, None, 0),
    'P4': ('P4.mkv', 1.15, 'IMG_2078.mov', 9.85, None, 0),
    'P5': ('P5.mkv', 1.30, 'IMG_2079.mov', 11.70, 'P5_mask.npy', 0),
    'P6': ('P6.mkv', 1.35, 'IMG_2079.mov', 14.80, 'P6_mask.npy', 0),
    'c2': ('c2.mov', 5.25, None, 0, 'c2_mask.npy', 0),
    # IMG_2066: landscape 1080p60 shot sideways; only used as centred 9:16 detail shots (wing / tail / wheel).
    'c1': ('c1.mov', 14.35, None, 0, 'c1_mask_full.npy', 3.0),
}

# Shot: (song start, song end, source, in-point, fx, engine gain or 0, duck song?)
# fx: fadein | push | neon (flash on the shot's first hit) | trace | burn | fromwhite | reverse | final
# Round 3 (user feedback): mostly static shots, the earlier clips (IMG_2084 = c2, IMG_2066 = c1 details)
# mixed in, and no source range used twice inside a variant (check() enforces it).
# fx 'detail:<x>' = 9:16 window on c1 centred at x (fraction of the car's width from the left).
VARIANTS = {
    # Hook 1 - the car rolls in from the horizon (locked-off) and reaches the lens on the drop.
    'v1': [
        (0.000, 5.383, 'A', 0.00, {'fadein', 'push'}, 0.45, False),
        (5.383, 6.560, 'B', 0.00, set(), 1.0, True),
        (6.560, 7.883, 'C', 0.00, set(), 1.0, True),
        (7.883, 9.217, 'c2', 0.00, {'neon'}, 0, False),
        (9.217, 10.700, 'P1', 0.00, set(), 0.6, False),
        (10.700, 11.900, 'P1', 1.90, set(), 0.8, False),
        (11.900, 13.220, 'P2', 0.40, set(), 1.0, True),
        (13.220, 14.550, 'c1', 9.00, {'detail:0.62'}, 0, False),
        (14.550, 16.040, 'c2', 3.767, {'burn'}, 0, False),
        (16.040, 17.230, 'P3', 2.60, {'fromwhite'}, 0.6, False),
        (17.230, 18.660, 'P3', 3.90, set(), 0.9, False),
        (18.660, 19.890, 'c2', 1.35, {'trace'}, 0, False),
        (19.890, 21.370, 'E', 0.00, {'push', 'neon'}, 0, False),
        (21.370, END, 'P6', 0.20, {'final'}, 0, False),
    ],
    # Hook 2 - golden-hour pan onto the road, the car comes at you and flies past on the drop.
    'v2': [
        (0.000, 5.383, 'P3', 0.00, {'fadein', 'push'}, 0.5, False),
        (5.383, 6.560, 'C', 0.00, set(), 1.0, True),
        (6.560, 7.883, 'c2', 2.44, {'neon'}, 0, False),
        (7.883, 9.217, 'A', 0.50, set(), 0.4, False),
        (9.217, 10.700, 'A', 2.00, set(), 0.6, False),
        (10.700, 11.900, 'A', 3.60, set(), 0.7, False),
        (11.900, 13.220, 'P5', 0.00, set(), 0, False),
        (13.220, 14.550, 'E', 0.00, {'neon'}, 0, False),
        (14.550, 16.040, 'c1', 11.00, {'detail:0.30'}, 0, False),
        (16.040, 17.230, 'P1', 0.00, set(), 0.5, False),
        (17.230, 18.660, 'P1', 1.80, set(), 0.9, False),
        (18.660, 19.890, 'B', 0.00, set(), 1.0, True),
        (19.890, 21.370, 'c2', 3.767, {'burn'}, 0, False),
        (21.370, END, 'P6', 0.60, {'final', 'fromwhite'}, 0, False),
    ],
    # Hook 3 - the parked car, low and still, then the sunset front 3/4; fly-bys on the drop.
    'v3': [
        (0.000, 1.800, 'E', 0.00, {'fadein', 'push'}, 0, False),
        (1.800, 3.150, 'P6', 0.00, {'push'}, 0, False),
        (3.150, 5.383, 'c2', 0.00, set(), 0, False),
        (5.383, 6.560, 'B', 0.00, set(), 1.0, True),
        (6.560, 7.883, 'C', 0.00, set(), 1.0, True),
        (7.883, 9.217, 'P1', 0.00, set(), 0.5, False),
        (9.217, 10.700, 'P1', 1.80, set(), 0.9, False),
        (10.700, 11.900, 'P2', 0.50, set(), 1.0, True),
        (11.900, 13.220, 'c1', 12.00, {'detail:0.62'}, 0, False),
        (13.220, 14.550, 'A', 0.00, set(), 0.4, False),
        (14.550, 16.040, 'A', 2.00, set(), 0.6, False),
        (16.040, 17.230, 'A', 3.60, {'neon'}, 0.7, False),
        (17.230, 18.660, 'P3', 2.60, set(), 0.6, False),
        (18.660, 19.890, 'P3', 4.03, set(), 0.9, False),
        (19.890, 21.370, 'c2', 3.767, {'burn'}, 0, False),
        (21.370, END, 'D', 0.60, {'final', 'fromwhite'}, 0, False),
    ],
}

D = None


def first_hit(t0, t1):
    return next((h for h in HITS if t0 - 1e-3 <= h < t1), t0)


_c1_boxes = None


def c1_window_x(ct, rel):
    """Left edge of a 608 px wide (9:16) window on the landscape c1 frame, centred on the car at `rel`."""
    global _c1_boxes
    if _c1_boxes is None:
        arr = np.load(os.path.join(D, 'c1_mask_full.npy'), mmap_mode='r')
        xs = []
        for mm in arr:
            cols = np.nonzero((np.asarray(mm) > 127).any(0))[0]
            xs.append((cols.min() * 2, cols.max() * 2) if len(cols) else xs[-1] if xs else (0, 1919))
        b = np.array(xs, np.float32)
        k = 15
        _c1_boxes = np.stack([np.convolve(np.pad(b[:, j], k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
                              for j in range(2)], 1)
    x0, x1 = _c1_boxes[min(max(ek.fr(ct - 3.0), 0), len(_c1_boxes) - 1)]
    return float(np.clip(x0 + (x1 - x0) * rel - 304, 0, 1920 - 608))


def detail_frame(frame, x):
    """608x1080 window at x -> 1080x1920 (sub-pixel affine, Lanczos, light unsharp)."""
    s = W_OUT / 608
    M = np.float32([[s, 0, -x * s], [0, s, 0]])
    img = cv2.warpAffine(frame, M, (W_OUT, H_OUT), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
    img = img.astype(np.float32)
    return np.clip(img * 1.5 - cv2.GaussianBlur(img, (0, 0), 1.3) * 0.5, 0, 255)


W_OUT, H_OUT = ek.W, ek.H


def render_shot(shot, out, t0, n):
    s0, s1, src, at, fx, _, _ = shot
    path, length, _, _, mpath, mt0 = SRC[src]
    detail = next((float(f.split(':')[1]) for f in fx if f.startswith('detail:')), None)
    if detail is not None:
        for i, f in enumerate(ek.read(os.path.join(D, path), at, n, transpose=2)):
            t = t0 + i / ek.FPS
            img = detail_frame(f, c1_window_x(at + i / ek.FPS, detail))
            k = ek.hit_env(t, HITS, 10.0)
            out.write(camera(img, zoom=1 + 0.045 * k) if k > 0.01 else img)
        return
    frames = ek.read(os.path.join(D, path), at, n)
    if 'reverse' in fx:
        frames = frames[::-1]
    masks = ek.Masks(os.path.join(D, mpath), mt0) if mpath else None
    fpath = os.path.join(D, os.path.splitext(path)[0] + '_faces.json')
    faces = FaceTrack(fpath) if os.path.exists(fpath) else None
    hit = first_hit(s0, s1)
    for i, f in enumerate(frames):
        t = t0 + i / ek.FPS
        ct = at + ((n - 1 - i) if 'reverse' in fx else i) / ek.FPS
        img = f.astype(np.float32)
        m = masks(ct) if masks is not None else None
        if faces is not None:
            # Driver's face behind the windscreen -> tinted glass, before any other effect.
            img = faces.hide(img, ek.fr(ct), m if m is not None and ct >= mt0 else None)
            f = np.clip(img, 0, 255).astype(np.uint8)
        if 'push' in fx:
            img = camera(img, zoom=1.0 + 0.05 * (i / n) ** 1.3, center=(540, 1100))
        if 'neon' in fx and m is not None:
            e = math.exp(-max(0.0, t - hit) * 3.2)
            if e > 0.03:
                lit, al = neon_layer(f, m, BLUE, intensity=0.4 + 1.1 * e)
                a = al[..., None] * min(1.0, e * 1.6)
                img = lit * a + img * (1 - a)
        if 'trace' in fx and m is not None:
            p = (t - s0 - 0.05) / 1.0
            if 0 <= p <= 1:
                img = trace_light(img, m, p, WHITE, 1 - max(0, (p - 0.8) / 0.2))
        if 'burn' in fx:
            k = i - (n - 20)
            if k >= 0:
                p = k / 20
                g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (0, 0), 25)
                _, _, _, (sx, sy) = cv2.minMaxLoc(g)
                img = camera(img, zoom=1 + 1.4 * p ** 2.2, center=(sx, sy))
                img = img + (255 - img) * min(1.0, p ** 1.6 * 1.1)
        if 'fromwhite' in fx and t < s0 + 0.12:
            img = img + (255 - img) * (1 - (t - s0) / 0.12)
        if 'fadein' in fx:
            img *= min(1.0, (t - s0) / 0.35)
        if 'final' in fx:
            w = math.exp(-max(0.0, t - s0) * 7)
            if m is not None:
                lit, al = neon_layer(f, m, BLUE, intensity=1.3)
                a = al[..., None] * min(1.0, w * 1.5)
                img = lit * a + img * (1 - a)
            img = img + (255 - img) * w * 0.75
            if t >= s0 + 0.25:
                img *= max(0.0, 1 - (t - s0 - 0.25) / 0.2)
        # Zoom-only punch on the hits: no shake, the static shots stay locked off.
        k = ek.hit_env(t, HITS, 10.0)
        out.write(camera(img, zoom=1 + 0.045 * k) if k > 0.01 else img)


def check(shots):
    """Every shot must fit inside its source (no frozen frames) and shots must tile the song."""
    prev = 0.0
    used = {}
    for s0, s1, src, at, fx, _, _ in shots:
        for u0, u1 in used.get(src, []):
            assert at >= u1 - 0.02 or at + (s1 - s0) <= u0 + 0.02, f'{src}@{at} repeats footage already used'
        used.setdefault(src, []).append((at, at + (s1 - s0)))
        assert abs(s0 - prev) < 1e-6, f'gap/overlap at {s0}'
        need = at + (s1 - s0)
        # At most one held frame (0.025 s) is invisible; more reads as lag.
        assert need <= SRC[src][1] + 0.025, f'{src}@{at} needs {need:.2f}s > {SRC[src][1]}s'
        prev = s1
    assert abs(prev - END) < 1e-6


def engine_audio(shots):
    extra = []
    for s0, s1, src, at, fx, gain, duck in shots:
        if gain and SRC[src][2] and 'reverse' not in fx:
            extra.append({'path': os.path.join(D, FOOTAGE, SRC[src][2]), 'src_in': SRC[src][3] + at, 'at': s0,
                          'dur': s1 - s0, 'gain': gain, 'duck': duck})
    return extra


def main():
    global D
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('variant', choices=list(VARIANTS))
    ap.add_argument('--target-mb', type=float)
    ap.add_argument('--check', action='store_true', help='only validate the shot list')
    a = ap.parse_args()
    D = a.workdir
    shots = VARIANTS[a.variant]
    check(shots)
    if a.check:
        print(f'{a.variant}: {len(shots)} shots OK')
        return
    segs = {f'{a.variant}_{i:02d}': (s[0], s[1]) for i, s in enumerate(shots)}
    fns = {f'{a.variant}_{i:02d}': functools.partial(render_shot, s) for i, s in enumerate(shots)}
    ek.run(D, segs, fns, os.path.join(D, 'song.wav'), END, f'porsche_gt3_{a.variant}_r3', target_mb=a.target_mb,
           extra_audio=engine_audio(shots))


if __name__ == '__main__':
    main()
