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


def clean_night(img):
    """[r5 cupraedits] Clean night: deep blacks, contrast 1.1, slight desat, cool highlights, lamps untouched."""
    x = img.astype(np.float32) / 255.0
    lm = lamp_mask(img)[..., None]
    gray = x.mean(axis=2, keepdims=True)
    y = gray + (x - gray) * 0.95
    y = np.clip((y - 0.5) * 1.1 + 0.5 - 0.015, 0, 1)
    hi = np.clip((y.mean(axis=2, keepdims=True) - 0.59) / 0.41, 0, 1)
    y = y + hi * np.array([0.04, 0.0, -0.03], np.float32)  # BGR: cooler highlights
    y = y * (1 - lm) + x * lm
    return np.clip(y, 0, 1) * 255.0


def punchy(img):
    """[r6 ti.cutz] Punchy garage look: crushed lows, contrast 1.15, saturation 1.3, warm highlights."""
    x = img.astype(np.float32) / 255.0
    gray = x.mean(axis=2, keepdims=True)
    y = gray + (x - gray) * 1.3
    y = np.clip((y - 0.5) * 1.15 + 0.5, 0, 1)
    y = np.clip((y - 0.06) / 0.94, 0, 1)
    hi = np.clip((y.mean(axis=2, keepdims=True) - 0.6) / 0.4, 0, 1)
    y = y + hi * np.array([-0.02, 0.0, 0.03], np.float32)
    return np.clip(y, 0, 1) * 255.0


def warm_natural(img):
    """[r7 m4jor3d] Natural overcast with crushed black paint and a slight warm cast."""
    x = img.astype(np.float32) / 255.0
    y = np.clip((x - 0.5) * 1.08 + 0.5, 0, 1)
    y = np.clip((y - 0.02) / 0.98, 0, 1)
    y = y + np.array([-0.015, 0.0, 0.02], np.float32) * (0.3 + 0.7 * y.mean(axis=2, keepdims=True))
    return np.clip(y, 0, 1) * 255.0


def daylight_fade(img):
    """[r4 quentin.fx] Soft washed-out daylight: contrast 0.92, saturation 0.45, gamma 1.05, blacks lifted to
    ~15/255, sky kept blue (saturation x1.6 inside the sky mask), slight softness."""
    x = img.astype(np.float32) / 255.0
    sm = sky_mask(img)[..., None]
    gray = x.mean(axis=2, keepdims=True)
    sat = 0.45 * (1 - sm) + 0.45 * 1.6 * sm
    y = gray + (x - gray) * sat
    y = np.clip((y - 0.5) * 0.92 + 0.5, 0, 1) ** (1 / 1.05)
    y = 0.06 + y * 0.94 * (228 / 255)
    soft = cv2.GaussianBlur(y, (0, 0), 1.2)
    return np.clip(y * 0.7 + soft * 0.3, 0, 1) * 255.0


def screen_insert(plate, render, corners, spill=0.1):
    """[r1/r2] Put a motion render onto a filmed screen: corner-pin (TL, TR, BR, BL px) into `plate`,
    x0.85 brightness, 3 px blur, plus a soft spill of the screen colour onto the plate (room light)."""
    h, w = plate.shape[:2]
    rh, rw = render.shape[:2]
    src = np.float32([[0, 0], [rw, 0], [rw, rh], [0, rh]])
    M = cv2.getPerspectiveTransform(src, np.float32(corners))
    warped = cv2.warpPerspective(render.astype(np.float32) * 0.85, M, (w, h))
    m = cv2.warpPerspective(np.ones((rh, rw), np.float32), M, (w, h))
    warped = cv2.GaussianBlur(warped, (0, 0), 1.0)
    mean = render.reshape(-1, 3).mean(0).astype(np.float32)
    light = plate.astype(np.float32) * (0.25 + 0.75 * mean / 255.0) + cv2.GaussianBlur(m, (0, 0), 120)[..., None] * mean * spill
    return np.clip(light * (1 - m[..., None]) + warped, 0, 255)
