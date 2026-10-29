import pandas as pd

from tdm.labels.annotation_grid import zone_blocks
from tdm.labels.split import load_split_config


def _kairouan():
    config = load_split_config()
    frozen = pd.read_csv(config.frozen_csv)
    return zone_blocks(frozen, config, "kairouan")


def test_kairouan_has_frozen_block_counts() -> None:
    blocks = _kairouan()
    assert len(blocks) == 73
    counts = blocks["split"].value_counts().to_dict()
    assert counts == {"train": 58, "test": 15}


def test_blocks_have_valid_geometry_in_split_crs() -> None:
    blocks = _kairouan()
    assert blocks.crs is not None
    assert blocks.crs.to_epsg() == 32632
    assert blocks.geometry.is_valid.all()
    assert (blocks.geometry.area > 0).all()
    assert (blocks.geometry.area <= 1e8 * 1.0001).all()


def test_block_ids_are_unique() -> None:
    blocks = _kairouan()
    assert blocks["block_id"].is_unique
