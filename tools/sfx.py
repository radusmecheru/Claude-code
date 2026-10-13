#!/usr/bin/env python3
"""Procedural sound effects for car edits (48 kHz stereo WAV, no third-party samples needed).

  whoosh   filtered-noise sweep with a doppler pitch bend - transitions, whips, fly-bys
  impact   sub boom + noise crack - drops, hard cuts, flashes
  riser    noise + tone sweeping up into a drop
  pops     exhaust crackle: random bursts of short decaying pops (overrun / anti-lag)
  rev      V12-style rev: harmonic stack on the firing frequency with a throttle curve, then pops on lift
  bang     single loud backfire

  python3 tools/sfx.py pack out_dir/           # writes one of each (variants) for preview
  from sfx import whoosh, impact, ...; write(path, sig)
"""
import os
import sys

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000


def _t(d):
    return np.arange(int(d * SR)) / SR


def _bp(x, lo, hi, order=2):
    sos = butter(order, [lo / (SR / 2), min(hi / (SR / 2), 0.99)], btype='band', output='sos')
    return sosfilt(sos, x)


def _lp(x, f, order=2):
    return sosfilt(butter(order, min(f / (SR / 2), 0.99), btype='low', output='sos'), x)


def _hp(x, f, order=2):
    return sosfilt(butter(order, f / (SR / 2), btype='high', output='sos'), x)


def _norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def _stereo(x, width=0.0, seed=0):
    if width <= 0:
        return np.stack([x, x], 1)
    rng = np.random.default_rng(seed)
    d = int(rng.uniform(0.0003, 0.0009) * SR)
    y = np.concatenate([np.zeros(d), x[:-d]])
    return np.stack([x * (1 - width / 2) + y * width / 2, y * (1 - width / 2) + x * width / 2], 1)


def whoosh(d=0.6, seed=0, pan_from=-0.8, pan_to=0.8):
    rng = np.random.default_rng(seed)
    t = _t(d)
    n = rng.normal(0, 1, len(t))
    env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    # Sweep a band through the noise (block-wise), high -> low like a doppler pass.
    out = np.zeros_like(n)
    blocks = 24
    for b in range(blocks):
        s, e = len(n) * b // blocks, len(n) * (b + 1) // blocks
        p = b / (blocks - 1)
        c = 2500 * (1 - p) + 350 * p
        out[s:e] = _bp(n, c * 0.6, c * 1.6)[s:e]
    out *= env
    pan = np.linspace(pan_from, pan_to, len(t))
    l, r = out * np.sqrt((1 - pan) / 2), out * np.sqrt((1 + pan) / 2)
    return _norm(np.stack([l, r], 1), 0.8)


def impact(d=1.4, seed=0):
    rng = np.random.default_rng(seed)
    t = _t(d)
    f = 55 * np.exp(-t * 3) + 32  # pitch drop
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    crack = _hp(rng.normal(0, 1, len(t)), 1500) * np.exp(-t * 28)
    body = _bp(rng.normal(0, 1, len(t)), 80, 600) * np.exp(-t * 9)
    x = sub * 1.0 + crack * 0.35 + body * 0.35
    return _stereo(_norm(np.tanh(x * 1.8)), 0.3, seed)


def riser(d=2.0, seed=0):
    rng = np.random.default_rng(seed)
    t = _t(d)
    p = t / d
    n = rng.normal(0, 1, len(t))
    out = np.zeros_like(n)
    blocks = 32
    for b in range(blocks):
        s, e = len(n) * b // blocks, len(n) * (b + 1) // blocks
        c = 300 + 5000 * (b / (blocks - 1)) ** 2
        out[s:e] = _bp(n, c * 0.7, c * 1.4)[s:e]
    tone = np.sin(2 * np.pi * np.cumsum(120 + 900 * p ** 2) / SR) * 0.25
    x = (out + tone) * p ** 2.2
    x[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return _stereo(_norm(x, 0.75), 0.6, seed)


def _pop(rng, loud=1.0):
    d = rng.uniform(0.03, 0.09)
    t = _t(d)
    n = rng.normal(0, 1, len(t))
    body = _bp(n, rng.uniform(60, 120), rng.uniform(1200, 3500)) * np.exp(-t * rng.uniform(40, 90))
    thump = np.sin(2 * np.pi * rng.uniform(45, 80) * t) * np.exp(-t * 35)
    return np.tanh((body * 2.2 + thump * 1.2) * loud * 2.5)


def pops(d=1.2, rate=14, seed=0, loud=1.0):
    """Exhaust crackle: Poisson pops, louder and denser at the start (like lifting off the throttle)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(d * SR))
    t = 0.0
    while t < d:
        k = 1 - t / d
        p = _pop(rng, loud * (0.4 + 0.6 * k) * rng.uniform(0.5, 1.0))
        s = int(t * SR)
        e = min(len(out), s + len(p))
        out[s:e] += p[:e - s]
        t += rng.exponential(1 / (rate * (0.4 + 0.8 * k)))
    out = out + _lp(out, 300) * 0.8  # exhaust resonance
    return _stereo(_norm(out, 0.9), 0.4, seed)


def bang(seed=0):
    rng = np.random.default_rng(seed)
    t = _t(0.5)
    n = rng.normal(0, 1, len(t))
    x = _lp(n, 2500) * np.exp(-t * 18) + np.sin(2 * np.pi * 50 * t) * np.exp(-t * 10) * 1.2
    return _stereo(_norm(np.tanh(x * 3)), 0.3, seed)


def rev(d=2.2, seed=0, cylinders=12, idle=1200, peak=8800, with_pops=True):
    """V12-style rev: blip up fast, hold, lift; harmonic stack on the firing frequency, rough combustion,
    exhaust low-pass + resonances, pops on the lift."""
    rng = np.random.default_rng(seed)
    t = _t(d)
    p = t / d
    up = np.clip(p / 0.35, 0, 1) ** 0.6
    down = np.clip((p - 0.55) / 0.35, 0, 1)
    rpm = idle + (peak - idle) * (up - down * 0.85)
    rpm = np.maximum(rpm, idle)
    f0 = rpm / 60 * cylinders / 2  # firing frequency of a 4-stroke
    phase = 2 * np.pi * np.cumsum(f0) / SR
    x = np.zeros_like(t)
    for h, a in [(0.5, 0.6), (1, 1.0), (1.5, 0.35), (2, 0.55), (3, 0.3), (4, 0.18), (6, 0.08)]:
        x += a * np.sin(h * phase + rng.uniform(0, 6.28))
    rough = 1 + 0.25 * _lp(rng.normal(0, 1, len(t)), 60)
    x *= rough
    noise = _bp(rng.normal(0, 1, len(t)), 200, 4000) * (0.15 + 0.35 * up)
    load = 0.35 + 0.65 * (up - down)
    x = (x * load + noise) * np.clip(p / 0.02, 0, 1) * np.clip((1 - p) / 0.05, 0, 1)
    x = np.tanh(x * 1.6) + _lp(x, 250) * 0.8
    sig = _stereo(_norm(x, 0.8), 0.25, seed)
    if with_pops:
        ps = pops(d * 0.4, rate=18, seed=seed + 1)
        s = int(d * 0.58 * SR)
        e = min(len(sig), s + len(ps))
        sig[s:e] += ps[:e - s] * 0.9
    return np.clip(sig, -1, 1) * 0.95


def write(path, sig):
    import soundfile as sf
    sf.write(path, np.asarray(sig, np.float32), SR)


def main():
    if len(sys.argv) != 3 or sys.argv[1] != 'pack':
        sys.exit(__doc__)
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for i in range(3):
        write(os.path.join(out, f'whoosh_{i}.wav'), whoosh(0.5 + 0.15 * i, seed=i))
        write(os.path.join(out, f'impact_{i}.wav'), impact(seed=i))
        write(os.path.join(out, f'pops_{i}.wav'), pops(1.0 + 0.3 * i, seed=i))
        write(os.path.join(out, f'rev_{i}.wav'), rev(2.0 + 0.3 * i, seed=i))
        write(os.path.join(out, f'bang_{i}.wav'), bang(seed=i))
    write(os.path.join(out, 'riser.wav'), riser())
    print(out)


if __name__ == '__main__':
    main()
