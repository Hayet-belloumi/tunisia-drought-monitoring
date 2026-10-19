# ADR 0002 : masque de nuages des composites Sentinel-2

- Date : 2026-10-19
- Statut : accepté à titre provisoire, à revalider (voir « À revalider »)

## Contexte

Un nuage ou une ombre de nuage fausse le NDVI, donc l'indice de sécheresse. Il faut masquer
les pixels nuageux avant de construire les composites mensuels de
COPERNICUS/S2_SR_HARMONIZED, pour les trois zones pilotes (Sfax, Béja, Kairouan).

## Options comparées

- SCL : bande de classification des pixels de Sentinel-2 L2A. Classes masquées : 3 (ombre de
  nuage), 8 et 9 (nuages), 10 (cirrus).
- Cloud Score+ (GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED), bande cs_cdf, pixels gardés si
  cs_cdf >= seuil, avec trois seuils testés : 0,5, 0,6 et 0,7.
- QA60 écartée : bande vide ou de définition changeante selon les périodes (masque absent
  de janvier 2022 à février 2024), donc inadaptée à une série longue.

## Évaluation

Script `src/tdm/gee/explore.py` : 3 zones, 12 mois de 2025, résolution 20 m. Mesures : part
des pixels avec au moins une observation claire dans le mois, et nombre moyen d'observations
claires par pixel. Contrôle visuel avec `src/tdm/gee/visual_check.py` (Béja, janvier 2025).

Résultats :

- La couverture vaut 1,000 presque partout avec les quatre méthodes. Exceptions avec SCL :
  Béja en janvier (0,939) et en avril (0,995), Sfax en mars (0,999).
- Les méthodes divergent surtout en saison humide. Observations moyennes par pixel :
  Béja en janvier, SCL 2,5 contre 4,7 / 4,2 / 3,4 pour Cloud Score+ (0,5 / 0,6 / 0,7) ;
  Sfax en février, 4,1 contre 6,4 / 6,2 / 5,7 ; Kairouan en janvier, 4,8 contre 6,8 / 6,6 /
  6,4. En été, les résultats sont quasi identiques (Béja en juillet : 11,7 contre 12,2 /
  12,0 / 11,7).
- Contrôle visuel : SCL retire les nuages denses et aussi le voile fin ; Cloud Score+ à 0,6
  retire les nuages denses mais conserve le voile fin et quelques bords de nuages.

## Décision

Utiliser Cloud Score+ (bande cs_cdf, seuil 0,6) comme masque par défaut. Le seuil sera un
paramètre de configuration. Le composite mensuel sera calculé avec la médiane des
observations, avec un nombre minimal d'observations claires par pixel.

## Conséquences et risques

- Le voile fin résiduel peut abaisser légèrement le NDVI et simuler un faible stress de
  végétation. La médiane atténue l'effet sans le supprimer.
- Plus d'observations conservées en saison humide, utile pour les céréales de Béja.

## À revalider

- Faux positifs ou négatifs sur les surfaces claires (sebkha, sol nu, urbain) : à tester
  avec les polygones annotés.
- Comparaison des profils de NDVI par classe entre les méthodes.
- Une seule image inspectée et une seule année (2025) : étendre à d'autres années et zones.

## Mise à jour : composites mensuels (étape 4)

Le composite est calculé avec `src/tdm/gee/composites.py` (médiane des observations claires,
paramètres dans `configs/composites.yaml`). Un pixel qui a moins de 2 observations claires dans
le mois reste vide. Test sur Béja, Sfax et Kairouan (janvier, avril, juillet 2025, à 100 m) :
part de pixels valides de 0,941 à 1,000, la plus faible étant Béja en janvier (5,9 % de
pixels vides). NDVI moyens plausibles (Béja : 0,41 en janvier, 0,61 en avril, 0,24 en juillet).
Limite : les pixels vides devront être exclus des statistiques et jamais remplis par défaut.