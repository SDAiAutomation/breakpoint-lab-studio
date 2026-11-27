#!/usr/bin/env python3
"""Long-format compilation (16:9) from finished episodes: no new render.

  python tools/compile.py configs/compilations/<spec>.json work            # downloaded sources in work/src_<i>.mp4
  python tools/compile.py ... --stills-only                                # only the key frames + review sheet

Each episode is kept from 0 to its call to action (spec "end_s"): hook, rounds, slow motion, WHY and source card,
without the next-test promise (it would announce the wrong next episode). The vertical video sits in the middle of a
1920x1080 frame over a blurred, darker copy of itself (the image moves everywhere, always); the side panels say which
test it is (left) and whose lab it is (right). Opens straight on the first test's hook with "Can you guess all 6?"
on the left panel (motion from frame 0), ends on a 10 s card (score + CTA) over the last test's slow motion.
Two text sizes only (60 and 40 px), every text stays the whole segment (readable), nothing covers the scene.
Writes work/compilation.mp4, work/description.txt (title, text, chapters, sources), work/stills/*.png, work/review.png.
"""
import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FONT = str(REPO / "engine" / "fonts" / "Poppins-Bold.ttf")
W, H, FPS = 1920, 1080, 30
FW = 608                       # the 9:16 episode scaled to the full height
PANEL = (W - FW) // 2          # 656 px on each side
WHITE, GOLD, GREY = "0xF2F2F2", "0xF7C21A", "0xD4D8DD"


def sh(cmd):
    subprocess.run(cmd, check=True)


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out)


def text(work, name, s):
    p = work / "txt" / f"{name}.txt"
    p.parent.mkdir(exist_ok=True)
    p.write_text(s, encoding="utf-8")
    return str(p)


def dt(work, name, s, size, color, x, y, enable=None):
    """drawtext from a file (apostrophes and colons need no escaping); x may be 'L' / 'R' = centred in a side panel"""
    cx = {"L": f"{PANEL // 2}-text_w/2", "R": f"{W - PANEL // 2}-text_w/2", "C": "(w-text_w)/2"}.get(x, x)
    f = (f"drawtext=fontfile={FONT}:textfile={text(work, name, s)}:fontsize={size}:fontcolor={color}"
         f":x={cx}:y={y}:shadowcolor=0x000000@0.55:shadowx=0:shadowy=3")
    if enable:
        f += f":enable='{enable}'"
    return f


def frame_chain(src_label, extra):
    """blurred cover background + the vertical episode centred, then the panel texts"""
    return (f"[{src_label}]split=2[a][b];"
            f"[a]scale={W}:-2,crop={W}:{H},gblur=sigma=40,eq=brightness=-0.42:saturation=0.6[bg];"
            f"[b]scale={FW}:{H}[fg];"
            f"[bg][fg]overlay=x={PANEL}:y=0,format=yuv420p" + ("," + ",".join(extra) if extra else "") + "[v]")


def panels(work, i, n, seg, spec, intro_s):
    label = seg["label"]
    tag = f"TEST {i + 1} / {n}"
    first = i == 0
    show = f"gte(t,{intro_s})" if first else None
    f = [dt(work, f"tag{i}", tag, 40, GOLD, "L", 430, show),
         dt(work, f"l{i}a", label[0], 60, WHITE, "L", 490, show)]
    if len(label) > 1:
        f.append(dt(work, f"l{i}b", label[1], 60, WHITE, "L", 565, show))
    if first:                                            # the opening question, over the first hook
        a, b = spec["intro"]
        f += [dt(work, "introa", a, 60, WHITE, "L", 470, f"lt(t,{intro_s})"),
              dt(work, "introb", b, 60, GOLD, "L", 545, f"lt(t,{intro_s})")]
    f += [dt(work, f"bp{i}", "BREAKPOINT", 60, GREY, "R", 470),
          dt(work, f"lab{i}", "LAB", 60, GOLD, "R", 545),
          dt(work, f"h{i}", spec.get("handle", "@BreakpointLabTV"), 40, WHITE, "R", 640)]
    return f


def encode(work, src, ss, t, chain, out, afilter):
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-t", f"{t:.3f}", "-i", str(src),
        "-filter_complex", chain + f";[0:a]{afilter}[aout]", "-map", "[v]", "-map", "[aout]",
        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out)])


def ts(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("work")
    ap.add_argument("--stills-only", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    work = Path(a.work).resolve()
    segs = spec["segments"]
    n = len(segs)
    intro_s = float(spec.get("intro_s", 3.5))

    for i, s in enumerate(segs):                        # the right file: same length as its rebuilt timeline
        d = probe(work / f"src_{i}.mp4")
        assert abs(d - s["duration"]) < 0.35, f"segment {i + 1}: video {d:.2f} s, timeline {s['duration']} s"

    parts, starts, t = [], [], 0.0
    # each episode's own loudness is brought to the same level, short fades so the hard cuts do not click
    for i, s in enumerate(segs):
        dur = float(s["end_s"])
        if a.stills_only:
            dur = min(dur, 12.0)
        out = work / f"part_{i}.mp4"
        af = f"loudnorm=I=-14:TP=-2:LRA=11,aresample=48000,afade=t=in:d=0.03,afade=t=out:st={dur - 0.25:.3f}:d=0.25"
        encode(work, work / f"src_{i}.mp4", 0, dur, frame_chain("0:v", panels(work, i, n, s, spec, intro_s)), out, af)
        starts.append(t)
        t += probe(out)
        parts.append(out)

    # end card: the last test's slow motion, blurred behind the score question and the CTA, sound kept low
    e = spec["end"]
    es = float(e.get("seconds", 10))
    last = segs[-1]
    ss = max(0.0, float(last["end_s"]) - es - 2.0)
    endc = [dt(work, "e0", e["lines"][0], 60, WHITE, "C", 360), dt(work, "e1", e["lines"][1], 60, GOLD, "C", 440),
            dt(work, "e2", e["cta"], 40, WHITE, "C", 600)]
    chain = (f"[0:v]scale={W}:-2,crop={W}:{H},gblur=sigma=40,eq=brightness=-0.45:saturation=0.6,format=yuv420p,"
             + ",".join(endc) + f",fade=t=out:st={es - 0.6:.2f}:d=0.6[v]")
    out = work / "part_end.mp4"
    encode(work, work / f"src_{n - 1}.mp4", ss, es, chain, out,
           f"loudnorm=I=-24:TP=-6,aresample=48000,afade=t=in:d=0.3,afade=t=out:st={es - 1.5:.2f}:d=1.5")
    starts.append(t)
    parts.append(out)

    lst = work / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    final = work / "compilation.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
        "-movflags", "+faststart", str(final)])
    sh(["python3", str(REPO / "tools" / "sound" / "tp_guard.py"), str(final)])
    total = probe(final)

    # key frames: the first second (motion from frame 0), each test's start and middle, the end card
    stills = work / "stills"
    stills.mkdir(exist_ok=True)
    marks = [("0.1", 0.1), ("1.5", 1.5), ("3.0", 3.0), ("4.0 intro gone", 4.0)]
    for i, s in enumerate(segs):
        marks += [(f"T{i + 1} start", starts[i] + 0.5), (f"T{i + 1} mid", starts[i] + (probe(parts[i]) * 0.5))]
    marks += [("end card", starts[-1] + 3.0)]
    pngs = []
    for k, (lab, tt) in enumerate(marks):
        p = stills / f"{k:02d}_{tt:07.2f}s.png"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{min(tt, total - 0.1):.3f}", "-i", str(final), "-frames:v", "1", str(p)])
        pngs.append((lab, p))
    try:
        from PIL import Image, ImageDraw, ImageFont
        cols, tw, th = 3, 640, 360
        rows = (len(pngs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * (th + 34)), (24, 26, 30))
        fnt = ImageFont.truetype(FONT, 22)
        for k, (lab, p) in enumerate(pngs):
            im = Image.open(p).convert("RGB").resize((tw, th))
            x, y = (k % cols) * tw, (k // cols) * (th + 34)
            sheet.paste(im, (x, y + 34))
            ImageDraw.Draw(sheet).text((x + 8, y + 4), lab, font=fnt, fill=(240, 240, 240))
        sheet.save(work / "review.png")
    except ImportError:
        pass

    # description: title, text, chapters (YouTube: first at 0:00, each >= 10 s), sources of every test
    lines = [spec["title"], ""] + spec["description"] + ["", "Chapters:"]
    for i, s in enumerate(segs):
        lines.append(f"{ts(starts[i])} {s['chapter']}")
    lines.append(f"{ts(starts[-1])} Your score")
    lines += ["", "Sources (one card at the end of each test):"]
    for s in segs:
        cfg = json.load(open(REPO / s["config"], encoding="utf-8"))
        src = cfg.get("source")
        src = " · ".join(src) if isinstance(src, list) else str(src)
        lines.append(f"- {s['chapter']} (test {s['episode']:03d}): {src}")
    lines += ["", "Subscribe: you pick the next test.", "#physics #science #experiment"]
    (work / "description.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"compilation: {total:.1f} s ({ts(total)}), {n} tests")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
