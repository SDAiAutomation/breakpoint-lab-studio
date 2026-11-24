#!/usr/bin/env python3
"""YouTube cut (~40 s) of a finished episode, taken from the long video with its timeline: no new render.

Keeps, in order: the hook, the whole round the hook teases (title, question, test, slow motion, answer, fact),
the WHY explanation and the outro (source + call to comment). TikTok keeps the long version (>= 60 s).

  python tools/shortcut.py work/config.json work/timeline.json work/video.mp4 work/video_short.mp4

Config (optional): "short": {"round": 2, "explain_lines": 3} or {"rounds": [1, 2]}; default round = hook_round,
"from": "question" (default: each kept round starts at its question, the title card is skipped) or "round",
all explain lines. Keep every round the explanation and the surprise rely on, even if the cut goes past 45 s.
The WHY is never sped up and never dropped. explain_lines stops the explanation just before a line that is about a
round the short leaves out (each line appears 2.2 s after the previous one, so every kept line stays readable).
"""
import json
import subprocess
import sys


def segments(cfg, tl):
    ev = tl["events"]
    rounds = sorted(e["t"] for e in ev if e["type"] == "round")
    explain = next((e for e in ev if e["type"] == "explain"), None)
    dur = float(tl["duration"])
    outro = max((e["t"] for e in ev if e["type"] == "card" and explain and e["t"] >= explain["t1"] - 0.01), default=None)
    short = cfg.get("short") or {}
    ks = short.get("rounds") or [short.get("round", cfg.get("hook_round", 1))]
    segs = [(0.0, rounds[0])]
    for r in ks:                                   # every round the story needs (e.g. metal THEN the lighter plastic)
        k = max(0, min(int(r) - 1, len(rounds) - 1))
        end_k = rounds[k + 1] if k + 1 < len(rounds) else (explain["t0"] if explain else dur)
        start = rounds[k]
        if short.get("from", "question") == "question":   # skip the round title: straight from the hook to the question + hit
            qs = [e["t0"] for e in ev if e["type"] == "question" and rounds[k] <= e["t0"] < end_k]
            start = qs[0] if qs else start
        segs.append((start, end_k))
    if explain:
        n = short.get("explain_lines")
        n_all = len((cfg.get("explain") or {}).get("lines", []))
        end = explain["t1"] if not n or n >= n_all else min(explain["t1"], explain["t0"] + 0.8 + n * 2.2)
        segs.append((explain["t0"], end))
    segs.append((outro if outro is not None else (explain["t1"] if explain else end_k), dur))
    return [(round(a, 3), round(b, 3)) for a, b in segs if b - a > 0.2]


def main():
    cfg_p, tl_p, src, dst = sys.argv[1:5]
    cfg = json.load(open(cfg_p, encoding="utf-8"))
    tl = json.load(open(tl_p, encoding="utf-8"))
    segs = segments(cfg, tl)
    f, parts = [], []
    for i, (a, b) in enumerate(segs):
        d = b - a
        f.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}]")
        f.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={max(0, d - 0.06):.3f}:d=0.06[a{i}]")
        parts.append(f"[v{i}][a{i}]")
    f.append("".join(parts) + f"concat=n={len(segs)}:v=1:a=1[v][ac]")
    f.append("[ac]alimiter=limit=0.84:level=0[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", ";".join(f), "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", dst], check=True)
    total = sum(b - a for a, b in segs)
    print(f"short cut: {len(segs)} parts, {total:.1f} s: " + ", ".join(f"{a:.1f}-{b:.1f}" for a, b in segs))


if __name__ == "__main__":
    main()
