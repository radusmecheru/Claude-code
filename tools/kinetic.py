"""Kinetic lyric typography rendered onto frames (BGR float32, 1080x1920) - style r4 "lyric portal".

Only for edits where the user asked for text (car edits are text-free by default).

  typed(img, text, p, ...)           letters appear one per step, white glow, optional accent word in red
  behind_car(img, text, mask, ...)   huge outline caps drawn BEHIND the car (car mask pasted back on top)
  curved(img, text, cx, cy, r, ...)  words along a circle (e.g. around a headlight)
  end_card(text, ...)                Anton white-on-black card (only if asked)
Fonts come from fonts/ (Anton, Montserrat, TikTok Sans, Inter, Poppins, Bebas Neue).
"""
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts')
RED = (26, 26, 255)  # BGR #FF1A1A


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _layer(size_wh):
    return Image.new('RGBA', size_wh, (0, 0, 0, 0))


def _composite(img, layer, glow_sigma=0, glow_amount=0.6):
    """Alpha-composite an RGBA PIL layer over a BGR float frame, with an optional glow of the layer."""
    rgba = np.asarray(layer).astype(np.float32) / 255.0
    rgb = rgba[..., :3][..., ::-1] * 255.0
    a = rgba[..., 3:4]
    out = img.astype(np.float32)
    if glow_sigma:
        g = cv2.GaussianBlur(rgb * a, (0, 0), glow_sigma)
        out = out + g * glow_amount
    return np.clip(out * (1 - a) + rgb * a, 0, 255)


def typed(img, text, p, xy=(540, 760), size=96, font='Montserrat-900.ttf', accent=None,
          color=(255, 255, 255), accent_color=(255, 26, 26), glow=12):
    """Typewriter reveal: the first round(p * len(text)) characters, centred on xy; `accent` word in red."""
    h, w = img.shape[:2]
    n = int(round(max(0.0, min(1.0, p)) * len(text)))
    shown = text[:n]
    if not shown:
        return img.astype(np.float32)
    f = _font(font, size)
    full_w = f.getlength(text)
    x = xy[0] - full_w / 2
    lay = _layer((w, h))
    d = ImageDraw.Draw(lay)
    for word in shown.split(' '):
        col = accent_color if accent and word.strip('.,!?').lower() == accent.lower() else color
        d.text((x, xy[1]), word, font=f, fill=col + (255,), anchor='lm')
        x += f.getlength(word + ' ')
    return _composite(img, lay, glow_sigma=glow)


def behind_car(img, text, car_mask, y=700, size=330, font='Anton-400.ttf', stroke=6, fill=False,
               color=(255, 255, 255)):
    """Huge caps behind the car: draw the text (outline by default), then paste the car back on top."""
    h, w = img.shape[:2]
    f = _font(font, size)
    while f.getlength(text) > w * 0.96 and size > 40:
        size -= 10
        f = _font(font, size)
    lay = _layer((w, h))
    d = ImageDraw.Draw(lay)
    if fill:
        d.text((w / 2, y), text, font=f, fill=color + (255,), anchor='mm')
    else:
        d.text((w / 2, y), text, font=f, fill=(0, 0, 0, 0), stroke_width=stroke, stroke_fill=color + (255,),
               anchor='mm')
    with_text = _composite(img, lay)
    m = car_mask.astype(np.float32)[..., None]
    return with_text * (1 - m) + img.astype(np.float32) * m


def curved(img, text, cx, cy, r, start_deg=200, size=54, font='Montserrat-800.ttf', color=(255, 255, 255),
           p=1.0, glow=8):
    """Characters along a circle of radius r around (cx, cy), clockwise from start_deg; p reveals them."""
    h, w = img.shape[:2]
    f = _font(font, size)
    lay = _layer((w, h))
    n = int(round(p * len(text)))
    ang = math.radians(start_deg)
    for ch in text[:n]:
        cw = f.getlength(ch) or size * 0.3
        a = ang + cw / (2 * r)
        tile = _layer((size * 2, size * 2))
        ImageDraw.Draw(tile).text((size, size), ch, font=f, fill=color + (255,), anchor='mm')
        tile = tile.rotate(-math.degrees(a) - 90, resample=Image.BICUBIC)
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        lay.alpha_composite(tile, (int(px - size), int(py - size)))
        ang += cw / r
    return _composite(img, lay, glow_sigma=glow)


def end_card(text, size=260, font='Anton-400.ttf', wh=(1080, 1920)):
    """White condensed caps on black (r3 'SAV' card). Only when the user asks for an end card."""
    w, h = wh
    lay = Image.new('RGB', (w, h), (0, 0, 0))
    ImageDraw.Draw(lay).text((w / 2, h / 2), text, font=_font(font, size), fill=(255, 255, 255), anchor='mm')
    return np.asarray(lay)[..., ::-1].astype(np.float32)
