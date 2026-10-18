import pytest

from tdm.gee.auth import ENV_VAR, init_ee


def test_init_ee_sans_projet_leve_une_erreur(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match=ENV_VAR):
        init_ee()
