# Video editing workspace

Editing short vertical videos (TikTok / YouTube Shorts) with the user, who works from a phone
and writes in Romanian.

User preferences (hard rules):
- Every frame fills 9:16. No letterbox, black bars, stacked bands or picture-in-picture on black.
- 60 fps, sharp, no lag. No text on car edits unless asked.
- A sound sent as a TikTok video is for its audio only; ignore its picture.
- Hook calm and clean; heavy effects from the drop on. Follow `.claude/skills/tiktok-edit/SKILL.md` for every editing task.

- `tools/carfx.py` - car-edit effects (mask, neon, popout, trace, portal, ramp, shake, beats)
- `tools/captions.py` - transcription, ASS caption styles, TikTok text box, burn-in
- `motion/` - Remotion motion-graphics templates (`GlowPromo`)
- `fonts/` - caption fonts, copied to ~/.fonts by the session-start hook
- `work/` - scratch output, gitignored
