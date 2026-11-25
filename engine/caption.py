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
    # production notes ("On screen: ...": which figure goes where) stay in the config, not in the public text
    detail = [s for s in as_list(cfg.get("sources_detail")) if not s.strip().lower().startswith("on screen")]
    sources = as_list(cfg.get("source")) + detail
    if sources:
        parts.append("SOURCES\n" + "\n".join("- " + s.strip() for s in sources))
    text = "\n\n".join(parts) + "\n"
    # YouTube refuse < et > dans la description : flèches et comparaisons en Unicode.
    for a, b in (("<->", "↔"), ("->", "→"), ("<-", "←"), (">=", "≥"), ("<=", "≤"), (">", "›"), ("<", "‹")):
        text = text.replace(a, b)
    return text


PINNED_DEFAULT = ("Next test is your call 👇 Most liked comment = next experiment. "
                  "Follow so you don't miss it!")


def pinned(cfg):
    """Commentaire à épingler sous la vidéo, séparé de la description (à ne pas y coller)."""
    text = cfg.get("pinned_comment") or PINNED_DEFAULT
    return "\n" + "=" * 40 + "\nPINNED COMMENT (post it, then pin it)\n" + text.strip() + "\n"


SEND_DEFAULT = "Send this to the friend who bet wrong 👀"


def instagram(cfg):
    """Légende Instagram (Reels) : la question, une raison d'envoyer en DM (le signal n°1 pour les non-abonnés),
    une ligne de mots-clés, 3 hashtags max. On y poste la version courte (~30 s), pas la longue."""
    cap = (cfg.get("caption") or "").strip()
    words = cap.split()
    tags = [w for w in words if w.startswith("#")][:3]
    text = " ".join(w for w in words if not w.startswith("#"))
    qs = [q.strip() + "?" for q in text.split("?")[:-1]]
    question = " ".join(qs[:2]) if len(" ".join(qs[:2])) <= 110 else (qs[0] if qs else text)   # the question + the bet
    lines = [question, cfg.get("send_line") or SEND_DEFAULT]
    if cfg.get("keywords"):
        lines.append(cfg["keywords"].strip())
    lines.append("Simulated in 3D with published test values." if any("imulat" in s for s in as_list(cfg.get("source")))
                 else "3D animation of a published test.")
    lines.append(" ".join(tags))
    return ("\n" + "=" * 40 + "\nINSTAGRAM (post the _youtube-short.mp4, 19:00-21:00 Brussels time)\n"
            + "\n".join(l for l in lines if l) + "\n")


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(build(cfg))
        f.write(pinned(cfg))
        f.write(instagram(cfg))
