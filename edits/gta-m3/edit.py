#!/usr/bin/env python3
"""Three TikTok car edits of the GTA V BMW M3 E46 clip (s09_flacari_si_pops.mp4, 1080x1920 60 fps) on
Romanian songs trending on Shazam Romania (13 Oct 2026). Songs are the official 30 s previews (Deezer).

  v1  Minelli - Full Option          103 BPM  J + I: cut on every 2nd bass, early cuts, zoom blur, roll
  v2  Ursaru & co - Gagica-ta        86 BPM   H: calm hook with V12 revs + flame pops, riser, drop at 4.32
  v3  Vescan & Bianca Mares -
      Absenta Ta                     92 BPM   glide: every 2 beats, RIFE slow motion on the flames

Audio is pre-mixed here (song window + the game sound with the voice-over removed by demucs + procedural
SFX from tools/sfx.py: revs, exhaust pops, bangs, whooshes, impacts, riser), then encoded once by editkit.

  python3 edits/gta-m3/edit.py work/ed4 v1 [--target-mb 29] [--check]
Work dir: src.mp4 (the clip), prep/s1_slow.mkv, s9_slow.mkv, s15_slow.mkv (2x slow motion of 0.45, 14.90,
24.85 + 0.75 s), game.wav (demucs no_vocals), songs/*.wav.
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
import sfx  # noqa: E402
import transitions as tr  # noqa: E402

# Source clips: name -> (file, seconds available). 'm' times are clip time; slow clips start at 0.
SRC = {'m': ('src.mp4', 27.8), 's1': ('prep/s1_slow.mkv', 1.5), 's9': ('prep/s9_slow.mkv', 1.5),
       's15': ('prep/s15_slow.mkv', 1.5)}
SLOW_ORIGIN = {'s1': 0.45, 's9': 14.90, 's15': 24.85}  # clip time of a slow clip's first frame
CLIP_CUTS = [5.65, 7.217, 11.05, 11.8, 23.25, 24.8, 26.233]  # hard cuts inside the source clip

SONG = {'v1': ('songs/full_option.wav', 0.0), 'v2': ('songs/gagica_ta.wav', 6.92), 'v3': ('songs/absenta_ta.wav', 0.0)}
END = {'v1': 15.70, 'v2': 15.60, 'v3': 15.30}

# Song-time beats/hits converted to edit time (minus the window start).
_FO_BASS = [1.47, 2.04, 2.62, 3.19, 3.78, 4.35, 4.93, 5.5, 6.1, 6.65, 7.24, 7.81, 8.39, 8.96, 9.54, 10.12, 10.7,
            11.27, 11.85, 12.42, 13.01, 13.58, 14.16, 14.73, 15.33]
_GT_BEATS = [11.24, 11.94, 12.63, 13.33, 14.02, 14.72, 15.42, 16.11, 16.81, 17.51, 18.2, 18.9, 19.6, 20.29, 20.99,
             21.69, 22.41]
_AT_BEATS = [0.07, 0.63, 1.28, 1.93, 2.58, 3.25, 3.88, 4.55, 5.18, 5.85, 6.5, 7.15, 7.8, 8.45, 9.1, 9.75, 10.4,
             11.08, 11.73, 12.38, 13.03, 13.68, 14.33, 14.98]
HITS = {'v1': _FO_BASS, 'v2': [round(b - 6.92, 3) for b in _GT_BEATS], 'v3': _AT_BEATS}
EARLY = {'v1': 1}

# (start, end, src, in-point, fx). fx: fadein push pushfast zoomin zoomout whipin roll punchout jump
#   flames (exhaust pops in the mix) final flash
SHOTS = {
    'v1': [
        (0.00, 1.47, 'm', 5.70, {'fadein', 'push', 'rev'}),
        (1.47, 2.62, 'm', 0.50, {'flames', 'impact'}),
        (2.62, 3.78, 'm', 8.65, {'flames', 'zoomin'}),
        (3.78, 4.93, 'm', 3.50, set()),
        (4.93, 6.10, 'm', 14.95, {'flames', 'whipin'}),
        (6.10, 7.24, 'm', 11.81, {'roll'}),
        (7.24, 8.39, 'm', 19.70, {'flames', 'zoomin'}),
        (8.39, 8.96, 'm', 22.55, set()),
        (8.96, 9.54, 'm', 23.30, {'push'}),
        (9.54, 10.70, 'm', 24.85, {'flames', 'whipin'}),
        (10.70, 11.85, 'm', 16.60, {'punchout'}),
        (11.85, 13.01, 'm', 13.60, set()),
        (13.01, 13.58, 'm', 10.47, {'whipin'}),
        (13.58, 14.16, 'm', 18.90, set()),
        (14.16, 15.70, 'm', 26.25, {'flames', 'final'}),
    ],
    'v2': [
        (0.00, 0.95, 'm', 22.28, {'fadein', 'push'}),
        (0.95, 1.85, 'm', 23.27, {'push', 'rev'}),
        (1.85, 4.32, 'm', 0.00, {'flames', 'zoomout', 'riser'}),
        (4.32, 5.71, 'm', 8.65, {'flames', 'impact', 'flash'}),
        (5.71, 7.10, 'm', 14.95, {'flames', 'zoomin'}),
        (7.10, 7.80, 'm', 11.85, {'roll'}),
        (7.80, 8.50, 'm', 11.07, {'whipin'}),
        (8.50, 9.89, 'm', 19.70, {'flames'}),
        (9.89, 10.59, 'm', 3.55, set()),
        (10.59, 11.28, 'm', 5.95, {'zoomin'}),
        (11.28, 12.68, 'm', 24.82, {'flames'}),
        (12.68, 13.37, 'm', 7.30, set()),
        (13.37, 14.07, 'm', 13.90, {'whipin'}),
        (14.07, 14.77, 'm', 16.80, {'push'}),
        (14.77, 15.60, 'm', 26.50, {'flames', 'final'}),
    ],
    'v3': [
        (0.00, 1.28, 'm', 16.60, {'fadein', 'push'}),
        (1.28, 2.58, 's1', 0.00, {'flames', 'zoomin'}),
        (2.58, 3.88, 'm', 5.75, {'push'}),
        (3.88, 5.18, 's9', 0.00, {'flames', 'zoomin'}),
        (5.18, 5.85, 'm', 22.55, {'push'}),
        (5.85, 6.50, 'm', 23.30, {'push'}),
        (6.50, 7.80, 'm', 19.70, {'flames', 'whipin'}),
        (7.80, 9.10, 'm', 8.70, {'flames'}),
        (9.10, 10.40, 'm', 13.60, set()),
        (10.40, 11.73, 's15', 0.00, {'flames', 'zoomin'}),
        (11.73, 12.38, 'm', 3.50, set()),
        (12.38, 13.03, 'm', 11.08, {'whipin'}),
        (13.03, 14.33, 'm', 26.30, {'flames'}),
        (14.33, 15.30, 'm', 11.81, {'roll', 'final'}),
    ],
}

D = None
V = None


def look(img):
    if V == 'v1':
        return 0.5 * img + 0.5 * looks.punchy(img)
    if V == 'v2':
        x = np.clip((img - 128.0) * 1.08 + 128.0 - 4, 0, 255)  # a touch more contrast, deeper blacks
        return x
    return 0.6 * img + 0.4 * looks.warm_natural(img)


def env(t, times, decay):
    since = min((t - b for b in times if b <= t + 1e-6), default=99)
    return math.exp(-max(since, 0) * decay)


def timeline(v):
    e = EARLY.get(v, 0) / ek.FPS
    out = []
    shots = SHOTS[v]
    for i, s in enumerate(shots):
        a = s[0] - (e if i else 0)
        b = s[1] - e if i + 1 < len(shots) else s[1]
        out.append((round(a, 4), round(b, 4), s))
    return out


def clip_range(src, at, dur):
    """Original clip-time range a shot covers (slow clips cover half their duration)."""
    if src == 'm':
        return at, at + dur
    o = SLOW_ORIGIN[src] + at / 2
    return o, o + dur / 2


def source_times(v, s0, at, n, fx):
    inner = [b for b in HITS[v] if s0 + 0.05 < b < s0 + n / ek.FPS - 0.05]
    out = []
    for i in range(n):
        t = s0 + i / ek.FPS
        skips = sum(1 for b in inner if b <= t) if 'jump' in fx else 0
        out.append(at + i / ek.FPS + 0.15 * skips)
    return out


def check(v):
    prev, used = 0.0, []
    for s0, s1, (_, _, src, at, fx) in timeline(v):
        assert abs(s0 - prev) < 1e-3, f'{v}: gap at {s0}'
        prev = s1
        n = ek.fr(s1) - ek.fr(s0)
        times = source_times(v, s0, at, n, fx)
        need = times[-1] + 1 / ek.FPS
        assert need <= SRC[src][1] + 0.025, f'{v}: {src}@{at} needs {need:.2f}s'
        a, b = clip_range(src, at, need - at)
        if src == 'm':
            assert not any(a + 0.02 < c < b - 0.02 for c in CLIP_CUTS), f'{v}: m@{at} crosses a clip cut'
        for u0, u1 in used:
            assert a >= u1 - 0.02 or b <= u0 + 0.02, f'{v}: {src}@{at} repeats footage ({a:.2f}-{b:.2f})'
        used.append((a, b))
    assert abs(prev - END[v]) < 1e-3, f'{v}: ends at {prev}'


def render(item, out, t0, n):
    s0, s1, (_, _, src, at, fx) = item
    times = source_times(V, s0, at, n, fx)
    span = times[-1] - at + 1 / ek.FPS
    raw = ek.read(os.path.join(D, SRC[src][0]), at, int(round(span * ek.FPS)) + 1)
    hits = HITS[V]
    last_angle = None
    for i, ct in enumerate(times):
        t = t0 + i / ek.FPS
        k = t - s0
        p = i / max(1, n - 1)
        img = raw[min(int(round((ct - at) * ek.FPS)), len(raw) - 1)].astype(np.float32)
        if 'push' in fx:
            img = camera(img, zoom=1.0 + 0.06 * p ** 1.3)
        if 'punchout' in fx:
            jumps = sum(1 for b in hits if s0 + 0.05 < b <= t)
            img = camera(img, zoom=[1.16, 1.07, 1.0][min(jumps, 2)])
        if 'roll' in fx:
            ang = 9 * (1 - (1 - min(1.0, i / 18)) ** 3)
            img = tr.roll(img, ang, last_angle)
            last_angle = ang
        if 'zoomout' in fx and i >= n - 8:
            img = tr.zoom_blur(img, (i - (n - 8)) / 7, out=True)
        if 'zoomin' in fx and i < 6:
            img = tr.zoom_blur(img, i / 5, out=False)
        if 'whipin' in fx and i < 5:
            img = tr.whip(img, -(1 - i / 5), direction=1)
        img = look(img)
        if 'fadein' in fx:
            img *= min(1.0, k / 0.35)
        if 'flash' in fx:
            img = tr.flash_in(img, 0.75 * math.exp(-k * 12))
        if 'final' in fx:
            hit = hits[-1] if hits[-1] >= s0 else s0
            if t >= hit:
                img = tr.flash_in(img, 0.8 * math.exp(-(t - hit) * 10))
                if t > hit + 0.12:
                    img = tr.fade(img, (t - hit - 0.12) / max(0.1, s1 - hit - 0.15))
        e = env(t + EARLY.get(V, 0) / ek.FPS, hits, 11)
        out.write(camera(img, zoom=1 + 0.035 * e) if e > 0.01 else img)


# ---------------- audio ----------------

def load_wav(path, start=0.0, dur=None):
    import soundfile as sf
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    if sr != sfx.SR:
        import librosa
        x = librosa.resample(x.T, orig_sr=sr, target_sr=sfx.SR).T
    if x.shape[1] == 1:
        x = np.repeat(x, 2, 1)
    a = int(start * sfx.SR)
    b = len(x) if dur is None else a + int(dur * sfx.SR)
    return x[a:b]


def place(mix, sig, at, gain=1.0):
    s = int(round(at * sfx.SR))
    if s < 0:
        sig, s = sig[-s:], 0
    e = min(len(mix), s + len(sig))
    if e > s:
        mix[s:e] += sig[:e - s] * gain


def build_audio(v, path):
    import soundfile as sf
    end = END[v]
    n = int(end * sfx.SR)
    song_path, w0 = SONG[v]
    song = load_wav(os.path.join(D, song_path), w0, end)
    song = np.pad(song, ((0, max(0, n - len(song))), (0, 0)))[:n]
    fx_bus = np.zeros((n, 2), np.float32)
    game = load_wav(os.path.join(D, 'game.wav'))
    duck = np.ones(n, np.float32)
    seed = {'v1': 10, 'v2': 20, 'v3': 30}[v]
    for i, (s0, s1, (_, _, src, at, fx)) in enumerate(timeline(v)):
        dur = s1 - s0
        # Real game exhaust under every real-time shot (voice-over removed), boosted.
        if src == 'm':
            a = int(at * sfx.SR)
            g = game[a:a + int(dur * sfx.SR)]
            g = g * np.minimum(1.0, np.arange(len(g))[:, None] / (0.02 * sfx.SR))
            place(fx_bus, g, s0, 6.0)
        if 'flames' in fx:
            place(fx_bus, sfx.pops(min(dur, 1.3), rate=16, seed=seed + i), s0 + 0.03, 0.55)
            place(fx_bus, sfx.bang(seed=seed + i), s0, 0.5)
            duck[int(s0 * sfx.SR):int(min(s1, s0 + 0.6) * sfx.SR)] = 0.8
        if 'rev' in fx:
            r = sfx.rev(min(2.2, dur + 0.4), seed=seed + i)
            place(fx_bus, r, max(0.0, s1 - len(r) / sfx.SR + 0.25), 0.55)
        if 'riser' in fx:
            r = sfx.riser(min(2.0, dur))
            place(fx_bus, r, s1 - len(r) / sfx.SR, 0.45)
        if 'impact' in fx or (i and s0 in HITS[v][:1]):
            place(fx_bus, sfx.impact(seed=seed + i), s0, 0.75)
        if fx & {'whipin', 'zoomin'}:
            w = sfx.whoosh(0.45, seed=seed + i, pan_from=-0.9 if i % 2 else 0.9, pan_to=0.9 if i % 2 else -0.9)
            place(fx_bus, w, s0 - 0.25, 0.5)
        if 'zoomout' in fx:
            place(fx_bus, sfx.whoosh(0.5, seed=seed + 50 + i), s1 - 0.3, 0.5)
        if 'final' in fx:
            hit = max(HITS[v][-1], s0)
            place(fx_bus, sfx.impact(seed=seed + 99), hit, 0.85)
            place(fx_bus, sfx.pops(0.9, rate=20, seed=seed + 98), hit + 0.05, 0.5)
    duck = np.convolve(duck, np.ones(2400) / 2400, mode='same')[:, None]
    mix = song * 0.85 * duck + fx_bus
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)  # soft limiter
    mix = mix / max(1e-6, np.max(np.abs(mix))) * 0.95
    sf.write(path, mix.astype(np.float32), sfx.SR)
    return path


def main():
    global D, V
    ap = argparse.ArgumentParser()
    ap.add_argument('workdir')
    ap.add_argument('variant', choices=list(SHOTS))
    ap.add_argument('--target-mb', type=float)
    ap.add_argument('--seg', action='append')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--audio-only', action='store_true')
    a = ap.parse_args()
    D, V = a.workdir, a.variant
    check(V)
    if a.check:
        print(f'{V}: {len(SHOTS[V])} shots OK')
        return
    mix = build_audio(V, os.path.join(D, f'mix_{V}.wav'))
    if a.audio_only:
        print(mix)
        return
    items = timeline(V)
    segs = {f'{V}_{i:02d}': (it[0], it[1]) for i, it in enumerate(items)}
    fns = {f'{V}_{i:02d}': functools.partial(render, it) for i, it in enumerate(items)}
    ek.run(D, segs, fns, mix, END[V], f'gta_m3_{V}', only=a.seg, target_mb=a.target_mb,
           grade='unsharp=5:5:0.3:5:5:0,format=yuv420p')


if __name__ == '__main__':
    main()
