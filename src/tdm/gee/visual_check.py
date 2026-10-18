"""Contrôle visuel des masques de nuages : une même image, trois aperçus PNG.

Les pixels retirés par un masque sont recouverts en rouge. Les aperçus s'ouvrent dans le
navigateur. Seul un aperçu est généré par Earth Engine : aucune donnée n'est enregistrée.
"""

import argparse
import webbrowser

import ee

from tdm.gee.auth import init_ee
from tdm.gee.explore import (
    CLOUD_SCORE_COLLECTION,
    CS_BAND,
    S2_COLLECTION,
    SCL_BAD_CLASSES,
    to_ee_geometry,
)
from tdm.zones import load_config, load_governorates, select_pilot_zones

CS_THRESHOLD = 0.6
DIMENSIONS = 1600


def pick_image(region: ee.Geometry, start: str, end: str) -> ee.Image:
    """Choisit une image assez nuageuse (20 à 70 % de nuages sur la tuile), avec Cloud Score+."""
    collection = (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.gte("CLOUDY_PIXEL_PERCENTAGE", 20))
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", 70))
        .sort("CLOUDY_PIXEL_PERCENTAGE", False)
        .linkCollection(ee.ImageCollection(CLOUD_SCORE_COLLECTION), [CS_BAND])
    )
    if collection.size().getInfo() == 0:
        raise RuntimeError("Aucune image assez nuageuse sur cette période : élargir les dates.")
    return collection.first()


def highlight(rgb: ee.Image, removed: ee.Image) -> ee.Image:
    """Recouvre en rouge les pixels `removed` (image 0/1) d'un aperçu RGB."""
    red = ee.Image.constant(1).visualize(palette=["FF0000"], min=0, max=1)
    return rgb.blend(red.updateMask(removed))


def main() -> None:
    """Point d'entrée : python -m tdm.gee.visual_check --zone beja"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", default="beja")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2025-02-01")
    args = parser.parse_args()

    init_ee()
    config = load_config()
    zones = select_pilot_zones(load_governorates(config), config)
    row = zones[zones["zone_id"] == args.zone].iloc[0]
    region = to_ee_geometry(row["geometry"])

    image = pick_image(region, args.start, args.end)
    image_id = image.get("system:index").getInfo()
    cloudy = image.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    print(f"Image : {image_id} (nuages sur la tuile : {cloudy:.0f} %)")

    rgb = image.visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
    removed_scl = image.select("SCL").remap(SCL_BAD_CLASSES, [1] * len(SCL_BAD_CLASSES), 0)
    removed_cs = image.select(CS_BAND).lt(CS_THRESHOLD)
    views = {
        "1_image_brute": rgb,
        "2_retire_par_SCL": highlight(rgb, removed_scl),
        f"3_retire_par_cloud_score_plus_{CS_THRESHOLD}": highlight(rgb, removed_cs),
    }
    for name, view in views.items():
        url = view.getThumbURL({"region": region, "dimensions": DIMENSIONS, "format": "png"})
        print(f"{name} : {url}")
        webbrowser.open(url)


if __name__ == "__main__":
    main()
