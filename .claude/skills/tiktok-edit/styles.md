# Style catalog (learned from the user's references)

Styles A-C live in SKILL.md. Each entry: what the reference does, how to rebuild it with our tools, and what
the user must film. The user's hard rules (CLAUDE.md) always win over a reference: full 9:16, one picture per
frame, 60 fps, no text unless asked, static shots preferred, driver's face hidden.

## Style D - Screen-lit reel

**Reference breakdown**

r1 Screen-Lit Reel (@motionlovee "Do you want a tutorial?") - 1080x1920 ~30fps 15 s, ONE locked-off shot of a laptop on a glossy table in a dark room; the screen (Claude-made motion reel) is the only light: room + table reflection change colour per scene. 129 BPM, spoken count-in "1,2,3,4" 0-1.6 s = hook. Screen scenes change on beats: asterisk burst -> drop 1.88 "CLAUDE" slam w/ flash -> easing-curves chart 3.3 -> shape morphs 5.4 -> tiled pattern + wipe 7.4 -> 3D particle sphere/torus 8.8 -> one word per beat w/ motion-blur slide 11.0-12.9 -> rings + logo 12.9 -> hold. Text: TikTok white text tilted ~5deg + coral asterisk sticker, top 8-23 %.
NEW: Remotion MotionReel (16:9, beat-driven scenes); fallback composite: corner-pin render on laptop still (warpPerspective), table reflection (flip+blur 6px, 0.4->0 fade), room light = plate x (0.25+0.75*avg screen colour, 3-frame smoothing).
Film: laptop/monitor on glossy black/glass table, lights off, tripod 3/4 low, 60 fps, locked exposure.

**Rebuild:** Remotion `MotionReel` (16:9) played on a laptop in a dark room, or `looks.screen_insert(plate, render, corners)`; text box via `captions.py textbox` only if asked.

## Style E - Filmed-screen motion promo

**Reference breakdown**

r2 Filmed-screen Motion Promo, dark desk (@vizibilonline "Motion design by OPUS 5.5, 1 prompt") - 1080x1920 59.94fps 19.4 s, one tripod take of a laptop playing a Claude-made motion render, no music: mouse clicks + render whooshes/sparkles through laptop speakers (very quiet, -40 dBFS). Crushed blacks, magenta/blue LED wall. TikTok text box "Motion design by / OPUS 5.5" (TikTok Sans Medium, black on white rounded plate, y 19-28.5 %, static).
Render scenes (each on its own SFX hit): prompt bar flies in + typing caret -> model dropdown + blue glow -> camera whip to pill switcher, sliding highlight -> teal light streaks reveal a word -> falling dot bursts into a word, vertical blur-roll swaps words -> icon ring pulse + particle field + "TRY" CTA -> black, logo stroke-draw.
NEW Remotion scenes: prompt bar + typing caret + dropdown, segmented pill switcher, word morph (scatter + vertical blur roll), ring pulse + particle field, stroke-draw logo, CameraMotionBlur whips; screen_insert() corner-pin fallback (warpPerspective, x0.85, 3 px blur, grain, 10 % screen spill on keyboard); SFX layer + loudnorm -14 LUFS.
Film: render full-screen on laptop/monitor (hide player controls), dark room with purple/blue LED glow, tripod vertical 4K60, screen in middle third slightly angled, top 35 % clean for the text box, exposure locked on the screen, no people, start motion within 0.5 s.

**Rebuild:** Remotion `MotionReel` (Prompt scene: typing bar + pill switcher, Logo stroke-draw) or `GlowPromo`; `looks.screen_insert`; SFX layered on scene changes, loudnorm -14 LUFS.

## Style F - Red night glitch-cut

**Reference breakdown**

r3 Red Night Glitch-Cut (@sav.edits001 Lamborghini Aventador SVJ) - 1920x1080 landscape 30fps 28.5 s ~50 shots, phonk 808 129 BPM, no vocals/engine. Very dark (luma 20-40), crushed blacks, teal shadows, red car stays saturated.
0-2.3 BLINK intro: 0.1-0.3 s shots separated by black, landing on beats. 2.3-6.3 pure black over a bassless breakdown. 6.3 drop: overexposed frame fades into static wheel shot. 6.3-26.1 cut on almost every beat; the bass drops out ~0.4 s and returns every 2.45 s: in every bass GAP a box glitch (1-2 frame white rectangles / windows) or white car SILHOUETTE flash; on every bass RETURN a hard cut / whip / badge pop. Also white sawtooth wipe, white bands closing. 26.1-28.5 white flash -> "SAV" Anton white on black end card.
NEW: bass-return detection (<150 Hz energy rising from <20 % to >80 % of median within 0.1 s), blink fx, flash-in, box glitch, silhouette flash / x-ray (mask), sawtooth wipe, white bands closing (transition only), badge pop overlay (user logo, optional), end card (only if asked).
Rules: keep black <= ~1 s; glitch windows <= 2 frames; 12-14 s length ending on a bass hit.
Film (night, vertical 60, overhead-lit locations, dark bg): static low tripod: rolling in front, 3/4, side, rear; 1-2 s details (tail-lights, badge/bonnet, wheel, intake, exhaust pops, headlights coming on); 2-3 rolling/fly-by shots with engine sound.

**Rebuild:** `looks.night_ritual`; `editkit.bass_returns(song)` -> gaps get `transitions.box_glitch` / `silhouette(mask, "car"|"bg"|"xray")`, returns get a hard cut / `whip`; intro `transitions.blink`; drop `flash_in`; `sawtooth_wipe`, `bands_close`; `kinetic.end_card` only if asked.

## Style G - Lyric portal

**Reference breakdown**

r4 Lyric Portal (@quentin.fx1 Porsche GT3 RS "Probably my best edit yet") - 1080x1920 59.94fps 20 s, music only, 103 BPM, drop ~10.7. Soft lifted washed-out daylight grade (blacks ~15, very low saturation, deep-blue sky + red accent text), light softness, mostly moving low gimbal shots, matched pairs (wheel<->rear, headlight<->front).
Lyric typography on every beat: typed white words + red accent word with glow; words curved around the headlight; glowing serif text; text pinned to the bumper (tracked homography); huge outline caps BEHIND the car (car mask on top); 3D extruded name.
Transitions: next car cut-out grows out of the headlight/wheel opening with white bloom; REVERSE wheel/headlight portals (B starts zoomed into its real opening showing A, eases out); red full-frame flash with handwritten word; car swap at the same spot (crossfade inside mask + soft wipe of bg); RIFE warp morph; whip + white flash at drop; detail cuts every half beat at the end (fades out, not on a hit).
NEW: reverse portal, cutout-grow + bloom, car swap, morph via RIFE, red flash, kinetic lyric text (typed reveal + glow, accent colour, text behind car, curved text, planar-tracked text), daylight_fade look (contrast 0.92 sat 0.45 gamma 1.05, lifted blacks, sky kept blue).
Conflicts: text-driven (only if user asks for text), brief cut-outs, moving shots; end on a hit instead.
Film (vertical 4K60, bright daylight, low): wheels side-on close (locked/slow push), headlight close-ups front+3/4, matching rear/front shots, locked front shot with plain wall/sky (room for text), second car same spot (swap), interior/mirror/wing details with no one inside.

**Rebuild:** `looks.daylight_fade`; `transitions.reverse_portal`, `cutout_grow`, `car_swap`, `morph` (RIFE), `color_flash`, `whip` + `flash_in` at the drop; lyrics with `kinetic.typed` (accent word), `behind_car`, `curved` - ONLY when the user asks for text.

## Style H - Light-bar wake-up -> blackout -> drop

**Reference breakdown**

r5 Light-bar Wake-up -> Blackout -> Drop (@cupraedits "Tuned Turbo S", 992 Turbo S, matte olive) - 1920x1080 landscape 60fps 11.5 s, no text, 161 BPM (0.37 s), explicit sped-up rap.
Grade clean night: deep blacks, cool white-blue highlights, neutral shadows, moderate sat, only lamps carry colour; no grain/vignette.
0-2.9 static rear at the pumps, very slow push-in, light bar start-up animation (hook). 2.9-5.9 PURE BLACK over the build. 5.9 drop: low rear wheel/diffuser close-up slow pull-back. Then one hard cut per bass hit: wide front at the station (fast zoom-out easing), garage 3/4 with brightness flash, moving orbit on headlights (reflections sweep the bonnet), static rear again, interior through open door, garage front 3/4 with small punch then 1.15 s fade to black. Each shot opens with ~0.1 s fast motion easing out ("arrives on the hit").
NEW: black-hold segment (breaks "every frame fills" -> ask user or keep 1-1.5 s), fade-out, looks.clean_night (contrast 1.1, black -1.5 %, sat 0.95, cool highlights above luma 150, lamps preserved), ease-in at clip heads (zoom 1.04->1 over 6 frames).
Film (night, vertical 60): static rear when the tail-light bar animates on (lock/unlock), low rear wheel+diffuser, wide front headlights on under a lit canopy, garage 3/4 static x2, slow arc over headlights/bonnet, interior via open door with no driver.

**Rebuild:** `looks.clean_night`; static hook with slow push while the lamps animate on; black hold <= 1.5 s (ask the user first); one cut per bass hit with `transitions.arrive`; `flash`; final `fade`.

## Style I - Garage roll

**Reference breakdown**

r6 Garage Roll (@ti.cutz red Fiat Punto, Sony + DJI Ronin, AE) - 720x1280 30fps 9.9 s, no text, Brazilian funk ~136 BPM (beat 0.44 s), vocal hook 0-1.6 s, louder from 5.5 (drop 5.53).
Grade: punchy, crushed blacks 0-5, highlights ~250, very saturated reds, neutral concrete so the red car is the only colour.
First half moving + transitions: static rear punch-in to badge (hook) -> zoom-blur into low mirror shot -> whip into badge -> 45deg rolled rear 3/4 -> low side shot with continuous ~180deg roll + rotational blur (beat 2.88) -> zoom THROUGH round mirror -> zoom through mirror reflection -> rear badge circle opens as portal onto roll shot.
Second half (from drop): calm static detail jump cuts twice as fast, on beats/half-beats: gear knob push, rear, wiper (rolled), front 3/4 headlights on, model script, sill, wheel, tail-light, bumper, grille/plate. Abrupt end (loops).
NEW: zoom-blur transition (4 frames out: scale 1->1.5 ease-in, radial blur = avg of 8 scaled copies s..1.06s; hard cut; incoming 1.3->1 with blur fading); roll/spin (rotate by angle(t), cover-scale |cos|+|sin|*16/9, rotational blur avg 6 sub-angles); whip function (5 frames 1-D motion blur <=80px + slide +-0.3W); elliptical portal (rx/ry).
Grade: contrast 1.15 sat 1.3, crush lows, warm highlights.
Film: vertical 60fps car park/night: locked rear, low side near ground, low mirror, front 3/4 headlights on, 6-8 static details 2-3 s each.

**Rebuild:** `looks.punchy`; `transitions.zoom_blur` (out/in), `roll` (synthetic gimbal roll on static shots), `whip`, `ellipse_portal` (oval mirror), `carfx.py portal` (badge); second half: static detail jump cuts on beats and half-beats.

## Style J - CGI autumn glide

**Reference breakdown**

r7 CGI Autumn Glide (@m4jor3d "Did I cook" Blender render, 14.4M views) - 1920x1080 landscape 30fps 15.2 s, no text/grain/flash, Turkish rap 129 BPM, kick enters 2.0 s. Three gloss-black cars parked on autumn leaves; natural overcast, crushed black paint reflecting the forest, slight warm cast, saturation rises with leaves.
0-2.0 hook: one wide low slow slide (slight dutch), no kick. 2.0-3.0 kick -> camera accelerates into the nose. 3.03-12.0 hard cut on almost every beat (0.45 s), ~1 frame BEFORE the beat; walkaround car by car (badge, 3/4, grille, macro, wheel+red caliper, door, haunch, tail-lights). Camera ALWAYS slides left->right (same direction) so cuts read as one continuous move. 11.9-12.7 active wing rises on a lyric. 12.4-14.3 beat jump cuts pulling back from the rear. 14.3-15.2 wide of the tails, motion settles, ends on the hit 14.77.
NEW: cut 1 frame early option; motion-matched in-points (match Farneback dx sign/magnitude +-30 % between end of A and start of B, search +-0.5 s); warm grade push.
Film: vertical 4K60, overcast, washed car on leaves/texture: low locked wide (3 s hook), slow push to nose, ~1 s locked details (badge macro, headlight 3/4, grille, wheel+caliper, door line, haunch, tail-lights, wing), low left->right side slides all same direction, static wide rear to end.

**Rebuild:** `looks.warm_natural`; cut on every beat with `editkit.early(beats)` (1 frame early); `editkit.shot_dx` + `match_inpoint` to keep every slide going the same direction across cuts; `ramp`/push into the nose on the kick entry.
