# Protocole d'annotation (zone pilote : Kairouan, TN41)

Ce document fixe les règles d'étiquetage **avant** de dessiner le premier polygone. Il ne doit pas être modifié après avoir vu des scores de modèle (sinon, nouvel ADR).

## 1. Classes

| id | classe | à annoter quand... |
|----|--------|--------------------|
| 1 | Oliviers / arboriculture | arbres alignés ou espacés, sol visible entre les arbres |
| 2 | Céréales | parcelle cultivée nette, verte en hiver-printemps puis récoltée |
| 3 | Steppe / parcours | végétation naturelle clairsemée, sans parcelle géométrique |
| 4 | Forêt | couvert arboré dense naturel ou reboisé |
| 5 | Sol nu / sebkha | sol sans végétation toute l'année, croûtes salées |
| 6 | Urbain | bâti, routes, zones imperméabilisées |
| 7 | Eau | retenues, lacs, plans d'eau permanents |

Une classe absente ou très rare à Kairouan est **documentée telle quelle**, jamais complétée artificiellement.

## 2. Règles de dessin

- Un polygone = une seule classe, homogène.
- Largeur minimale : 3 pixels Sentinel-2 (30 m), pour éviter les pixels mixtes.
- Marge de 20 m par rapport aux bords de la parcelle ou de la classe voisine.
- **Un polygone ne traverse jamais la limite entre deux blocs de 10 km.** On coupe à la limite si besoin.
- Si tu hésites sur la classe : **ne dessine pas** (pas de polygone « peut-être »).
- Regarder plusieurs mois (et pas une seule image) : céréales et sol nu se confondent selon la date.

## 3. Équité entre entraînement et test

- Le même protocole s'applique dans les blocs de test et d'entraînement.
- Interdit d'annoter seulement les zones faciles dans les blocs de test.
- Le découpage gelé (`configs/spatial_split.csv`) n'est jamais modifié.
- L'attribut train/test n'est **pas** saisi à la main : il est ajouté plus tard par jointure spatiale avec le CSV gelé.

## 4. Objectifs quantitatifs (rythme normal)

- Visé : au moins 30 polygones par classe en entraînement et 10 en test, quand la classe existe.
- Les comptes réels sont publiés dans le README, même s'ils sont inférieurs.

## 5. Format du fichier

- Fichier : `data/labels/kairouan_labels.gpkg` (GeoPackage, hors Git).
- Projection : EPSG:32632 (celle des blocs).
- Colonnes : `class_id` (entier 1 à 7), `class_name` (texte).
- Source de photo-interprétation : composites Sentinel-2 mensuels du projet ; un fond haute résolution peut aider à décider mais n'est ni redistribué ni publié.
## Révision n°1 (22 novembre 2026)

Cette révision a été faite avant tout entraînement et avant tout score de modèle.

- **Cibles en pixels** : au moins 200 pixels Sentinel-2 entièrement contenus dans
  les polygones en train, et 50 en test, par classe. Elles remplacent les cibles
  exprimées en nombre de polygones, peu pertinentes quand les parcelles sont
  petites ou étroites. Le nombre de pixels est estimé en rétrécissant chaque
  polygone de 10 m et en divisant l'aire par 400 m² (voir le contrôle automatique).
- **Taille des polygones** : de 1 à 3 ha, en forme compacte. Une alerte est émise
  sous 900 m² ou au-dessus de 50 ha.
- **Image de référence** : une imagerie haute résolution sert à décider de la
  classe, puis les composites Sentinel-2 des quatre dates servent à vérifier la
  cohérence temporelle. L'imagerie de référence n'est ni exportée ni versionnée.

Retour d'expérience et limites : [journal d'annotation](journal-annotation.md).