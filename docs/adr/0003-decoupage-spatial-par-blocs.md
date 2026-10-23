# ADR 0003 : découpage spatial par blocs et gel des zones de test

- Date : 2026-10-21
- Statut : accepté, gelé

## Contexte

Deux pixels voisins se ressemblent (même parcelle, même type de sol). Si les pixels de test
sont tirés au hasard, chacun a un voisin presque identique dans l'entraînement : le modèle
recopie ce qu'il a vu et les scores sont gonflés. C'est la fuite spatiale. Le cahier des
charges impose une validation par blocs géographiques et des zones de test figées avant tout
entraînement.

## Décision

- Les trois zones pilotes sont quadrillées en blocs carrés de 10 km, sur une grille alignée sur
  des multiples de 10 km en UTM 32N (EPSG:32632). Un bloc est rattaché à la zone qui le
  recouvre le plus et gardé si 25 % au moins de sa surface est dans cette zone.
- Dans chaque zone, 20 % des blocs (au moins un) sont mis de côté pour le test. Les autres sont
  répartis en 5 folds pour une validation croisée par blocs.
- Le tirage porte sur des blocs entiers, avec la graine 42, avant toute annotation.
- Le résultat est gelé dans `configs/spatial_split.csv`, avec son empreinte SHA-256 dans
  `configs/spatial_split.sha256`. Le fichier fait foi, pas la graine, car le flux aléatoire de
  numpy n'est pas garanti identique entre versions. Des tests échouent si le fichier change.
- Règle : le découpage ne change jamais après avoir vu un score. Toute modification passe par
  un nouvel ADR dont la justification est indépendante des scores obtenus.

## Justification des valeurs

- 10 km : assez grand pour éloigner entraînement et test, assez petit pour garder plusieurs
  dizaines de blocs par zone. Avec 20 km, Béja n'aurait que 1 ou 2 blocs de test.
- 20 % de test et 5 folds : valeurs usuelles. La graine 42 est arbitraire, seule sa fixation
  compte.

## Limites

- Le tirage est aléatoire par zone, non stratifié par classe d'occupation du sol, faute
  d'étiquettes à ce stade. Après annotation, on vérifiera que les blocs de test contiennent
  assez d'exemples de chaque classe ; sinon on annotera davantage dans ces blocs, sans modifier
  la découpe.
- Une marge de 1 km autour des blocs de test (`buffer_m`) est paramétrée mais pas appliquée :
  elle le sera à l'échantillonnage des pixels d'entraînement.
- La taille de 10 km n'est pas justifiée par une mesure de l'autocorrélation spatiale de nos
  données : c'est un choix défendable mais non démontré.