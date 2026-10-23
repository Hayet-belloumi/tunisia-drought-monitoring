"""Tests qui protègent le découpage gelé (ADR 0003) : le fichier ne doit jamais changer."""

from pathlib import Path

import pandas as pd
import pytest

from tdm.labels.split import (
    assign_splits,
    blocks_to_geodataframe,
    build_blocks,
    csv_sha256,
    load_split_config,
    render_csv,
    validate_split,
)
from tdm.zones import DEFAULT_BOUNDARIES_DIR, load_config, load_governorates, select_pilot_zones

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_split_config(ROOT / "configs" / "spatial_split.yaml")
FROZEN_CSV = ROOT / CONFIG.frozen_csv
FROZEN_SHA256 = ROOT / CONFIG.frozen_sha256
LAYER_PATH = ROOT / DEFAULT_BOUNDARIES_DIR / "tun_admin2.shp"

requires_frozen = pytest.mark.skipif(
    not FROZEN_CSV.exists(), reason="découpage pas encore généré : python -m tdm.labels.split"
)
requires_boundaries = pytest.mark.skipif(
    not LAYER_PATH.exists(), reason="frontières absentes : lancer tdm.boundaries"
)


@pytest.fixture(scope="module")
def pilot_zones():  # type: ignore[no-untyped-def]
    zones_config = load_config(ROOT / "configs" / "zones.yaml")
    governorates = load_governorates(zones_config, ROOT / DEFAULT_BOUNDARIES_DIR)
    return select_pilot_zones(governorates, zones_config)


@requires_frozen
def test_le_fichier_gele_correspond_a_son_empreinte() -> None:
    assert csv_sha256(FROZEN_CSV) == FROZEN_SHA256.read_text(encoding="utf-8").strip()


@requires_frozen
def test_le_decoupage_gele_est_valide() -> None:
    frozen = pd.read_csv(FROZEN_CSV)
    validate_split(frozen, CONFIG)
    assert set(frozen["zone_id"]) == {"sfax", "beja", "kairouan"}


@requires_frozen
def test_la_part_de_test_est_proche_de_la_cible_dans_chaque_zone() -> None:
    frozen = pd.read_csv(FROZEN_CSV)
    for _, group in frozen.groupby("zone_id"):
        share = (group["split"] == "test").mean()
        assert abs(share - CONFIG.test_fraction) <= 0.05


@requires_frozen
@requires_boundaries
def test_le_decoupage_gele_se_regenere_a_l_identique(pilot_zones) -> None:  # type: ignore[no-untyped-def]
    zone_order = list(pilot_zones["zone_id"])
    regenerated = assign_splits(build_blocks(pilot_zones, CONFIG), CONFIG, zone_order)
    frozen_text = FROZEN_CSV.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    assert render_csv(regenerated) == frozen_text


@requires_frozen
@requires_boundaries
def test_chaque_bloc_gele_recouvre_sa_zone(pilot_zones) -> None:  # type: ignore[no-untyped-def]
    frozen = pd.read_csv(FROZEN_CSV)
    squares = blocks_to_geodataframe(frozen, CONFIG)
    zones = pilot_zones.to_crs(CONFIG.crs).set_index("zone_id")
    minimum = CONFIG.min_overlap_fraction * CONFIG.block_size_m**2 * 0.999
    for _, block in squares.iterrows():
        overlap = block["geometry"].intersection(zones.loc[block["zone_id"], "geometry"]).area
        assert overlap >= minimum
