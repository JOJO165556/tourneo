from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

from tourneo.analysis import JOURS, calculer_indicateurs_pandas, sauvegarder_indicateurs
from tourneo.dashboard import CATALOGUE_FIGURES, generer_figure_heatmap_jour_heure


@pytest.fixture()
def dossier_indicateurs(tmp_path: Path) -> Path:
    """Jeu minimal hermétique : clients + commandes -> indicateurs."""
    clients = pd.DataFrame(
        {
            "id_client": [1, 2],
            "nom": ["Client Test A", "Client Test B"],
            "quartier": ["tokoin", "be"],
            "lat": [6.155, 6.138],
            "lon": [1.222, 1.236],
            "type_client": ["boutique", "supermarche"],
        }
    )
    # 2026-11-09 est un lundi, 2026-11-15 un dimanche
    commandes = pd.DataFrame(
        {
            "id_commande": [1, 2, 3],
            "id_client": [1, 2, 1],
            "date_commande": pd.to_datetime(
                ["2026-11-08 10:00", "2026-11-10 09:00", "2026-11-14 11:00"]
            ),
            "date_livraison": pd.to_datetime(["2026-11-09", "2026-11-10", "2026-11-15"]),
            "quantite_kg": [10.0, 25.0, 15.0],
            "creneau_debut": pd.to_datetime(
                ["2026-11-09 08:00", "2026-11-10 13:00", "2026-11-15 09:00"]
            ),
            "creneau_fin": pd.to_datetime(
                ["2026-11-09 10:00", "2026-11-10 15:00", "2026-11-15 11:00"]
            ),
            "urgente": [0, 1, 0],
            "mois": ["2026-11", "2026-11", "2026-11"],
        }
    )
    clients.to_parquet(tmp_path / "clients.parquet", index=False)
    commandes.to_parquet(tmp_path / "commandes", partition_cols=["mois"], index=False)

    indicateurs = calculer_indicateurs_pandas(tmp_path)
    sortie = tmp_path / "indicateurs"
    sauvegarder_indicateurs(indicateurs, sortie)
    return tmp_path


def test_all_figures_callable(dossier_indicateurs: Path):
    for nom, fn in CATALOGUE_FIGURES.items():
        fig = fn(dossier_indicateurs)
        assert isinstance(fig, go.Figure), nom


def test_fig_heatmap_y_axis_labels(dossier_indicateurs: Path):
    fig = generer_figure_heatmap_jour_heure(dossier_indicateurs)
    y_labels = fig.data[0].y
    assert len(y_labels) == len(JOURS)
    for label in y_labels:
        assert isinstance(label, str), f"L'etiquette d'axe Y '{label}' doit etre du texte"
        assert label in JOURS, f"L'etiquette d'axe Y '{label}' n'est pas dans {JOURS}"


def test_fig_demande_jour_affiche_jours_vides(dossier_indicateurs: Path):
    fig = CATALOGUE_FIGURES["demande_jour"](dossier_indicateurs)
    # Les 7 jours ISO doivent apparaître même à zéro
    assert len(fig.data[0].x) == len(JOURS)
