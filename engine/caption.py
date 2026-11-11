"""Écrit le .txt envoyé avec la vidéo : légende, explication de l'expérience, sources.

Usage : python3 engine/caption.py work/config.json work/caption.txt
La config doit contenir `description` (texte ou liste de paragraphes) : ce qu'on teste,
ce qui se passe et pourquoi, avec les mêmes chiffres que la vidéo.
"""
import json
import sys


def as_list(v):
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)


def build(cfg):
    parts = []
    if cfg.get("caption"):
        parts.append(cfg["caption"].strip())
    desc = as_list(cfg.get("description"))
    if desc:
        parts.append("THE EXPERIMENT\n" + "\n\n".join(p.strip() for p in desc))
    sources = as_list(cfg.get("source")) + as_list(cfg.get("sources_detail"))
    if sources:
        parts.append("SOURCES\n" + "\n".join("- " + s.strip() for s in sources))
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(build(cfg))
