"""Per-frame looks (BGR float32 in, BGR float32 out) for edit scripts.

night_ritual: the @rayden77777 "BMWs ritual" look - very low key, crushed blacks, cool shadows, colour pulled
out of everything except the car's lamps (DRLs, tail-lights), which keep their colour and bloom.
lamp_glow: bloom on the lamps only, scaled by a beat envelope -> lights "blink" on the beat.
"""
import cv2
import numpy as np


def lamp_mask(img):
    """Bright, saturated pixels (lit tail-lights / DRLs / indicators) plus near-white highlights, feathered."""
    hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    s, v = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    red = ((hsv[..., 0] < 10) | (hsv[..., 0] > 165)) & (s > 0.55) & (v > 0.45)
    # Amber DRLs / indicators: very bright and saturated only (sunlit grass must not count).
    warm = (hsv[..., 0] >= 10) & (hsv[..., 0] < 25) & (s > 0.7) & (v > 0.85)
    m = (red | warm).astype(np.float32)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return cv2.GaussianBlur(m, (0, 0), 1.5)


def night_ritual(img, strength=1.0, sky_mask=None):
    """Turn golden-hour / daylight footage into the dark ritual look. strength 0..1."""
    x = img.astype(np.float32) / 255.0
    lm = lamp_mask(img)[..., None]
    gray = x.mean(axis=2, keepdims=True)
    desat = gray + (x - gray) * 0.45
    # Exposure down hard, S-curve, crushed blacks.
    y = np.clip(desat * 0.62, 0, 1)
    y = y ** 1.35
    y = np.clip((y - 0.015) / 0.985, 0, 1)
    # Cool (teal-blue) shadows, neutral highlights.
    shadow = (1 - y) ** 2
    y = y + shadow * np.array([0.035, 0.012, -0.01], np.float32)  # BGR
    if sky_mask is not None:  # bright skies would give daylight away: pull them down further
        y = y * (1 - 0.45 * sky_mask[..., None])
    # Lamps keep colour and brightness.
    y = y * (1 - lm) + x * lm
    # Vignette.
    h, w = y.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    y = y * np.clip(1.05 - 0.35 * r ** 2, 0.45, 1)[..., None]
    out = x * (1 - strength) + np.clip(y, 0, 1) * strength
    return out * 255.0


def lamp_glow(img, env, color_boost=1.0):
    """Bloom the lamps by `env` (0..1+, e.g. a beat envelope) so they flare on the beat."""
    if env < 0.01:
        return img
    lm = lamp_mask(img)
    src = img.astype(np.float32) * lm[..., None]
    bloom = cv2.GaussianBlur(src, (0, 0), 9) * 2.6 + cv2.GaussianBlur(src, (0, 0), 30) * 2.4
    return np.clip(img + bloom * env * color_boost + src * env * 0.6, 0, 255)


def grain(img, amount=4.0, seed=0):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, img.shape[:2]).astype(np.float32)[..., None]
    return np.clip(img + n, 0, 255)


def sky_mask(img):
    """Rough sky mask: bright, low-saturation or blue pixels in the upper part of the frame."""
    hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    v, s, hch = hsv[..., 2] / 255, hsv[..., 1] / 255, hsv[..., 0]
    m = ((v > 0.55) & ((s < 0.35) | ((hch > 90) & (hch < 130)))).astype(np.float32)
    h = img.shape[0]
    m[int(h * 0.65):] = 0
    return cv2.GaussianBlur(m, (0, 0), 15)
