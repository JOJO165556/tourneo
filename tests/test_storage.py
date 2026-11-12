from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from tourneo.storage import commandes_par_date, load_clients, load_commandes

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


def test_load_sample_clients():
    df = load_clients(SAMPLE_DIR)
    assert not df.empty
    assert "id_client" in df.columns
    assert "type_client" in df.columns


def test_load_sample_commandes():
    df = load_commandes(SAMPLE_DIR)
    assert not df.empty
    assert "id_commande" in df.columns
    assert "mois" in df.columns


def test_commandes_par_date_security_and_filter():
    # Test avec une date valide
    cmd = load_commandes(SAMPLE_DIR)
    target_date = str(cmd["date_livraison"].iloc[0])[:10]

    res = commandes_par_date(target_date, data_dir=SAMPLE_DIR)
    assert isinstance(res, pd.DataFrame)
    assert not res.empty
    assert (pd.to_datetime(res["date_livraison"]).dt.strftime("%Y-%m-%d") == target_date).all()

    # Test d'injection SQL : des guillemets ne doivent ni casser ni injecter du code
    malicious_date = f"'{target_date}' OR 1=1 --"
    # Avec une requête paramétrée DuckDB retourne 0 ligne sans erreur de syntaxe
    res_malicious = commandes_par_date(malicious_date, data_dir=SAMPLE_DIR)
    assert isinstance(res_malicious, pd.DataFrame)
    assert len(res_malicious) == 0

