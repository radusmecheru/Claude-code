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
    """Near-lossless RGB intermediate (x264rgb CRF 4, ~5x smaller than -qp 0); the real encode is finalize()."""

    def __init__(self, path):
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                                   '-r', str(FPS), '-i', '-', '-c:v', 'libx264rgb', '-crf', '4', '-preset', 'veryfast',
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


def run(workdir, segments, fns, song, end, out_name, only=None, final=True, target_mb=None, grade=GRADE,
        extra_audio=()):
    """fns[name] must be picklable (a top-level function or functools.partial of one)."""
    names = only or list(segments)
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {n: ex.submit(_render, workdir, n, segments[n], fns[n]) for n in names}
        for n, f in futs.items():
            print(f'{n}: {f.result()} frames', file=sys.stderr)
    if final:
        finalize(workdir, list(segments), song, end, out_name, target_mb, grade, extra_audio)


def _render(workdir, name, span, fn):
    t0, t1 = span
    n = fr(t1) - fr(t0)
    w = Writer(os.path.join(workdir, f'{name}.seg.mkv'))
    fn(w, t0, n)
    w.close()
    return n


def audio_graph(extra, end, first_input=2):
    """Song (input 1) ducked under clip sounds, plus each clip sound placed on the song timeline.
    extra: [{'path', 'src_in', 'at', 'dur', 'gain', 'duck'}] -> (ffmpeg input args, filter_complex, out label)."""
    args, chains, labels = [], [], []
    ducks = [f"between(t,{e['at'] - 0.05:.3f},{e['at'] + e['dur']:.3f})" for e in extra if e.get('duck')]
    vol = f"if({'+'.join(ducks)},0.5,1)" if ducks else '1'
    chains.append(f"[1:a]aresample=48000,volume='{vol}':eval=frame[song]")
    for i, e in enumerate(extra):
        k = first_input + i
        args += ['-i', e['path']]
        ms = int(round(e['at'] * 1000))
        chains.append(f"[{k}:a:0]atrim=start={e['src_in']:.3f}:duration={e['dur']:.3f},asetpts=PTS-STARTPTS,"
                      f"aresample=48000,afade=t=in:d=0.04,afade=t=out:st={max(0.0, e['dur'] - 0.12):.3f}:d=0.12,"
                      f"volume={e['gain']},adelay={ms}|{ms}[e{i}]")
        labels.append(f'[e{i}]')
    chains.append(f"[song]{''.join(labels)}amix=inputs={1 + len(labels)}:normalize=0:dropout_transition=0,"
                  f"alimiter=limit=0.95,afade=t=out:st={end - 0.25}:d=0.25[aout]")
    return args, ';'.join(chains), '[aout]'


def finalize(workdir, names, song, end, out_name, target_mb=None, grade=GRADE, extra_audio=()):
    lst = os.path.join(workdir, f'{out_name}_segments.txt')
    with open(lst, 'w') as fh:
        fh.writelines(f"file '{n}.seg.mkv'\n" for n in names)
    common = ['-profile:v', 'high', '-level', '4.2', '-r', str(FPS), '-g', '120', '-color_primaries', 'bt709',
              '-color_trc', 'bt709', '-colorspace', 'bt709']
    a_args, a_graph, a_out = audio_graph(list(extra_audio), end)
    inputs = ['-f', 'concat', '-safe', '0', '-i', lst, '-i', song, *a_args,
              '-filter_complex', f'[0:v]{grade}[vout];{a_graph}', '-map', '[vout]', '-map', a_out, '-t', str(end)]
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


def bass_returns(song, lo=150, gap_level=0.4, back_level=0.8, window=0.1):
    """Times where the sub-bass (< lo Hz) comes back after a drop-out: energy rises from under gap_level x
    median to over back_level x median within `window` s. Returns (gaps, returns) as lists of seconds."""
    import librosa
    y, sr = librosa.load(song, sr=22050, mono=True)
    hop = 256
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    e = S[f < lo].mean(0)
    med = np.median(e[e > 0]) if (e > 0).any() else 1.0
    t = librosa.frames_to_time(np.arange(len(e)), sr=sr, hop_length=hop)
    w = max(1, int(window * sr / hop))
    gaps, rets = [], []
    i = 0
    while i < len(e) - w:
        if e[i] < gap_level * med:
            j = i
            while j < len(e) and e[j] < gap_level * med:
                j += 1
            if j < len(e) and (j - i) * hop / sr > 0.15:
                gaps.append(round(float(t[i]), 3))
                if (e[j:j + w] > back_level * med).any():
                    rets.append(round(float(t[j]), 3))
            i = j + 1
        else:
            i += 1
    return gaps, rets


def match_inpoint(path, planned, dx_target, search=0.5, frames=4):
    """In-point near `planned` (s) whose first `frames` frames move horizontally like dx_target
    (mean Farneback dx, px/frame at 320 px wide): same sign, closest magnitude. Keeps slides continuous
    across a cut (r7 style)."""
    best, best_err = planned, 1e9
    for k in range(-int(search * 10), int(search * 10) + 1):
        t = max(0.0, planned + k / 10)
        fr_ = read(path, t, frames + 1, size=(320, 568))
        g = [cv2.cvtColor(x, cv2.COLOR_BGR2GRAY) for x in fr_]
        dx = np.mean([cv2.calcOpticalFlowFarneback(g[i], g[i + 1], None, 0.5, 3, 15, 3, 5, 1.2, 0)[..., 0].mean()
                      for i in range(frames)])
        if np.sign(dx) != np.sign(dx_target):
            continue
        err = abs(dx - dx_target)
        if err < best_err:
            best, best_err = t, err
    return best


def shot_dx(path, t_end, frames=4):
    """Mean horizontal motion (px/frame at 320 px wide) over the last `frames` frames before t_end."""
    fr_ = read(path, max(0.0, t_end - (frames + 1) / FPS), frames + 1, size=(320, 568))
    g = [cv2.cvtColor(x, cv2.COLOR_BGR2GRAY) for x in fr_]
    return float(np.mean([cv2.calcOpticalFlowFarneback(g[i], g[i + 1], None, 0.5, 3, 15, 3, 5, 1.2, 0)[..., 0].mean()
                          for i in range(frames)]))


def early(times, frames=1):
    """Shift cut times `frames` frames before the beat (r7 cuts land ~1 frame early - feels tighter)."""
    return [round(t - frames / FPS, 4) for t in times]
