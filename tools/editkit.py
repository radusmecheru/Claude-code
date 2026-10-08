"""Shared plumbing for per-edit scripts (edits/<name>/edit.py).

An edit = a dict of segments {name: (song_start, song_end)} plus one function per segment that
writes frames (BGR float/uint8, 1080x1920) to a Writer. Segments render in parallel to lossless
intermediates; finalize() concatenates, grades, adds the song and encodes once.
"""
import math
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from carfx import camera  # noqa: E402

FPS = 60
W, H = 1080, 1920
GRADE = ('eq=contrast=1.06:saturation=1.08:gamma=0.98,'
         'colorbalance=rs=-0.02:bs=0.03:rh=0.03:bh=-0.02,'
         'unsharp=5:5:0.35:5:5:0,format=yuv420p')


def fr(t):
    return int(round(t * FPS))


def read(path, start, n, transpose=None, size=None):
    """n frames at 60 fps from `start` (seconds); repeats the last frame if the clip runs out.
    size=(w, h) to force a decode size (default 1080x1920, or 1920x1080 when transposing)."""
    vf = [f'fps={FPS}']
    if transpose:
        vf.append(f'transpose={transpose}')
    w, h = size or ((1920, 1080) if transpose else (W, H))
    vf.append(f'scale={w}:{h}:flags=area')
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', f'{start:.4f}', '-i', path, '-vf', ','.join(vf),
                          '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    out = []
    while len(out) < n:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        out.append(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
    p.stdout.close(); p.wait()
    if not out:
        raise RuntimeError(f'no frames from {path} at {start}')
    while len(out) < n:
        out.append(out[-1])
    return out


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


def clean_mask(m):
    """Drop thin attachments (road lines, gravel) and stray blobs: opening + largest component + 1 px erode."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
    body = cv2.morphologyEx((m > 127).astype(np.uint8), cv2.MORPH_OPEN, k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(body)
    if n > 1:
        body = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    keep = cv2.dilate(body, np.ones((3, 3), np.uint8))
    return cv2.erode((m * keep).astype(np.uint8), np.ones((3, 3), np.uint8))


class Masks:
    """Masks precomputed by tools/masks.py for a clip range starting at clip time t0."""

    def __init__(self, path, t0=0.0):
        self.arr = np.load(path, mmap_mode='r')
        self.t0 = t0

    def __call__(self, t, size=(W, H)):
        i = min(max(fr(t - self.t0), 0), len(self.arr) - 1)
        m = clean_mask(np.asarray(self.arr[i]))
        return cv2.resize(m, size, interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0


def hit_env(t, hits, decay=10.0):
    """1 on a bass hit, decaying exponentially; 0 far from hits."""
    since = min((t - h for h in hits if h <= t + 1e-6), default=99)
    return math.exp(-max(since, 0) * decay)


def punch(img, t, hits, strength=0.06, shake_px=7, decay=10.0):
    k = hit_env(t, hits, decay)
    if k < 0.01:
        return img
    rng = np.random.default_rng(int(t * 1000))
    dx, dy = rng.normal(0, shake_px * k, 2)
    return camera(img, zoom=1 + strength * k, dx=dx, dy=dy, angle=rng.normal(0, 0.5 * k))


def run(workdir, segments, fns, song, end, out_name, only=None, final=True, target_mb=None, grade=GRADE):
    names = only or list(segments)
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {n: ex.submit(_render, workdir, n, segments[n], fns[n]) for n in names}
        for n, f in futs.items():
            print(f'{n}: {f.result()} frames', file=sys.stderr)
    if final:
        finalize(workdir, list(segments), song, end, out_name, target_mb, grade)


def _render(workdir, name, span, fn):
    t0, t1 = span
    n = fr(t1) - fr(t0)
    w = Writer(os.path.join(workdir, f'{name}.seg.mkv'))
    fn(w, t0, n)
    w.close()
    return n


def finalize(workdir, names, song, end, out_name, target_mb=None, grade=GRADE):
    lst = os.path.join(workdir, 'segments.txt')
    with open(lst, 'w') as fh:
        fh.writelines(f"file '{n}.seg.mkv'\n" for n in names)
    common = ['-profile:v', 'high', '-level', '4.2', '-r', str(FPS), '-g', '120', '-color_primaries', 'bt709',
              '-color_trc', 'bt709', '-colorspace', 'bt709']
    inputs = ['-f', 'concat', '-safe', '0', '-i', lst, '-i', song, '-vf', grade,
              '-af', f'afade=t=out:st={end - 0.25}:d=0.25', '-map', '0:v', '-map', '1:a', '-t', str(end)]
    master = os.path.join(workdir, f'{out_name}.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', *common,
                    '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart', master], check=True)
    print(master)
    if target_mb:
        # Two-pass copy under a size cap (chat upload limit).
        out = os.path.join(workdir, f'{out_name}_{target_mb:g}mb.mp4')
        kbps = int(target_mb * 8 * 1024 * 0.97 / end) - 192
        log = os.path.join(workdir, 'x264pass')
        for p in (1, 2):
            dst = [out] if p == 2 else ['-f', 'mp4', os.devnull]
            subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-c:v', 'libx264', '-preset', 'slow',
                            '-b:v', f'{kbps}k', '-maxrate', f'{int(kbps * 1.5)}k', '-bufsize', f'{kbps * 2}k',
                            '-pass', str(p), '-passlogfile', log, *common, '-c:a', 'aac', '-b:a', '192k',
                            '-ar', '48000', '-movflags', '+faststart', *dst], check=True)
        print(out)
