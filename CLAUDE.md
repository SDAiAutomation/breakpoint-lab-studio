# Breakpoint Lab — studio vidéo (@BreakpointLabTV)

Chaîne YouTube/TikTok **Breakpoint Lab**, handle **@BreakpointLabTV**. Séries : **Tests** (presse, traction, chute — `engine/engine.html`) et **Physics** (expériences de physique, ex. courses de billes — `engine/physics.html`).

## Ne pas mélanger
- Ce dépôt n'a RIEN à voir avec SliceLoop / `asmr-slicing-studio` (vidéos de découpe ASMR, compte @sliceloop). Ne jamais mettre @sliceloop ici, ni @BreakpointLabTV là-bas.
- Le handle va dans chaque config : `"handle": "@BreakpointLabTV"`.
- Exception voulue : sur TikTok, les vidéos Breakpoint Lab sont publiées sur le compte SliceLoop (audience existante). Le filigrane reste @BreakpointLabTV ; ne pas le signaler comme une erreur.
- Stats : W = vues YouTube, AB = vues TikTok.
- Numéro à l'écran (`series`, ex. « PHYSICS · TEST 008 ») = numéro d'épisode (colonne AA de la Sheet), jamais le numéro de ligne (colonne A). Il ne fait que monter : dernier numéro publié + 1, même si l'on change de série. On ne réutilise jamais un numéro déjà en ligne.

## Ligne éditoriale (ce qui fait des vues)
- **Un sujet que les gens connaissent** : un objet du quotidien, un mythe, une question qu'on s'est déjà posée (« ah ça, je l'ai déjà vu »). C'est le critère qui pèse le plus.
- **Une vraie preuve** : de préférence une expérience publiée et mesurée (étude, labo, MythBusters, norme) qu'on reproduit avec ses chiffres et qu'on nomme dès l'accroche (« MIT test », « BBC test »). Sinon, on fait l'expérience nous-mêmes avec la loi physique (ex. pendule T = 2π√(L/g)) : on montre la formule, c'est « Simulated ». Sans l'un ni l'autre : pas d'épisode.
- **Partir d'une croyance** : l'accroche (≤ 2 s, en pleine action) pose ce que les gens croient ou une question fermée ; la réponse n'arrive qu'après le ralenti.
- **Faire parier** : question avec 2-3 choix (« 2, 3 or MORE? »), commentaire épinglé qui invite à donner son pari.
- **Ton** : clair et factuel (c'est ce qui marche en physique/ingénierie), le texte doit se suffire à lui-même (beaucoup regardent sans le son).

## Règles de contenu
- Tout chiffre à l'écran est vrai : source publiée (norme, étude, loi physique) dans `source` (affiché) et `sources_detail` (calcul). Pas de source fiable → pas d'épisode. Une simulation se dit « Simulated … ».
- Anglais, texte minimal (≤ 6 mots par ligne), textes dans le bandeau du haut (y 260–600 sur 1920) : rien ne couvre la scène. Zone sûre : rien d'important au-dessus de y=250 ni sous y=1440.
- Chaque config a un champ `description` (liste de paragraphes, langue de la vidéo) : ce qu'on teste, ce qui se passe, pourquoi, avec les mêmes chiffres que la vidéo et la mention « simulation » si c'en est une. Il est écrit dans le .txt envoyé avec la vidéo (`engine/caption.py`) ; le workflow refuse une config sans `description`.
- Durée ≥ 60 s (rémunération TikTok), rythme serré, mouvement jusqu'à la fin, ralenti sur le moment clé.
- Qualité visuelle soignée : géométrie propre, pas d'artefacts ; vérifier des images clés (`render.js stills`) avant un rendu complet.

## Rendu
- Son : mode **hybride** par défaut (choix de l'utilisateur, 21/11/2026). Chaque config a un bloc `"sound": {"mode": "hybrid", ...}` : les sons graphiques du moteur (bips, compte à rebours, tampon, whooshes) gardent le rythme ; les sons physiques (chocs, spires, clacs, impacts) sont de vrais enregistrements CC0 trouvés sur Openverse, choisis et vérifiés par earshot, placés à l'image près par real-sfx (`tools/sound/realsound.py`, exemple : `configs/physics_011_slinky_drop_en.json`). Limiteur −1 dBTP sur chaque MP4. Refaire seulement le son d'un rendu fini : `render.yml` avec `sound_from_run`.
- `.github/workflows/render.yml` (workflow_dispatch, `config_path` ou `config_json`) : rendu parallèle sur ~20 machines, son, MP4, Google Drive si le secret `RCLONE_CONF` et la variable `DRIVE_FOLDER_ID` existent, sinon la vidéo est un artefact du run.
- Une PR séparée par modification.

## Procédure « fais une vidéo »
Liste des sujets : Google Sheet « Breakpoint Lab – 100 Experiments » (id `1hl-jYG9e2N5L2_xycGPkE_SprXOnQWE8BR-vbNOqrkk`), onglet `Experiments`, lignes 2–101. Colonnes : D réponse, K série, L moteur, M source, N statut, O Pick, P note, Q lien source, R lien vidéo, S « Familiar » /5, T « Busts a belief » /5, U Preuve (`Experiment` ou `Formula`), V Score v2 = 2×S + T + (5 si Experiment, 3 si Formula) + G, W–Z stats (vues, likes, abonnés gagnés, partages). AA « Episode # (on screen) ».

1. **Choisir** : lire `Experiments!A1:R101` (et les lignes ajoutées après 101). Écarter les statuts `Done`, `In progress`, `Needs test data`, `Suggested`. Parmi `Verified` et `Corrected`, prendre d'abord les lignes Pick = TRUE, puis le score V (Score v2) le plus haut ; à score égal, le plus petit numéro (colonne A, ordre croissant). Si l'utilisateur nomme un sujet, prendre celui-là.

### Sujet proposé par un abonné (commentaire)
Le commentaire épinglé promet : « Most liked comment = next experiment ». Quand l'utilisateur transmet une proposition :
1. Chercher dans la Sheet si le sujet existe déjà (même question, même sous un autre nom). Si oui, mettre O = TRUE sur cette ligne et noter dans P « Viewer pick: <auteur>, <date> ».
2. Sinon, ajouter une ligne à la fin : A = numéro suivant, B sujet, C question à l'écran, K série, L moteur (`Tests (ready)`, `Physics (ready)`, `(extend)` ou `New engine`), N = `Suggested`, P = « Viewer suggestion: <auteur>, <date> ».
3. Chercher une source fiable (norme, étude, loi physique). Trouvée → remplir D, M, Q, les notes E–I et J, passer N à `Verified` et O à TRUE. Pas de source → N = `Needs test data`, cause dans P, et le dire à l'utilisateur (on ne fait pas d'épisode sans source).
4. Une fois `Verified`, la suite est la procédure « fais une vidéo » normale. Dans la `description` de la vidéo, remercier l'auteur de l'idée (« Suggested by <auteur> »).
2. **Réserver** : passer N à `In progress` avant tout travail.
3. **Construire** :
   - L = `Tests (ready)` ou `Physics (ready)` : écrire `configs/<serie>_<num>_<slug>_en.json` à partir d'une config existante.
   - L = `(extend)` ou `New engine` : coder la scène dans une PR séparée, vérifier les images clés (`render.js stills`), montrer les stills à l'utilisateur avant le rendu complet.
   - Chiffres à l'écran : uniquement ceux des colonnes D, M, P (et leur source Q). Rien d'autre.
4. **Rendre** : lancer `render.yml` (`config_path` ou `config_json`), suivre le run jusqu'à la fin.
5. **Clore** : N = `Done`, R = lien du run + lien Drive de la vidéo, AA = numéro d'épisode affiché (fixé dès l'étape 3 : plus grand AA existant + 1).
7. **Mesurer** : l'utilisateur donne les stats à J+3 → W–Z. Toutes les 5 vidéos publiées, comparer les stats aux notes S, T, U, G et proposer d'ajuster les poids du score V.
6. **Échec** : remettre N à son statut d'avant, noter la cause dans P, prévenir l'utilisateur.
