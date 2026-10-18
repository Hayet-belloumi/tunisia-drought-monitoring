# ADR 0001 : source des limites administratives

- Date : 2026-10-18
- Statut : accepté

## Contexte

Le projet agrège les indicateurs par gouvernorat et délimite les zones pilotes (Sfax, Béja,
Kairouan). Il faut un contour fiable des 24 gouvernorats de la Tunisie, utilisable dans un
dépôt public.

## Décision

Utiliser le jeu de données OCHA / HDX « Tunisia - Subnational Administrative Boundaries »
(COD-AB, données de l'Institut National de la Statistique, version v01 du 2022-11-15),
sous licence CC BY-IGO. On utilise la couche `tun_admin2` (24 gouvernorats, EPSG:4326) et
non les couches `_em` (version pour la cartographie). Les gouvernorats sont identifiés par
leur P-code (adm2_pcode), pas par leur nom.

## Conséquences

- Le fichier est téléchargé par script (`python -m tdm.boundaries`) dans `data/`, non
  versionné. Son empreinte SHA-256 est affichée pour détecter un changement côté HDX.
- La licence CC BY-IGO impose de citer la source : mention à ajouter au README.
- Dans cette source, les gouvernorats sont au niveau administratif 2 (le niveau 1 contient
  6 grandes régions).

## Alternative écartée

GADM : licence jugée plus restrictive pour la redistribution (non vérifiée en détail),
et numérotation des niveaux différente.