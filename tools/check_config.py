#!/usr/bin/env python3
"""Editorial checks run before a render (CLAUDE.md, YouTube Studio Nov 2026). Exit 1 with the reasons if a rule fails.

- the caption (YouTube title / TikTok text) opens with a question: '?' in its first sentence;
- the caption never gives the answer: no number from a stamp (the result) may appear in it (lone digits are choices);
- the end screen: "cta" asks to subscribe with a reason, "next_test" (if set) is a question of <= 6 words;
- every config has a source and a description.
"""
import json
import re
import sys

NUM = re.compile(r"\d+(?:[.,]\d+)?")


def check(c):
    err = []
    cap = (c.get("caption") or "").strip()
    first = re.split(r"(?<=[.!?])\s", cap, maxsplit=1)[0] if cap else ""
    if "?" not in first:
        err.append(f"caption: the title must open with a question (2-3 choices or a paradox): '{first[:90]}'")
    answers = set()
    for r in c.get("rounds", []):
        for k in ("stamp",):
            v = r.get(k)
            txt = v.get("text") if isinstance(v, dict) else v
            answers.update(NUM.findall(txt or ""))
        answers.update(NUM.findall(str(r.get("result_chip") or "")))
    answers = {a for a in answers if len(a) > 1}      # a lone digit is a choice ("1, 2 or 3?"), not a spoiler
    spoil = sorted(a for a in answers if re.search(r"(?<![\d.,])" + re.escape(a) + r"(?![\d.,])", cap))
    if spoil:
        err.append(f"caption: gives the answer ({', '.join(spoil)} is a result on screen); ask, don't tell")
    nx = c.get("next_test")
    if nx is not None:
        if "?" not in nx:
            err.append(f"next_test: must be a question: '{nx}'")
        if len(nx.replace("?", " ").split()) > 6:
            err.append(f"next_test: <= 6 words: '{nx}'")
    if not c.get("source"):
        err.append("source: missing (every number must be sourced)")
    if not c.get("description"):
        err.append("description: missing")
    return err


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        e = check(json.load(open(p, encoding="utf-8")))
        for x in e:
            print(f"{p}: {x}")
        bad += bool(e)
    sys.exit(1 if bad else 0)
