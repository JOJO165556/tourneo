from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(scope="session", autouse=True)
def assurer_sample_disponible() -> None:
    """Garantit que le dossier data/sample/ existe pour les tests."""
    sample_dir = ROOT_DIR / "data" / "sample"
    clients_file = sample_dir / "clients.parquet"
    commandes_dir = sample_dir / "commandes"

    if not (clients_file.exists() and commandes_dir.exists()):
        from tourneo.generate import PARAMETRES_SAMPLE, generer_et_sauvegarder

        generer_et_sauvegarder(PARAMETRES_SAMPLE)
