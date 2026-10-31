import geopandas as gpd
from shapely.geometry import box

from tdm.labels.validate_labels import check_labels

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
