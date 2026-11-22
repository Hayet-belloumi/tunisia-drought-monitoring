"""Tests de la ligne de commande de contrôle des polygones (fonction main)."""

from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from tdm.labels import validate_labels as vl

CRS = "EPSG:32632"


def _blocks() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "block_id": ["a", "b"],
            "split": ["train", "test"],
            "geometry": [box(0, 0, 10000, 10000), box(10000, 0, 20000, 10000)],
        },
        crs=CRS,
    )


def _write_labels(path: Path, rows: list[tuple[int, str, object]]) -> None:
    labels = gpd.GeoDataFrame(
        {
            "class_id": [r[0] for r in rows],
            "class_name": [r[1] for r in rows],
            "geometry": [r[2] for r in rows],
        },
        crs=CRS,
    )
    labels.to_file(path, layer=vl.LABELS_LAYER, driver="GPKG")


def _prepare(monkeypatch: pytest.MonkeyPatch, labels_path: Path) -> None:
    """Remplace les accès disque et le découpage gelé par des données de test."""
    monkeypatch.setattr(vl, "LABELS_PATH", labels_path)
    monkeypatch.setattr(vl, "load_split_config", lambda: SimpleNamespace(frozen_csv="gele.csv"))
    monkeypatch.setattr(vl.pd, "read_csv", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(vl, "zone_blocks", lambda *_args, **_kwargs: _blocks())


def test_main_prints_full_report_when_labels_are_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "labels.gpkg"
    _write_labels(path, [(1, "oliviers", box(100, 100, 200, 200))])
    _prepare(monkeypatch, path)

    vl.main()

    out = capsys.readouterr().out
    assert "1 polygones lus" in out
    assert "Surface annotée (hectares)" in out
    assert "Objectifs du protocole" in out
    assert "Aucun problème détecté." in out


def test_main_exits_with_code_1_when_a_problem_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "labels.gpkg"
    _write_labels(path, [(9, "inconnu", box(100, 100, 200, 200))])
    _prepare(monkeypatch, path)

    with pytest.raises(SystemExit) as exit_info:
        vl.main()

    assert exit_info.value.code == 1
    assert "problème(s)" in capsys.readouterr().out


def test_main_prints_warnings_without_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "labels.gpkg"
    _write_labels(path, [(1, "oliviers", box(100, 100, 110, 110))])
    _prepare(monkeypatch, path)

    vl.main()

    out = capsys.readouterr().out
    assert "avertissement(s)" in out
    assert "très petit" in out


def test_main_stops_when_the_labels_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(monkeypatch, tmp_path / "absent.gpkg")

    with pytest.raises(SystemExit) as exit_info:
        vl.main()

    assert "Fichier introuvable" in str(exit_info.value.code)
