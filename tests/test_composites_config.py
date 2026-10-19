from pathlib import Path

from tdm.gee.composites import load_composite_config

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "composites.yaml"


def test_config_reelle_correspond_a_l_adr_0002() -> None:
    config = load_composite_config(CONFIG_PATH)
    assert config.cloud_band == "cs_cdf"
    assert config.cloud_threshold == 0.6
    assert config.min_clear_observations == 2


def test_les_bandes_incluent_celles_du_ndvi() -> None:
    config = load_composite_config(CONFIG_PATH)
    assert {"B4", "B8"} <= set(config.bands)
