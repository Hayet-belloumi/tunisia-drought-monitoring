"""Exporte les blocs d'une zone pilote vers un GeoPackage pour l'annotation dans QGIS.

Le découpage gelé (configs/spatial_split.csv) est seulement lu, jamais modifié.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from tdm.labels.split import SplitConfig, blocks_to_geodataframe, load_split_config

ZONE_ID = "kairouan"
OUTPUT = Path("data/labels/kairouan_blocks.gpkg")
LAYER = "blocs_kairouan"


def zone_blocks(
    frozen: pd.DataFrame, config: SplitConfig, zone_id: str = ZONE_ID
) -> gpd.GeoDataFrame:
    """Retourne les blocs d'une zone, avec leur géométrie, leur split et leur pli."""
    zone_df = frozen[frozen["zone_id"] == zone_id].copy()
    if zone_df.empty:
        raise ValueError(f"Aucun bloc pour la zone '{zone_id}' dans le CSV gelé.")
    blocks = gpd.GeoDataFrame(blocks_to_geodataframe(zone_df, config))
    missing = [c for c in ("split", "fold") if c not in blocks.columns]
    if missing:
        blocks = gpd.GeoDataFrame(
            blocks.merge(zone_df[["block_id", *missing]], on="block_id", how="left")
        )
    return blocks


def main() -> None:
    config = load_split_config()
    frozen = pd.read_csv(config.frozen_csv)
    blocks = zone_blocks(frozen, config)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    blocks.to_file(OUTPUT, layer=LAYER, driver="GPKG")
    counts = blocks["split"].value_counts().to_dict()
    print(f"{len(blocks)} blocs écrits dans {OUTPUT} (couche '{LAYER}'), CRS {blocks.crs}")
    print(f"Répartition : {counts}")


if __name__ == "__main__":
    main()
