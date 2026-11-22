#!/usr/bin/env python3
"""Lay a voice-over (one ElevenLabs take, lines separated by pauses) on a finished video.

  python tools/voiceover.py video.mp4 voice.mp3 "0.15,7.3,14.3,17.9,24.5" out.mp4

The take is cut on its silences into as many lines as there are cue times; each line starts at its cue, or just
after the previous line if that one is still speaking (never two lines at once). The video's own sound is ducked
under the voice (sidechain), never removed, and the mix goes through the usual limiter (-1 dBTP).
"""
import json
import re
import subprocess
import sys


def probe_dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())


def speech_segments(voice, n):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", voice, "-af", "silencedetect=noise=-38dB:d=0.35", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    dur = probe_dur(voice)
    sil = list(zip(starts, ends + [dur] * (len(starts) - len(ends))))
    segs, cur = [], 0.0
    for a, b in sil:
        if a - cur > 0.15:
            segs.append([cur, a])
        cur = b
    if dur - cur > 0.15:
        segs.append([cur, dur])
    while len(segs) > n:                    # pauses inside a sentence: merge across the shortest gap
        gaps = [segs[i + 1][0] - segs[i][1] for i in range(len(segs) - 1)]
        i = gaps.index(min(gaps))
        segs[i] = [segs[i][0], segs[i + 1][1]]
        del segs[i + 1]
    if len(segs) < n:
        raise SystemExit(f"voice take has {len(segs)} lines, {n} cues given")
    return [(max(0.0, a - 0.05), b + 0.08) for a, b in segs]


def main():
    video, voice, cues, out = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3].split(",")], sys.argv[4]
    vdur = probe_dur(video)
    segs = speech_segments(voice, len(cues))
    place, prev_end = [], -1.0
    for (a, b), c in zip(segs, cues):
        t = max(c, prev_end + 0.25)
        place.append((a, b, t))
        prev_end = t + (b - a)
    f = []
    for i, (a, b, t) in enumerate(place):
        f.append(f"[1:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,adelay={int(t * 1000)}:all=1[v{i}]")
    f.append("".join(f"[v{i}]" for i in range(len(place))) + f"amix=inputs={len(place)}:normalize=0,apad,atrim=0:{vdur:.3f}[vo]")
    f.append("[vo]asplit[vo1][vo2]")
    f.append("[0:a][vo1]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck]")
    f.append("[duck][vo2]amix=inputs=2:weights='1 1.6':normalize=0,alimiter=limit=0.84:level=0[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", voice, "-filter_complex", ";".join(f),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out], check=True)
    rep = [{"line": i + 1, "cue": c, "start": round(t, 2), "end": round(t + b - a, 2)} for i, ((a, b, t), c) in enumerate(zip(place, cues))]
    print(json.dumps({"video_s": round(vdur, 2), "lines": rep}, indent=1))
    if prev_end > vdur:
        raise SystemExit(f"voice runs past the end of the video ({prev_end:.1f} s > {vdur:.1f} s)")


if __name__ == "__main__":
    main()
