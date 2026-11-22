# Journal d'annotation - zone pilote de Kairouan

Ce document garde la trace de la méthode suivie pour étiqueter la zone pilote,
des chiffres obtenus et des limites connues. Il complète le
[protocole d'annotation](protocole-annotation.md).

## Méthode

1. **Choix de la parcelle** : repérage sur une imagerie aérienne haute résolution
   (fond de carte affiché dans QGIS, utilisé comme référence visuelle uniquement,
   non exporté et non versionné), à l'échelle 1:1000 à 1:3000.
2. **Dessin** : un polygone compact par parcelle homogène, de 1 à 3 ha, à environ
   20 m du bord de la parcelle et des chemins, entièrement dans un seul bloc du
   découpage gelé.
3. **Contrôle de cohérence temporelle** : le même polygone est regardé sur les
   composites Sentinel-2 de 2025 (février, avril, juin, septembre), exportés à 20 m.
4. **Contrôle automatique** : `uv run python -m tdm.labels.validate_labels` vérifie
   la validité des géométries, la cohérence `class_id` / `class_name`, l'appartenance
   à un seul bloc, puis rapporte les surfaces et les pixels estimés par classe et
   par split. Le split (train / test) n'est jamais saisi à la main : il vient de la
   position du polygone dans le découpage gelé.

## Avancement au 22 novembre 2026

| Classe | Polygones (train / test) | Pixels estimés (train / test) | Cible | État |
|---|---|---|---|---|
| 1 oliviers | 11 / 6 | 206 / 66 | 200 / 50 | atteinte |
| 2 à 7 | 0 / 0 | 0 / 0 | 200 / 50 | à faire |

Les « pixels estimés » sont les pixels de 20 m entièrement contenus dans les
polygones : chaque polygone est rétréci de 10 m (la moitié d'un pixel), puis son
aire est divisée par 400 m².

## Enseignements

- **Taille** : les premiers polygones, trop grands (8 à 18 ha), mélangeaient
  plusieurs parcelles et ont tous été supprimés. Les polygones trop petits
  (0,2 à 0,3 ha) donnent moins de 10 pixels purs chacun. La plage de 1 à 3 ha, en
  forme compacte, est le meilleur compromis.
- **Parcelles étroites** : beaucoup de parcelles d'oliviers font 60 à 80 m de large,
  soit 3 à 4 pixels. Les grands blocs homogènes de plaine sont à privilégier.
- **Zones à éviter** : collines couvertes de maquis, jachères avec arbres isolés,
  abords de bâtiments et de routes.

## Limites connues

- **Oliviers espacés** : lorsque les arbres sont tous les 8 à 10 m sur sol nu, un
  pixel de 20 m mélange arbres et sol. Ces vergers ressemblent au sol nu sur
  Sentinel-2, ce qui devrait se traduire par des confusions entre `oliviers` et
  `sol_nu` ou `steppe`. À mesurer dans la matrice de confusion.
- **Jeunes plantations** : deux polygones de test sur terrain vallonné sont des
  plantations jeunes et très espacées, jugées plausibles mais moins sûres que les
  vergers adultes. À réexaminer en cas de résultats surprenants.
- **Date de l'imagerie de référence** : elle peut différer de 2025. Pour les cultures
  annuelles (céréales), la classe devra être confirmée avec la série Sentinel-2.
- **Conditions d'usage de l'imagerie de référence** : à vérifier avant toute
  publication de captures d'écran contenant ce fond.