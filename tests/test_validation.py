from __future__ import annotations

import shutil
from pathlib import Path
import pandas as pd
import pytest

from tourneo.validate import valider

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_DIR = DATA_DIR / "sample"


def test_valider_sample_clean():
    # L'échantillon versionné doit passer la validation sans anomalie
    assert valider(SAMPLE_DIR) == 0


def test_valider_full_clean():
    # Si le jeu de données complet est présent, il doit également être valide
    if (DATA_DIR / "clients.parquet").exists():
        assert valider(DATA_DIR) == 0


def test_valider_detects_invalid_type_client(tmp_path):
    # Copie de l'échantillon dans un répertoire isolé
    for f in ["clients.parquet", "vehicules.csv", "depot.csv"]:
        shutil.copy(SAMPLE_DIR / f, tmp_path / f)
    shutil.copytree(SAMPLE_DIR / "commandes", tmp_path / "commandes")

    # Altération d'un type de client pour tester la détection
    df = pd.read_parquet(tmp_path / "clients.parquet")
    df.loc[0, "type_client"] = "particulier_inconnu"
    df.to_parquet(tmp_path / "clients.parquet", index=False)

    n_errors = valider(tmp_path)
    assert n_errors > 0


def test_valider_detects_negative_quantite(tmp_path):
    for f in ["clients.parquet", "vehicules.csv", "depot.csv"]:
        shutil.copy(SAMPLE_DIR / f, tmp_path / f)
    shutil.copytree(SAMPLE_DIR / "commandes", tmp_path / "commandes")

    # Altération d'une charge pour vérifier le rejet de quantite_kg <= 0
    part = next((tmp_path / "commandes").glob("**/*.parquet"))
    df = pd.read_parquet(part)
    df.loc[0, "quantite_kg"] = -10.0
    df.to_parquet(part, index=False)

    n_errors = valider(tmp_path)
    assert n_errors > 0

