"""Exporte vers Google Drive des images d'aide à l'annotation pour Kairouan.

Deux images 8 bits par mois : couleur naturelle et fausse couleur (la végétation
ressort en rouge), à partir des composites mensuels du projet (masque Cloud Score+).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import ee
import pandas as pd

from tdm.gee.auth import init_ee
from tdm.gee.composites import load_composite_config, monthly_composite
from tdm.labels.annotation_grid import zone_blocks
from tdm.labels.split import load_split_config

YEAR = 2025
MONTHS = (2, 4, 6, 9)
SCALE_M = 20
CRS = "EPSG:32632"
DRIVE_FOLDER = "tdm_annotation"
REFLECTANCE_MAX = 0.3

PRODUCTS: dict[str, tuple[str, str, str]] = {
    "couleur_naturelle": ("B4", "B3", "B2"),
    "fausse_couleur": ("B8", "B4", "B3"),
}


@dataclass(frozen=True)
class ExportItem:
    """Une image à exporter : un mois et un type de rendu."""

    year: int
    month: int
    product: str
    bands: tuple[str, str, str]

    @property
    def name(self) -> str:
        return f"kairouan_{self.year}_{self.month:02d}_{self.product}"


def export_plan(year: int = YEAR, months: tuple[int, ...] = MONTHS) -> list[ExportItem]:
    """Liste des images à produire (sans appeler Earth Engine)."""
    return [
        ExportItem(year, month, product, bands)
        for month in months
        for product, bands in PRODUCTS.items()
    ]


def blocks_region() -> ee.Geometry:
    """Rectangle englobant des blocs de Kairouan, exprimé en UTM 32N."""
    config = load_split_config()
    frozen = pd.read_csv(config.frozen_csv)
    minx, miny, maxx, maxy = (float(v) for v in zone_blocks(frozen, config).total_bounds)
    return ee.Geometry.Rectangle([minx, miny, maxx, maxy], proj=CRS, geodesic=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="affiche le plan sans exporter")
    args = parser.parse_args()

    plan = export_plan()
    print(f"{len(plan)} images prévues dans le dossier Drive '{DRIVE_FOLDER}' :")
    for item in plan:
        print(f"  - {item.name}  bandes {item.bands}")
    if args.dry_run:
        return

    init_ee()
    region = blocks_region()
    composite_config = load_composite_config()
    for item in plan:
        composite = monthly_composite(region, item.year, item.month, composite_config)
        image = composite.select(list(item.bands)).visualize(min=0, max=REFLECTANCE_MAX)
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=item.name,
            folder=DRIVE_FOLDER,
            fileNamePrefix=item.name,
            region=region,
            scale=SCALE_M,
            crs=CRS,
            maxPixels=int(1e9),
            fileFormat="GeoTIFF",
        )
        task.start()
        print(f"Export lancé : {item.name}")


if __name__ == "__main__":
    main()
