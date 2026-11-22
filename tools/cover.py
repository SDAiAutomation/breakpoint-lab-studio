#!/usr/bin/env python3
"""Instagram / profile cover: the key moment (scene only, no answer shown) + the question in big letters.

  python tools/cover.py time  work/config.json work/timeline.json          -> prints the cover time (s)
  python tools/cover.py build work/config.json work/cover_scene.png work/cover.jpg

Same look every episode so the profile grid reads as one channel. Everything that matters sits inside the centre
3:4 crop (y 240-1680) that the profile grid shows. Time: config "cover_t", else the slow motion of the last replay,
just before the break (tension, no answer).
"""
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT = os.path.join(os.path.dirname(__file__), "..", "engine", "fonts", "Poppins-Bold.ttf")
NAVY, WHITE, YELLOW, RED = (16, 22, 34), (255, 255, 255), (255, 196, 0), (230, 57, 70)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def cover_time(cfg, tl):
    if cfg.get("cover_t") is not None:
        return float(cfg["cover_t"])
    reps = [e for e in tl["events"] if e["type"] == "replay"]
    if reps:
        r = reps[-1]
        return r["t0"] + 0.35 * (r["t1"] - r["t0"])
    return tl["duration"] * 0.4


def texts(cfg):
    q = cfg.get("cover_question") or " ".join(cfg.get("hook") or []) or (cfg.get("caption") or "").split("?")[0] + "?"
    bet = cfg.get("cover_bet")
    if bet is None:
        parts = [p.strip() for p in EMOJI.sub("", cfg.get("caption") or "").split("?")]
        bet = (parts[1] + "?") if len(parts) > 2 and 0 < len(parts[1]) <= 34 else ""
    return EMOJI.sub("", q).strip(), EMOJI.sub("", bet).strip()


def wrap(d, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def build(cfg, scene_p, out_p):
    img = Image.open(scene_p).convert("RGB").resize((W, H))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(ov)
    for y in range(0, 980):                                # navy band fading into the scene: text always readable
        a = 235 if y < 700 else int(235 * (1 - (y - 700) / 280) ** 1.6)
        g.line([(0, y), (W, y)], fill=NAVY + (a,))
    img = Image.alpha_composite(img.convert("RGBA"), ov)
    d = ImageDraw.Draw(img)
    q, bet = texts(cfg)
    series = (cfg.get("series") or "").replace("QUALITY CONTROL", "TEST").strip()
    f_tag, f_bet = ImageFont.truetype(FONT, 34), ImageFont.truetype(FONT, 50)
    size = 104
    while size > 60:
        f_q = ImageFont.truetype(FONT, size)
        lines = wrap(d, q.upper(), f_q, 920)
        if len(lines) <= 4:
            break
        size -= 6
    tag = "BREAKPOINT LAB" + (" · " + series.split("·")[-1].strip() if "·" in series else "")
    tw = d.textlength(tag, font=f_tag)
    d.rounded_rectangle([(W - tw) / 2 - 24, 290, (W + tw) / 2 + 24, 346], 28, fill=RED)
    d.text((W / 2, 318), tag, font=f_tag, fill=WHITE, anchor="mm")
    y = 400
    for i, line in enumerate(lines):
        col = YELLOW if i == len(lines) - 1 else WHITE
        d.text((W / 2, y), line, font=f_q, fill=col, anchor="ma", stroke_width=3, stroke_fill=NAVY)
        y += int(size * 1.08)
    if bet:
        bw = d.textlength(bet, font=f_bet)
        y += 24
        d.rounded_rectangle([(W - bw) / 2 - 30, y, (W + bw) / 2 + 30, y + 84], 42, fill=WHITE)
        d.text((W / 2, y + 42), bet, font=f_bet, fill=NAVY, anchor="mm")
    img.convert("RGB").save(out_p, quality=92)
    print(f"cover: {out_p} ({len(lines)} lines, {size}px)")


if __name__ == "__main__":
    mode = sys.argv[1]
    cfg = json.load(open(sys.argv[2], encoding="utf-8"))
    if mode == "time":
        print(f"{cover_time(cfg, json.load(open(sys.argv[3], encoding='utf-8'))):.2f}")
    else:
        build(cfg, sys.argv[3], sys.argv[4])
