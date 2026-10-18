"""Définition et chargement des zones pilotes (gouvernorats de la v1.0)."""

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import yaml

DEFAULT_CONFIG = Path("configs/zones.yaml")
DEFAULT_BOUNDARIES_DIR = Path("data/raw/boundaries/extracted")


@dataclass(frozen=True)
class Zone:
    """Une zone pilote : un gouvernorat identifié par son P-code."""

    id: str
    name: str
    pcode: str
    role: str


@dataclass(frozen=True)
class ZonesConfig:
    """Contenu de configs/zones.yaml."""

    layer: str
    id_column: str
    name_column: str
    expected_governorates: int
    zones: tuple[Zone, ...]


def load_config(path: Path = DEFAULT_CONFIG) -> ZonesConfig:
    """Lit le fichier de configuration des zones."""
    with path.open(encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    boundaries = raw["boundaries"]
    return ZonesConfig(
        layer=boundaries["layer"],
        id_column=boundaries["id_column"],
        name_column=boundaries["name_column"],
        expected_governorates=boundaries["expected_governorates"],
        zones=tuple(Zone(**zone) for zone in raw["zones"]),
    )


def load_governorates(
    config: ZonesConfig, boundaries_dir: Path = DEFAULT_BOUNDARIES_DIR
) -> gpd.GeoDataFrame:
    """Charge la couche des gouvernorats et vérifie leur nombre."""
    path = boundaries_dir / config.layer
    if not path.exists():
        raise FileNotFoundError(
            f"{path} introuvable : lancer d'abord `uv run python -m tdm.boundaries`."
        )
    governorates = gpd.read_file(path)
    if len(governorates) != config.expected_governorates:
        raise ValueError(
            f"{len(governorates)} gouvernorats trouvés, {config.expected_governorates} attendus."
        )
    return governorates


def select_pilot_zones(governorates: gpd.GeoDataFrame, config: ZonesConfig) -> gpd.GeoDataFrame:
    """Extrait les zones pilotes, une ligne par zone, dans l'ordre du fichier de config."""
    wanted = {zone.pcode: zone for zone in config.zones}
    selected = governorates[governorates[config.id_column].isin(wanted)].copy()
    missing = set(wanted) - set(selected[config.id_column])
    if missing:
        raise ValueError(f"Gouvernorats introuvables dans les frontières : {sorted(missing)}")
    selected["zone_id"] = selected[config.id_column].map(lambda code: wanted[code].id)
    selected["role"] = selected[config.id_column].map(lambda code: wanted[code].role)
    ordered = selected.set_index("zone_id").loc[[zone.id for zone in config.zones]].reset_index()
    return ordered[["zone_id", config.id_column, config.name_column, "role", "geometry"]]


def main() -> None:
    """Affiche un résumé des zones pilotes (contrôle visuel)."""
    config = load_config()
    zones = select_pilot_zones(load_governorates(config), config)
    print(f"{len(zones)} zones pilotes (CRS : {zones.crs})")
    for _, row in zones.iterrows():
        bounds = tuple(round(value, 3) for value in row["geometry"].bounds)
        zone_id, name, role = row["zone_id"], row[config.name_column], row["role"]
        print(f"  {zone_id:<9} {name:<9} {role:<18} {bounds}")


if __name__ == "__main__":
    main()
