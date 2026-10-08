#!/usr/bin/env python3
"""Porsche 911 GT3 car edit #1 - 22 s, 1080x1920, 60 fps, cut to the TikTok sound.

Media (not in git) lives in a work dir: c1.mov (landscape footage shot sideways),
c2.mov (vertical), song.wav, c1_mask.npy (c1 6.0-14.2 s), c2_mask.npy (c2 0-3.6 s).

  python3 edits/porsche-gt3-01/edit.py work/ed1            # render every segment + final
  python3 edits/porsche-gt3-01/edit.py work/ed1 --seg s3   # re-render one segment, then final

Rule for sharpness: footage is never scaled above 1:1 except during the punch-ins
(<= 8 %, a few frames) and inside the white flash of the sun transition.
"""
import argparse
import math
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from carfx import camera, ease, ease_in_out, hex_bgr, neon_layer, trace_light  # noqa: E402

FPS = 60
W, H = 1080, 1920
BLUE = hex_bgr('#2A8CFF')
# Bass hits measured on the sound (seconds).
HITS = [5.383, 6.56, 7.883, 9.217, 10.70, 11.90, 13.22, 14.55, 16.04, 17.23, 18.66, 19.04, 19.89, 20.32, 21.37]
END = 21.95
SEGMENTS = {  # name: (start, end) in song time
    's1': (0.0, 5.383), 's2': (5.383, 7.883), 's3': (7.883, 9.217), 's4': (9.217, 10.70),
    's5': (10.70, 16.05), 's6': (16.05, 18.66), 's7': (18.66, END),
}
C1_MASK_T0, C2_MASK_T0 = 6.0, 0.0

D = None  # work dir, set in main


def fr(t):
    return int(round(t * FPS))


def read(name, start, n, transpose=None):
    """n frames at 60 fps from `start`; repeats the last frame if the clip runs out."""
    vf = f'fps={FPS}' + (f',transpose={transpose}' if transpose else '')
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', f'{start:.4f}', '-i', os.path.join(D, name), '-vf', vf,
                          '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    w, h = (1920, 1080) if transpose else (1080, 1920)
    out = []
    while len(out) < n:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        out.append(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
    p.stdout.close(); p.wait()
    while len(out) < n:
        out.append(out[-1])
    return out


c1 = lambda start, n: read('c1.mov', start, n, transpose=2)  # noqa: E731
c2 = lambda start, n: read('c2.mov', start, n)  # noqa: E731

_masks = {}


def mask(clip, t, size):
    """Float mask 0..1 for clip time t, resized to `size` (w, h)."""
    if clip not in _masks:
        _masks[clip] = np.load(os.path.join(D, f'{clip}_mask.npy'), mmap_mode='r')
    arr = _masks[clip]
    t0 = C1_MASK_T0 if clip == 'c1' else C2_MASK_T0
    i = min(max(fr(t - t0), 0), len(arr) - 1)
    return cv2.resize(clean_mask(np.asarray(arr[i])), size, interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0


def clean_mask(m):
    """Drop thin attachments (road lines, gravel) and stray blobs: opening + largest component + 1 px erode."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
    body = cv2.morphologyEx((m > 127).astype(np.uint8), cv2.MORPH_OPEN, k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(body)
    if n > 1:
        body = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    keep = cv2.dilate(body, np.ones((3, 3), np.uint8))
    return cv2.erode((m * keep).astype(np.uint8), np.ones((3, 3), np.uint8))


_bbox = {}


def car_box(clip, t):
    """Smoothed subject bounding box (x0, y0, x1, y1) in full-res pixels of the clip."""
    if clip not in _bbox:
        arr = np.load(os.path.join(D, f'{clip}_mask.npy'), mmap_mode='r')
        boxes = []
        for m in arr:
            ys, xs = np.nonzero(m > 127)
            if len(xs):
                c = clean_mask(np.asarray(m))
                ys, xs = np.nonzero(c > 127) if c.any() else (ys, xs)
            boxes.append([xs.min(), ys.min(), xs.max(), ys.max()] if len(xs) else boxes[-1] if boxes else [0, 0, 1, 1])
        b = np.array(boxes, np.float32) * 2
        k = 15  # moving average over a quarter second
        b = np.stack([np.convolve(np.pad(b[:, j], k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
                      for j in range(4)], 1)
        _bbox[clip] = b
    b = _bbox[clip]
    t0 = C1_MASK_T0 if clip == 'c1' else C2_MASK_T0
    return b[min(max(fr(t - t0), 0), len(b) - 1)]


def hit_env(t, decay=10.0, hits=HITS):
    """1 on a bass hit, decaying exponentially; 0 far from hits."""
    since = min((t - h for h in hits if h <= t + 1e-6), default=99)
    return math.exp(-max(since, 0) * decay)


def punch(img, t, strength=0.06, shake_px=7, decay=10.0, seed=0):
    k = hit_env(t, decay)
    if k < 0.01:
        return img
    rng = np.random.default_rng(int(t * 1000) + seed)
    dx, dy = rng.normal(0, shake_px * k, 2)
    return camera(img, zoom=1 + strength * k, dx=dx, dy=dy, angle=rng.normal(0, 0.5 * k))


def fit_width(img, width=W, scale=1.0):
    h, w = img.shape[:2]
    s = width / w * scale
    return cv2.resize(img, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)


def band(canvas, img, y, h, x_off=0):
    """Paste a landscape frame as a horizontal band (centre-cropped to height h) at row y."""
    ih = img.shape[0]
    top = max(0, (ih - h) // 2)
    piece = img[top:top + h, :W]
    x0 = int(x_off)
    xs, xe = max(0, x0), min(W, x0 + piece.shape[1])
    if xe > xs:
        canvas[y:y + piece.shape[0], xs:xe] = piece[:, xs - x0:xe - x0]
    return canvas


def detail_crop(frame, clip, t, fx, fy, size=(1080, 608), zoom=1.0):
    """1:1-pixel crop around a point given relative to the car's bounding box."""
    x0, y0, x1, y1 = car_box(clip, t)
    cw, ch = int(size[0] * zoom), int(size[1] * zoom)
    cx = int(x0 + (x1 - x0) * fx - cw / 2)
    cy = int(y0 + (y1 - y0) * fy - ch / 2)
    fh, fw = frame.shape[:2]
    cx, cy = min(max(cx, 0), fw - cw), min(max(cy, 0), fh - ch)
    crop = frame[cy:cy + ch, cx:cx + cw]
    return cv2.resize(crop, size, interpolation=cv2.INTER_AREA) if zoom != 1.0 else crop


class Writer:
    """Lossless RGB intermediate; the single lossy encode happens in finalize()."""

    def __init__(self, path):
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                                   '-r', str(FPS), '-i', '-', '-c:v', 'libx264rgb', '-qp', '0', '-preset', 'ultrafast',
                                   path], stdin=subprocess.PIPE)

    def write(self, img):
        self.p.stdin.write(np.ascontiguousarray(np.clip(img, 0, 255), np.uint8).tobytes())

    def close(self):
        self.p.stdin.close(); self.p.wait()


# ---------------- segments ----------------

def s1(out, t0, n):
    """Hook: cinematic letterbox, calm walk-up to the car while the news voice plays."""
    frames = c1(3.2, n)
    for i, f in enumerate(frames):
        t = i / FPS
        canvas = np.zeros((H, W, 3), np.float32)
        open_p = ease(t / 0.9)
        bh = max(2, int(810 * open_p))
        push = 1.0 + 0.05 * (t / (n / FPS)) ** 1.5
        img = fit_width(f, width=1440, scale=push).astype(np.float32)
        y = (H - bh) // 2
        # Keep the push centred: crop the wider frame back to 1080.
        xo = (img.shape[1] - W) // 2
        band(canvas, img[:, xo:xo + W], y, bh)
        # A thin light line on the band edges while it opens.
        glow = max(0.0, 1 - t / 1.2)
        if glow > 0:
            line = np.zeros((H, W), np.float32)
            line[max(0, y - 1):y + 1, :] = 1
            line[y + bh - 1:y + bh + 1, :] = 1
            g = cv2.GaussianBlur(line, (0, 0), 6) * 2 + line
            canvas += g[..., None] * np.array([255, 235, 215], np.float32) * glow * 0.8
        out.write(canvas)


def s2(out, t0, n):
    """Drop: full-screen vertical, punch-ins on the bass, light trace round the car."""
    frames = c2(0.0, n)
    for i, f in enumerate(frames):
        t = t0 + i / FPS
        ct = i / FPS
        img = f.astype(np.float32)
        p = (t - 5.42) / 1.05
        if 0 <= p <= 1:
            fade = 1 - max(0.0, (p - 0.8) / 0.2)
            img = trace_light(img, mask('c2', ct, (W, H)), p, np.array([255, 255, 255], np.float32), fade,
                              length=0.3)
        out.write(punch(img, t, strength=0.07, shake_px=8))


def s3(out, t0, n):
    """Neon cut-out of the rear (c1) drops in over the tilting front shot (c2)."""
    bg = c2(2.5, n)
    fg = c1(10.0, n)
    s = 0.62
    for i, (b, f) in enumerate(zip(bg, fg)):
        t = t0 + i / FPS
        ct = 10.0 + i / FPS
        m = mask('c1', ct, (1920, 1080))
        inten = 0.9 + 0.6 * hit_env(t, 6)
        lit, al = neon_layer(f, m, BLUE, intensity=inten)
        x0, y0, x1, y1 = car_box('c1', ct)
        ccx, ccy = (x0 + x1) / 2, (y0 + y1) / 2
        p = ease(i / 16)
        tx = W / 2
        ty = -450 + (430 + 450) * p + math.sin(i / 20) * 6
        # Downscale with area filtering first (sharp, no aliasing), then translate into place.
        lit_s = cv2.resize(lit, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        al_s = cv2.resize(al, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        M = np.float32([[1, 0, tx - ccx * s], [0, 1, ty - ccy * s]])
        lay = cv2.warpAffine(lit_s, M, (W, H), flags=cv2.INTER_LINEAR)
        a = cv2.warpAffine(al_s, M, (W, H), flags=cv2.INTER_LINEAR)
        base = b.astype(np.float32)
        sh = cv2.GaussianBlur(a, (0, 0), 28)[..., None] * 0.55
        base *= 1 - sh
        a = a[..., None]
        img = lay * a + base * (1 - a)
        out.write(punch(img, t, strength=0.05, shake_px=6))


def s4(out, t0, n):
    """Camera swings to the sun; zoom into the sun and burn to white."""
    frames = c2(3.833, n)
    burn = 20
    for i, f in enumerate(frames):
        t = t0 + i / FPS
        img = f.astype(np.float32)
        k = i - (n - burn)
        if k >= 0:
            p = k / burn
            g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (0, 0), 25)
            _, _, _, (sx, sy) = cv2.minMaxLoc(g)
            img = camera(img, zoom=1 + 1.4 * p ** 2.2, center=(sx, sy))
            img = img + (255 - img) * min(1.0, p ** 1.6 * 1.1)
        out.write(punch(img, t, strength=0.04, shake_px=5))


STACK_Y = (0, 656, 1312)
STACK_H = 608


def s5(out, t0, n):
    """Triple stack of the landscape orbit: full frame in the middle, 1:1 detail crops above/below."""
    frames = c1(8.6, n)
    looks = [  # (from song time, top crop, bottom crop) - crops relative to the car's box
        (0.0, (0.30, 0.80), (0.70, 0.12)),    # wheel / wing
        (13.22, (0.62, 0.50), (0.25, 0.30)),  # tail-light bar / roof + mirror
        (14.55, (0.70, 0.12), (0.30, 0.80)),  # wing / wheel (swapped)
    ]
    for i, f in enumerate(frames):
        t = t0 + i / FPS
        ct = 8.6 + i / FPS
        canvas = np.zeros((H, W, 3), np.float32)
        mid = fit_width(f).astype(np.float32)
        if 14.55 <= t < 15.4:  # neon flash on the middle band
            m = mask('c1', ct, (mid.shape[1], mid.shape[0]))
            lit, al = neon_layer(mid.astype(np.uint8), m, BLUE, intensity=1.3 * hit_env(t, 3) + 0.2)
            al = al[..., None] * min(1.0, hit_env(t, 3) * 1.5)
            mid = lit * al + mid * (1 - al)
        band(canvas, mid, STACK_Y[1], STACK_H)
        _, top_c, bot_c = [lk for lk in looks if lk[0] <= t][-1]
        drift = 1.06 - 0.06 * ((t - 10.7) % 1.33) / 1.33  # slow push inside each crop, never above 1:1
        if t >= 11.9:
            p = ease((t - 11.9) / 0.22)
            top = detail_crop(f, 'c1', ct, *top_c, zoom=drift).astype(np.float32)
            bot = detail_crop(f, 'c1', ct, *bot_c, zoom=drift).astype(np.float32)
            band(canvas, top, STACK_Y[0], STACK_H, x_off=-(1 - p) * W)
            band(canvas, bot, STACK_Y[2], STACK_H, x_off=(1 - p) * W)
        flash = 0.18 * hit_env(t, 12)
        canvas = canvas + (255 - canvas) * flash * (canvas.sum(2, keepdims=True) > 0)
        out.write(punch(canvas, t, strength=0.04, shake_px=5))


def s6(out, t0, n):
    """Reverse of the front shot, car lit in neon on the hits over a darkened background."""
    frames = c2(0.787, n)[::-1]
    for i, f in enumerate(frames):
        t = t0 + i / FPS
        ct = 0.787 + (n - 1 - i) / FPS
        m = mask('c2', ct, (W, H))
        k = hit_env(t, 2.5)
        lit, al = neon_layer(f, m, BLUE, intensity=0.45 + 1.0 * k)
        bg = f.astype(np.float32) * (0.85 - 0.35 * min(1.0, k * 2))
        a = al[..., None]
        out.write(punch(lit * a + bg * (1 - a), t, strength=0.06, shake_px=7))


def s7(out, t0, n):
    """Outro: back to the letterbox, the car breaks out of the band; white hit, cut to black."""
    frames = c1(11.2, n)
    s = 0.75
    band_h = 400
    for i, f in enumerate(frames):
        t = t0 + i / FPS
        ct = 11.2 + i / FPS
        x0, y0, x1, y1 = car_box('c1', ct)
        big = cv2.resize(f, (int(1920 * s), int(1080 * s)), interpolation=cv2.INTER_AREA).astype(np.float32)
        m = cv2.resize(mask('c1', ct, (1920, 1080)), (big.shape[1], big.shape[0]))
        # Centre the car horizontally; place the band so the roof and wing stick out above it.
        cx = int((x0 + x1) / 2 * s - W / 2)
        cx = min(max(cx, 0), big.shape[1] - W)
        big, m = big[:, cx:cx + W], m[:, cx:cx + W]
        car_top = y0 * s
        band_top = min(int(car_top + 0.38 * (y1 - y0) * s), big.shape[0] - band_h)
        y_screen = (H - band_h) // 2
        canvas = np.zeros((H, W, 3), np.float32)
        oy = y_screen - band_top  # offset from big-frame rows to screen rows
        canvas[y_screen:y_screen + band_h] = big[band_top:band_top + band_h]
        # Car pixels outside the band are drawn on top of the black bars.
        full = np.zeros((H, W, 3), np.float32); fm = np.zeros((H, W), np.float32)
        r0, r1 = max(0, oy), min(H, oy + big.shape[0])
        full[r0:r1] = big[r0 - oy:r1 - oy]
        fm[r0:r1] = m[r0 - oy:r1 - oy]
        fm = fm[..., None]
        canvas = full * fm + canvas * (1 - fm)
        if t >= 21.37:
            w = math.exp(-(t - 21.37) * 9)
            canvas = canvas + (255 - canvas) * w * 0.85
        if t >= 21.72:
            canvas *= max(0.0, 1 - (t - 21.72) / 0.12)
        out.write(punch(canvas, t, strength=0.05, shake_px=6))


def render(name):
    t0, t1 = SEGMENTS[name]
    n = fr(t1) - fr(t0)
    w = Writer(os.path.join(D, f'{name}.mkv'))
    globals()[name](w, t0, n)
    w.close()
    return name, n


def finalize(target_mb=None):
    names = list(SEGMENTS)
    lst = os.path.join(D, 'segments.txt')
    with open(lst, 'w') as fh:
        fh.writelines(f"file '{n}.mkv'\n" for n in names)
    grade = ('eq=contrast=1.06:saturation=1.08:gamma=0.98,'
             'colorbalance=rs=-0.02:bs=0.03:rh=0.03:bh=-0.02,'
             'unsharp=5:5:0.35:5:5:0,format=yuv420p')
    common = ['-profile:v', 'high', '-level', '4.2', '-r', str(FPS), '-g', '120', '-color_primaries', 'bt709',
              '-color_trc', 'bt709', '-colorspace', 'bt709']
    inputs = ['-f', 'concat', '-safe', '0', '-i', lst, '-i', os.path.join(D, 'song.wav'), '-vf', grade,
              '-af', f'afade=t=out:st={END - 0.25}:d=0.25', '-map', '0:v', '-map', '1:a', '-t', str(END)]
    if target_mb:
        # Two-pass to a size cap (chat upload limit); ~10 Mbps at 22 s is still above what TikTok streams.
        out = os.path.join(D, f'porsche_gt3_edit01_{target_mb}mb.mp4')
        kbps = int(target_mb * 8 * 1024 * 0.97 / END) - 192
        log = os.path.join(D, 'x264pass')
        for p in (1, 2):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{kbps}k',
                            '-maxrate', f'{int(kbps * 1.5)}k', '-bufsize', f'{kbps * 2}k', '-pass', str(p),
                            '-passlogfile', log, *common, '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                            '-movflags', '+faststart', out if p == 2 else '-f', *([] if p == 2 else ['mp4', os.devnull])],
                           check=True)
    else:
        out = os.path.join(D, 'porsche_gt3_edit01.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', *common,
                        '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart', out], check=True)
    print(out)


def main():
    global D
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('--seg', action='append', help='only these segments (default: all)')
    ap.add_argument('--no-final', action='store_true')
    ap.add_argument('--target-mb', type=float, help='also make a size-capped copy (e.g. 29 for chat upload)')
    a = ap.parse_args()
    D = a.workdir
    names = a.seg if a.seg is not None else list(SEGMENTS)
    if a.target_mb and not a.seg:
        names = []  # size-capped copy only: reuse the rendered segments
    with ProcessPoolExecutor(max_workers=4, initializer=_init, initargs=(D,)) as ex:
        for name, n in ex.map(render, names):
            print(f'{name}: {n} frames', file=sys.stderr)
    if not a.no_final:
        finalize(a.target_mb)


def _init(d):
    global D
    D = d


if __name__ == '__main__':
    main()
