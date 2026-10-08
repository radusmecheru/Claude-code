#!/usr/bin/env python3
"""AI frame interpolation (RIFE 4.26, CPU) - turns 30 fps footage into smooth 60 fps.

Library:  from interp import Interpolator; mid = Interpolator()(frame_a, frame_b)   # BGR uint8, t = 0.5
CLI:      python3 tools/interp.py in30.mp4 out60.mp4      (doubles the frame rate, lossless RGB output)

Weights: ~/.cache/rife426/flownet.pkl (RIFE v4.26 "flownet" state dict, fetched by the session-start hook).
The network below is the official IFNet_HDv3 inference path, vendored so no third-party code is imported.
"""
import os
import subprocess
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

WEIGHTS = os.path.expanduser('~/.cache/rife426/flownet.pkl')


def warp(x, flow):
    n, _, h, w = x.shape
    gx = torch.linspace(-1.0, 1.0, w).view(1, 1, 1, w).expand(n, -1, h, -1)
    gy = torch.linspace(-1.0, 1.0, h).view(1, 1, h, 1).expand(n, -1, -1, w)
    grid = torch.cat([gx, gy], 1)
    flow = torch.cat([flow[:, 0:1] / ((w - 1.0) / 2.0), flow[:, 1:2] / ((h - 1.0) / 2.0)], 1)
    return F.grid_sample(x, (grid + flow).permute(0, 2, 3, 1), mode='bilinear', padding_mode='border',
                         align_corners=True)


def conv(i, o, k=3, s=1, p=1):
    return nn.Sequential(nn.Conv2d(i, o, k, s, p, bias=True), nn.LeakyReLU(0.2, True))


class Head(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn0 = nn.Conv2d(3, 16, 3, 2, 1)
        self.cnn1 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn2 = nn.Conv2d(16, 16, 3, 1, 1)
        self.cnn3 = nn.ConvTranspose2d(16, 4, 4, 2, 1)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        x = self.relu(self.cnn0(x))
        x = self.relu(self.cnn1(x))
        x = self.relu(self.cnn2(x))
        return self.cnn3(x)


class ResConv(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.conv = nn.Conv2d(c, c, 3, 1, 1)
        self.beta = nn.Parameter(torch.ones((1, c, 1, 1)))
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        return self.relu(self.conv(x) * self.beta + x)


class IFBlock(nn.Module):
    def __init__(self, in_planes, c=64):
        super().__init__()
        self.conv0 = nn.Sequential(conv(in_planes, c // 2, 3, 2, 1), conv(c // 2, c, 3, 2, 1))
        self.convblock = nn.Sequential(*[ResConv(c) for _ in range(8)])
        self.lastconv = nn.Sequential(nn.ConvTranspose2d(c, 4 * 13, 4, 2, 1), nn.PixelShuffle(2))

    def forward(self, x, flow=None, scale=1):
        x = F.interpolate(x, scale_factor=1. / scale, mode='bilinear', align_corners=False)
        if flow is not None:
            flow = F.interpolate(flow, scale_factor=1. / scale, mode='bilinear', align_corners=False) / scale
            x = torch.cat((x, flow), 1)
        tmp = self.lastconv(self.convblock(self.conv0(x)))
        tmp = F.interpolate(tmp, scale_factor=scale, mode='bilinear', align_corners=False)
        return tmp[:, :4] * scale, tmp[:, 4:5], tmp[:, 5:]


class IFNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.block0 = IFBlock(7 + 8, c=192)
        self.block1 = IFBlock(8 + 4 + 8 + 8, c=128)
        self.block2 = IFBlock(8 + 4 + 8 + 8, c=96)
        self.block3 = IFBlock(8 + 4 + 8 + 8, c=64)
        self.block4 = IFBlock(8 + 4 + 8 + 8, c=32)
        self.encode = Head()

    def forward(self, img0, img1, timestep, scale_list):
        timestep = (img0[:, :1].clone() * 0 + 1) * timestep
        f0, f1 = self.encode(img0), self.encode(img1)
        blocks = [self.block0, self.block1, self.block2, self.block3, self.block4]
        flow = mask = feat = None
        w0, w1 = img0, img1
        for i, blk in enumerate(blocks):
            if flow is None:
                flow, mask, feat = blk(torch.cat((img0, img1, f0, f1, timestep), 1), None, scale=scale_list[i])
            else:
                wf0, wf1 = warp(f0, flow[:, :2]), warp(f1, flow[:, 2:4])
                fd, mask, feat = blk(torch.cat((w0, w1, wf0, wf1, timestep, mask, feat), 1), flow,
                                     scale=scale_list[i])
                flow = flow + fd
            w0, w1 = warp(img0, flow[:, :2]), warp(img1, flow[:, 2:4])
        mask = torch.sigmoid(mask)
        return w0 * mask + w1 * (1 - mask)


class Interpolator:
    def __init__(self, scale=1.0):
        self.net = IFNet()
        state = torch.load(WEIGHTS, map_location='cpu', weights_only=True)
        state = {k.replace('module.', '', 1): v for k, v in state.items()}
        self.net.load_state_dict(state, strict=False)
        missing = [k for k in self.net.state_dict() if k not in state]
        if missing:
            raise RuntimeError(f'RIFE weights missing keys: {missing[:5]}')
        self.net.eval()
        self.scale_list = [16 / scale, 8 / scale, 4 / scale, 2 / scale, 1 / scale]
        self.pad = max(64, int(64 / scale))

    @staticmethod
    def _t(img):
        return torch.from_numpy(img[..., ::-1].copy()).permute(2, 0, 1)[None].float() / 255.0

    @torch.inference_mode()
    def __call__(self, a, b, t=0.5):
        h, w = a.shape[:2]
        ph, pw = (self.pad - h % self.pad) % self.pad, (self.pad - w % self.pad) % self.pad
        x0 = F.pad(self._t(a), (0, pw, 0, ph))
        x1 = F.pad(self._t(b), (0, pw, 0, ph))
        y = self.net(x0, x1, t, self.scale_list)[0, :, :h, :w].clamp(0, 1)
        return (y.permute(1, 2, 0).numpy()[..., ::-1] * 255.0 + 0.5).astype(np.uint8)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate', '-of', 'csv=p=0', src], capture_output=True, text=True)
    w, h, r = out.stdout.strip().split(',')
    w, h = int(w), int(h)
    num, den = (int(x) for x in r.split('/'))
    rd = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                          stdout=subprocess.PIPE)
    wr = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}',
                           '-r', f'{2 * num}/{den}', '-i', '-', '-c:v', 'libx264rgb', '-qp', '0', '-preset',
                           'ultrafast', dst], stdin=subprocess.PIPE)
    it = Interpolator()
    prev = None
    n = 0
    while True:
        buf = rd.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        cur = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        if prev is not None:
            wr.stdin.write(it(prev, cur).tobytes())
        wr.stdin.write(cur.tobytes())
        prev = cur
        n += 1
        print(f'\r{n}', end='', file=sys.stderr)
    if prev is not None:
        wr.stdin.write(prev.tobytes())  # keep 2x frame count
    wr.stdin.close(); wr.wait()
    print(file=sys.stderr)


if __name__ == '__main__':
    main()
