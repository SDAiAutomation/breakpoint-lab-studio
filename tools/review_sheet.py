#!/usr/bin/env python3
"""Comfort review sheet: the key stills side by side, with what the viewer's phone puts on top of them.

  python tools/review_sheet.py STILLS_DIR OUT.png [--cols 4]

Each still gets: the TikTok / YouTube Shorts buttons (right column) and caption block (bottom left) in red,
the safe zone lines (y 250 and 1440) and the text band (y 260-600) outlined. Look for:
  - the subject (the object, the moment that matters) clear of every red zone and of the text band,
  - the subject big enough to read without effort (>= ~80 px wide on 1080),
  - one thing to look at per frame (text OR action, not both fighting),
  - the same framing from one round to the next.
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
UI = [  # (x0, y0, x1, y1) in 1080x1920: what the apps draw over the video (union of TikTok and YouTube Shorts)
    (948, 980, 1080, 1720, "buttons"),        # like / comment / share / avatar column
    (0, 1560, 900, 1920, "caption"),          # account name, caption, music line
    (0, 0, 1080, 170, "top bar"),             # tabs / search / live
]


def annotate(img):
    im = img.convert("RGBA").resize((W, H))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for x0, y0, x1, y1, _ in UI:
        d.rectangle([x0, y0, x1, y1], fill=(224, 48, 63, 70), outline=(224, 48, 63, 200), width=3)
    d.rectangle([0, 260, W - 1, 600], outline=(40, 110, 230, 220), width=4)            # text band
    for y in (250, 1440):
        d.line([(0, y), (W, y)], fill=(224, 48, 63, 230), width=4)
    return Image.alpha_composite(im, ov).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stills")
    ap.add_argument("out")
    ap.add_argument("--cols", type=int, default=4)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.stills, "*.png")) + glob.glob(os.path.join(a.stills, "*.jpg")),
                   key=lambda p: float("".join(ch for ch in os.path.basename(p) if ch.isdigit() or ch == ".").strip(".") or 0))
    if not files:
        raise SystemExit("no stills")
    tw, th = 360, 640
    rows = (len(files) + a.cols - 1) // a.cols
    sheet = Image.new("RGB", (a.cols * tw, rows * (th + 34)), (245, 246, 248))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(os.path.join(os.path.dirname(__file__), "..", "engine", "fonts", "Poppins-Bold.ttf"), 22)
    except OSError:
        font = ImageFont.load_default()
    for i, f in enumerate(files):
        x, y = (i % a.cols) * tw, (i // a.cols) * (th + 34)
        sheet.paste(annotate(Image.open(f)).resize((tw, th)), (x, y + 34))
        d.text((x + 8, y + 4), os.path.splitext(os.path.basename(f))[0].replace("still_", "t = ") + " s", fill=(29, 33, 38), font=font)
    sheet.save(a.out)
    print(f"review sheet: {len(files)} stills -> {a.out}")


if __name__ == "__main__":
    main()
