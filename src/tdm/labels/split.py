"""Découpage spatial par blocs géographiques (exigence F03) : test gelé et folds de validation.

Les zones pilotes sont quadrillées en blocs carrés. Chaque bloc entier est affecté à un camp,
jamais un pixel isolé : des pixels voisins se ressemblent, et un tirage de pixels au hasard
gonflerait les scores (fuite spatiale). Le découpage est tiré une seule fois puis gelé dans un
fichier CSV versionné : ce fichier fait foi, pas la graine.
"""

import argparse
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import box

from tdm.zones import load_config, load_governorates, select_pilot_zones

DEFAULT_CONFIG = Path("configs/spatial_split.yaml")
COLUMNS = ["block_id", "zone_id", "ix", "iy", "split", "fold"]


@dataclass(frozen=True)
class SplitConfig:
    """Contenu de configs/spatial_split.yaml."""

    block_size_m: int
    crs: str
    min_overlap_fraction: float
    test_fraction: float
    n_folds: int
    seed: int
    buffer_m: int
    frozen_csv: Path
    frozen_sha256: Path


def load_split_config(path: Path = DEFAULT_CONFIG) -> SplitConfig:
    """Lit le fichier de configuration du découpage."""
    with path.open(encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    return SplitConfig(
        block_size_m=int(raw["block_size_m"]),
        crs=str(raw["crs"]),
        min_overlap_fraction=float(raw["min_overlap_fraction"]),
        test_fraction=float(raw["test_fraction"]),
        n_folds=int(raw["n_folds"]),
        seed=int(raw["seed"]),
        buffer_m=int(raw["buffer_m"]),
        frozen_csv=Path(raw["frozen_csv"]),
        frozen_sha256=Path(raw["frozen_sha256"]),
    )


def build_blocks(zones: gpd.GeoDataFrame, config: SplitConfig) -> pd.DataFrame:
    """Quadrille les zones en blocs carrés alignés sur une grille fixe (en mètres).

    Un bloc est rattaché à la zone qui le recouvre le plus, et gardé si au moins
    `min_overlap_fraction` de sa surface est dans cette zone.
    """
    projected = zones.to_crs(config.crs)
    size = config.block_size_m
    min_x, min_y, max_x, max_y = projected.total_bounds
    rows: list[dict[str, object]] = []
    for ix in range(math.floor(min_x / size), math.floor(max_x / size) + 1):
        for iy in range(math.floor(min_y / size), math.floor(max_y / size) + 1):
            cell = box(ix * size, iy * size, (ix + 1) * size, (iy + 1) * size)
            best_zone, best_area = "", 0.0
            for _, zone in projected.iterrows():
                area = cell.intersection(zone["geometry"]).area
                if area > best_area:
                    best_zone, best_area = zone["zone_id"], area
            if best_area >= config.min_overlap_fraction * cell.area:
                rows.append({"block_id": f"{ix}_{iy}", "zone_id": best_zone, "ix": ix, "iy": iy})
    return pd.DataFrame(rows)


def assign_splits(blocks: pd.DataFrame, config: SplitConfig, zone_order: list[str]) -> pd.DataFrame:
    """Affecte chaque bloc à `test` ou `train`, puis les blocs `train` à un fold (0 à n-1).

    Le tirage se fait zone par zone, avec une graine fixe : chaque zone a ses blocs de test.
    Les blocs de test ont le fold -1.
    """
    rng = np.random.default_rng(config.seed)
    parts: list[pd.DataFrame] = []
    for zone_id in zone_order:
        part = blocks[blocks["zone_id"] == zone_id].sort_values(["ix", "iy"]).reset_index(drop=True)
        n_blocks = len(part)
        n_test = max(1, round(config.test_fraction * n_blocks))
        order = rng.permutation(n_blocks)
        split = ["train"] * n_blocks
        fold = [-1] * n_blocks
        for index in order[:n_test]:
            split[index] = "test"
        for rank, index in enumerate(order[n_test:]):
            fold[index] = rank % config.n_folds
        part["split"] = split
        part["fold"] = fold
        parts.append(part)
    return pd.concat(parts, ignore_index=True)[COLUMNS]


def validate_split(blocks: pd.DataFrame, config: SplitConfig) -> None:
    """Vérifie les propriétés qui rendent le découpage utilisable ; lève ValueError sinon."""
    if blocks["block_id"].duplicated().any():
        raise ValueError("Identifiants de blocs en double.")
    if not set(blocks["split"]) <= {"train", "test"}:
        raise ValueError("Valeur de `split` inconnue (attendu : train ou test).")
    for zone_id, group in blocks.groupby("zone_id"):
        test = group[group["split"] == "test"]
        train = group[group["split"] == "train"]
        if test.empty or train.empty:
            raise ValueError(
                f"Zone {zone_id} : il faut au moins un bloc de test et un bloc d'entraînement."
            )
        if (test["fold"] != -1).any():
            raise ValueError(f"Zone {zone_id} : un bloc de test a un numéro de fold.")
        if set(train["fold"].tolist()) != set(range(config.n_folds)):
            raise ValueError(f"Zone {zone_id} : chaque fold doit contenir au moins un bloc.")


def blocks_to_geodataframe(blocks: pd.DataFrame, config: SplitConfig) -> gpd.GeoDataFrame:
    """Reconstruit la géométrie carrée de chaque bloc (en mètres) à partir de ses indices."""
    size = config.block_size_m
    geometry = [
        box(ix * size, iy * size, (ix + 1) * size, (iy + 1) * size)
        for ix, iy in zip(blocks["ix"], blocks["iy"], strict=True)
    ]
    return gpd.GeoDataFrame(blocks.copy(), geometry=geometry, crs=config.crs)


def render_csv(blocks: pd.DataFrame) -> str:
    """Texte du fichier gelé (fins de ligne LF, pour un résultat identique sur tout système)."""
    return blocks.to_csv(index=False, lineterminator="\n")


def csv_sha256(path: Path) -> str:
    """Empreinte SHA-256 d'un fichier texte, insensible aux fins de ligne Windows."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_frozen(blocks: pd.DataFrame, config: SplitConfig) -> None:
    """Enregistre le découpage gelé et son empreinte."""
    config.frozen_csv.write_text(render_csv(blocks), encoding="utf-8", newline="\n")
    digest = csv_sha256(config.frozen_csv)
    config.frozen_sha256.write_text(digest + "\n", encoding="utf-8", newline="\n")


def print_summary(blocks: pd.DataFrame, zone_order: list[str]) -> None:
    """Affiche le nombre de blocs par zone et par camp."""
    summary = blocks.groupby("zone_id").agg(
        blocs=("block_id", "count"), test=("split", lambda s: int((s == "test").sum()))
    )
    summary["train"] = summary["blocs"] - summary["test"]
    print(summary.reindex(zone_order).to_string())
    train = blocks[blocks["split"] == "train"]
    print("blocs d'entraînement par fold :", train["fold"].value_counts().sort_index().to_dict())


def main() -> None:
    """Point d'entrée : python -m tdm.labels.split [--check]"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare avec le fichier gelé")
    parser.add_argument("--force", action="store_true", help="écrase le fichier gelé (à éviter)")
    args = parser.parse_args()

    config = load_split_config()
    zones_config = load_config()
    zones = select_pilot_zones(load_governorates(zones_config), zones_config)
    zone_order = list(zones["zone_id"])
    blocks = assign_splits(build_blocks(zones, config), config, zone_order)
    validate_split(blocks, config)
    print_summary(blocks, zone_order)

    if args.check:
        frozen = config.frozen_csv.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
        same = config.frozen_csv.exists() and frozen == render_csv(blocks)
        print("Identique au découpage gelé." if same else "DIFFÉRENT du découpage gelé !")
        return
    if config.frozen_csv.exists() and not args.force:
        raise SystemExit(f"{config.frozen_csv} existe déjà : le découpage est gelé (ADR 0003).")
    write_frozen(blocks, config)
    print(f"Enregistré : {config.frozen_csv} (SHA-256 : {csv_sha256(config.frozen_csv)})")


if __name__ == "__main__":
    main()
