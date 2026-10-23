from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from tdm.labels.split import (
    SplitConfig,
    assign_splits,
    blocks_to_geodataframe,
    build_blocks,
    csv_sha256,
    validate_split,
)

ZONE_ORDER = ["a", "b"]


def _config() -> SplitConfig:
    return SplitConfig(
        block_size_m=10_000,
        crs="EPSG:32632",
        min_overlap_fraction=0.25,
        test_fraction=0.2,
        n_folds=5,
        seed=42,
        buffer_m=1000,
        frozen_csv=Path("unused.csv"),
        frozen_sha256=Path("unused.sha256"),
    )


def _zones() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "zone_id": ZONE_ORDER,
            "geometry": [box(10.0, 35.0, 10.5, 35.4), box(9.2, 36.0, 9.7, 36.4)],
        },
        crs="EPSG:4326",
    )


def _assigned() -> pd.DataFrame:
    config = _config()
    return assign_splits(build_blocks(_zones(), config), config, ZONE_ORDER)


def test_build_blocks_couvre_chaque_zone_avec_des_blocs_carres() -> None:
    config = _config()
    blocks = build_blocks(_zones(), config)
    assert set(blocks["zone_id"]) == set(ZONE_ORDER)
    assert len(blocks) > 10
    assert not blocks["block_id"].duplicated().any()

    squares = blocks_to_geodataframe(blocks, config)
    assert (squares.area == config.block_size_m**2).all()
    zones = _zones().to_crs(config.crs).set_index("zone_id")
    for _, block in squares.iterrows():
        overlap = block["geometry"].intersection(zones.loc[block["zone_id"], "geometry"]).area
        assert overlap >= config.min_overlap_fraction * config.block_size_m**2 * 0.999


def test_assign_splits_est_deterministe() -> None:
    assert _assigned().equals(_assigned())


def test_assign_splits_respecte_les_proportions_dans_chaque_zone() -> None:
    config = _config()
    for _, group in _assigned().groupby("zone_id"):
        expected = max(1, round(config.test_fraction * len(group)))
        assert (group["split"] == "test").sum() == expected
        train_folds = set(group.loc[group["split"] == "train", "fold"].tolist())
        assert train_folds == set(range(config.n_folds))


def test_validate_split_accepte_un_decoupage_valide() -> None:
    validate_split(_assigned(), _config())


def test_validate_split_refuse_une_zone_sans_bloc_de_test() -> None:
    blocks = _assigned()
    mask = blocks["zone_id"] == "a"
    blocks.loc[mask, "split"] = "train"
    blocks.loc[mask, "fold"] = 0
    with pytest.raises(ValueError, match="au moins un bloc"):
        validate_split(blocks, _config())


def test_validate_split_refuse_les_doublons() -> None:
    blocks = _assigned()
    duplicated = pd.concat([blocks, blocks.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="double"):
        validate_split(duplicated, _config())


def test_csv_sha256_ignore_les_fins_de_ligne(tmp_path: Path) -> None:
    unix = tmp_path / "unix.csv"
    windows = tmp_path / "windows.csv"
    unix.write_bytes(b"a,b\n1,2\n")
    windows.write_bytes(b"a,b\r\n1,2\r\n")
    assert csv_sha256(unix) == csv_sha256(windows)
