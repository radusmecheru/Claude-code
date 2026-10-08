#!/usr/bin/env python3
"""Car-edit effects in the style of TikTok #caredit videos.

Subcommands (all output 1080x1920 unless --size is given):
  mask     subject alpha mask for a clip (rembg), saved as a grayscale video
  neon     glowing outline on the subject (dark body, electric edges)
  popout   cut-out of one clip floating over another clip, sliding in
  trace    a light streak running around the subject's contour
  portal   reveal clip B through a circle in clip A (wheel / lens), then zoom through
  ramp     speed ramp with frame-blended motion blur
  shake    beat-synced camera shake / zoom punches
  beats    print beat times of an audio track as JSON

Every effect reads and writes plain video files so they chain with ffmpeg.
"""
import argparse
import json
import math
import subprocess
import sys

import cv2
import numpy as np

W, H = 1080, 1920


# ---------- video IO ----------

def probe(path):
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=width,height,r_frame_rate,nb_frames:format=duration', '-of', 'json', path],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d['streams'][0]
    num, den = s['r_frame_rate'].split('/')
    return int(s['width']), int(s['height']), float(num) / float(den), float(d['format']['duration'])


def read_frames(path, size=(W, H), fps=None, gray=False):
    """Yield frames scaled and center-cropped to fill `size`."""
    w, h = size
    vf = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
    if fps:
        vf += f',fps={fps}'
    pix = 'gray' if gray else 'bgr24'
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf, '-f', 'rawvideo', '-pix_fmt', pix, '-'],
                         stdout=subprocess.PIPE)
    n = w * h * (1 if gray else 3)
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            f = np.frombuffer(buf, np.uint8)
            yield f.reshape(h, w) if gray else f.reshape(h, w, 3)
    finally:
        p.stdout.close()
        p.wait()


class Writer:
    def __init__(self, path, fps, size=(W, H), gray=False, audio=None, crf=16):
        w, h = size
        cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray' if gray else 'bgr24',
               '-s', f'{w}x{h}', '-r', str(fps), '-i', '-']
        if audio:
            cmd += ['-i', audio, '-map', '0:v', '-map', '1:a?', '-c:a', 'aac', '-b:a', '192k', '-shortest']
        cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf), '-pix_fmt', 'yuv420p', path]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame):
        self.p.stdin.write(np.ascontiguousarray(frame, np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def ease(t):
    """easeOutExpo-like curve used for all slide/zoom moves."""
    t = min(max(t, 0.0), 1.0)
    return 1 - math.pow(2, -10 * t) if t < 1 else 1.0


def ease_in_out(t):
    t = min(max(t, 0.0), 1.0)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def hex_bgr(h):
    h = h.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return np.array([b, g, r], np.float32)


# ---------- masks ----------

def cmd_mask(a):
    from rembg import new_session, remove
    from PIL import Image
    _, _, fps, _ = probe(a.input)
    if a.fps:
        fps = a.fps
    session = new_session(a.model)
    work = (W // a.downscale, H // a.downscale)
    out = Writer(a.output, fps, gray=True, crf=10)
    prev = None
    for i, f in enumerate(read_frames(a.input, fps=a.fps)):
        if i % a.every == 0 or prev is None:
            small = cv2.resize(f, work, interpolation=cv2.INTER_AREA)
            rgba = remove(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)), session=session,
                          only_mask=True, post_process_mask=True)
            m = cv2.resize(np.array(rgba), (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)
            # Temporal smoothing kills the flicker that per-frame segmentation produces.
            prev = m if prev is None else prev * a.smooth + m * (1 - a.smooth)
        out.write(prev)
        print(f'\rmask frame {i}', end='', file=sys.stderr)
    out.close()
    print(file=sys.stderr)


def load_mask_frames(path):
    for m in read_frames(path, gray=True):
        yield m.astype(np.float32) / 255.0


# ---------- neon outline ----------

def neon_layer(frame, mask, color, intensity=1.0, inner_edges=True):
    """Return (lit subject BGR float, alpha) — dark body with electric edges, like the reference."""
    m8 = (mask > 0.5).astype(np.uint8)
    contour = cv2.morphologyEx(m8, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8)).astype(np.float32)
    lines = contour
    if inner_edges:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, 50, 140).astype(np.float32) / 255.0
        edges *= cv2.erode(m8, np.ones((9, 9), np.uint8))
        lines = np.maximum(contour, edges * 0.8)
    glow = np.zeros_like(lines)
    for sigma, wgt in ((1.5, 1.0), (5, 0.8), (14, 0.6), (30, 0.4)):
        glow += cv2.GaussianBlur(lines, (0, 0), sigma) * wgt
    glow = np.clip(glow * intensity, 0, 1.5)[..., None]
    body = frame.astype(np.float32) * 0.35
    core = lines[..., None] * 255.0  # white-hot core of each line
    lit = body + glow * color * 1.2 + core * 0.6
    alpha = np.clip(np.maximum(mask, cv2.GaussianBlur(lines, (0, 0), 14) * 1.5), 0, 1)
    return np.clip(lit, 0, 255), alpha


def cmd_neon(a):
    _, _, fps, _ = probe(a.input)
    color = hex_bgr(a.color)
    out = Writer(a.output, fps, audio=a.input if a.keep_audio else None)
    for i, (f, m) in enumerate(zip(read_frames(a.input), load_mask_frames(a.mask))):
        p = ease(i / max(1, a.ramp_frames)) if a.ramp_frames else 1.0
        lit, alpha = neon_layer(f, m, color, intensity=p * a.intensity)
        bg = f.astype(np.float32) * (1 - a.dim_bg)
        alpha = alpha[..., None] * p
        out.write(lit * alpha + bg * (1 - alpha) if a.dim_bg else lit * alpha + f * (1 - alpha))
    out.close()


# ---------- pop-out cutout ----------

def place(layer, alpha, scale, cx, cy):
    """Scale a full-frame layer around its center and move the center to (cx, cy) in pixels."""
    M = np.float32([[scale, 0, cx - W / 2 * scale], [0, scale, cy - H / 2 * scale]])
    lay = cv2.warpAffine(layer, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    al = cv2.warpAffine(alpha, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    return lay, al


def cmd_popout(a):
    _, _, fps, _ = probe(a.bg)
    color = hex_bgr(a.color)
    out = Writer(a.output, fps, audio=a.bg if a.keep_audio else None)
    anchors = {'top': (0.5, 0.12), 'bottom': (0.5, 0.88), 'center': (0.5, 0.5)}
    ax, ay = anchors[a.anchor]
    start_y = -0.6 if a.anchor == 'top' else 1.6
    for i, (bg, fg, m) in enumerate(zip(read_frames(a.bg), read_frames(a.fg), load_mask_frames(a.mask))):
        p = ease(i / max(1, a.slide_frames))
        y = (start_y + (ay - start_y) * p) * H
        if a.neon:
            lit, al = neon_layer(fg, m, color, intensity=a.intensity)
        else:
            lit, al = fg.astype(np.float32), m
        lay, al = place(lit, al, a.scale, ax * W, y)
        # Soft drop shadow sells the "floating in front" depth.
        sh = cv2.GaussianBlur(al, (0, 0), 25)[..., None] * 0.55
        base = bg.astype(np.float32) * (1 - sh)
        al = al[..., None]
        out.write(lay * al + base * (1 - al))
    out.close()


# ---------- light trace around contour ----------

def cmd_trace(a):
    _, _, fps, _ = probe(a.input)
    color = hex_bgr(a.color)
    out = Writer(a.output, fps, audio=a.input if a.keep_audio else None)
    total = a.frames
    for i, (f, m) in enumerate(zip(read_frames(a.input), load_mask_frames(a.mask))):
        frame = f.astype(np.float32)
        if i < total:
            cs, _ = cv2.findContours((m > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if cs:
                c = max(cs, key=cv2.contourArea)[:, 0, :]
                n = len(c)
                head = ease_in_out(i / total) * n * a.loops
                tail = head - n * a.length
                idx = np.arange(int(tail), int(head)) % n
                canvas = np.zeros((H, W), np.float32)
                if len(idx) > 1:
                    pts = c[idx]
                    # Taper: thin and faint at the tail, bright at the head.
                    seg = max(1, len(pts) // 12)
                    for k in range(0, len(pts) - 1, seg):
                        t = k / len(pts)
                        cv2.polylines(canvas, [pts[k:k + seg + 1].reshape(-1, 1, 2)], False, 0.3 + 0.7 * t,
                                      thickness=max(2, int(3 + 7 * t)), lineType=cv2.LINE_AA)
                fade = 1 - max(0, (i - total * 0.8) / (total * 0.2))
                glow = canvas + cv2.GaussianBlur(canvas, (0, 0), 6) * 2.5 + cv2.GaussianBlur(canvas, (0, 0), 20) * 3
                frame = frame + (glow[..., None] * color * 0.9 + canvas[..., None] * 255) * fade
        out.write(np.clip(frame, 0, 255))
    out.close()


# ---------- circular portal transition ----------

def cmd_portal(a):
    _, _, fps, _ = probe(a.a)
    out = Writer(a.output, fps, audio=a.a if a.keep_audio else None)
    cx, cy, r0 = a.cx * W, a.cy * H, a.r * W
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    frames_b = read_frames(a.b)
    for i, fa in enumerate(read_frames(a.a)):
        t = (i - a.start) / max(1, a.dur)
        p = ease_in_out(t) if t > 0 else 0.0
        if t > 1.2:
            fb = next(frames_b, None)
            if fb is None:
                break
            out.write(fb)
            continue
        # Zoom A into the circle; the circle grows until it covers the frame.
        zoom = 1 + p * (max(W, H) * 1.6 / r0 - 1)
        M = np.float32([[zoom, 0, cx - cx * zoom], [0, zoom, cy - cy * zoom]])
        A = cv2.warpAffine(fa, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
        r = r0 * zoom
        fb = next(frames_b, None) if i >= a.start - a.hold else None
        if fb is None:
            fb = np.zeros_like(fa)
        # B is seen through the hole as a smaller full frame (fisheye-ish look), growing to full size.
        bs = 0.55 + 0.45 * p
        Mb = np.float32([[bs, 0, cx - W / 2 * bs + (W / 2 - cx) * p], [0, bs, cy - H / 2 * bs + (H / 2 - cy) * p]])
        B = cv2.warpAffine(fb, Mb, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        hole = np.clip((r - d) / 3.0, 0, 1)[..., None]
        rim = np.clip(1 - np.abs(d - r) / (0.08 * r), 0, 1)[..., None]  # dark tyre-like ring
        img = B * hole + A * (1 - hole)
        img = img * (1 - rim * 0.85)
        if i < a.start - a.hold:
            img = fa.astype(np.float32)
        out.write(np.clip(img, 0, 255))
    for fb in frames_b:
        out.write(fb)
    out.close()


# ---------- speed ramp ----------

def cmd_ramp(a):
    _, _, fps, _ = probe(a.input)
    frames = [cv2.imencode('.jpg', f, [cv2.IMWRITE_JPEG_QUALITY, 95])[1] for f in read_frames(a.input)]
    dec = lambda k: cv2.imdecode(frames[min(max(int(k), 0), len(frames) - 1)], cv2.IMREAD_COLOR).astype(np.float32)
    # keyframes "t:speed,t:speed" in output-normalised time 0..1
    keys = sorted((float(x), float(y)) for x, y in (kv.split(':') for kv in a.curve.split(',')))
    ts, ss = zip(*keys)
    out = Writer(a.output, fps)
    src = 0.0
    while src < len(frames) - 1:
        speed = float(np.interp(src / len(frames), ts, ss))
        if speed > 1.4 and a.blur:
            # Average the source frames we skip over: real motion blur instead of judder.
            n = min(int(speed), 8)
            img = sum(dec(src + k * speed / n) for k in range(n)) / n
        else:
            img = dec(src)
        out.write(img)
        src += speed
    out.close()


# ---------- shake / punch-in on beats ----------

def cmd_shake(a):
    _, _, fps, _ = probe(a.input)
    beats = json.load(open(a.beats)) if a.beats else []
    rng = np.random.default_rng(7)
    out = Writer(a.output, fps, audio=a.input if a.keep_audio else None)
    for i, f in enumerate(read_frames(a.input)):
        t = i / fps
        since = min((t - b for b in beats if b <= t), default=99)
        k = math.exp(-since * a.decay)
        zoom = 1 + a.punch * k
        dx, dy = rng.normal(0, a.amount * k, 2) * W
        ang = rng.normal(0, a.amount * 40 * k)
        M = cv2.getRotationMatrix2D((W / 2, H / 2), ang, zoom)
        M[:, 2] += (dx, dy)
        img = cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        if a.blur and k > 0.3:
            img = cv2.addWeighted(img, 0.6, cv2.blur(img, (1, int(30 * k) | 1)), 0.4, 0)
        out.write(img)
    out.close()


def cmd_beats(a):
    import librosa
    y, sr = librosa.load(a.input, sr=22050, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    times = librosa.frames_to_time(frames, sr=sr)
    strong = [float(round(t, 3)) for t, fr in zip(times, frames) if onset[fr] > np.percentile(onset, 75)]
    json.dump({'tempo': float(np.atleast_1d(tempo)[0]), 'beats': [float(round(t, 3)) for t in times],
               'strong': strong}, sys.stdout, indent=1)
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('mask'); p.add_argument('input'); p.add_argument('output')
    p.add_argument('--model', default='isnet-general-use', help='u2netp = fast draft, birefnet-general-lite = best')
    p.add_argument('--downscale', type=int, default=2); p.add_argument('--every', type=int, default=1)
    p.add_argument('--smooth', type=float, default=0.35); p.add_argument('--fps', type=float)
    p.set_defaults(fn=cmd_mask)

    p = sub.add_parser('neon'); p.add_argument('input'); p.add_argument('mask'); p.add_argument('output')
    p.add_argument('--color', default='#1E90FF'); p.add_argument('--intensity', type=float, default=1.0)
    p.add_argument('--ramp-frames', type=int, default=6); p.add_argument('--dim-bg', type=float, default=0.0)
    p.add_argument('--keep-audio', action='store_true'); p.set_defaults(fn=cmd_neon)

    p = sub.add_parser('popout'); p.add_argument('bg'); p.add_argument('fg'); p.add_argument('mask')
    p.add_argument('output'); p.add_argument('--anchor', choices=['top', 'bottom', 'center'], default='top')
    p.add_argument('--scale', type=float, default=0.75); p.add_argument('--slide-frames', type=int, default=10)
    p.add_argument('--neon', action='store_true'); p.add_argument('--color', default='#1E90FF')
    p.add_argument('--intensity', type=float, default=1.0); p.add_argument('--keep-audio', action='store_true')
    p.set_defaults(fn=cmd_popout)

    p = sub.add_parser('trace'); p.add_argument('input'); p.add_argument('mask'); p.add_argument('output')
    p.add_argument('--frames', type=int, default=30); p.add_argument('--length', type=float, default=0.25)
    p.add_argument('--loops', type=float, default=1.0); p.add_argument('--color', default='#FFFFFF')
    p.add_argument('--keep-audio', action='store_true'); p.set_defaults(fn=cmd_trace)

    p = sub.add_parser('portal'); p.add_argument('a'); p.add_argument('b'); p.add_argument('output')
    p.add_argument('--cx', type=float, required=True, help='circle centre x, 0..1')
    p.add_argument('--cy', type=float, required=True, help='circle centre y, 0..1')
    p.add_argument('--r', type=float, required=True, help='radius as fraction of width')
    p.add_argument('--start', type=int, default=20, help='frame where the zoom-through starts')
    p.add_argument('--dur', type=int, default=14); p.add_argument('--hold', type=int, default=12,
                                                               help='frames B is visible in the hole before zoom')
    p.add_argument('--keep-audio', action='store_true'); p.set_defaults(fn=cmd_portal)

    p = sub.add_parser('ramp'); p.add_argument('input'); p.add_argument('output')
    p.add_argument('--curve', default='0:0.4,0.35:0.4,0.5:3,0.65:0.4,1:0.4',
                   help='position:speed keyframes over the clip')
    p.add_argument('--no-blur', dest='blur', action='store_false'); p.set_defaults(fn=cmd_ramp)

    p = sub.add_parser('shake'); p.add_argument('input'); p.add_argument('output')
    p.add_argument('--beats', help='JSON list of beat times (seconds)')
    p.add_argument('--amount', type=float, default=0.012); p.add_argument('--punch', type=float, default=0.08)
    p.add_argument('--decay', type=float, default=9.0); p.add_argument('--blur', action='store_true')
    p.add_argument('--keep-audio', action='store_true'); p.set_defaults(fn=cmd_shake)

    p = sub.add_parser('beats'); p.add_argument('input'); p.set_defaults(fn=cmd_beats)

    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
