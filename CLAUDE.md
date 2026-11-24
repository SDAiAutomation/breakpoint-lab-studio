# Breakpoint Lab — studio vidéo (@BreakpointLabTV)

Chaîne YouTube/TikTok **Breakpoint Lab**, handle **@BreakpointLabTV**. Séries : **Tests** (presse, traction, chute — `engine/engine.html`) et **Physics** (expériences de physique, ex. courses de billes — `engine/physics.html`).

## Ne pas mélanger
- Ce dépôt n'a RIEN à voir avec SliceLoop / `asmr-slicing-studio` (vidéos de découpe ASMR, compte @sliceloop). Ne jamais mettre @sliceloop ici, ni @BreakpointLabTV là-bas.
- Le handle va dans chaque config : `"handle": "@BreakpointLabTV"`.
- Exception voulue : sur TikTok, les vidéos Breakpoint Lab sont publiées sur le compte SliceLoop (audience existante). Le filigrane reste @BreakpointLabTV ; ne pas le signaler comme une erreur.
- Stats : W = vues YouTube, AB = vues TikTok.
- Numéro à l'écran (`series`, ex. « PHYSICS · TEST 008 ») = numéro d'épisode (colonne AA de la Sheet), jamais le numéro de ligne (colonne A). Il ne fait que monter : dernier numéro publié + 1, même si l'on change de série. On ne réutilise jamais un numéro déjà en ligne.

## Ligne éditoriale (ce qui fait des vues)
- **Titres** (YouTube Studio, nov. 2026) : toujours une question à 2-3 choix ou un paradoxe (« Lift 2 balls: how many fly out? 1, 2 or 3? »). Jamais la réponse ni le chiffre clé dans le titre, jamais de titre descriptif de labo (« A 15 cm concrete cube: crushed, then pulled »).
- **Sujets** : bonus aux tests de rupture ou de limite (canette, diamant, spaghetti). Un classique déjà vu partout (Mentos, plume dans le vide) n'est pas exclu pour sa physique, mais il lui faut un angle ou un pari neuf ; sans angle neuf, il passe derrière.
- **Un sujet que les gens connaissent** : un objet du quotidien, un mythe, une question qu'on s'est déjà posée (« ah ça, je l'ai déjà vu »). C'est le critère qui pèse le plus.
- **Une vraie preuve** : de préférence une expérience publiée et mesurée (étude, labo, MythBusters, norme) qu'on reproduit avec ses chiffres et qu'on nomme dès l'accroche (« MIT test », « BBC test »). Sinon, on fait l'expérience nous-mêmes avec la loi physique (ex. pendule T = 2π√(L/g)) : on montre la formule, c'est « Simulated ». Sans l'un ni l'autre : pas d'épisode.
- **Mouvement dès la 1re image** (YouTube Studio, épisode 013 : accroche quasi fixe + titre + compte à rebours = choc à 7 s, 24 % des gens restent au lieu de 51-55 %) : l'objet bouge dès l'image 0 (ex. le maillet tombe, frappe, ralenti, image figée juste avant la casse), jamais plus de 1 s sans mouvement dans les 5 premières secondes, pas de compte à rebours « 3, 2, 1 » (le pari se fait pendant que ça bouge). La version courte enchaîne l'accroche directement sur la question de la manche (`"short": {"from": "question"}`, par défaut). À vérifier sur la planche (images à 0,1 s, 0,5 s, 1,5 s, 3 s).
- **Partir d'une croyance** : l'accroche (≤ 2 s, en pleine action) pose ce que les gens croient ou une question fermée ; la réponse n'arrive qu'après le ralenti.
- **Faire parier** : question avec 2-3 choix (« 2, 3 or MORE? »), commentaire épinglé qui invite à donner son pari.
- **Fidéliser (écran de fin)** : `"cta": "Subscribe: you pick the next test"` et `"next_test"` = la question du prochain épisode (≤ 6 mots, une question, chiffres sourcés comme le reste). C'est une promesse : le sujet annoncé est réservé dans la Sheet (O = TRUE, P « Announced in episode N ») et c'est lui qu'on fait ensuite.
- Le rendu refuse une config dont la légende ne commence pas par une question ou donne un résultat du tampon (`tools/check_config.py`).
- **Ton** : clair et factuel (c'est ce qui marche en physique/ingénierie), le texte doit se suffire à lui-même (beaucoup regardent sans le son).

## Règles de contenu
- Tout chiffre à l'écran est vrai : source publiée (norme, étude, loi physique) dans `source` (affiché) et `sources_detail` (calcul). Pas de source fiable → pas d'épisode. Une simulation se dit « Simulated … ».
- Anglais, texte minimal (≤ 6 mots par ligne), textes dans le bandeau du haut (y 260–600 sur 1920) : rien ne couvre la scène. Zone sûre : rien d'important au-dessus de y=250 ni sous y=1440.
- Chaque config a un champ `description` (liste de paragraphes, langue de la vidéo) : ce qu'on teste, ce qui se passe, pourquoi, avec les mêmes chiffres que la vidéo et la mention « simulation » si c'en est une. Il est écrit dans le .txt envoyé avec la vidéo (`engine/caption.py`) ; le workflow refuse une config sans `description`.
- Durée ≥ 60 s (rémunération TikTok), rythme serré, mouvement jusqu'à la fin, ralenti sur le moment clé.
- **Version courte YouTube** (~35-45 s, `tools/shortcut.py`, découpée dans la vidéo longue, pas de nouveau rendu) : accroche + la manche montrée dans l'accroche + l'explication + la fin. TikTok garde la version longue.
  - Le « pourquoi » est la valeur de la chaîne : il n'est jamais coupé ni accéléré. On coupe des manches secondaires, jamais l'explication.
  - L'explication doit coller à la manche gardée : si une ligne parle d'une manche coupée, s'arrêter avant elle (`"short": {"round": N, "explain_lines": K}`), ou garder cette manche.
  - Garder toutes les manches qui portent la surprise (ex. Slinky : métal PUIS plastique 4x plus léger, même 0,27 s → `"short": {"rounds": [1, 2]}`). Une manche qui ne fait que confirmer peut partir.
  - Plutôt 45 s claires que 38 s incomplètes.
- Qualité visuelle soignée : géométrie propre, pas d'artefacts ; vérifier des images clés (`render.js stills`) avant un rendu complet.

## Confort du spectateur (il doit se sentir à l'aise, tout est harmonisé)
- **Un seul point d'attention à la fois** : le texte OU l'action qui compte, pas les deux qui se battent. Un nouveau texte n'arrive pas pendant le moment clé.
- **Lisible sans effort** : l'objet testé fait au moins ~80 px de large (sur 1080) au moment clé, hors bandeau de texte et hors des zones de l'appli (boutons à droite, légende en bas, barre du haut).
- **Temps de lecture** : chaque texte reste ≥ 1,5 s à l'écran (plus si > 4 mots). Pas de texte qui clignote.
- **Respiration** : marges autour des textes, une ligne de plus vaut mieux qu'un texte serré ; ≤ 2 tailles de texte par écran.
- **Caméra douce et constante** : même cadrage d'une manche à l'autre (on compare), mouvements lents et lissés, pas de saut sauf coupe franche.
- **Son sans surprise** : pas de pic plus fort que le reste (limiteur −1 dBTP), pas de silence > 3 s hors effet voulu.
- **Planche de contrôle** (`tools/review_sheet.py`) : les images clés avec, par-dessus, ce que le téléphone dessine (TikTok + YouTube Shorts). Le workflow la fait à chaque rendu ; pour une nouvelle vidéo, la faire et la montrer à l'utilisateur AVANT le rendu complet.

## Instagram (Reels) — ce qui compte (Meta + réponse de Meta AI vérifiée, nov. 2026)
- Instagram teste chaque Reel sur un petit groupe de non-abonnés puis élargit selon : ne pas swiper dans les 3 premières s, temps de visionnage / vu jusqu'au bout, **envois en DM** (le signal le plus fort pour les non-abonnés), puis likes par personne touchée.
- On y poste la **version courte** (`_youtube-short.mp4`, ~30 s), jamais la longue de 60 s. Première image : la question + l'action déjà lancée.
- Légende Instagram (écrite dans le .txt par `engine/caption.py`) : la question + le pari, une phrase qui pousse à envoyer (`"send_line"`, ex. « Send this to the friend who said 40 kg 👀 »), une ligne de mots-clés (`"keywords"`), « Simulated in 3D… », 3 hashtags max.
- **Couverture** (`<nom>_cover.jpg` sur Drive, faite à chaque rendu par `tools/cover.py`) : le moment de tension juste avant la casse (jamais la réponse), la question en gros + le pari, même style à chaque épisode, tout dans le recadrage 3:4 de la grille du profil (y 240-1680). Peu utile dans le fil (la vidéo démarre seule), importante sur le profil et dans l'aperçu des envois en DM. Réglages : `"cover_t"`, `"cover_question"`, `"cover_bet"`.
- Publier 3-4 fois par semaine, 19 h-21 h (heure de Bruxelles) ; un compte = un thème (pas de découpe ASMR sur le compte du labo).

## Voix off : par plateforme (décision du 22/11/2026)
- Par défaut **sans voix** partout : la vidéo se comprend en muet (texte ≤ 6 mots, son hybride). Données : Virlo, 70 787 vidéos postées du 1/10 au 5/11/2026 — vidéos sans visage et sans voix avec texte 1,59× les vues habituelles sur TikTok contre 1,06× avec voix off ; sur Instagram 1,06× contre 0,98×. Corrélation, pas preuve, mais rien ne montre que la voix aide.
- **TikTok** : version longue, sans voix. **YouTube Shorts** : version courte, sans voix (aucune donnée fiable sur la voix).
- **Instagram** : test A/B de la voix off sur la version courte (`.github/workflows/voiceover.yml`, voix ElevenLabs « Miles », phrases calées sur les textes à l'écran, son de la vidéo baissé dessous). Alterner avec et sans voix, même horaire, 4 vidéos de chaque.
- Règle de décision : à J+3, comparer la durée moyenne de visionnage et les envois (Insights). La voix n'est adoptée sur une plateforme que si elle gagne sur les deux ; sinon on l'arrête. Le texte reste toujours à l'écran (beaucoup regardent sans le son).
- Le texte dit par la voix = les textes à l'écran + le pourquoi en une phrase ; aucun chiffre qui ne soit pas déjà à l'écran.

## Effet « comment il a fait ça ? »
- Le rendu doit avoir l'air d'un vrai labo filmé : matières crédibles, ombres, lumière, ralenti net. Le chiffre mesuré s'affiche en direct (chrono, force, compteur), comme un instrument.
- **Logo de la chaîne** : « BREAKPOINT » (gris foncé) + « LAB » (or), Poppins Bold, sur la face avant du socle gris clair, centré, le même dans toutes les scènes (moteur presse : décalque du socle ; Blender : `tools/blender/lab_set.py`, `add_logo_base`). Il doit être lisible dans chaque plan large, au-dessus de la légende de l'appli (y < 1440) ; une config qui zoome au point de le sortir du cadre est refusée. À vérifier sur la planche de contrôle à chaque nouvelle vidéo.
- Objectif long terme : montrer comment on fait ces vidéos. Chaque rendu archive son **making-of** sur Drive (`making-of/<nom>/` : config, timeline, images clés, planche, rapport son). Ne pas le supprimer.

## Rendu
- Son : mode **hybride** par défaut (choix de l'utilisateur, 21/11/2026). Chaque config a un bloc `"sound": {"mode": "hybrid", ...}` : les sons graphiques du moteur (bips, compte à rebours, tampon, whooshes) gardent le rythme ; les sons physiques (chocs, spires, clacs, impacts) sont de vrais enregistrements CC0 trouvés sur Openverse, choisis et vérifiés par earshot, placés à l'image près par real-sfx (`tools/sound/realsound.py`, exemple : `configs/physics_011_slinky_drop_en.json`). Limiteur −1 dBTP sur chaque MP4. Refaire seulement le son d'un rendu fini : `render.yml` avec `sound_from_run`.
- **Image** (règles tirées des skills Blender `blender-rendering`, `blender-lighting-lookdev`, `blender-pbr-materials`, `scenario-blender-lighting-rendering`) :
  - Le sujet se détache du fond par la valeur (clair sur sombre ou l'inverse), jamais noyé dans l'ombre d'une pièce de la machine.
  - Liseré de lumière côté clé sur les objets (silhouette lisible), reflets jamais brûlés en blanc plat (épaule Khronos PBR Neutral dans le shader).
  - Brillance jamais constante sur une surface (légère variation), métal = 0 ou 1, pas de noir ni de blanc purs en couleur de base.
  - Objectif long pour un objet seul (`"lens": 1.4` dans la config, moteur presse) : lignes droites, aspect produit.
  - Plans Blender (objets « vedettes ») : Cycles sur CPU (EEVEE demande une carte graphique), 85 mm, AgX, débruitage OIDN, rendu image par image puis assemblage (`tools/blender/`).
  - Moteur `bottle` (épisode 013) : toute la scène est rendue par Blender (`tools/blender/bottle_scene.py`), le moteur (`engine/bottle.html`) ne dessine que les textes et dit quelle « pose » chaque image montre ; les moments immobiles gardent la même image (≈ 360 images Blender pour 60 s). `render.yml` lance alors un job `blender` (18 poses par machine, ~5 min par image) avant les images. Vérifier d'abord avec `blender_stills.yml` (quelques images + textes + planche poussées sur la branche `previews/<run>`).
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
   - Images clés + planche de contrôle (`render.js stills`, puis `tools/review_sheet.py`) : vérifier le confort du spectateur, montrer la planche à l'utilisateur avant le rendu complet.
   - Écran de fin : choisir le sujet suivant avec la règle de l'étape 1, mettre sa question (colonne C, ≤ 6 mots) dans `next_test`, le réserver dans la Sheet (O = TRUE, P « Announced in episode N »).
4. **Rendre** : lancer `render.yml` (`config_path` ou `config_json`), suivre le run jusqu'à la fin.
5. **Clore** : N = `Done`, R = lien du run + lien Drive de la vidéo, AA = numéro d'épisode affiché (fixé dès l'étape 3 : plus grand AA existant + 1).
7. **Mesurer** : l'utilisateur donne les stats à J+3 → W–Z. Toutes les 5 vidéos publiées, comparer les stats aux notes S, T, U, G et proposer d'ajuster les poids du score V.
6. **Échec** : remettre N à son statut d'avant, noter la cause dans P, prévenir l'utilisateur.
