#!/usr/bin/env python3
"""Porsche 911 GT3 edit #4 - first edit with the learned styles (13.62 s, the original TikTok sound).

Mix: J (cuts 1 frame before each bass hit, warm natural look, jump cuts in a locked-off framing),
I (zoom-blur transition, synthetic camera roll with rotational blur), G without text (reverse portal through
the real wheel), F (x-ray silhouette on the final hit). User rules: full 9:16, one picture per frame,
60 fps, face hidden, engine sound on the fly-by, no text, ends on a bass hit.

  python3 edits/porsche-gt3-04/edit.py work/ed2 [--target-mb 29]
Uses the prepped sources of edits/porsche-gt3-03 (same work dir).
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
import transitions as tr  # noqa: E402
from privacy import FaceTrack  # noqa: E402

_spec = importlib.util.spec_from_file_location('gt3v', os.path.join(HERE, '..', 'porsche-gt3-03', 'edit.py'))
gt3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gt3)

HITS = [5.383, 6.56, 7.883, 9.217, 10.70, 11.90, 13.22]
END = 13.62
EARLY = 1 / ek.FPS  # J: cuts land one frame before the beat

# (nominal song start, end, source, in-point, fx, engine gain, duck)
SHOTS = [
    (0.000, 5.383, 'P3', 0.00, {'fadein', 'push', 'zoomout'}, 0.45, False),
    (5.383, 6.560, 'B', 0.00, {'zoomin'}, 1.0, True),
    (6.560, 7.883, 'c2', 2.44, {'roll'}, 0, False),
    (7.883, 9.217, 'E', 0.00, {'rportal', 'push'}, 0, False),
    (9.217, 10.700, 'c1', 9.00, {'detail:0.62', 'whipin'}, 0, False),
    (10.700, 11.900, 'A', 0.00, {'arrive'}, 0.4, False),
    (11.900, 13.220, 'A', 2.00, {'arrive'}, 0.6, False),
    (13.220, END, 'P6', 0.20, {'final'}, 0, False),
]
WHEEL_E = (330, 1345, 150, 150)  # front wheel of the parked hero (E), for the reverse portal


def timeline():
    """Shift every cut except the first one frame early; returns [(start, end, shot)]."""
    out = []
    for i, s in enumerate(SHOTS):
        a = s[0] - (EARLY if i else 0)
        b = s[1] - EARLY if i + 1 < len(SHOTS) else s[1]
        out.append((round(a, 4), round(b, 4), s))
    return out


def src_frame(src, t, n=1):
    path = gt3.SRC[src][0]
    return ek.read(os.path.join(D, path), t, n, transpose=2 if src == 'c1' else None)


def render(item, prev, out, t0, n):
    s0, s1, (_, _, src, at, fx, _, _) = item
    gt3.D = D
    path, length, _, _, mpath, mt0 = gt3.SRC[src]
    detail = next((float(f.split(':')[1]) for f in fx if f.startswith('detail:')), None)
    frames = src_frame(src, at, n)
    fpath = os.path.join(D, os.path.splitext(path)[0] + '_faces.json')
    faces = FaceTrack(fpath) if os.path.exists(fpath) else None
    masks = ek.Masks(os.path.join(D, mpath), mt0) if mpath and detail is None else None
    prev_img = None
    if 'rportal' in fx and prev is not None:
        prev_img = src_frame(prev[0], prev[1])[0].astype(np.float32)
        if prev[0] == 'c1':
            prev_img = gt3.detail_frame(prev_img.astype(np.uint8), gt3.c1_window_x(prev[1], 0.62))
    last_angle = None
    for i, f in enumerate(frames):
        t = t0 + i / ek.FPS
        ct = at + i / ek.FPS
        if detail is not None:
            img = gt3.detail_frame(f, gt3.c1_window_x(ct, detail))
            m = None
        else:
            img = f.astype(np.float32)
            m = masks(ct) if masks is not None else None
            if faces is not None:
                img = faces.hide(img, ek.fr(ct), m if m is not None and ct >= mt0 else None)
        if 'push' in fx:
            img = camera(img, zoom=1.0 + 0.05 * (i / n) ** 1.3, center=(540, 1150))
        if 'zoomout' in fx and i >= n - 8:
            img = tr.zoom_blur(img, (i - (n - 8)) / 7, out=True, center=(540, 1050))
        if 'zoomin' in fx and i < 6:
            img = tr.zoom_blur(img, i / 5, out=False)
        if 'roll' in fx:
            ang = -14 * (1 - (1 - min(1.0, i / 14)) ** 3)
            img = tr.roll(img, ang, last_angle)
            last_angle = ang
        if 'rportal' in fx and prev_img is not None and i < 16:
            img = tr.reverse_portal(img, prev_img, *WHEEL_E, i / 15)
        if 'whipin' in fx and i < 5:
            img = tr.whip(img, -(1 - i / 5), direction=1)
        if 'arrive' in fx:
            img = tr.arrive(img, max(0.0, 1 - i / 6))
        img = looks.warm_natural(img)
        if 'fadein' in fx:
            img *= min(1.0, (t - s0) / 0.4)
        if 'final' in fx:
            k = t - s0
            if k < 3 / ek.FPS and m is not None:
                img = tr.silhouette(img, m, 'xray')
            img = tr.flash_in(img, 0.8 * math.exp(-k * 9))
            if k > 0.2:
                img = tr.fade(img, (k - 0.2) / 0.18)
        e = ek.hit_env(t + EARLY, HITS, 10.0)  # zoom-only punch (no shake), aligned with the early cuts
        out.write(camera(img, zoom=1 + 0.04 * e) if e > 0.01 else img)


D = None


def main():
    global D
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('--target-mb', type=float)
    ap.add_argument('--seg', action='append')
    a = ap.parse_args()
    D = a.workdir
    items = timeline()
    used = {}
    for s0, s1, (_, _, src, at, fx, _, _) in items:
        need = at + (s1 - s0)
        assert need <= gt3.SRC[src][1] + 0.025, f'{src}@{at} needs {need:.2f}s'
        for u0, u1 in used.get(src, []):
            assert at >= u1 - 0.02 or need <= u0 + 0.02, f'{src}@{at} repeats footage'
        used.setdefault(src, []).append((at, need))
    segs, fns = {}, {}
    for i, it in enumerate(items):
        prev = None
        if i:
            p0, p1, (_, _, psrc, pat, _, _, _) = items[i - 1]
            prev = (psrc, pat + (p1 - p0) - 1 / ek.FPS)
        segs[f'g4_{i:02d}'] = (it[0], it[1])
        fns[f'g4_{i:02d}'] = functools.partial(render, it, prev)
    extra = []
    for s0, s1, (_, _, src, at, fx, gain, duck) in items:
        if gain and gt3.SRC[src][2]:
            extra.append({'path': os.path.join(D, gt3.FOOTAGE, gt3.SRC[src][2]), 'src_in': gt3.SRC[src][3] + at,
                          'at': s0, 'dur': s1 - s0, 'gain': gain, 'duck': duck})
    ek.run(D, segs, fns, os.path.join(D, 'song.wav'), END, 'porsche_gt3_edit05', only=a.seg,
           target_mb=a.target_mb, grade='unsharp=5:5:0.3:5:5:0,format=yuv420p', extra_audio=extra)


if __name__ == '__main__':
    main()
