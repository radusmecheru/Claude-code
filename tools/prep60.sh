#!/bin/bash
# Cut a range of a (4K / vertical / 30 fps) phone clip, downscale to 1080x1920 and interpolate to 60 fps.
# usage: tools/prep60.sh SRC START DUR OUT.mkv     (lossless RGB output; ~6 s per source frame on CPU)
set -euo pipefail
SRC=$1; START=$2; DUR=$3; OUT=$4
TMP="${OUT%.mkv}_30.mkv"
ffmpeg -v error -y -ss "$START" -i "$SRC" -t "$DUR" -vf "scale=1080:1920:flags=area" -an \
  -c:v libx264rgb -qp 0 -preset ultrafast "$TMP"
OMP_NUM_THREADS=${THREADS:-2} python3 "$(dirname "$0")/interp.py" "$TMP" "$OUT"
rm -f "$TMP"
