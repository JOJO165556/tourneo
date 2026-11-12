"""Visualisation interactive des indicateurs de tournée avec Plotly.

Chaque fonction charge un indicateur précalculé depuis data/indicateurs/*.parquet
et retourne un objet Figure prêt pour intégration dans un tableau de bord web
ou une exportation HTML statique.

Usage :
    python -m tourneo.dashboard   # Génère les prévisualisations HTML sous data/indicateurs/html/
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Final

import pandas as pd
import plotly.graph_objects as go

from tourneo.referentiel import BBOX_LATITUDE

DOSSIER_RACINE: Final[Path] = Path(__file__).resolve().parents[2]
DOSSIER_DONNEES_DEFAUT: Final[Path] = DOSSIER_RACINE / "data"
JOURS_SEMAINE_ISO: Final[list[str]] = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]

# Alias de compatibilité
DATA_DIR = DOSSIER_DONNEES_DEFAUT
JOURS = JOURS_SEMAINE_ISO


def _charger_indicateur(nom_indicateur: str, dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> pd.DataFrame:
    """Charge un tableau d'indicateur précalculé depuis son fichier Parquet."""
    return pd.read_parquet(dossier_donnees / "indicateurs" / f"{nom_indicateur}.parquet")


def generer_figure_volume_quartier(dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> go.Figure:
    """Diagramme à barres comparant le nombre de commandes et la masse (kg) par quartier."""
    donnees = _charger_indicateur("volume_quartier", dossier_donnees).sort_values("nb_commandes", ascending=False)
    figure = go.Figure()
    figure.add_bar(x=donnees["quartier"], y=donnees["nb_commandes"], name="Commandes")
    figure.add_bar(x=donnees["quartier"], y=donnees["kg"], name="Masse (kg)", yaxis="y2")
    figure.update_layout(
        title="Volume et masse des commandes par quartier à Lomé",
        xaxis_title="Quartier",
        yaxis_title="Nombre de commandes",
        yaxis2=dict(title="Masse cumulée (kg)", overlaying="y", side="right"),
        barmode="group",
    )
    return figure


def generer_figure_demande_jour(dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> go.Figure:
    """Histogramme de la répartition des commandes selon les jours de la semaine (ISO)."""
    donnees = _charger_indicateur("demande_jour", dossier_donnees)
    donnees = (
        donnees.set_index("jour")
        .reindex(JOURS_SEMAINE_ISO, fill_value=0)
        .reset_index()
    )

    figure = go.Figure(go.Bar(x=donnees["jour"], y=donnees["nb"], marker_color="#1f77b4"))
    figure.update_layout(
        title="Distribution hebdomadaire de la demande",
        xaxis_title="Jour de livraison",
        yaxis_title="Nombre de commandes",
    )
    return figure


def generer_figure_demande_heure(dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> go.Figure:
    """Histogramme de la demande par tranche horaire de début de créneau."""
    donnees = _charger_indicateur("demande_heure", dossier_donnees).sort_values("heure")
    labels_heures = [f"{int(h)}h" for h in donnees["heure"]]

    figure = go.Figure(go.Bar(x=labels_heures, y=donnees["nb"], marker_color="#2ca02c"))
    figure.update_layout(
        title="Distribution horaire des débuts de créneau de livraison",
        xaxis_title="Heure de début",
        yaxis_title="Nombre de commandes",
    )
    return figure


def generer_figure_evolution_mois(dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> go.Figure:
    """Courbe d'évolution chronologique mensuelle du nombre de commandes et du tonnage."""
    donnees = _charger_indicateur("evolution_mois", dossier_donnees).sort_values("mois")
    figure = go.Figure()
    figure.add_scatter(x=donnees["mois"], y=donnees["nb_commandes"], name="Commandes", mode="lines+markers")
    figure.add_scatter(x=donnees["mois"], y=donnees["kg"], name="Masse (kg)", mode="lines+markers", yaxis="y2")
    figure.update_layout(
        title="Évolution mensuelle de la demande logistique",
        xaxis_title="Mois",
        yaxis_title="Nombre de commandes",
        yaxis2=dict(title="Masse (kg)", overlaying="y", side="right"),
    )
    return figure


def generer_figure_heatmap_jour_heure(dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> go.Figure:
    """Carte de chaleur spatio-temporelle croisant le jour de semaine et l'heure."""
    donnees = _charger_indicateur("heatmap_jour_heure", dossier_donnees).copy()
    if pd.api.types.is_numeric_dtype(donnees["jour"]):
        donnees["jour"] = donnees["jour"].map(
            lambda i: JOURS_SEMAINE_ISO[int(i)] if 0 <= int(i) < len(JOURS_SEMAINE_ISO) else str(i)
        )

    matrice = donnees.pivot_table(index="jour", columns="heure", values="nb", aggfunc="sum", fill_value=0)
    matrice = matrice.reindex(JOURS_SEMAINE_ISO, fill_value=0)

    figure = go.Figure(
        go.Heatmap(
            z=matrice.to_numpy(),
            x=[f"{int(col)}h" for col in matrice.columns],
            y=matrice.index.tolist(),
            colorscale="Blues",
        )
    )
    figure.update_layout(
        title="Matrice de densité de livraison (Jour x Heure)",
        xaxis_title="Créneau horaire",
        yaxis_title="Jour de la semaine",
    )
    return figure


def generer_figure_top_clients(
    dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT, nombre_clients: int = 20
) -> go.Figure:
    """Classement des points de vente enregistrant le plus fort volume d'activité."""
    donnees = _charger_indicateur("top_clients", dossier_donnees).head(nombre_clients)
    libelles = donnees["nom"].astype(str) if "nom" in donnees.columns else "Client " + donnees["id_client"].astype(str)

    figure = go.Figure(go.Bar(x=libelles, y=donnees["nb_commandes"], marker_color="#ff7f0e"))
    figure.update_layout(
        title=f"Top {nombre_clients} des points de vente les plus actifs",
        xaxis_title="Point de vente",
        yaxis_title="Nombre de commandes",
    )
    return figure


def generer_figure_taux_urgent_quartier(dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> go.Figure:
    """Diagramme à barres du pourcentage de livraisons urgentes par quartier."""
    donnees = _charger_indicateur("urgent_quartier", dossier_donnees).sort_values("taux_urgent", ascending=False)
    figure = go.Figure(go.Bar(x=donnees["quartier"], y=donnees["taux_urgent"] * 100, marker_color="#d62728"))
    figure.update_layout(
        title="Part des commandes urgentes par quartier (%)",
        xaxis_title="Quartier",
        yaxis_title="% de commandes urgentes",
    )
    return figure


# Alias pour rétro-compatibilité avec les scripts et modules appelants
fig_volume_quartier = generer_figure_volume_quartier
fig_demande_jour = generer_figure_demande_jour
fig_demande_heure = generer_figure_demande_heure
fig_evolution_mois = generer_figure_evolution_mois
fig_heatmap_jour_heure = generer_figure_heatmap_jour_heure
fig_top_clients = generer_figure_top_clients
fig_taux_urgent_quartier = generer_figure_taux_urgent_quartier

CATALOGUE_FIGURES: Final[dict[str, Callable[[Path], go.Figure]]] = {
    "volume_quartier": generer_figure_volume_quartier,
    "demande_jour": generer_figure_demande_jour,
    "demande_heure": generer_figure_demande_heure,
    "evolution_mois": generer_figure_evolution_mois,
    "heatmap_jour_heure": generer_figure_heatmap_jour_heure,
    "top_clients": generer_figure_top_clients,
    "taux_urgent_quartier": generer_figure_taux_urgent_quartier,
}

# Alias pour compatibilité
TOUTES_LES_FIGURES = CATALOGUE_FIGURES


def main() -> int:
    """Génère les aperçus HTML statiques sous data/indicateurs/html/."""
    dossier_export = DOSSIER_DONNEES_DEFAUT / "indicateurs" / "html"
    dossier_export.mkdir(parents=True, exist_ok=True)

    for nom, constructeur_figure in CATALOGUE_FIGURES.items():
        figure = constructeur_figure(DOSSIER_DONNEES_DEFAUT)
        fichier_cible = dossier_export / f"{nom}.html"
        figure.write_html(str(fichier_cible))
        print(f"Graphique exporté : {fichier_cible.name}")

    return 0


if __name__ == "__main__":
    main()
