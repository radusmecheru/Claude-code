---
name: tiktok-edit
description: Edit vertical videos for TikTok / YouTube Shorts / Reels from footage the user uploads - car edits (night ritual walkarounds, neon outlines, floating cut-outs, light traces, wheel/vent portal transitions, speed ramps, beat shake), Claude-made motion-graphics promos (glow, 3D phone, UI cards, kinetic type) and trendy captions (word pop, karaoke, TikTok white text box with emoji). Use whenever the user sends a clip to edit, asks for subtitles/captions, zooms, effects, a promo/motion graphics video, or says "make it like this TikTok".
---

# TikTok / Shorts editing

Toolchain (installed by `.claude/hooks/session-start.sh`): ffmpeg + libass, faster-whisper,
rembg (isnet / u2netp / birefnet), OpenCV, librosa, yt-dlp (with curl-cffi impersonation),
Remotion in `motion/`, fonts in `fonts/` (TikTok Sans, Montserrat, Poppins, Anton, Bebas Neue, Inter).

The user works from a phone and speaks Romanian. Reply in Romanian, keep messages short,
send every finished video with SendUserFile (`display: render`), and keep scratch work in `work/`
(gitignored).

## Workflow

1. **Understand the footage.** `ffprobe` it, make a contact sheet and look at it:
   `ffmpeg -i in.mp4 -vf "fps=2,scale=216:384,tile=9x4" -frames:v 1 work/sheet.png`
   If it has speech, transcribe first (`tools/captions.py transcribe`) and read the words.
2. **Reference links.** For a TikTok/YouTube link: `yt-dlp --impersonate chrome -o work/ref.%(ext)s URL`
   (plain yt-dlp fails on TikTok). Metadata without downloading: `https://www.tiktok.com/oembed?url=URL`.
   Analyse with contact sheets (dense: `fps=8` over 3 s), scene cuts
   (`ffmpeg -i ref.mp4 -vf scdet=threshold=12 -an -f null -` and grep `lavfi.scd.time`) and beats.
3. **Propose the plan** in 3-6 bullets (hook, effects at which seconds, caption style, music),
   then build it.
4. **Verify before sending:** contact sheet of the result + `ffprobe` (1080x1920, h264, yuv420p, aac).

## Style A - car edit (ref: @akaryu.media "smooth enough? 👀")

What the reference does (18 s, 60 fps, cool desaturated grade, no captions, music only):
- Wide shot of the car with a **close-up cut-out of another angle floating over it**
  (grille at the top, rear at the bottom), body darkened with **electric-blue neon edges**.
- A **white light streak runs around the car's contour** in the wide shot.
- **Shape-matched transitions**: the next shot shows through an opening of the car
  (side vent, mirror, wheel rim) and the camera zooms through it. Hard cuts are rare.
- Smooth gimbal moves, speed ramps into transitions, cuts and pops on the beat.

Recipe with `tools/carfx.py` (all outputs 1080x1920; pass `--keep-audio` where useful):
```bash
python3 tools/carfx.py mask clip.mp4 work/clip_mask.mp4            # ~1 s/frame; --model u2netp for drafts
python3 tools/carfx.py neon close.mp4 work/close_mask.mp4 out.mp4 --color '#1E90FF' --dim-bg 0.5
python3 tools/carfx.py popout wide.mp4 close.mp4 work/close_mask.mp4 out.mp4 --neon --anchor top --scale 0.8
python3 tools/carfx.py trace wide.mp4 work/wide_mask.mp4 out.mp4 --frames 40
python3 tools/carfx.py portal a.mp4 b.mp4 out.mp4 --cx 0.53 --cy 0.5 --r 0.1 --start 26 --dur 14
python3 tools/carfx.py ramp clip.mp4 out.mp4 --curve '0:0.4,0.4:0.4,0.5:3,0.6:0.4,1:0.4'
python3 tools/carfx.py beats music.mp3 > work/beats.json   # then: shake --beats (list of times)
```
- For `portal`, pick the circle by looking at a still of clip A at frame `--start`
  (wheel rim, headlight, exhaust); cx/cy are 0-1, r is a fraction of the width.
- Masks: run on short clips (1-3 s). Check one mask frame visually; if it grabs the ground,
  try `--model birefnet-general-lite` (slow, ~14 s/frame at half res; use `--every 2`).
- Cut clips to the beat: get `beats.json`, then trim each clip so cuts land on `strong` beats.
- Join with `ffmpeg -f concat` after re-encoding every piece to the same fps (30 or 60).

### Full edits to music (the way edit #1 was built)

For a real edit, do not chain CLI calls - write a per-edit script like
`edits/porsche-gt3-01/edit.py` (one function per segment, song-time envelopes, lossless intermediates,
one final encode). Team: `footage-scout` + `beat-mapper` (+ `reference-analyst` for links) in parallel →
`edit-director` plan → `vfx-compositor` render → `qa-reviewer` before sending.

**The user rejected letterbox / stacked bands: every frame must fill 9:16.** Landscape footage is
cropped to a 9:16 window that follows the car (`vert()` + `car_cx()` in the edit script: centre from the
mask bounding box, sub-pixel affine, Lanczos 1.78x + unsharp). Ask for vertical footage when possible.
AI upscaling (`tools/upscale.py`, Real-ESRGAN compact) is available but ~10 s/frame on CPU and makes
matte paint look plastic - use only for a few hero frames.

Extra techniques used there:
- **Sun burn**: zoom into the brightest point of the frame while blending to white; cut on the hit.
- **Reframe on a hit**: jump the 9:16 window to another part of the car (wheel, tail-light) on a bass hit.
  Never mirror car footage: plates and badges read backwards.
- **Whip cut**: +-5 frames of directional blur and slide around the cut.
- **Reverse + neon**: reuse a shot reversed, car neon-lit on hits over a darkened background.
- **Neon cut-out drop-in** over a different shot, and **light lap** (`trace_light`) on hits.

Quality rules (the user hates blur and lag):
- Keep 60 fps sources at 60 fps (`fps=60` on decode; phones record VFR). No slow-mo from 60 fps sources.
- Landscape footage: crop to 9:16 following the subject (1.78x Lanczos + unsharp is the floor; never go
  tighter than ~2x). Downscaled cut-outs over vertical shots stay perfectly sharp.
- Downscale with `INTER_AREA`; punch-ins at most 8 % and decaying.
- Intermediates lossless (`libx264rgb -qp 0`); final x264 `-preset slow -crf 14 -profile:v high`, bt709 tags,
  light `unsharp`, AAC 320k.
- iPhone clips may be shot sideways: check a frame, fix with `transpose=1|2`. ffprobe width/height ignore
  the rotation side data - judge orientation from a decoded frame (scale with `-2`, never a fixed WxH).
- 30 fps footage in a 60 fps edit: interpolate with RIFE (`tools/interp.py in30.mkv out60.mkv`, ~6 s per
  1080x1920 frame on CPU). Prep only the ranges you use, downscaled to 1080x1920 first
  with `tools/prep60.sh SRC START DUR out.mkv`. Never just duplicate frames.
- 4K vertical sources: downscale to 1080x1920 (INTER_AREA) - sharpest material; prefer it for hero shots.
- Shared plumbing for new edits: `tools/editkit.py` (read, Writer, Masks, hit_env, punch, run/finalize).
- Disk: lossless `*.seg.mkv` intermediates are 100 MB-1 GB each and the session disk fills up (writes then
  fail with BrokenPipe from the ffmpeg writer). After a version is delivered, delete its `*.seg.mkv` and
  the uncapped master; keep the prepped sources (`A.mkv`...) and the `_29mb` deliveries. Check `df -h`.
- Shot-list edits with variants: `edits/porsche-gt3-03/edit.py` - each variant is a list of
  (song start, end, source, in-point, fx, engine gain, duck). `--check` validates that shots tile the song
  and fit their sources (no frozen frames). Use it as the template for multi-variant requests.
- Engine sound: pass `extra_audio` to `editkit.run` (clip audio placed under its shot, song ducked to 50 %
  on fly-bys). The user wants engines audible when the car passes.
- Keep the car fully in frame: build edits from vertical sources; never crop landscape footage so the car
  is cut off.
- Privacy: YuNet fires on wheels, badges and flowers in night footage - always look at the detections
  (crop + Read) before hiding anything; if nobody is in the car, do not apply it.
- Footage triage before planning (see `edits/night-gt3/edit.py` docstring): per 0.25 s sharpness
  (Laplacian var), optical-flow motion, luma, lights; drop ranges with motion > ~4 px/frame @180 w,
  sharpness < ~150 (ground / pocket shots) and handheld whips unless used as transitions. Compilations
  (like 07162.mp4) need their internal cuts listed so no shot crosses one.
- The driver's face must never be visible: `python3 tools/privacy.py track clip.mkv clip_faces.json`
  on every close shot, then `FaceTrack(...).hide(img, frame, car_mask)` (tint clipped to the car mask).
- Static style: locked-off shots with the car approaching, and jump cuts on the beat within the same framing;
  zoom-only punch on hits (no shake).

## Style C - night ritual walkaround (ref: @rayden77777 "BMWs ritual")

What the reference does (13.7 s, 1280x720 landscape, 30 fps, reggaeton at 112 BPM, no text): night under a
gas-station canopy, matte black BMW M, one gimbal walkaround - ceiling lights -> tilt down to the car ->
push in to the badge/grille -> headlights with the yellow DRLs blinking on the beat -> front lip -> wheel ->
door open on the seats -> rear wheel -> tail-lights on -> plate. A cut or jump-cut on every beat (~0.5 s),
exposure pumps on the beat (luma spikes), very low key (mean luma 15-20 %), crushed blacks, cool shadows,
colour only in the lamps.

Rebuild: `edits/ritual-demo/edit.py` (shot list + `fx`: jump = 0.2 s skip on each beat inside a shot,
glow = lamps flare on beats, push, fadein/fadeout, detail:<x>). Look in `tools/looks.py`:
`night_ritual(img, sky_mask=sky_mask(img))`, `lamp_glow(img, env)`, `grain`. Order shots as a walkaround
(far -> front -> lights -> side/wheel -> rear -> tail-lights -> plate). Best with night footage where the
lamps are on (DRLs, welcome animation, tail-lights); daylight footage graded dark works for mood but the
headlights stay unlit. Keep the user's rules: 9:16 full frame, 60 fps, face hidden.

## More styles (D-J)

`styles.md` (next to this file) holds seven more reference breakdowns with rebuild recipes and filming lists:
D screen-lit reel, E filmed-screen motion promo, F red night glitch-cut, G lyric portal, H light-bar wake-up ->
blackout -> drop, I garage roll, J CGI autumn glide. Read it whenever the user names a style or sends a
reference that resembles one.

Tools added for them:
- `tools/transitions.py`: zoom_blur, whip, roll, ellipse_portal, reverse_portal, cutout_grow, car_swap, morph,
  arrive, fade, flash, flash_in, color_flash, blink, box_glitch, silhouette, sawtooth_wipe, bands_close.
- `tools/looks.py`: night_ritual, lamp_glow, clean_night, punchy, warm_natural, daylight_fade, screen_insert, grain.
- `tools/editkit.py`: bass_returns (bass drop-outs/returns), shot_dx + match_inpoint (motion-matched cuts),
  early (cut N frames before the beat).
- `tools/kinetic.py`: typed lyrics with accent word + glow, outline caps behind the car, curved text, end card.
- `motion/src/MotionReel.tsx`: beat-driven reel (burst logo, easing curves, shape morph, tiles wipe, dot sphere,
  prompt bar + pill switcher, word per beat, stroke-drawn logo); `MotionReel` 16:9 and `MotionReelVertical`.

## Style B - Claude-made motion-graphics promo (ref: @rikibosso "Claude has cooked 😳")

What the reference does (21-23 s): a brand promo generated with Claude, played in DaVinci
Resolve and **filmed off the monitor with a phone**, with a TikTok text box on top
("New Claude Opus 5.5 🤓", "Claude has cooked 😳") and "check bio for the prompt" in the caption.
Promo structure: dark background + breathing radial glow in the brand colour → logo reveal →
3D phone with app icons lighting up → glass UI cards staggering in (one highlighted) →
kinetic text word by word with the key word in the accent colour → light streak → logo + CTA.
Audio: AI voice-over + drum loop + whooshes / UI clicks.

Build it with Remotion (`motion/`, composition `GlowPromo` 9:16 and `GlowPromoWide` 16:9):
```bash
cd motion
npx remotion still src/index.ts GlowPromo out/check.png --frame=230 --scale=0.25   # quick look
npx remotion render src/index.ts GlowPromo out/promo.mp4 --props='{"brand":"Nume","accent":"#FF3B5C","headline":["Vinde","ce","creezi"],"accentWord":"creezi","subline":"dintr-un singur click","cards":[{"title":"...","meta":"..."}],"cta":"Descarcă acum"}'
```
Edit `motion/src/GlowPromo.tsx` for new scenes; timings live in `SCENES`.
Fonts must be local (`motion/public/fonts`) - the render browser cannot reach Google Fonts.
For the "filmed screen" look, render `GlowPromoWide`, let the user film their monitor, then
add the text box. Do not put real brands' logos in our own templates; the user supplies them.
Remotion is free for individuals and companies of up to 3 people; bigger companies need a licence.

## Captions (`tools/captions.py`)

```bash
python3 tools/captions.py transcribe in.mp4 work/words.json             # --lang ro default, medium model
python3 tools/captions.py ass work/words.json work/subs.ass --style pop --accent '#FFE500'
python3 tools/captions.py textbox "Claude a gătit 😳" work/title.png    # TikTok-native white box
python3 tools/captions.py burn in.mp4 out.mp4 --ass work/subs.ass --png work/title.png@0.14
```
Styles: `pop` (2-3 words, current word pops + accent colour), `highlight` (karaoke fill),
`box` (white plate, black text, builds word by word). Before burning, read `words.json`
and fix misheard words (names, brands, slang) by editing the JSON.
Keep captions out of TikTok's UI: top 8 % and bottom 20 % of the frame, and the right edge.

## Export

TikTok/Shorts: 1080x1920, H.264 high, yuv420p, 30 or 60 fps, CRF 16-18, AAC 192k,
`-movflags +faststart`, loudness about -14 LUFS (`loudnorm=I=-14:TP=-1:LRA=11`).
Keep the hook in the first 1-2 s, and keep the video under 60 s unless the user wants longer.
