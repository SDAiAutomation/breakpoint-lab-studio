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

## Procédure « fais une vidéo »
Liste des sujets : Google Sheet « Breakpoint Lab – 100 Experiments » (id `1hl-jYG9e2N5L2_xycGPkE_SprXOnQWE8BR-vbNOqrkk`), onglet `Experiments`, lignes 2–101. Colonnes : D réponse, K série, L moteur, M source, N statut, O Pick, P note, Q lien source, R lien vidéo.

1. **Choisir** : lire `Experiments!A1:R101`. Écarter les statuts `Done`, `In progress`, `Needs test data`. Parmi `Verified` et `Corrected`, prendre d'abord les lignes Pick = TRUE, puis le score J le plus haut. Si l'utilisateur nomme un sujet, prendre celui-là.
2. **Réserver** : passer N à `In progress` avant tout travail.
3. **Construire** :
   - L = `Tests (ready)` ou `Physics (ready)` : écrire `configs/<serie>_<num>_<slug>_en.json` à partir d'une config existante.
   - L = `(extend)` ou `New engine` : coder la scène dans une PR séparée, vérifier les images clés (`render.js stills`), montrer les stills à l'utilisateur avant le rendu complet.
   - Chiffres à l'écran : uniquement ceux des colonnes D, M, P (et leur source Q). Rien d'autre.
4. **Rendre** : lancer `render.yml` (`config_path` ou `config_json`), suivre le run jusqu'à la fin.
5. **Clore** : N = `Done`, R = lien du run + lien Drive de la vidéo.
6. **Échec** : remettre N à son statut d'avant, noter la cause dans P, prévenir l'utilisateur.
