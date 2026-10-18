"""Exploration de Sentinel-2 : couverture sans nuages par zone et par mois.

Compare deux méthodes de masquage des nuages : la bande SCL de Sentinel-2 L2A et
Cloud Score+ (bande cs_cdf, plusieurs seuils). Aucune image n'est téléchargée : le calcul
est fait côté Earth Engine, seules des statistiques par zone reviennent.
"""

import argparse
import json
import time
from pathlib import Path

import ee
import pandas as pd
from shapely import to_geojson
from shapely.geometry.base import BaseGeometry

from tdm.gee.auth import init_ee
from tdm.zones import load_config, load_governorates, select_pilot_zones

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
CLOUD_SCORE_COLLECTION = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
CS_BAND = "cs_cdf"
CS_THRESHOLDS = (0.5, 0.6, 0.7)
# Classes SCL masquées : 3 ombre de nuage, 8 et 9 nuages (probabilité moyenne, haute), 10 cirrus.
SCL_BAD_CLASSES = [3, 8, 9, 10]
METHODS = ["scl"] + [f"cs{round(threshold * 100)}" for threshold in CS_THRESHOLDS]
SCALE_M = 20
OUTPUT_DIR = Path("data/interim")


def to_ee_geometry(geometry: BaseGeometry, tolerance: float = 0.001) -> ee.Geometry:
    """Convertit une géométrie shapely en géométrie Earth Engine, légèrement simplifiée."""
    simplified = geometry.simplify(tolerance)
    return ee.Geometry(json.loads(to_geojson(simplified)), None, False)


def _clear_bands(image: ee.Image) -> ee.Image:
    """Image à une bande par méthode : 1 si le pixel est clair, masqué sinon."""
    bad = image.select("SCL").remap(SCL_BAD_CLASSES, [1] * len(SCL_BAD_CLASSES), 0)
    score = image.select(CS_BAND)
    bands = [bad.eq(0).rename("scl")]
    for threshold, name in zip(CS_THRESHOLDS, METHODS[1:], strict=True):
        bands.append(score.gte(threshold).rename(name))
    return ee.Image.cat(bands).selfMask()


def month_stats(region: ee.Geometry, year: int, month: int) -> dict[str, float]:
    """Statistiques d'un mois sur une zone : images disponibles et couverture par méthode."""
    start = ee.Date.fromYMD(year, month, 1)
    linked = (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(region)
        .filterDate(start, start.advance(1, "month"))
        .linkCollection(ee.ImageCollection(CLOUD_SCORE_COLLECTION), [CS_BAND])
    )
    n_images = linked.size().getInfo()
    stats: dict[str, float] = {"n_images": n_images}
    if n_images == 0:
        empty = {f"{kind}_{name}": 0.0 for kind in ("cover", "obs") for name in METHODS}
        return {**stats, **empty}

    clear_count = linked.map(_clear_bands).count().unmask(0)
    cover = clear_count.gt(0).rename([f"cover_{name}" for name in METHODS])
    obs = clear_count.rename([f"obs_{name}" for name in METHODS])
    values = (
        ee.Image.cat([cover, obs])
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=SCALE_M,
            maxPixels=int(1e10),
            tileScale=4,
        )
        .getInfo()
    )
    return {**stats, **values}


def run(year: int, months: list[int]) -> pd.DataFrame:
    """Calcule les statistiques pour les 3 zones pilotes ; enregistre un CSV au fur et à mesure."""
    init_ee()
    config = load_config()
    zones = select_pilot_zones(load_governorates(config), config)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"s2_cloud_exploration_{year}.csv"

    rows: list[dict[str, object]] = []
    for _, zone in zones.iterrows():
        region = to_ee_geometry(zone["geometry"])
        for month in months:
            started = time.perf_counter()
            stats = month_stats(region, year, month)
            rows.append({"zone": zone["zone_id"], "year": year, "month": month, **stats})
            pd.DataFrame(rows).to_csv(output, index=False)
            elapsed = time.perf_counter() - started
            print(f"{zone['zone_id']:<9} {year}-{month:02d} terminé en {elapsed:.0f} s", flush=True)
    return pd.DataFrame(rows)


def main() -> None:
    """Point d'entrée : python -m tdm.gee.explore --year 2025 --months 1 7"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)))
    args = parser.parse_args()

    table = run(args.year, args.months)
    columns = ["zone", "month", "n_images"] + [f"cover_{name}" for name in METHODS]
    print("\nCouverture = part des pixels avec au moins une observation claire dans le mois")
    print(table[columns].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
