"""Téléchargement des limites administratives de la Tunisie.

Source : OCHA / HDX, « Tunisia - Subnational Administrative Boundaries » (COD-AB),
licence CC BY-IGO (citer la source).
"""

import hashlib
import time
import urllib.request
import zipfile
from pathlib import Path

BOUNDARIES_URL = (
    "https://data.humdata.org/dataset/e47eda48-8f83-4858-b739-dbffb8a50c47"
    "/resource/d70d07db-a11c-4b83-9ae6-2f301a06fdd4/download/tun_admin_boundaries.shp.zip"
)
DEFAULT_DIR = Path("data/raw/boundaries")
ARCHIVE_NAME = "tun_admin_boundaries.shp.zip"
USER_AGENT = "Mozilla/5.0 (compatible; tunisia-drought-monitoring/0.1)"


def _is_valid_zip(path: Path) -> bool:
    """Vrai si `path` est une archive zip lisible et sans fichier corrompu."""
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as archive:
        return archive.testzip() is None


def _fetch(url: str, target: Path, attempts: int = 3) -> None:
    """Télécharge `url` vers `target` en affichant la progression, avec quelques tentatives."""
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                with target.open("wb") as out:
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        out.write(chunk)
                        total += len(chunk)
                        print(f"\r  {total / 1e6:.1f} Mo reçus", end="", flush=True)
            print()
            return
        except OSError as error:
            print(f"\nTentative {attempt}/{attempts} échouée : {error}")
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)


def download_boundaries(dest_dir: Path = DEFAULT_DIR, url: str = BOUNDARIES_URL) -> Path:
    """Télécharge, valide puis extrait l'archive des frontières ; renvoie le dossier extrait."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / ARCHIVE_NAME

    if zip_path.exists() and not _is_valid_zip(zip_path):
        print("Archive existante invalide : suppression et nouveau téléchargement.")
        zip_path.unlink()

    if not zip_path.exists():
        part_path = zip_path.with_name(ARCHIVE_NAME + ".part")
        _fetch(url, part_path)
        if not _is_valid_zip(part_path):
            part_path.unlink()
            raise RuntimeError("Archive téléchargée invalide (téléchargement incomplet ?).")
        part_path.replace(zip_path)

    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"Archive : {zip_path} ({zip_path.stat().st_size / 1e6:.1f} Mo)")
    print(f"SHA-256 : {sha256}")

    extract_dir = dest_dir / "extracted"
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)
    return extract_dir


def main() -> None:
    """Télécharge les frontières et liste les shapefiles extraits."""
    extract_dir = download_boundaries()
    print(f"Fichiers extraits dans : {extract_dir}")
    for shp in sorted(extract_dir.rglob("*.shp")):
        print(f"  {shp.relative_to(extract_dir)}")


if __name__ == "__main__":
    main()
