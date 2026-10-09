"""Frame-level transitions and camera moves for edit scripts (BGR float32 in -> BGR float32 out).

All functions take a progress value p in 0..1 (or an angle) for the current frame, so a segment
function can drive them from song time. Used by the style templates in .claude/skills/tiktok-edit.

  zoom_blur(img, p, out=True)    radial zoom blur into the centre (outgoing) / out of it (incoming)  [r6]
  whip(img, p, direction)        directional motion blur + slide around a cut                         [r6, ritual]
  roll(img, angle, prev_angle)   rotate with a cover crop (no borders) + rotational blur              [r6]
  ellipse_portal(a, b, ...)      clip B seen through an elliptical opening in A (mirror, badge)       [r6]
  arrive(img, k)                 fast move that eases out at a clip head ("camera lands on the hit")  [r5, r7]
  fade(img, p) / flash(img, k)   fade to black / brightness flash                                     [r5]
  flash_in(img, a) / color_flash  blend toward white / a colour (overexposed drop, red flash)           [r3, r4]
  blink(img, t, beats, hold)     picture for `hold` s after each beat, black otherwise (blink intro)   [r3]
  box_glitch(img, frame, seed)   1-2 white rectangles jumping every 2 frames                          [r3]
  silhouette(img, mask, mode)    car white / background white / x-ray inside the mask                 [r3]
  sawtooth_wipe(img, p)          white sawtooth edge sweeping across                                  [r3]
  bands_close(img, p)            white bars closing to the centre (transition only)                  [r3]
  reverse_portal(b, a, ...)      B zoomed into its own opening (wheel/headlight) showing A, eases out [r4]
  cutout_grow(base, fg, m, ...)  next shot's car grows out of an opening with a white bloom           [r4]
  car_swap(a, b, ma, mb, p)      swap the car in place: crossfade inside the mask, then soft bg wipe  [r4]
  morph(a, b, n)                 RIFE in-betweens from A's last frame to B's first (warp morph)       [r4]
"""
import math

import cv2
import numpy as np


def _scale_about(img, s, cx, cy):
    M = np.float32([[s, 0, cx - cx * s], [0, s, cy - cy * s]])
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT)


def zoom_blur(img, p, out=True, center=None, samples=8, max_scale=1.5):
    """Outgoing (out=True): scale 1 -> max_scale with ease-in, radial blur growing with p.
    Incoming (out=False): scale 1.3 -> 1 with the blur fading out. Average of `samples` scaled copies."""
    h, w = img.shape[:2]
    cx, cy = center if center is not None else (w / 2, h / 2)
    if out:
        s = 1 + (max_scale - 1) * p ** 2
        spread = 0.06 * p
    else:
        s = 1 + 0.3 * (1 - p) ** 2
        spread = 0.06 * (1 - p)
    if spread < 1e-3:
        return _scale_about(img, s, cx, cy).astype(np.float32)
    acc = np.zeros_like(img, np.float32)
    for k in range(samples):
        acc += _scale_about(img, s * (1 + spread * k / (samples - 1)), cx, cy)
    return acc / samples


def whip(img, p, direction=1, max_blur=80, slide=0.3):
    """p in -1..1 around the cut (0 = cut frame): slide +-slide*W and 1-D motion blur up to max_blur px."""
    k = max(0.0, 1 - abs(p))
    if k <= 0:
        return img.astype(np.float32)
    h, w = img.shape[:2]
    dx = -direction * np.sign(p or 1) * slide * w * k
    M = np.float32([[1, 0, dx], [0, 1, 0]])
    out = cv2.warpAffine(img.astype(np.float32), M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    ks = int(max_blur * k) | 1
    return cv2.blur(out, (ks, 1)) if ks > 1 else out


def roll(img, angle, prev_angle=None, samples=6):
    """Rotate by `angle` degrees with a cover scale so no border shows; rotational blur over the per-frame delta."""
    h, w = img.shape[:2]

    def rot(a):
        r = math.radians(a)
        c, s = abs(math.cos(r)), abs(math.sin(r))
        cover = max(c + s * h / w, c + s * w / h)  # scale so the rotated frame still covers the canvas
        M = cv2.getRotationMatrix2D((w / 2, h / 2), a, cover)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    if prev_angle is None or abs(angle - prev_angle) < 0.5:
        return rot(angle).astype(np.float32)
    acc = np.zeros_like(img, np.float32)
    for k in range(samples):
        acc += rot(prev_angle + (angle - prev_angle) * (k + 1) / samples)
    return acc / samples


def ellipse_portal(a, b, cx, cy, rx, ry, p, rim=0.85):
    """B through an elliptical hole in A (centre/radii in px). p 0..1 zooms A into the hole until B fills."""
    h, w = a.shape[:2]
    zoom = 1 + p ** 2 * (max(w, h) * 1.6 / min(rx, ry) - 1)
    A = _scale_about(a.astype(np.float32), zoom, cx, cy)
    bs = 0.55 + 0.45 * p
    Mb = np.float32([[bs, 0, cx - w / 2 * bs + (w / 2 - cx) * p], [0, bs, cy - h / 2 * bs + (h / 2 - cy) * p]])
    B = cv2.warpAffine(b.astype(np.float32), Mb, (w, h), borderMode=cv2.BORDER_REFLECT)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / (rx * zoom)) ** 2 + ((yy - cy) / (ry * zoom)) ** 2)
    hole = np.clip((1 - d) * min(rx, ry) * zoom / 3.0, 0, 1)[..., None]
    ring = np.clip(1 - np.abs(d - 1) * 12, 0, 1)[..., None]
    return (B * hole + A * (1 - hole)) * (1 - ring * rim)


def arrive(img, k, strength=0.04):
    """Clip-head ease-out: k = 1 on the first frame -> 0 after ~6 frames; slight zoom that settles."""
    if k <= 0.01:
        return img.astype(np.float32)
    h, w = img.shape[:2]
    return _scale_about(img.astype(np.float32), 1 + strength * k * k, w / 2, h / 2)


def fade(img, p):
    """p 0 -> 1: picture -> black."""
    return img.astype(np.float32) * max(0.0, 1 - p)


def flash(img, k, gain=0.2):
    """Brightness flash scaled by k (e.g. a fast-decaying hit envelope)."""
    return np.clip(img.astype(np.float32) * (1 + gain * k), 0, 255)


def flash_in(img, a):
    """Blend toward white by a (0..1)."""
    return img.astype(np.float32) * (1 - a) + 255.0 * a


def color_flash(img, a, color=(32, 32, 255)):
    """Blend toward a BGR colour by a (red flash default #FF2020)."""
    return img.astype(np.float32) * (1 - a) + np.array(color, np.float32) * a


def blink(img, t, beats, hold=0.15):
    """Blink intro: the picture only for `hold` seconds after each beat."""
    since = min((t - b for b in beats if b <= t + 1e-6), default=99)
    return img.astype(np.float32) if since <= hold else np.zeros_like(img, np.float32)


def box_glitch(img, frame, seed=0, boxes=2, white=245):
    """White rectangles (15-45 % W, 8-25 % H) at a new random spot every 2 frames."""
    h, w = img.shape[:2]
    out = img.astype(np.float32).copy()
    rng = np.random.default_rng(seed * 1000 + frame // 2)
    for _ in range(rng.integers(1, boxes + 1)):
        bw, bh = int(w * rng.uniform(0.15, 0.45)), int(h * rng.uniform(0.08, 0.25))
        x, y = int(rng.uniform(0, w - bw)), int(rng.uniform(0, h - bh))
        out[y:y + bh, x:x + bw] = white
    return out


def silhouette(img, mask, mode='car'):
    """mode 'car': car pixels white; 'bg': background white, car kept; 'xray': inverted inside the mask."""
    m = mask.astype(np.float32)[..., None]
    x = img.astype(np.float32)
    if mode == 'car':
        return x * (1 - m) + 245.0 * m
    if mode == 'bg':
        return x * m + 245.0 * (1 - m)
    return x * (1 - m) + (255.0 - x) * m


def sawtooth_wipe(img, p, teeth=9, white=245):
    """White region left of a sawtooth edge that sweeps across the frame as p goes 0 -> 1."""
    h, w = img.shape[:2]
    yy = np.arange(h, dtype=np.float32)[:, None]
    xx = np.arange(w, dtype=np.float32)[None, :]
    period = h / teeth
    tri = np.abs((yy % period) / period * 2 - 1)
    edge = p * (w * 1.4) - 0.2 * w + 0.2 * w * tri
    m = (xx < edge).astype(np.float32)[..., None]
    return img.astype(np.float32) * (1 - m) + white * m


def bands_close(img, p, white=245):
    """Top and bottom white bars closing to the centre (p 0 -> 1). A transition only, never a resting layout."""
    h = img.shape[0]
    out = img.astype(np.float32).copy()
    b = int(h / 2 * min(1.0, p))
    out[:b] = white
    out[h - b:] = white
    return out


def reverse_portal(b, a, cx, cy, rx, ry, p):
    """B starts zoomed into its own opening (ellipse cx, cy, rx, ry in B) with A visible through it, then
    eases out to 1x as p goes 0 -> 1 (no synthetic rim: the real tyre/headlight frames it)."""
    q = 1 - (1 - p) ** 3
    return ellipse_portal(b, a, cx, cy, rx, ry, 1 - q, rim=0.0)


def cutout_grow(base, fg, mask, cx, cy, p, bloom=1.5):
    """Next shot's car (fg + mask, full frame) scaled 0.1 -> 1 from (cx, cy) over base, with a white bloom."""
    h, w = base.shape[:2]
    s = 0.1 + 0.9 * (1 - (1 - p) ** 2)
    M = np.float32([[s, 0, cx - w / 2 * s], [0, s, cy - h / 2 * s]])
    f = cv2.warpAffine(fg.astype(np.float32), M, (w, h))
    m = cv2.warpAffine(mask.astype(np.float32), M, (w, h))
    glow = np.clip(cv2.GaussianBlur(m, (0, 0), 18) * bloom, 0, 1)[..., None] * (1 - p * 0.5)
    out = base.astype(np.float32) * (1 - m[..., None]) + f * m[..., None]
    return np.clip(out + 255.0 * glow * (1 - m[..., None]) * 0.8, 0, 255)


def car_swap(a, b, ma, mb, p):
    """Swap the car in place: first half crossfades inside the car masks, second half wipes the background
    left -> right with a soft edge. a/b are aligned frames of the same spot, ma/mb their masks."""
    h, w = a.shape[:2]
    a, b = a.astype(np.float32), b.astype(np.float32)
    car = np.maximum(ma, mb).astype(np.float32)[..., None]
    k = min(1.0, p * 2)
    inside = a * (1 - k) + b * k
    xx = np.arange(w, dtype=np.float32)[None, :]
    edge = (p * 2 - 1) * w * 1.2
    wipe = np.clip((edge - xx) / (0.15 * w) + 0.5, 0, 1)[:, :, None] if p > 0.5 else np.zeros((1, w, 1), np.float32)
    outside = a * (1 - wipe) + b * wipe
    return inside * car + outside * (1 - car)


def morph(a, b, n, interp=None):
    """n RIFE in-between frames from a to b (warp morph between two shots)."""
    if interp is None:
        from interp import Interpolator
        interp = Interpolator()
    return [interp(a, b, (k + 1) / (n + 1)).astype(np.float32) for k in range(n)]
