"""Tests de géométrie : projections, emprises et cohérence des contours (frontières HDX).

Ces tests lisent les vraies frontières dans data/ (téléchargées par `python -m tdm.boundaries`).
Ils sont ignorés si le fichier est absent.
"""

import inspect
from pathlib import Path

import geopandas as gpd
import pytest

from tdm.gee.explore import to_ee_geometry
from tdm.zones import DEFAULT_BOUNDARIES_DIR, load_config, load_governorates, select_pilot_zones

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "zones.yaml"
LAYER_PATH = ROOT / DEFAULT_BOUNDARIES_DIR / "tun_admin2.shp"

# Emprise large de la Tunisie : (longitude min, latitude min, longitude max, latitude max).
TUNISIA_BOUNDS = (7.0, 30.0, 12.5, 38.0)
EQUAL_AREA_CRS = "EPSG:6933"  # conserve les aires
UTM_32N = "EPSG:32632"  # mètres ; couvre toute la Tunisie

requires_boundaries = pytest.mark.skipif(
    not LAYER_PATH.exists(), reason="frontières absentes : lancer tdm.boundaries"
)


@pytest.fixture(scope="module")
def governorates() -> gpd.GeoDataFrame:
    return load_governorates(load_config(CONFIG_PATH), ROOT / DEFAULT_BOUNDARIES_DIR)


@pytest.fixture(scope="module")
def pilot_zones(governorates: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return select_pilot_zones(governorates, load_config(CONFIG_PATH))


@requires_boundaries
def test_les_contours_sont_en_wgs84(governorates: gpd.GeoDataFrame) -> None:
    assert governorates.crs == "EPSG:4326"


@requires_boundaries
def test_les_geometries_sont_valides_et_non_vides(governorates: gpd.GeoDataFrame) -> None:
    assert governorates.geometry.is_valid.all()
    assert not governorates.geometry.is_empty.any()
    assert governorates.geom_type.isin(["Polygon", "MultiPolygon"]).all()


@requires_boundaries
def test_les_gouvernorats_sont_dans_l_emprise_de_la_tunisie(governorates: gpd.GeoDataFrame) -> None:
    min_lon, min_lat, max_lon, max_lat = governorates.total_bounds
    assert min_lon >= TUNISIA_BOUNDS[0]
    assert min_lat >= TUNISIA_BOUNDS[1]
    assert max_lon <= TUNISIA_BOUNDS[2]
    assert max_lat <= TUNISIA_BOUNDS[3]


@requires_boundaries
def test_les_surfaces_recalculees_correspondent_a_area_sqkm(governorates: gpd.GeoDataFrame) -> None:
    recomputed = governorates.to_crs(EQUAL_AREA_CRS).area / 1e6
    error = (recomputed - governorates["area_sqkm"]).abs() / governorates["area_sqkm"]
    assert error.max() < 0.05, f"écart maximal : {error.max():.1%}"


@requires_boundaries
def test_les_zones_pilotes_ont_la_taille_attendue(pilot_zones: gpd.GeoDataFrame) -> None:
    areas_km2 = pilot_zones.set_index("zone_id").to_crs(UTM_32N).area / 1e6
    assert 6500 < areas_km2["sfax"] < 7500
    assert 3300 < areas_km2["beja"] < 4000
    assert 6000 < areas_km2["kairouan"] < 7000


@requires_boundaries
def test_les_zones_pilotes_ne_se_chevauchent_pas(pilot_zones: gpd.GeoDataFrame) -> None:
    geometries = list(pilot_zones.to_crs(UTM_32N).geometry)
    for index, first in enumerate(geometries):
        for second in geometries[index + 1 :]:
            assert first.intersection(second).area < 1e6  # moins de 1 km²


@requires_boundaries
def test_la_simplification_pour_earth_engine_change_peu_les_surfaces(
    pilot_zones: gpd.GeoDataFrame,
) -> None:
    tolerance = inspect.signature(to_ee_geometry).parameters["tolerance"].default
    original = pilot_zones.geometry
    simplified = original.simplify(tolerance)
    original_area = original.to_crs(UTM_32N).area
    simplified_area = simplified.to_crs(UTM_32N).area
    assert ((original_area - simplified_area).abs() / original_area).max() < 0.01
