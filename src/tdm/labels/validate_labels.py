"""Contrôle qualité des polygones d'annotation de Kairouan.

Chaque polygone doit être valide, avoir une classe cohérente et être contenu dans
un seul bloc du découpage gelé (jamais à cheval sur deux blocs). Le contrôle
rapporte aussi les surfaces annotées et une estimation du nombre de pixels
Sentinel-2 réellement utilisables, à comparer aux cibles du protocole.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry.base import BaseGeometry

from tdm.labels.annotation_grid import zone_blocks
from tdm.labels.split import load_split_config

LABELS_PATH = Path("data/labels/kairouan_labels.gpkg")
LABELS_LAYER = "labels"
TOLERANCE_M = 0.5

# Taille d'un pixel Sentinel-2 dans nos exports (10 m natif, rééchantillonné à 20 m).
PIXEL_SIZE_M = 20.0
PIXEL_AREA_M2 = PIXEL_SIZE_M**2
# Seuils d'alerte sur la taille d'un polygone : 900 m² = 3 x 3 pixels, 50 ha = très grand.
MIN_AREA_M2 = 900.0
MAX_AREA_M2 = 500_000.0
# Cibles du protocole, en pixels utilisables par classe et par split.
TARGET_PIXELS: dict[str, int] = {"train": 200, "test": 50}
SPLITS = ("train", "test")

CLASSES: dict[int, str] = {
    1: "oliviers",
    2: "cereales",
    3: "steppe",
    4: "foret",
    5: "sol_nu",
    6: "urbain",
    7: "eau",
}


@dataclass(frozen=True)
class LabelReport:
    """Résultat du contrôle.

    - problems : erreurs bloquantes (le script s'arrête avec un code 1) ;
    - counts : nombre de polygones par classe et par split ;
    - warnings : alertes non bloquantes (polygone très petit ou très grand, fichier vide) ;
    - hectares : surface annotée par classe et par split ;
    - pixels : estimation des pixels entièrement à l'intérieur des polygones.
    """

    problems: list[str]
    counts: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    hectares: pd.DataFrame | None = None
    pixels: pd.DataFrame | None = None


def _where(geom: BaseGeometry | None) -> str:
    """Position du centre du polygone, pour le retrouver dans QGIS."""
    if geom is None or geom.is_empty:
        return ""
    centre = geom.centroid
    return f" (centre : x={centre.x:.0f}, y={centre.y:.0f})"


def _usable_pixels(geom: BaseGeometry | None) -> float:
    """Estime les pixels entièrement dans le polygone.

    Un pixel de 20 m est entièrement dedans si son centre est à plus de 10 m du
    bord : on rétrécit donc le polygone de 10 m et on divise l'aire par celle
    d'un pixel.
    """
    if geom is None or geom.is_empty or not geom.is_valid:
        return 0.0
    return float(geom.buffer(-PIXEL_SIZE_M / 2).area) / PIXEL_AREA_M2


def _table(assigned: pd.DataFrame, column: str) -> pd.DataFrame:
    """Somme d'une colonne par classe (lignes) et par split (colonnes)."""
    table = pd.DataFrame(0.0, index=list(CLASSES), columns=list(SPLITS))
    if not assigned.empty:
        sums = assigned.groupby(["class_id", "split"])[column].sum()
        for (class_id, split), value in sums.items():
            if split in table.columns:
                table.loc[int(str(class_id)), str(split)] = float(value)
    table.index = pd.Index([f"{i} {CLASSES[i]}" for i in table.index], name="classe")
    return table


def check_labels(labels: gpd.GeoDataFrame, blocks: gpd.GeoDataFrame) -> LabelReport:
    """Contrôle les polygones d'annotation par rapport aux blocs gelés."""
    labels = labels.reset_index(drop=True)
    problems: list[str] = []
    warnings: list[str] = []

    if labels.empty:
        warnings.append("Aucun polygone dans le fichier d'annotation.")

    for idx, row in labels.iterrows():
        num = int(str(idx)) + 1
        geom = row.geometry
        where = _where(geom)
        if geom is None or geom.is_empty or not geom.is_valid:
            problems.append(f"Polygone n°{num} : géométrie invalide ou vide{where}.")
        else:
            if geom.area < MIN_AREA_M2:
                warnings.append(
                    f"Polygone n°{num} : très petit ({geom.area:.0f} m², "
                    f"minimum conseillé {MIN_AREA_M2:.0f} m²){where}."
                )
            elif geom.area > MAX_AREA_M2:
                warnings.append(
                    f"Polygone n°{num} : très grand ({geom.area / 10_000:.1f} ha), "
                    f"vérifier qu'il est homogène{where}."
                )
        class_id = row["class_id"]
        if pd.isna(class_id) or int(class_id) not in CLASSES:
            problems.append(f"Polygone n°{num} : class_id invalide ({class_id}){where}.")
        elif row["class_name"] != CLASSES[int(class_id)]:
            problems.append(
                f"Polygone n°{num} : class_name incohérent "
                f"('{row['class_name']}' au lieu de '{CLASSES[int(class_id)]}'){where}."
            )

    tolerant = blocks[["block_id", "split", "geometry"]].copy()
    tolerant["geometry"] = tolerant.geometry.buffer(TOLERANCE_M)
    joined = gpd.sjoin(labels[["class_id", "geometry"]], tolerant, predicate="within", how="left")
    per_polygon = joined.groupby(level=0)["block_id"].nunique()
    for idx, n_blocks in per_polygon.items():
        num = int(str(idx)) + 1
        where = _where(labels.geometry.loc[idx])
        if n_blocks == 0:
            problems.append(
                f"Polygone n°{num} : traverse une limite de bloc ou sort des blocs{where}."
            )
        elif n_blocks > 1:
            problems.append(f"Polygone n°{num} : ambigu, contenu dans {n_blocks} blocs{where}.")

    assigned = joined.dropna(subset=["block_id"])
    assigned = assigned[~assigned.index.duplicated(keep="first")]
    assigned = assigned[assigned["class_id"].isin(list(CLASSES))].copy()
    assigned["class_id"] = assigned["class_id"].astype(int)
    assigned["n"] = 1
    assigned["ha"] = labels.geometry.loc[assigned.index].area / 10_000
    assigned["pixels"] = [_usable_pixels(labels.geometry.loc[i]) for i in assigned.index]

    counts = _table(assigned, "n").astype(int)
    return LabelReport(
        problems,
        counts,
        warnings,
        hectares=_table(assigned, "ha"),
        pixels=_table(assigned, "pixels"),
    )


def target_lines(pixels: pd.DataFrame) -> list[str]:
    """Compare les pixels estimés aux cibles du protocole, classe par classe."""
    lines: list[str] = []
    for label, row in pixels.iterrows():
        parts = []
        for split, target in TARGET_PIXELS.items():
            value = round(float(row[split]))
            status = "ok" if value >= target else "manque"
            parts.append(f"{split} {value}/{target} ({status})")
        lines.append(f"  {label} : " + ", ".join(parts))
    return lines


def main() -> None:
    if not LABELS_PATH.exists():
        raise SystemExit(f"Fichier introuvable : {LABELS_PATH}")
    config = load_split_config()
    blocks = zone_blocks(pd.read_csv(config.frozen_csv), config)
    labels = gpd.read_file(LABELS_PATH, layer=LABELS_LAYER)
    report = check_labels(labels, blocks)

    print(f"{len(labels)} polygones lus dans {LABELS_PATH}")
    print("\nPolygones par classe et par split :")
    print(report.counts.to_string())
    if report.hectares is not None:
        print("\nSurface annotée (hectares) :")
        print(report.hectares.round(1).to_string())
    if report.pixels is not None:
        print("\nPixels Sentinel-2 entièrement dans les polygones (estimation) :")
        print(report.pixels.round(0).astype(int).to_string())
        print("\nObjectifs du protocole (pixels) :")
        print("\n".join(target_lines(report.pixels)))
    if report.warnings:
        print(f"\n{len(report.warnings)} avertissement(s) :")
        for warning in report.warnings:
            print(f"  - {warning}")
    if report.problems:
        print(f"\n{len(report.problems)} problème(s) :")
        for problem in report.problems:
            print(f"  - {problem}")
        raise SystemExit(1)
    print("\nAucun problème détecté.")


if __name__ == "__main__":
    main()
