"""Composites mensuels Sentinel-2 sans nuages (exigence F01).

Pour un mois et une zone : les pixels nuageux sont masqués avec Cloud Score+ (ADR 0002), puis
on prend la médiane des observations claires de chaque pixel. Un pixel qui a moins de
`min_clear_observations` observations claires reste vide plutôt que d'être rempli avec une
valeur peu fiable. Le calcul reste côté Earth Engine : le composite n'est jamais téléchargé.
"""

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import ee
import pandas as pd
import yaml

from tdm.gee.auth import init_ee
from tdm.gee.explore import to_ee_geometry
from tdm.zones import load_config, load_governorates, select_pilot_zones

DEFAULT_CONFIG = Path("configs/composites.yaml")
OUTPUT_DIR = Path("data/interim")
CHECK_SCALE_M = 100


@dataclass(frozen=True)
class CompositeConfig:
    """Contenu de configs/composites.yaml."""

    s2_collection: str
    cloud_collection: str
    cloud_band: str
    cloud_threshold: float
    bands: tuple[str, ...]
    scale_factor: float
    min_clear_observations: int


def load_composite_config(path: Path = DEFAULT_CONFIG) -> CompositeConfig:
    """Lit le fichier de configuration des composites."""
    with path.open(encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    cloud, composite = raw["cloud_mask"], raw["composite"]
    return CompositeConfig(
        s2_collection=composite["collection"],
        cloud_collection=cloud["collection"],
        cloud_band=cloud["band"],
        cloud_threshold=float(cloud["threshold"]),
        bands=tuple(composite["bands"]),
        scale_factor=float(composite["scale_factor"]),
        min_clear_observations=int(composite["min_clear_observations"]),
    )


def monthly_composite(
    region: ee.Geometry, year: int, month: int, config: CompositeConfig
) -> ee.Image:
    """Composite médian d'un mois : bandes en réflectance (0-1) et bande `n_obs`.

    `n_obs` donne le nombre d'observations claires par pixel. Les pixels qui en ont moins
    que `min_clear_observations` sont masqués dans les bandes spectrales.
    """
    start = ee.Date.fromYMD(year, month, 1)
    collection = (
        ee.ImageCollection(config.s2_collection)
        .filterBounds(region)
        .filterDate(start, start.advance(1, "month"))
        .linkCollection(ee.ImageCollection(config.cloud_collection), [config.cloud_band])
    )

    def mask_clouds(image: ee.Image) -> ee.Image:
        clear = image.select(config.cloud_band).gte(config.cloud_threshold)
        return image.select(list(config.bands)).updateMask(clear)

    masked = collection.map(mask_clouds)
    n_obs = masked.select(config.bands[0]).count().rename("n_obs")
    reflectance = masked.median().multiply(config.scale_factor)
    enough = n_obs.gte(config.min_clear_observations)
    return reflectance.updateMask(enough).addBands(n_obs)


def check_month(
    region: ee.Geometry, year: int, month: int, config: CompositeConfig
) -> dict[str, float | None]:
    """Contrôle rapide (à 100 m) : part de pixels valides, NDVI moyen, observations moyennes."""
    composite = monthly_composite(region, year, month, config)
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("ndvi")
    valid = composite.select("B4").mask().rename("valid")
    return (
        ee.Image.cat([valid, ndvi, composite.select("n_obs")])
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=CHECK_SCALE_M,
            maxPixels=int(1e10),
            tileScale=4,
        )
        .getInfo()
    )


def run(year: int, months: list[int]) -> pd.DataFrame:
    """Contrôle les composites des 3 zones pilotes ; enregistre un CSV au fur et à mesure."""
    init_ee()
    config = load_composite_config()
    zones_config = load_config()
    zones = select_pilot_zones(load_governorates(zones_config), zones_config)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"composites_check_{year}.csv"

    rows: list[dict[str, object]] = []
    for _, zone in zones.iterrows():
        region = to_ee_geometry(zone["geometry"])
        for month in months:
            started = time.perf_counter()
            stats = check_month(region, year, month, config)
            rows.append({"zone": zone["zone_id"], "year": year, "month": month, **stats})
            pd.DataFrame(rows).to_csv(output, index=False)
            elapsed = time.perf_counter() - started
            print(f"{zone['zone_id']:<9} {year}-{month:02d} terminé en {elapsed:.0f} s", flush=True)
    return pd.DataFrame(rows)


def main() -> None:
    """Point d'entrée : python -m tdm.gee.composites --year 2025 --months 1 4 7"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)))
    args = parser.parse_args()

    table = run(args.year, args.months)
    print("\nvalid = part de pixels avec assez d'observations claires ; ndvi = NDVI moyen")
    print(table[["zone", "month", "valid", "ndvi", "n_obs"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
