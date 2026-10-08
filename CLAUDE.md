# Video editing workspace

Editing short vertical videos (TikTok / YouTube Shorts) with the user, who works from a phone
and writes in Romanian. Follow `.claude/skills/tiktok-edit/SKILL.md` for every editing task.

User preferences (hard rules):
- Every frame fills 9:16. No letterbox, black bars, stacked bands or picture-in-picture on black.
- One picture per frame: no split screen, no cut-out of the car floating over another shot.
- 60 fps, sharp, no lag. No text on car edits unless asked.
- Short edits (~10-15 s) ending on a bass hit are preferred over using the whole sound.
- A sound sent as a TikTok video is for its audio only; ignore its picture.
- Hook calm and clean; heavy effects from the drop on.

Layout:
- `tools/carfx.py` - car-edit effects (mask, neon, popout, trace, portal, ramp, shake, beats)
- `tools/masks.py` - subject masks for a time range at 60 fps
- `tools/captions.py` - transcription, ASS caption styles, TikTok text box, burn-in
- `tools/upscale.py` - Real-ESRGAN compact upscaler (slow on CPU; hero frames only)
- `edits/<name>/edit.py` - one script per edit (segments + final encode)
- `motion/` - Remotion motion-graphics templates (`GlowPromo`)
- `fonts/` - caption fonts, copied to ~/.fonts by the session-start hook
- `work/` - scratch output and user media, gitignored
