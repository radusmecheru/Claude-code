#!/usr/bin/env python3
"""Captions and on-screen text for TikTok / Shorts.

  transcribe  video -> words.json (word-level timestamps, faster-whisper, Romanian by default)
  ass         words.json -> .ass subtitles in a trending style (pop | highlight | box)
  textbox     TikTok-native rounded text box (white box, black text, colour emoji) as a PNG
  burn        burn an .ass file and/or overlay PNGs onto a video

Typical run:
  python3 tools/captions.py transcribe in.mp4 work/words.json
  python3 tools/captions.py ass work/words.json work/subs.ass --style pop --accent '#FFE500'
  python3 tools/captions.py textbox "Claude has cooked 😳" work/title.png
  python3 tools/captions.py burn in.mp4 out.mp4 --ass work/subs.ass --png work/title.png@0.2
"""
import argparse
import json
import os
import re
import subprocess
import sys

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts')


def cmd_transcribe(a):
    from faster_whisper import WhisperModel
    import numpy as np
    model = WhisperModel(a.model, device='cpu', compute_type='int8')
    # Decode with ffmpeg ourselves: faster-whisper's PyAV path breaks whenever pip upgrades `av`.
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', a.input, '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    segs, info = model.transcribe(audio, language=a.lang or None, word_timestamps=True, vad_filter=True,
                                  beam_size=5)
    words = []
    for s in segs:
        for w in s.words:
            words.append({'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3), 'p': round(w.probability, 3)})
        print(f'[{s.start:6.2f}] {s.text.strip()}', file=sys.stderr)
    json.dump({'lang': info.language, 'words': words}, open(a.output, 'w'), ensure_ascii=False, indent=1)


def ass_color(hex_rgb, alpha=0):
    h = hex_rgb.lstrip('#')
    return f'&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}'.upper()


def chunk(words, max_words, max_gap=0.6):
    """Group words into short on-screen phrases, breaking on pauses and punctuation."""
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w['s'] - cur[-1]['e'] > max_gap or re.search(r'[.!?]$', cur[-1]['w'])):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def ts(t):
    t = max(t, 0)
    return f'{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}'


def cmd_ass(a):
    words = json.load(open(a.input))['words']
    if a.upper:
        for w in words:
            w['w'] = w['w'].upper()
    font, size = a.font, a.size
    white, black, acc = ass_color('#FFFFFF'), ass_color('#000000'), ass_color(a.accent)
    margin_v = int(1920 * a.y)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font},{size},{white},{acc},{black},{ass_color('#000000', 0x60)},-1,0,0,0,100,100,0,0,1,{a.outline},{a.shadow},2,70,70,{margin_v},1
Style: Box,{font},{size},{ass_color('#000000')},{acc},{white},{white},-1,0,0,0,100,100,0,0,3,14,0,2,70,70,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    pop = r'{\fscx70\fscy70\t(0,90,\fscx112\fscy112)\t(90,160,\fscx100\fscy100)}'
    for grp in chunk(words, a.words):
        start, end = grp[0]['s'], grp[-1]['e'] + 0.05
        if a.style == 'pop':
            # One phrase on screen; the word being spoken pops and takes the accent colour.
            for i, w in enumerate(grp):
                ws = w['s']
                we = grp[i + 1]['s'] if i + 1 < len(grp) else end
                parts = []
                for j, x in enumerate(grp):
                    if j == i:
                        parts.append(r'{\c' + acc + r'}' + pop + x['w'] + r'{\r}')
                    else:
                        parts.append(x['w'])
                lines.append(f'Dialogue: 0,{ts(ws)},{ts(we)},Main,,0,0,0,,' + ' '.join(parts))
        elif a.style == 'highlight':
            # Karaoke fill: words light up in the accent colour as they are spoken.
            parts = []
            for i, w in enumerate(grp):
                nxt = grp[i + 1]['s'] if i + 1 < len(grp) else w['e']
                parts.append(r'{\kf' + str(max(1, round((nxt - w['s']) * 100))) + '}' + w['w'])
            lead = r'{\k' + str(max(0, round((grp[0]['s'] - start) * 100))) + '}'
            lines.append(f'Dialogue: 0,{ts(start)},{ts(end)},Main,,0,0,0,,{pop}{lead}' + ' '.join(parts))
        else:  # box: TikTok-native white box, one word at a time appears
            for i, w in enumerate(grp):
                ws = w['s']
                we = grp[i + 1]['s'] if i + 1 < len(grp) else end
                text = ' '.join(x['w'] for x in grp[:i + 1])
                lines.append(f'Dialogue: 0,{ts(ws)},{ts(we)},Box,,0,0,0,,{text}')
    if a.style == 'highlight':
        # In karaoke mode SecondaryColour is the "not yet sung" colour.
        head = head.replace(f'Style: Main,{font},{size},{white},{acc}', f'Style: Main,{font},{size},{acc},{white}')
    open(a.output, 'w', encoding='utf-8').write(head + '\n'.join(lines) + '\n')
    print(f'{len(lines)} events -> {a.output}', file=sys.stderr)


def cmd_textbox(a):
    """TikTok's classic text style: rounded white plate, bold dark text, colour emoji."""
    from PIL import Image, ImageDraw, ImageFont
    text_font = ImageFont.truetype(os.path.join(FONT_DIR, a.font_file), a.size)
    # CBDT bitmap emoji (Ubuntu fonts-noto-color-emoji); PIL cannot draw the COLRv1 build from Google Fonts.
    emoji_path = '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'
    emoji_font = ImageFont.truetype(emoji_path, 109) if os.path.exists(emoji_path) else None
    emoji_re = re.compile('[\U0001F000-\U0001FAFF☀-➿️‍]+')
    runs = []
    pos = 0
    for m in emoji_re.finditer(a.text):
        if m.start() > pos:
            runs.append(('t', a.text[pos:m.start()]))
        runs.append(('e', m.group().replace('️', '')))
        pos = m.end()
    if pos < len(a.text):
        runs.append(('t', a.text[pos:]))
    # Measure
    asc, desc = text_font.getmetrics()
    line_h = asc + desc
    es = a.size / 109 * 1.05
    widths = []
    for kind, s in runs:
        if kind == 't':
            widths.append(text_font.getlength(s))
        else:
            widths.append(len(s) * 109 * es + 6) if emoji_font else widths.append(0)
    tw = sum(widths)
    pad_x, pad_y = int(a.size * 0.45), int(a.size * 0.22)
    Wd, Hd = int(tw + pad_x * 2), int(line_h + pad_y * 2)
    img = Image.new('RGBA', (Wd, Hd), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, Wd - 1, Hd - 1], radius=int(a.size * 0.28), fill=a.bg)
    x = pad_x
    for (kind, s), w in zip(runs, widths):
        if kind == 't':
            d.text((x, pad_y), s, font=text_font, fill=a.fg)
        elif emoji_font:
            for ch in s:
                e = Image.new('RGBA', (160, 160), (0, 0, 0, 0))
                ImageDraw.Draw(e).text((0, 0), ch, font=emoji_font, embedded_color=True)
                e = e.crop(e.getbbox() or (0, 0, 1, 1))
                e = e.resize((int(e.width * es), int(e.height * es)), Image.LANCZOS)
                img.alpha_composite(e, (int(x + 3), int(pad_y + (line_h - e.height) / 2)))
                x += 109 * es
            x -= len(s) * 109 * es
        x += w
    img.save(a.output)
    print(f'{Wd}x{Hd} -> {a.output}', file=sys.stderr)


def cmd_burn(a):
    inputs = ['-i', a.input]
    chain = '[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1'
    if a.ass:
        chain += f",ass='{a.ass}':fontsdir='{FONT_DIR}'"
    chain += '[v0]'
    last = 'v0'
    for i, spec in enumerate(a.png or []):
        path, _, y = spec.partition('@')
        y = float(y or 0.2)
        inputs += ['-i', path]
        chain += f';[{last}][{i + 1}:v]overlay=x=(W-w)/2:y=H*{y}-h/2[v{i + 1}]'
        last = f'v{i + 1}'
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', chain, '-map', f'[{last}]', '-map', '0:a?',
           '-c:v', 'libx264', '-crf', '17', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
           '-movflags', '+faststart', a.output]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('transcribe'); p.add_argument('input'); p.add_argument('output')
    p.add_argument('--model', default='medium'); p.add_argument('--lang', default='ro', help="'' = auto-detect")
    p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser('ass'); p.add_argument('input'); p.add_argument('output')
    p.add_argument('--style', choices=['pop', 'highlight', 'box'], default='pop')
    p.add_argument('--font', default='Montserrat Black'); p.add_argument('--size', type=int, default=88)
    p.add_argument('--accent', default='#FFE500'); p.add_argument('--words', type=int, default=3)
    p.add_argument('--y', type=float, default=0.30, help='distance from bottom, fraction of height')
    p.add_argument('--outline', type=int, default=6); p.add_argument('--shadow', type=int, default=2)
    p.add_argument('--no-upper', dest='upper', action='store_false'); p.set_defaults(fn=cmd_ass)

    p = sub.add_parser('textbox'); p.add_argument('text'); p.add_argument('output')
    p.add_argument('--size', type=int, default=64); p.add_argument('--font-file', default='TikTokSans-700.ttf')
    p.add_argument('--bg', default='#FFFFFF'); p.add_argument('--fg', default='#111111')
    p.set_defaults(fn=cmd_textbox)

    p = sub.add_parser('burn'); p.add_argument('input'); p.add_argument('output'); p.add_argument('--ass')
    p.add_argument('--png', action='append', help='overlay.png@y  (y = centre as fraction of height)')
    p.set_defaults(fn=cmd_burn)

    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
