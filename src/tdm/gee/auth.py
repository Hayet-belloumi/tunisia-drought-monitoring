"""Initialisation de l'API Google Earth Engine."""

import os

import ee

ENV_VAR = "TDM_EE_PROJECT"


def init_ee(project: str | None = None) -> str:
    """Initialise Earth Engine et renvoie l'identifiant du projet utilisé.

    Le projet vient de l'argument, sinon de la variable d'environnement TDM_EE_PROJECT.
    """
    project_id = project or os.environ.get(ENV_VAR)
    if not project_id:
        raise RuntimeError(
            "Identifiant de projet Earth Engine manquant : "
            f"définir la variable d'environnement {ENV_VAR}."
        )
    ee.Initialize(project=project_id)
    return project_id


def main() -> None:
    """Test de connexion : un calcul trivial exécuté côté serveur Earth Engine."""
    project_id = init_ee()
    result = ee.Number(1).add(1).getInfo()
    print(f"Connexion Earth Engine OK (projet {project_id}) : 1 + 1 = {result}")


if __name__ == "__main__":
    main()
