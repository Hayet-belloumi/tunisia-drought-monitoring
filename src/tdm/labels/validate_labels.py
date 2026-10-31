"""Contrôle qualité des polygones d'annotation de Kairouan.

Chaque polygone doit être valide, avoir une classe cohérente et être contenu dans
un seul bloc du découpage gelé (jamais à cheval sur deux blocs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from tdm.labels.annotation_grid import zone_blocks
from tdm.labels.split import load_split_config

LABELS_PATH = Path("data/labels/kairouan_labels.gpkg")
LABELS_LAYER = "labels"
TOLERANCE_M = 0.5

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
    """Résultat du contrôle : liste de problèmes et comptage par classe et split."""

    problems: list[str]
    counts: pd.DataFrame


def check_labels(labels: gpd.GeoDataFrame, blocks: gpd.GeoDataFrame) -> LabelReport:
    """Contrôle les polygones d'annotation par rapport aux blocs gelés."""
    labels = labels.reset_index(drop=True)
    problems: list[str] = []

    for idx, row in labels.iterrows():
        num = int(str(idx)) + 1
        geom = row.geometry
        if geom is None or geom.is_empty or not geom.is_valid:
            problems.append(f"Polygone n°{num} : géométrie invalide ou vide.")
        class_id = row["class_id"]
        if pd.isna(class_id) or int(class_id) not in CLASSES:
            problems.append(f"Polygone n°{num} : class_id invalide ({class_id}).")
        elif row["class_name"] != CLASSES[int(class_id)]:
            problems.append(
                f"Polygone n°{num} : class_name incohérent "
                f"('{row['class_name']}' au lieu de '{CLASSES[int(class_id)]}')."
            )

    tolerant = blocks[["block_id", "split", "geometry"]].copy()
    tolerant["geometry"] = tolerant.geometry.buffer(TOLERANCE_M)
    joined = gpd.sjoin(labels[["class_id", "geometry"]], tolerant, predicate="within", how="left")
    per_polygon = joined.groupby(level=0)["block_id"].nunique()
    for idx, n_blocks in per_polygon.items():
        num = int(str(idx)) + 1
        if n_blocks == 0:
            problems.append(f"Polygone n°{num} : traverse une limite de bloc ou sort des blocs.")
        elif n_blocks > 1:
            problems.append(f"Polygone n°{num} : ambigu, contenu dans {n_blocks} blocs.")

    assigned = joined.dropna(subset=["block_id"])
    assigned = assigned[~assigned.index.duplicated(keep="first")]
    assigned = assigned[assigned["class_id"].isin(list(CLASSES))]
    counts = pd.crosstab(assigned["class_id"].astype(int), assigned["split"])
    counts = counts.reindex(list(CLASSES), fill_value=0)
    for split in ("train", "test"):
        if split not in counts.columns:
            counts[split] = 0
    counts = counts[["train", "test"]]
    counts.index = pd.Index([f"{i} {CLASSES[i]}" for i in counts.index], name="classe")
    return LabelReport(problems, counts)


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
    if report.problems:
        print(f"\n{len(report.problems)} problème(s) :")
        for problem in report.problems:
            print(f"  - {problem}")
        raise SystemExit(1)
    print("\nAucun problème détecté.")


if __name__ == "__main__":
    main()
