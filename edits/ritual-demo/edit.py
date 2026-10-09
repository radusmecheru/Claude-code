#!/usr/bin/env python3
"""Style C demo - "night ritual" walkaround (ref: @rayden77777 "BMWs ritual"), built from the GT3 footage.

What it borrows from the reference: very dark low-key grade with the lamps keeping their colour, a
walkaround order (approach -> front -> headlight -> side/wheel -> rear -> tail-light), a cut on every beat
(112 BPM, ~0.5 s), micro jump-cuts inside a shot on the half beat, exposure pumps and lamp flares on the
beat, music only, no text. Kept from the user's rules: 9:16 full frame, 60 fps, face hidden.

  python3 edits/ritual-demo/edit.py work/ed2 [--target-mb 29]
Uses the prepped sources of edits/porsche-gt3-03 (same work dir) and ritual_song.wav (the reference sound).
"""
import argparse
import functools
import importlib.util
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from carfx import camera  # noqa: E402
import editkit as ek  # noqa: E402
import looks  # noqa: E402
from privacy import FaceTrack  # noqa: E402

_spec = importlib.util.spec_from_file_location('gt3v', os.path.join(HERE, '..', 'porsche-gt3-03', 'edit.py'))
gt3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gt3)

BEATS = [0.116, 0.65, 1.138, 1.625, 2.113, 2.601, 3.111, 3.669, 4.226, 4.783, 5.317, 5.875, 6.385, 6.943,
         7.5, 8.034, 8.568, 9.056, 9.543, 10.054, 10.495, 11.029, 11.564, 12.121, 12.655, 13.212]
END = 13.45

# (song start, end, source, in-point, fx); fx: fadein | push | jump (skip 0.2 s on each beat inside the shot)
#   | glow (lamps flare on beats) | fadeout | detail:<x> (c1 9:16 window)
SHOTS = [
    (0.000, 1.138, 'A', 0.00, {'fadein'}),
    (1.138, 2.601, 'A', 2.30, {'jump'}),
    (2.601, 3.669, 'E', 0.00, {'push'}),
    (3.669, 4.783, 'D', 0.00, set()),
    (4.783, 5.875, 'c2', 0.00, {'jump'}),
    (5.875, 6.943, 'P5', 0.00, set()),
    (6.943, 8.034, 'c1', 11.00, {'detail:0.30', 'jump'}),
    (8.034, 9.056, 'c1', 9.00, {'detail:0.62', 'glow'}),
    (9.056, 10.495, 'P2', 0.30, {'glow'}),
    (10.495, 12.121, 'c1', 12.00, {'detail:0.62', 'glow', 'push'}),
    (12.121, END, 'P6', 0.00, {'push', 'fadeout'}),
]


def beat_env(t, decay=12.0):
    since = min((t - b for b in BEATS if b <= t + 1e-6), default=99)
    return math.exp(-max(since, 0) * decay)


def source_times(s0, at, n, fx):
    """Clip time of each output frame; with 'jump', skip 0.2 s at every beat inside the shot."""
    inner = [b for b in BEATS if s0 + 0.05 < b < s0 + n / ek.FPS - 0.05]
    out = []
    for i in range(n):
        t = s0 + i / ek.FPS
        skips = sum(1 for b in inner if b <= t) if 'jump' in fx else 0
        out.append(at + i / ek.FPS + 0.2 * skips)
    return out


def render(shot, out, t0, n):
    s0, s1, src, at, fx = shot
    gt3.D = D
    path, length, _, _, mpath, mt0 = gt3.SRC[src]
    times = source_times(s0, at, n, fx)
    span = times[-1] - at + 1 / ek.FPS
    detail = next((float(f.split(':')[1]) for f in fx if f.startswith('detail:')), None)
    raw = ek.read(os.path.join(D, path), at, int(round(span * ek.FPS)) + 1, transpose=2 if detail is not None else None)
    fpath = os.path.join(D, os.path.splitext(path)[0] + '_faces.json')
    faces = FaceTrack(fpath) if os.path.exists(fpath) else None
    masks = ek.Masks(os.path.join(D, mpath), mt0) if mpath and detail is None else None
    for i, ct in enumerate(times):
        t = s0 + i / ek.FPS
        f = raw[min(int(round((ct - at) * ek.FPS)), len(raw) - 1)]
        if detail is not None:
            img = gt3.detail_frame(f, gt3.c1_window_x(ct, detail))
        else:
            img = f.astype(np.float32)
            if faces is not None:
                m = masks(ct) if masks is not None and ct >= mt0 else None
                img = faces.hide(img, ek.fr(ct), m)
        if 'push' in fx:
            img = camera(img, zoom=1.0 + 0.06 * (i / n))
        img = looks.night_ritual(img, sky_mask=looks.sky_mask(img))
        e = beat_env(t)
        if 'glow' in fx:
            img = looks.lamp_glow(img, 0.35 + 0.9 * e)
        if t > 1.0:  # exposure pump + small zoom punch on every beat after the intro
            img = img * (1 + 0.28 * e)
            img = camera(img, zoom=1 + 0.03 * e) if e > 0.02 else img
        if 'fadein' in fx:
            img *= min(1.0, (t - s0) / 0.5)
        if 'fadeout' in fx:
            img *= max(0.0, min(1.0, (END - t) / 0.35))
        out.write(looks.grain(img, 3.0, seed=int(t * 1000)))


D = None


def main():
    global D
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('--target-mb', type=float)
    ap.add_argument('--seg', action='append', help='re-render only these segments, e.g. rd_06')
    a = ap.parse_args()
    D = a.workdir
    for s0, s1, src, at, fx in SHOTS:
        need = source_times(s0, at, ek.fr(s1) - ek.fr(s0), fx)[-1]
        assert need <= gt3.SRC[src][1] + 0.025, f'{src}@{at} needs {need:.2f}s'
    segs = {f'rd_{i:02d}': (s[0], s[1]) for i, s in enumerate(SHOTS)}
    fns = {f'rd_{i:02d}': functools.partial(render, s) for i, s in enumerate(SHOTS)}
    ek.run(D, segs, fns, os.path.join(D, 'ritual_song.wav'), END, 'ritual_demo', only=a.seg,
           target_mb=a.target_mb, grade='format=yuv420p')


if __name__ == '__main__':
    main()
