from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from tourneo.analysis import JOURS, _calcul_pandas, _calcul_spark, _normaliser

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


def test_jours_convention():
    # Ordre normalisé ISO : du lundi au dimanche
    assert JOURS == ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]


def test_calcul_pandas_day_mapping(tmp_path):
    # Jeu de données synthétique pour tester l'assignation des jours
    clients = pd.DataFrame(
        {
            "id_client": [1],
            "nom": ["Test Client"],
            "quartier": ["tokoin"],
            "lat": [6.155],
            "lon": [1.225],
            "type_client": ["boutique"],
        }
    )
    # Le 2026-11-09 est un lundi, le 2026-11-15 est un dimanche
    cmd = pd.DataFrame(
        {
            "id_commande": [1, 2],
            "id_client": [1, 1],
            "date_commande": pd.to_datetime(["2026-11-08 10:00:00", "2026-11-14 10:00:00"]),
            "date_livraison": pd.to_datetime(["2026-11-09", "2026-11-15"]),
            "quantite_kg": [10.0, 20.0],
            "creneau_debut": pd.to_datetime(["2026-11-09 08:00:00", "2026-11-15 08:00:00"]),
            "creneau_fin": pd.to_datetime(["2026-11-09 10:00:00", "2026-11-15 10:00:00"]),
            "urgente": [0, 1],
            "mois": ["2026-11", "2026-11"],
        }
    )
    clients.to_parquet(tmp_path / "clients.parquet", index=False)
    cmd.to_parquet(tmp_path / "commandes", partition_cols=["mois"], index=False)

    res = _calcul_pandas(tmp_path)
    demande_jour = res["demande_jour"].set_index("jour")
    # Le lundi et le dimanche doivent comptabiliser une commande chacun
    assert demande_jour.loc["lun", "nb"] == 1
    assert demande_jour.loc["dim", "nb"] == 1
    assert demande_jour.loc["mar", "nb"] == 0

    # La matrice de chaleur doit utiliser les libellés textuels des jours
    heatmap = res["heatmap_jour_heure"]
    assert set(heatmap["jour"].unique()) <= set(JOURS)


def test_spark_pandas_parity():
    try:
        spark_raw = _calcul_spark(SAMPLE_DIR)
        spark_res = _normaliser(spark_raw)
    except Exception as exc:
        pytest.skip(f"PySpark indisponible dans l'environnement de test : {exc}")

    pandas_res = _calcul_pandas(SAMPLE_DIR)

    # Les deux moteurs doivent retourner les noms textuels des jours
    assert set(spark_res["heatmap_jour_heure"]["jour"].unique()) <= set(JOURS)
    assert set(pandas_res["heatmap_jour_heure"]["jour"].unique()) <= set(JOURS)

    # Parité stricte du volume par quartier (commandes et tonnage)
    vq_spark = spark_res["volume_quartier"].sort_values("quartier").reset_index(drop=True)
    vq_pandas = pandas_res["volume_quartier"].sort_values("quartier").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        vq_spark[["quartier", "nb_commandes"]],
        vq_pandas[["quartier", "nb_commandes"]],
    )
    pd.testing.assert_series_equal(
        vq_spark["kg"].round(1),
        vq_pandas["kg"].round(1),
    )

    # Parité stricte de la demande journalière
    dj_spark = spark_res["demande_jour"].sort_values("jour").reset_index(drop=True)
    dj_pandas = pandas_res["demande_jour"].sort_values("jour").reset_index(drop=True)
    pd.testing.assert_frame_equal(dj_spark, dj_pandas)

    # Parité stricte de la distribution horaire sur 24 heures
    dh_spark = spark_res["demande_heure"].sort_values("heure").reset_index(drop=True)
    dh_pandas = pandas_res["demande_heure"].sort_values("heure").reset_index(drop=True)
    pd.testing.assert_frame_equal(dh_spark, dh_pandas)

    # Parité stricte de l'évolution mensuelle
    em_spark = spark_res["evolution_mois"].sort_values("mois").reset_index(drop=True)
    em_pandas = pandas_res["evolution_mois"].sort_values("mois").reset_index(drop=True)
    pd.testing.assert_series_equal(em_spark["nb_commandes"], em_pandas["nb_commandes"])
    pd.testing.assert_series_equal(em_spark["kg"].round(1), em_pandas["kg"].round(1))

