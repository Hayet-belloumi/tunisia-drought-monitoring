from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from tdm.zones import Zone, ZonesConfig, load_config, select_pilot_zones

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "zones.yaml"


def _config() -> ZonesConfig:
    return ZonesConfig(
        layer="tun_admin2.shp",
        id_column="adm2_pcode",
        name_column="adm2_name",
        expected_governorates=3,
        zones=(
            Zone(id="sfax", name="Sfax", pcode="TN34", role="oléiculture"),
            Zone(id="beja", name="Béja", pcode="TN21", role="céréaliculture"),
        ),
    )


def _governorates() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "adm2_pcode": ["TN11", "TN21", "TN34"],
            "adm2_name": ["Tunis", "Béja", "Sfax"],
            "geometry": [box(10, 36, 11, 37), box(9, 36, 10, 37), box(10, 34, 11, 35)],
        },
        crs="EPSG:4326",
    )


def test_select_pilot_zones_respecte_l_ordre_de_la_config() -> None:
    zones = select_pilot_zones(_governorates(), _config())
    assert list(zones["zone_id"]) == ["sfax", "beja"]
    assert zones.crs == "EPSG:4326"


def test_select_pilot_zones_signale_un_gouvernorat_absent() -> None:
    governorates = _governorates()
    governorates = governorates[governorates["adm2_pcode"] != "TN34"]
    with pytest.raises(ValueError, match="TN34"):
        select_pilot_zones(governorates, _config())


def test_config_reelle_definit_les_trois_zones_pilotes() -> None:
    config = load_config(CONFIG_PATH)
    assert [zone.id for zone in config.zones] == ["sfax", "beja", "kairouan"]
    assert config.expected_governorates == 24
