# Breakpoint Lab — studio vidéo (@BreakpointLabTV)

Chaîne YouTube/TikTok **Breakpoint Lab**, handle **@BreakpointLabTV**. Séries : **Tests** (presse, traction, chute — `engine/engine.html`) et **Physics** (expériences de physique, ex. courses de billes — `engine/physics.html`).

## Ne pas mélanger
- Ce dépôt n'a RIEN à voir avec SliceLoop / `asmr-slicing-studio` (vidéos de découpe ASMR, compte @sliceloop). Ne jamais mettre @sliceloop ici, ni @BreakpointLabTV là-bas.
- Le handle va dans chaque config : `"handle": "@BreakpointLabTV"`.

## Règles de contenu
- Tout chiffre à l'écran est vrai : source publiée (norme, étude, loi physique) dans `source` (affiché) et `sources_detail` (calcul). Pas de source fiable → pas d'épisode. Une simulation se dit « Simulated … ».
- Anglais, texte minimal (≤ 6 mots par ligne), textes dans le bandeau du haut (y 260–600 sur 1920) : rien ne couvre la scène. Zone sûre : rien d'important au-dessus de y=250 ni sous y=1440.
- Chaque config a un champ `description` (liste de paragraphes, langue de la vidéo) : ce qu'on teste, ce qui se passe, pourquoi, avec les mêmes chiffres que la vidéo et la mention « simulation » si c'en est une. Il est écrit dans le .txt envoyé avec la vidéo (`engine/caption.py`) ; le workflow refuse une config sans `description`.
- Durée ≥ 60 s (rémunération TikTok), rythme serré, mouvement jusqu'à la fin, ralenti sur le moment clé.
- Qualité visuelle soignée : géométrie propre, pas d'artefacts ; vérifier des images clés (`render.js stills`) avant un rendu complet.

## Rendu
- `.github/workflows/render.yml` (workflow_dispatch, `config_path` ou `config_json`) : rendu parallèle sur ~20 machines, son, MP4, Google Drive si le secret `RCLONE_CONF` et la variable `DRIVE_FOLDER_ID` existent, sinon la vidéo est un artefact du run.
- Une PR séparée par modification.
