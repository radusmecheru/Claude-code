#!/usr/bin/env python3
"""AI upscaling (Real-ESRGAN realesr-general-x4v3, CPU) for filling 9:16 from landscape footage.

Library use:  from upscale import Upscaler; up = Upscaler(); big = up(bgr_uint8)   # 4x
CLI (bench):  python3 tools/upscale.py frame.png out.png
Weights: ~/.cache/sr/realesr-general-x4v3.pth (downloaded by the session-start hook).
"""
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

WEIGHTS = os.path.expanduser('~/.cache/sr/realesr-general-x4v3.pth')


class SRVGGNetCompact(nn.Module):
    """Real-ESRGAN's compact VGG-style network (same layer layout as the released weights)."""

    def __init__(self, num_feat=64, num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        body = [nn.Conv2d(3, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        for _ in range(num_conv):
            body += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        body.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(body)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        return self.upsampler(out) + F.interpolate(x, scale_factor=self.upscale, mode='nearest')


class Upscaler:
    def __init__(self, threads=None):
        if threads:
            torch.set_num_threads(threads)
        self.net = SRVGGNetCompact()
        state = torch.load(WEIGHTS, map_location='cpu')
        self.net.load_state_dict(state.get('params', state))
        self.net.eval()

    @torch.inference_mode()
    def __call__(self, bgr):
        x = torch.from_numpy(bgr[..., ::-1].copy()).permute(2, 0, 1)[None].float() / 255.0
        y = self.net(x).clamp_(0, 1)[0].permute(1, 2, 0).numpy()[..., ::-1]
        return (y * 255.0 + 0.5).astype(np.uint8)


if __name__ == '__main__':
    import cv2
    img = cv2.imread(sys.argv[1])
    up = Upscaler()
    t = time.time()
    out = up(img)
    print(f'{img.shape[1]}x{img.shape[0]} -> {out.shape[1]}x{out.shape[0]} in {time.time() - t:.1f}s', file=sys.stderr)
    cv2.imwrite(sys.argv[2], out)
