#!/bin/bash
# Installs the video-editing toolchain (see EDITING.md) in Claude Code cloud sessions.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

pip install -q -r requirements.txt 2>&1 | grep -v "Running pip as the 'root' user" || true

# Fonts used by captions (ASS/libass) and text boxes.
mkdir -p ~/.fonts
cp -u fonts/*.ttf ~/.fonts/
fc-cache -f >/dev/null

# Remotion motion-graphics project.
(cd motion && npm install --no-audit --no-fund --loglevel=error)

# Models are cached in the container snapshot after the first run.
python3 -c "from faster_whisper import WhisperModel; WhisperModel('medium', device='cpu', compute_type='int8')" >/dev/null 2>&1
python3 -c "from rembg import new_session; new_session('isnet-general-use'); new_session('u2netp')" >/dev/null 2>&1

echo 'export REMOTION_BROWSER=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell' >> "${CLAUDE_ENV_FILE:-/dev/null}"

# Optional AI upscaler (Real-ESRGAN compact) used by tools/upscale.py.
pip install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | grep -v "Running pip as the 'root' user" || true
mkdir -p ~/.cache/sr
[ -f ~/.cache/sr/realesr-general-x4v3.pth ] || curl -sSfL -o ~/.cache/sr/realesr-general-x4v3.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth || true

# RIFE 4.26 weights for tools/interp.py (30 -> 60 fps frame interpolation).
mkdir -p ~/.cache/rife426
[ -f ~/.cache/rife426/flownet.pkl ] || curl -sSfL -o ~/.cache/rife426/flownet.pkl \
  https://huggingface.co/MonsterMMORPG/RIFE_4_26/resolve/main/train_log/flownet.pkl || true

# YuNet face detector for tools/privacy.py.
mkdir -p ~/.cache/yunet
[ -f ~/.cache/yunet/yunet.onnx ] || curl -sSfL -o ~/.cache/yunet/yunet.onnx \
  https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx || true

# Demucs htdemucs_ft (voice-over removal) from a Hugging Face mirror; files are checked against the
# official sha256 prefixes in their names before use.
pip install -q demucs soundfile 2>&1 | grep -v "Running pip as the 'root' user" || true
mkdir -p ~/.cache/demucs_repo
for f in 04573f0d-f3cf25b2.th 92cfc3b6-ef3bcb9c.th d12395a8-e57c48e6.th f7e0c4bc-ba3fe64a.th htdemucs_ft.yaml; do
  [ -f ~/.cache/demucs_repo/$f ] || curl -sSfL -o ~/.cache/demucs_repo/$f \
    "https://huggingface.co/dokodesuka/htdemucs_ft/resolve/main/$f" || true
done
for f in ~/.cache/demucs_repo/*.th; do
  exp=$(basename "$f" .th | cut -d- -f2)
  [ "$(sha256sum "$f" | cut -c1-8)" = "$exp" ] || rm -f "$f"
done
