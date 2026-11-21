#!/usr/bin/env python3
"""Real sound for a rendered Breakpoint Lab episode, with three tools:

  1. Openverse  (api.openverse.org)  finds REAL recordings for each physical sound of the episode, CC0 only
                                     (no credit needed, commercial use allowed);
  2. earshot    (Leonxlnx/earshot)   listens to the candidates and picks the recording + the clean single hit in it
                                     that best matches a description ("a metal spring coil clicking shut"), checks it is
                                     a real recording, and MAKES the graphic sounds (whooshes, ticks, stamp) from its
                                     catalogue learned from public-domain recordings; at the end it listens to the film;
  3. real-sfx   (Clipwing/skills)    places every sound on its exact frame (events of the engine's timeline), levels the
                                     roles, slows the slow-motion sounds down, mixes, masters and writes the MP4, a
                                     separate SFX WAV, a cue report, then verifies and critiques its own mix.

  python tools/sound/realsound.py work/config.json work/timeline.json work/video_synth.mp4 work/sound \
         --realsfx /tmp/clipwing/skills/real-sfx

The config's "sound" block decides what is real and what is made:
  "sound": {"mode": "real",
            "find":  {ROLE: {"q": ["openverse query", ...], "hear": "what the single hit sounds like", "role": "click|hit|...",
                             "make": "earshot words if Openverse has nothing that passes"}},
            "make":  {ROLE: {"words": "earshot words", "role": "whoosh|ui|hit|click"}},
            "events": {EVENT_TYPE: ROLE | {MATERIAL: ROLE}}}
Writes OUT/result/film_sfx.mp4 (+ _sfx_track.wav, _cue_report.md, _resolved_cues.json), OUT/sources.json (what each
sound is and where it comes from, with licence), OUT/report.md (all checks).
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.openverse.org/v1/audio/"
UA = {"User-Agent": "BreakpointLab-realsound/1.0 (github.com/SDAiAutomation/breakpoint-lab-studio)"}
CC0 = {"cc0", "pdm"}                  # public domain only: nothing to credit, commercial use fine
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def to_wav(src, dst):
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le", str(dst)])


def duration(p):
    out = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip()
    return float(out or 0)


# ------------------------------------------------------------------ 1. Openverse: real recordings, CC0 only
def openverse(query, n=20):
    url = API + "?" + urllib.parse.urlencode({"q": query, "license": "cc0", "page_size": n})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r).get("results", [])
        except Exception as e:                                   # rate limit or a hiccup: wait and retry
            log(f"  openverse '{query}': {e} (retry {attempt + 1})")
            time.sleep(4 * (attempt + 1))
    return []


def fetch_role(name, spec, folder, per_role=8):
    folder.mkdir(parents=True, exist_ok=True)
    got, seen = [], set()
    for q in spec.get("q", []):
        for r in openverse(q):
            lic = (r.get("license") or "").lower()
            dur = (r.get("duration") or 0) / 1000.0
            if r["id"] in seen or lic not in CC0 or not r.get("url") or (dur and dur > 20):
                continue
            seen.add(r["id"])
            raw = folder / f"{r['id']}.src"
            wav = folder / f"{r['id']}.wav"
            try:
                with urllib.request.urlopen(urllib.request.Request(r["url"], headers=UA), timeout=60) as resp:
                    raw.write_bytes(resp.read())
                to_wav(raw, wav)
                raw.unlink()
            except Exception as e:
                log(f"  {name}: skip {r['id']} ({e})")
                continue
            got.append({"file": str(wav), "openverse_id": r["id"], "title": r.get("title"), "creator": r.get("creator"),
                        "source": r.get("source"), "license": lic, "license_url": r.get("license_url"),
                        "landing": r.get("foreign_landing_url"), "query": q})
            if len(got) >= per_role:
                break
        if len(got) >= per_role:
            break
    log(f"  {name}: {len(got)} CC0 recording(s) from Openverse")
    return got


# ------------------------------------------------------------------ 2. earshot: listen, choose, trim, make
def earshot_api():
    try:
        from earshot import api
        return api
    except Exception as e:
        log(f"  earshot not importable: {e}")
        return None


def choose(api, name, spec, cands, out_dir, takes=3):
    """rank the candidates by how they sound against spec['hear'], take the clean single hits of the best one(s)"""
    if not cands or api is None:
        return []
    hear = spec["hear"]
    try:
        ranked = api.rank([c["file"] for c in cands], hear)["results"]
    except Exception as e:
        log(f"  {name}: rank failed ({e})")
        return []
    by_path = {c["file"]: c for c in cands}
    picks = []
    for r in ranked:
        if r.get("near_silent") or r["verdict"] in ("no match",) or r["z"] < 2.0:
            continue
        c = by_path[r["path"]]
        try:
            segs = api.find(r["path"], hear, top=takes, kind="event")["segments"]
        except Exception as e:
            log(f"  {name}: find failed on {r['name']} ({e})")
            continue
        for s in segs:
            if s.get("cut") or s["z"] < 2.0:
                continue
            try:
                real = api.realness(r["path"], start=s["start"], end=s["end"])
            except Exception as e:
                real = {"p_real": None, "verdict": f"not checked ({e})"}
            if real.get("p_real") is not None and (real["p_real"] < 0.6 or real["verdict"].startswith("likely code")):
                log(f"  {name}: {r['name']} {s['start']:.2f}-{s['end']:.2f} not clearly a real recording "
                    f"(p_real {real['p_real']:.2f}), skipped")
                continue
            take = (out_dir / f"{name}_{len(picks) + 1}.wav").resolve()
            sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['start']:.3f}", "-to", f"{s['end']:.3f}", "-i", r["path"],
                "-af", "afade=t=out:st=%.3f:d=0.01" % max(0.0, s["end"] - s["start"] - 0.01), str(take)])
            picks.append(dict(c, take=str(take), trim=[s["start"], s["end"]], z_file=r["z"], z_hit=s["z"],
                              p_real=real.get("p_real"), real_verdict=real.get("verdict"), hear=hear))
            log(f"  {name}: take {len(picks)} = {r['name']} {s['start']:.2f}-{s['end']:.2f} s "
                f"(match z {s['z']:+.1f}, real p {real.get('p_real')})  '{c.get('title')}' by {c.get('creator')}")
            if len(picks) >= takes:
                return picks
        if len(picks) >= takes:
            break
    return picks


def make(api, name, words, out_dir, n=1):
    """a sound made by earshot from its catalogue (learned from public-domain recordings; free, no credit)"""
    if api is None:
        return []
    out = out_dir / f"{name}.wav"
    try:
        res = api.make(words, str(out), n=n)
    except Exception as e:
        log(f"  {name}: earshot make failed ({e})")
        return []
    files = [str(Path(f).resolve()) for f in (res.get("files") or [str(out)])]
    log(f"  {name}: made by earshot: {res.get('summary', '').splitlines()[0] if res.get('summary') else files}")
    return [{"take": f, "made_by": "earshot", "words": words, "design": res.get("sound"), "license": "earshot: free, no credit"}
            for f in files]


# ------------------------------------------------------------------ 3. real-sfx: the cue sheet from the timeline
def role_for(ev, events_map):
    m = events_map.get(ev["type"])
    if isinstance(m, dict):
        return m.get(ev.get("material") or "", m.get("*"))
    return m


def cue_times(ev):
    """the frames where an event of the engine makes a sound (the same moments engine/audio.py used)"""
    ty = ev["type"]
    if ty == "question":                                    # a tick every half second while the question is up
        ts, t = [], ev["t0"] + 0.05
        while t < ev["t1"] - 0.1:
            ts.append(t)
            t += 0.5
        return ts
    if ty == "replay":
        return [max(0.0, ev["t0"] - 0.1)]
    if ty == "stamp":
        return [ev["t"] + 0.17]
    if "t" in ev:
        return [ev["t"]]
    return [ev.get("t0", 0.0)]


def build_sheet(tl, cfg, bank, video, roles_cfg):
    events_map = cfg["sound"].get("events", {})
    cues, rot, missing = [], {}, {}
    for ev in tl["events"]:
        name = role_for(ev, events_map)
        if not name:
            continue
        takes = bank.get(name) or []
        if not takes:
            missing[name] = missing.get(name, 0) + 1
            continue
        spec = roles_cfg.get(name, {})
        speed = float(ev.get("speed", 1) or 1)
        gain = float(ev.get("gain", 1) or 1)
        for t in cue_times(ev):
            k = rot.get(name, 0)
            rot[name] = k + 1
            c = {"_role": name, "t": round(t, 4), "label": f"{ev['type']}" + (f" {ev['material']}" if ev.get("material") else "")
                 + (" slow" if speed < 1 else ""),
                 "file": takes[k % len(takes)]["take"], "role": spec.get("role", "hit"),
                 "gain_db": round(20 * math.log10(max(gain, 0.05)), 1) + float(spec.get("gain_db", 0))}
            if speed < 1:                                     # slow motion: a lower, heavier take of the same sound
                c["pitch"] = -12 if speed <= 0.25 else round(12 * math.log2(speed), 1)
                c["lowpass"] = 6000
            if spec.get("anchor"):
                c["anchor"] = spec["anchor"]
            if spec.get("max_dur"):
                c["max_dur"] = spec["max_dur"]
            cues.append(c)
    cues.sort(key=lambda c: c["t"])
    # a run of one role faster than max_rate per second (a slinky's coils closing) is thinned: keep the loudest
    kept, last = [], {}
    for c in cues:
        rate = float(roles_cfg.get(c["_role"], {}).get("max_rate", 0) or 0)
        prev = last.get(c["label"])
        if rate and prev is not None and c["t"] - prev["t"] < 1.0 / rate:
            if c["gain_db"] > prev["gain_db"]:
                prev["gain_db"] = c["gain_db"]
            continue
        kept.append(c)
        last[c["label"]] = c
    for c in kept:
        del c["_role"]
    log(f"  thinned {len(cues) - len(kept)} cue(s) of fast runs")
    cues = kept
    for k, n in missing.items():
        log(f"  no sound for '{k}' ({n} event(s)): left quiet")
    return {"video": str(video), "keep_audio": "no", "cues": cues}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("timeline")
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--realsfx", required=True, help="the real-sfx skill folder (Clipwing/skills/skills/real-sfx)")
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    tl = json.load(open(a.timeline, encoding="utf-8"))
    snd = cfg.get("sound") or {}
    out = Path(a.out).resolve()
    (out / "lib").mkdir(parents=True, exist_ok=True)
    (out / "takes").mkdir(parents=True, exist_ok=True)
    random.seed(1)
    api = earshot_api()

    log("## 1-2. Openverse finds, earshot chooses")
    bank, sources, roles_cfg = {}, {}, {}
    for name, spec in (snd.get("find") or {}).items():
        roles_cfg[name] = spec
        cands = fetch_role(name, spec, out / "lib" / name)
        picks = choose(api, name, spec, cands, out / "takes")
        if not picks and spec.get("make"):
            log(f"  {name}: no CC0 recording passed earshot's ears: made instead")
            picks = make(api, name, spec["make"], out / "takes", n=2)
        bank[name] = picks
        sources[name] = picks
    hybrid = snd.get("mode") == "hybrid"
    if hybrid:                  # the channel's own graphic sounds (beeps, countdown, stamp, whooshes) keep the rhythm
        snd = dict(snd, make={})
        cfg = dict(cfg, sound=dict(snd, events={k: v for k, v in snd.get("events", {}).items()
                                               if any(r in (snd.get("find") or {}) for r in
                                                      ((v.values() if isinstance(v, dict) else [v])))}))
    log("## 2b. earshot makes the graphic sounds" + (" (hybrid: no, the engine's own graphic sounds stay)" if hybrid else ""))
    for name, spec in (snd.get("make") or {}).items():
        roles_cfg[name] = spec
        bank[name] = make(api, name, spec["words"], out / "takes", n=spec.get("n", 1))
        sources[name] = bank[name]
    json.dump(sources, open(out / "sources.json", "w"), indent=2, ensure_ascii=False)

    log("## 3. real-sfx places, mixes, verifies, critiques")
    sheet = build_sheet(tl, cfg, bank, Path(a.video).resolve(), roles_cfg)
    log(f"  {len(sheet['cues'])} cues on the frames")
    if hybrid:                  # graphic layer = engine/audio.py on the timeline without the physical events
        phys = set(cfg["sound"]["events"])
        tl_ui = dict(tl, events=[e for e in tl["events"] if e["type"] not in phys])
        json.dump(tl_ui, open(out / "timeline_ui.json", "w"))
        repo = Path(__file__).resolve().parents[2]
        subprocess.run([sys.executable, str(repo / "engine" / "audio.py"), str(out / "timeline_ui.json"), str(out / "ui.wav")],
                       check=True, cwd=repo)
        sheet["base_audio"] = [{"file": str(out / "ui.wav"), "keep_level": True}]
        sheet["keep_audio"] = "yes"   # "no" would drop the base stems too (real-sfx: the stems ARE the original audio)
        log(f"  graphic layer: engine sounds for {len(tl_ui['events'])} event(s), physical sounds are the real recordings")
    sp = out / "cues.json"
    json.dump(sheet, open(sp, "w"), indent=1)
    res = out / "result"
    res.mkdir(exist_ok=True)
    rs = Path(a.realsfx)
    run = lambda *x: subprocess.run([sys.executable, *x], cwd=rs, capture_output=True, text=True)
    p = run("scripts/mix.py", str(sp.resolve()), "--out", str((res / "film_sfx.mp4").resolve()), "--target-lufs", "-14")
    log(p.stdout[-3000:])
    if p.returncode:
        log(p.stderr[-3000:])
        sys.exit("real-sfx mix failed")
    resolved = res / "film_sfx_resolved_cues.json"
    track = res / "film_sfx_sfx_track.wav"
    for script, extra in (("scripts/verify.py", []), ("scripts/critique.py", ["--out", str((res / "critique.md").resolve())])):
        q = run(script, str(resolved.resolve()), str(track.resolve()), *extra)
        log(f"### {script}\n" + q.stdout[-4000:] + (q.stderr[-1500:] if q.returncode else ""))

    log("## 4. earshot listens to the finished film")
    film = res / "film_sfx.mp4"
    for cmd in (["critique", str(film)], ["timeline", str(film), "--detail", "low"]):
        q = subprocess.run(["earshot", *cmd], capture_output=True, text=True)
        log(f"### earshot {cmd[0]}\n" + (q.stdout[-4000:] or q.stderr[-1500:]))
    with open(out / "report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    print(f"done: {film}")


if __name__ == "__main__":
    main()
