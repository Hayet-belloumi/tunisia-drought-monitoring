from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from tdm.zones import Zone, ZonesConfig, load_governorates


def _config(expected: int) -> ZonesConfig:
    return ZonesConfig(
        layer="layer.shp",
        id_column="adm2_pcode",
        name_column="adm2_name",
        expected_governorates=expected,
        zones=(Zone(id="sfax", name="Sfax", pcode="TN34", role="oléiculture"),),
    )


def _write_layer(directory: Path) -> None:
    gpd.GeoDataFrame(
        {
            "adm2_pcode": ["TN34", "TN21"],
            "adm2_name": ["Sfax", "Béja"],
            "geometry": [box(10, 34, 11, 35), box(9, 36, 10, 37)],
        },
        crs="EPSG:4326",
    ).to_file(directory / "layer.shp")


def test_load_governorates_lit_la_couche(tmp_path: Path) -> None:
    _write_layer(tmp_path)
    assert len(load_governorates(_config(2), tmp_path)) == 2


def test_load_governorates_refuse_un_nombre_inattendu(tmp_path: Path) -> None:
    _write_layer(tmp_path)
    with pytest.raises(ValueError, match="attendus"):
        load_governorates(_config(24), tmp_path)


def test_load_governorates_signale_un_fichier_absent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="tdm.boundaries"):
        load_governorates(_config(24), tmp_path)
