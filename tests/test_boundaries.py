import io
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from tdm import boundaries


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("tun_admin2.shp", b"fake")
    return buffer.getvalue()


def _fake_fetch(content: bytes, calls: list[str]) -> Callable[..., None]:
    def fake(url: str, target: Path, attempts: int = 3) -> None:
        calls.append(url)
        target.write_bytes(content)

    return fake


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._buffer = io.BytesIO(payload)

    def read(self, size: int) -> bytes:
        return self._buffer.read(size)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_is_valid_zip_accepts_real_archive(tmp_path: Path) -> None:
    path = tmp_path / "a.zip"
    path.write_bytes(_zip_bytes())
    assert boundaries._is_valid_zip(path)


def test_is_valid_zip_rejects_text_file(tmp_path: Path) -> None:
    path = tmp_path / "a.zip"
    path.write_text("pas un zip")
    assert not boundaries._is_valid_zip(path)


def test_is_valid_zip_rejects_truncated_archive(tmp_path: Path) -> None:
    data = _zip_bytes()
    path = tmp_path / "a.zip"
    path.write_bytes(data[: len(data) // 2])
    assert not boundaries._is_valid_zip(path)


def test_fetch_retries_then_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"n": 0}
    sleeps: list[float] = []

    def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("réseau coupé")
        return _FakeResponse(b"contenu")

    monkeypatch.setattr(boundaries.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(boundaries.time, "sleep", sleeps.append)
    target = tmp_path / "out.bin"
    boundaries._fetch("http://exemple.test", target)
    assert target.read_bytes() == b"contenu"
    assert attempts["n"] == 3
    assert sleeps == [5, 10]


def test_fetch_raises_after_last_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    def always_fail(request: object, timeout: int) -> _FakeResponse:
        raise OSError("hors ligne")

    monkeypatch.setattr(boundaries.urllib.request, "urlopen", always_fail)
    monkeypatch.setattr(boundaries.time, "sleep", sleeps.append)
    with pytest.raises(OSError, match="hors ligne"):
        boundaries._fetch("http://exemple.test", tmp_path / "out.bin", attempts=2)
    assert sleeps == [5]


def test_download_extracts_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(boundaries, "_fetch", _fake_fetch(_zip_bytes(), calls))
    extract_dir = boundaries.download_boundaries(tmp_path, url="http://exemple.test/x.zip")
    assert extract_dir == tmp_path / "extracted"
    assert (extract_dir / "tun_admin2.shp").read_bytes() == b"fake"
    assert calls == ["http://exemple.test/x.zip"]


def test_invalid_download_raises_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(boundaries, "_fetch", _fake_fetch(b"pas un zip", calls))
    with pytest.raises(RuntimeError, match="invalide"):
        boundaries.download_boundaries(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_corrupt_existing_archive_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / boundaries.ARCHIVE_NAME).write_bytes(b"corrompu")
    calls: list[str] = []
    monkeypatch.setattr(boundaries, "_fetch", _fake_fetch(_zip_bytes(), calls))
    extract_dir = boundaries.download_boundaries(tmp_path)
    assert len(calls) == 1
    assert (extract_dir / "tun_admin2.shp").exists()


def test_valid_existing_archive_is_not_downloaded_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / boundaries.ARCHIVE_NAME).write_bytes(_zip_bytes())
    calls: list[str] = []
    monkeypatch.setattr(boundaries, "_fetch", _fake_fetch(b"inutile", calls))
    extract_dir = boundaries.download_boundaries(tmp_path)
    assert calls == []
    assert (extract_dir / "tun_admin2.shp").exists()


def test_main_lists_extracted_shapefiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "sous").mkdir()
    (tmp_path / "sous" / "tun_admin2.shp").write_bytes(b"x")
    monkeypatch.setattr(boundaries, "download_boundaries", lambda: tmp_path)
    boundaries.main()
    assert "tun_admin2.shp" in capsys.readouterr().out
