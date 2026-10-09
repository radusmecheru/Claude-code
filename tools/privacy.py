#!/usr/bin/env python3
"""Hide the driver's face behind the windscreen: track it with YuNet and cover it with "tinted glass"
(heavy blur + darkening in a feathered ellipse), so close-ups of the car never show who is inside.

  python3 tools/privacy.py track clip.mkv clip_faces.json     # one entry per frame: [cx, cy, w, h] or null
  from privacy import FaceTrack; ft = FaceTrack('clip_faces.json'); img = ft.hide(img, frame_index)

Model: ~/.cache/yunet/yunet.onnx (opencv/face_detection_yunet on Hugging Face; fetched by the hook).
"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np

MODEL = os.path.expanduser('~/.cache/yunet/yunet.onnx')


def detect_all(path):
    w, h = 1080, 1920
    det = cv2.FaceDetectorYN.create(MODEL, '', (w, h), 0.45, 0.3, 5000)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={w}:{h}', '-f', 'rawvideo',
                          '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    out = []
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        _, faces = det.detect(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
        out.append([] if faces is None else [[float(v) for v in f[:4]] + [float(f[-1])] for f in faces])
    p.stdout.close(); p.wait()
    return out


def track(dets, acquire=0.75, keep=0.45, max_jump=140, max_gap=40):
    """Follow one face: start on a confident detection, then take the nearest plausible box each frame.
    Gaps are filled by interpolation (and held at the ends), then the track is smoothed."""
    n = len(dets)
    boxes = [None] * n
    last = None
    for i, cands in enumerate(dets):
        cands = [c for c in cands if 18 <= c[2] <= 160 and c[4] >= keep]
        pick = None
        if last is not None and i - last[0] <= max_gap:
            lx, ly = last[1][0], last[1][1]
            near = [c for c in cands if abs(c[0] + c[2] / 2 - lx) + abs(c[1] + c[3] / 2 - ly) < max_jump]
            if near:
                pick = max(near, key=lambda c: c[4])
        if pick is None:
            strong = [c for c in cands if c[4] >= acquire]
            if strong:
                pick = max(strong, key=lambda c: c[4])
        if pick is not None:
            box = [pick[0] + pick[2] / 2, pick[1] + pick[3] / 2, pick[2], pick[3]]
            boxes[i] = box
            last = (i, box)
    known = [i for i, b in enumerate(boxes) if b is not None]
    if not known:
        return boxes
    # Interpolate short gaps between detections; hold the first/last box for up to max_gap frames.
    for a, b in zip(known[:-1], known[1:]):
        if 1 < b - a <= max_gap * 2:
            for j in range(a + 1, b):
                t = (j - a) / (b - a)
                boxes[j] = [boxes[a][k] * (1 - t) + boxes[b][k] * t for k in range(4)]
    for j in range(max(0, known[0] - max_gap), known[0]):
        boxes[j] = boxes[known[0]]
    for j in range(known[-1] + 1, min(n, known[-1] + max_gap + 1)):
        boxes[j] = boxes[known[-1]]
    # Smooth the centre/size (5-frame moving average over present boxes).
    sm = []
    for i in range(n):
        win = [boxes[j] for j in range(max(0, i - 2), min(n, i + 3)) if boxes[j] is not None]
        sm.append([sum(b[k] for b in win) / len(win) for k in range(4)] if boxes[i] is not None and win else None)
    return sm


class FaceTrack:
    def __init__(self, path):
        self.boxes = json.load(open(path))

    def hide(self, img, i, car_mask=None):
        if not self.boxes:
            return img
        b = self.boxes[min(max(i, 0), len(self.boxes) - 1)]
        return tint(img, b, car_mask) if b else img


def tint(img, box, car_mask=None):
    """Cover the head with blurred, darkened glass in a soft ellipse. With the car's mask (0..1, full frame)
    the patch is clipped to the car body so it stays on the glass and never smears the sky."""
    cx, cy, w, h = box
    ax, ay = int(w * 1.5 + 22), int(h * 1.2 + 24)
    x0, y0 = int(max(0, cx - ax * 2)), int(max(0, cy - ay * 2))
    x1, y1 = int(min(img.shape[1], cx + ax * 2)), int(min(img.shape[0], cy + ay * 2))
    if x1 <= x0 or y1 <= y0:
        return img
    roi = img[y0:y1, x0:x1].astype(np.float32)
    m = np.zeros(roi.shape[:2], np.float32)
    cv2.ellipse(m, (int(cx - x0), int(cy - y0)), (ax, ay), 0, 0, 360, 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), max(6.0, ax * 0.3))[..., None]
    m = np.clip(m * 1.6, 0, 1)  # keep the centre fully covered after feathering
    if car_mask is not None:
        cm = cv2.erode(car_mask[y0:y1, x0:x1].astype(np.float32), np.ones((5, 5), np.uint8))
        m = m * cv2.GaussianBlur(cm, (0, 0), 3)[..., None]
    glass = cv2.GaussianBlur(roi, (0, 0), max(12.0, ax * 0.4)) * 0.5
    out = img.astype(np.float32).copy()
    out[y0:y1, x0:x1] = roi * (1 - m) + glass * m
    return out


def main():
    if len(sys.argv) != 4 or sys.argv[1] != 'track':
        sys.exit(__doc__)
    dets = detect_all(sys.argv[2])
    boxes = track(dets)
    json.dump(boxes, open(sys.argv[3], 'w'))
    print(f'{sys.argv[3]}: {sum(b is not None for b in boxes)}/{len(boxes)} frames covered', file=sys.stderr)


if __name__ == '__main__':
    main()
