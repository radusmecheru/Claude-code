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
