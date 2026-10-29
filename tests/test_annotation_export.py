from tdm.gee.annotation_export import export_plan


def test_plan_has_two_products_per_month() -> None:
    plan = export_plan(2025, (2, 4, 6, 9))
    assert len(plan) == 8


def test_plan_names_are_unique_and_explicit() -> None:
    names = [item.name for item in export_plan(2025, (2, 4))]
    assert len(names) == len(set(names))
    assert "kairouan_2025_02_couleur_naturelle" in names
    assert "kairouan_2025_04_fausse_couleur" in names


def test_each_item_uses_three_bands() -> None:
    assert all(len(item.bands) == 3 for item in export_plan())
