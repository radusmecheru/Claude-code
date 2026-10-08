#!/usr/bin/env python3
"""Precompute subject masks for a time range of a clip, at 60 fps, any orientation.

Runs the segmenter on every Nth frame and interpolates the rest, then saves a uint8
array [frames, h, w] (.npy) at half resolution. Upscale with cv2.resize when compositing.

  python3 tools/masks.py c1.mov work/c1_mask.npy --start 6 --dur 8 --transpose 2 --every 3
"""
import argparse
import subprocess
import sys

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input'); ap.add_argument('output')
    ap.add_argument('--start', type=float, default=0); ap.add_argument('--dur', type=float, required=True)
    ap.add_argument('--fps', type=float, default=60)
    ap.add_argument('--transpose', help='ffmpeg transpose value to fix sideways phone footage')
    ap.add_argument('--every', type=int, default=3)
    ap.add_argument('--model', default='isnet-general-use')
    a = ap.parse_args()

    from rembg import new_session, remove
    from PIL import Image

    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                          '-of', 'csv=p=0', a.input], capture_output=True, text=True).stdout.strip().split(',')
    vf = [f'fps={a.fps}']
    if a.transpose:
        vf.append(f'transpose={a.transpose}')
    # Probe the decoded size (autorotate + transpose) with one frame.
    probe = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(a.start), '-i', a.input, '-vf', ','.join(vf),
                            '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
    fh, fw = cv2.imdecode(np.frombuffer(probe, np.uint8), cv2.IMREAD_COLOR).shape[:2]
    w, h = fw // 2, fh // 2
    vf.append(f'scale={w}:{h}:flags=area')
    n = int(round(a.dur * a.fps))
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(a.start), '-i', a.input, '-t', str(a.dur), '-vf',
                          ','.join(vf), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    session = new_session(a.model)
    keys = {}
    i = 0
    while i < n:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        if i % a.every == 0:
            img = Image.fromarray(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
            keys[i] = np.array(remove(img, session=session, only_mask=True, post_process_mask=True), np.float32)
            print(f'\r{a.output}: {i}/{n}', end='', file=sys.stderr)
        i += 1
    p.stdout.close(); p.wait()
    n = i
    ks = sorted(keys)
    if ks[-1] != n - 1:
        keys[n - 1] = keys[ks[-1]]
        ks.append(n - 1)
    masks = np.zeros((n, h, w), np.uint8)
    for k0, k1 in zip(ks[:-1], ks[1:]):
        for j in range(k0, k1 + 1):
            t = (j - k0) / max(1, k1 - k0)
            masks[j] = np.clip(keys[k0] * (1 - t) + keys[k1] * t, 0, 255)
    np.save(a.output, masks)
    print(f'\n{a.output}: {masks.shape}', file=sys.stderr)


if __name__ == '__main__':
    main()
