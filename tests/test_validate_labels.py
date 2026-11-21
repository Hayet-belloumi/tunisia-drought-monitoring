import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from tdm.labels.validate_labels import check_labels, target_lines

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


def _labels(rows: list[tuple[int, str, object]]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "class_id": [r[0] for r in rows],
            "class_name": [r[1] for r in rows],
            "geometry": [r[2] for r in rows],
        },
        crs=CRS,
    )


def test_valid_polygons_are_counted_by_split() -> None:
    labels = _labels(
        [(3, "steppe", box(100, 100, 200, 200)), (2, "cereales", box(10100, 100, 10200, 200))]
    )
    report = check_labels(labels, _blocks())
    assert report.problems == []
    assert report.counts.loc["3 steppe", "train"] == 1
    assert report.counts.loc["2 cereales", "test"] == 1


def test_polygon_across_two_blocks_is_flagged() -> None:
    labels = _labels([(3, "steppe", box(9900, 100, 10100, 200))])
    report = check_labels(labels, _blocks())
    assert any("limite de bloc" in p for p in report.problems)


def test_bad_class_id_and_name_are_flagged() -> None:
    labels = _labels(
        [(9, "inconnu", box(100, 100, 200, 200)), (3, "foret", box(300, 300, 400, 400))]
    )
    report = check_labels(labels, _blocks())
    assert any("class_id invalide" in p for p in report.problems)
    assert any("class_name incohérent" in p for p in report.problems)


def test_problem_message_gives_polygon_location() -> None:
    labels = _labels([(3, "foret", box(300, 300, 400, 400))])
    report = check_labels(labels, _blocks())
    assert any("centre : x=350, y=350" in p for p in report.problems)


def test_hectares_are_summed_by_class_and_split() -> None:
    labels = _labels(
        [
            (3, "steppe", box(100, 100, 200, 200)),  # 1 ha, train
            (2, "cereales", box(10100, 100, 10300, 200)),  # 2 ha, test
        ]
    )
    report = check_labels(labels, _blocks())
    assert report.hectares is not None
    assert report.hectares.loc["3 steppe", "train"] == pytest.approx(1.0)
    assert report.hectares.loc["2 cereales", "test"] == pytest.approx(2.0)
    assert report.hectares.loc["1 oliviers", "train"] == 0


def test_usable_pixels_shrink_polygon_by_half_a_pixel() -> None:
    # 100 m x 100 m rétréci de 10 m de chaque côté = 80 m x 80 m = 16 pixels de 400 m².
    labels = _labels([(3, "steppe", box(100, 100, 200, 200))])
    report = check_labels(labels, _blocks())
    assert report.pixels is not None
    assert report.pixels.loc["3 steppe", "train"] == pytest.approx(16.0)


def test_tiny_and_huge_polygons_raise_warnings_not_problems() -> None:
    labels = _labels(
        [
            (3, "steppe", box(100, 100, 110, 110)),  # 100 m²
            (3, "steppe", box(2000, 2000, 3000, 3000)),  # 100 ha
        ]
    )
    report = check_labels(labels, _blocks())
    assert report.problems == []
    assert any("très petit" in w for w in report.warnings)
    assert any("très grand" in w for w in report.warnings)


def test_empty_file_gives_a_warning_and_zero_counts() -> None:
    labels = gpd.GeoDataFrame({"class_id": [], "class_name": []}, geometry=[], crs=CRS)
    report = check_labels(labels, _blocks())
    assert report.problems == []
    assert any("Aucun polygone" in w for w in report.warnings)
    assert int(report.counts.to_numpy().sum()) == 0
    assert report.pixels is not None
    assert float(report.pixels.to_numpy().sum()) == 0


def test_target_lines_compare_pixels_with_protocol_targets() -> None:
    pixels = pd.DataFrame(
        {"train": [250.0, 10.0], "test": [60.0, 0.0]},
        index=pd.Index(["1 oliviers", "2 cereales"], name="classe"),
    )
    lines = target_lines(pixels)
    assert "train 250/200 (ok)" in lines[0]
    assert "test 60/50 (ok)" in lines[0]
    assert "train 10/200 (manque)" in lines[1]
