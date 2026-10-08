#!/usr/bin/env python3
"""Porsche 911 GT3 car edit #2 - 13.6 s, 1080x1920, 60 fps, same TikTok sound as edit #1.

Every frame is one full-screen 9:16 picture. New footage: IMG_2077/2078/2079 (4K vertical, 30 fps),
downscaled to 1080x1920 and interpolated to 60 fps with RIFE (work/ed2/prep.sh -> A..E.mkv).
c2.mov is IMG_2084 (vertical 60 fps) from edit #1.

Work dir contents: A.mkv (2079 5.0 s, approach), B.mkv (2077 15.30 s, pass), C.mkv (2078 8.45 s,
sunset pass), D.mkv (2079 10.45 s, face to camera), E.mkv (2079 13.0 s, parked hero), E_mask.npy,
c2.mov, c2_mask.npy, song.wav.

  python3 edits/porsche-gt3-02/edit.py work/ed2 [--seg s7] [--target-mb 29]
"""
import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from carfx import camera, hex_bgr, neon_layer, trace_light  # noqa: E402
import editkit as ek  # noqa: E402

BLUE = hex_bgr('#2A8CFF')
WHITE = np.array([255, 255, 255], np.float32)
HITS = [5.383, 6.56, 7.883, 9.217, 10.70, 11.90, 13.22]
END = 13.62
SEGMENTS = {
    's1': (0.0, 5.383),    # hook: car rolls in from the horizon under the news voice
    's2': (5.383, 6.56),   # drop: fly-by past the camera
    's3': (6.56, 7.883),   # second fly-by, golden light
    's4': (7.883, 9.217),  # front 3/4 dutch tilt, car flashes neon
    's5': (9.217, 10.70),  # swing to the sun, burn to white
    's6': (10.70, 11.90),  # out of the white: car face right in the lens
    's7': (11.90, END),    # parked hero, light lap, neon + flash on the last hit
}
D = None


def clip(name):
    return os.path.join(D, name)


def s1(out, t0, n):
    frames = ek.read(clip('A.mkv'), 0.0, n)
    for i, f in enumerate(frames):
        t = i / ek.FPS
        p = t / (n / ek.FPS)
        img = camera(f.astype(np.float32), zoom=1.0 + 0.05 * p ** 1.5, center=(540, 1050))
        img *= min(1.0, t / 0.35)
        out.write(img)


def s2(out, t0, n):
    for i, f in enumerate(ek.read(clip('B.mkv'), 0.0, n)):
        t = t0 + i / ek.FPS
        out.write(ek.punch(f.astype(np.float32), t, HITS, strength=0.07, shake_px=9))


def s3(out, t0, n):
    for i, f in enumerate(ek.read(clip('C.mkv'), 0.0, n)):
        t = t0 + i / ek.FPS
        out.write(ek.punch(f.astype(np.float32), t, HITS, strength=0.06, shake_px=8))


def s4(out, t0, n):
    masks = ek.Masks(clip('c2_mask.npy'), 0.0)
    for i, f in enumerate(ek.read(clip('c2.mov'), 2.5, n)):
        t = t0 + i / ek.FPS
        img = f.astype(np.float32)
        e = ek.hit_env(t, HITS, 4)
        if e > 0.03:
            lit, al = neon_layer(f, masks(2.5 + i / ek.FPS), BLUE, intensity=0.4 + 1.1 * e)
            a = al[..., None] * min(1.0, e * 1.6)
            img = lit * a + img * (1 - a)
        out.write(ek.punch(img, t, HITS, strength=0.05, shake_px=6))


def s5(out, t0, n):
    import cv2
    frames = ek.read(clip('c2.mov'), 3.833, n)
    burn = 20
    for i, f in enumerate(frames):
        t = t0 + i / ek.FPS
        img = f.astype(np.float32)
        k = i - (n - burn)
        if k >= 0:
            p = k / burn
            g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (0, 0), 25)
            _, _, _, (sx, sy) = cv2.minMaxLoc(g)
            img = camera(img, zoom=1 + 1.4 * p ** 2.2, center=(sx, sy))
            img = img + (255 - img) * min(1.0, p ** 1.6 * 1.1)
        out.write(ek.punch(img, t, HITS, strength=0.04, shake_px=5))


def s6(out, t0, n):
    for i, f in enumerate(ek.read(clip('D.mkv'), 0.0, n)):
        t = t0 + i / ek.FPS
        img = f.astype(np.float32)
        if t < t0 + 0.12:  # come out of the sun-burn white
            img = img + (255 - img) * (1 - (t - t0) / 0.12)
        out.write(ek.punch(img, t, HITS, strength=0.06, shake_px=7))


def s7(out, t0, n):
    masks = ek.Masks(clip('E_mask.npy'), 0.0)
    for i, f in enumerate(ek.read(clip('E.mkv'), 0.0, n)):
        t = t0 + i / ek.FPS
        ct = i / ek.FPS
        m = masks(ct)
        img = f.astype(np.float32)
        p = (t - 11.95) / 1.0
        if 0 <= p <= 1:
            img = trace_light(img, m, p, WHITE, 1 - max(0, (p - 0.8) / 0.2))
        if t >= 13.22:
            w = math.exp(-(t - 13.22) * 7)
            lit, al = neon_layer(f, m, BLUE, intensity=1.3)
            a = al[..., None] * min(1.0, w * 1.5)
            img = lit * a + img * (1 - a)
            img = img + (255 - img) * w * 0.75
        if t >= 13.45:
            img *= max(0.0, 1 - (t - 13.45) / 0.15)
        out.write(ek.punch(img, t, HITS, strength=0.05, shake_px=6))


FNS = {'s1': s1, 's2': s2, 's3': s3, 's4': s4, 's5': s5, 's6': s6, 's7': s7}


def main():
    global D
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('--seg', action='append')
    ap.add_argument('--target-mb', type=float)
    a = ap.parse_args()
    D = a.workdir
    ek.run(D, SEGMENTS, FNS, clip('song.wav'), END, 'porsche_gt3_edit04', only=a.seg, target_mb=a.target_mb)


if __name__ == '__main__':
    main()
