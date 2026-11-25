#!/usr/bin/env python3
"""True-peak guard for finished MP4s (CLAUDE.md: limiter -1 dBTP on every MP4).

A sample-peak limiter before AAC is not enough: the encoder can overshoot by 2-3 dB on
sharp transients (glass shattering). This measures the true peak of the encoded file and,
while it is above the target, re-encodes the audio only (video copied) through a 4x
oversampled limiter with a lower ceiling.

usage: tp_guard.py file.mp4 [file2.mp4 ...]
"""
import os
import re
import subprocess
import sys

TARGET = -1.0


def true_peak(path):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"True peak:\s*\n\s*Peak:\s*(-?[\d.]+|-inf)", out)
    return float(m[-1]) if m and m[-1] != "-inf" else -99.0


def guard(path):
    tp = true_peak(path)
    limit = 0.80
    tries = 0
    while tp > TARGET and tries < 5:
        tmp = path + ".tp.mp4"
        af = f"aresample=192000,alimiter=limit={limit:.3f}:attack=1:release=60:level=0,aresample=48000"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-map", "0:v?", "-map", "0:a", "-c:v", "copy",
                        "-af", af, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp], check=True)
        os.replace(tmp, path)
        new = true_peak(path)
        print(f"tp_guard {os.path.basename(path)}: {tp:+.1f} -> {new:+.1f} dBTP (limit {limit:.2f})")
        tp, limit, tries = new, limit * 0.9, tries + 1
    if tries == 0:
        print(f"tp_guard {os.path.basename(path)}: {tp:+.1f} dBTP ok")
    if tp > TARGET:
        sys.exit(f"tp_guard: {path} still at {tp:+.1f} dBTP")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        if os.path.isfile(p):
            guard(p)
