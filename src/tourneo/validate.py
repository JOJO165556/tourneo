"""Validation de la conformité des données au contrat de service.

Ce module contrôle l'intégrité structurelle, relationnelle et géographique
des tables de données générées selon les spécifications de docs/contrat.md.

Usage :
    python -m tourneo.validate            # Valide le jeu complet
    python -m tourneo.validate --sample   # Valide l'extrait réduit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

import pandas as pd

from tourneo.referentiel import (
    BBOX_LATITUDE,
    BBOX_LONGITUDE,
    QUARTIERS_LOME,
    TYPOLOGIE_CLIENTS,
)

DOSSIER_RACINE: Final[Path] = Path(__file__).resolve().parents[2]
DOSSIER_DONNEES_DEFAUT: Final[Path] = DOSSIER_RACINE / "data"

SCHEMA_CLIENTS: Final[dict[str, str]] = {
    "id_client": "int",
    "nom": "str",
    "quartier": "str",
    "lat": "float",
    "lon": "float",
    "type_client": "str",
}

SCHEMA_COMMANDES: Final[dict[str, str]] = {
    "id_commande": "int",
    "id_client": "int",
    "date_commande": "datetime",
    "date_livraison": "datetime",
    "quantite_kg": "float",
    "creneau_debut": "datetime",
    "creneau_fin": "datetime",
    "urgente": "int",
}

SCHEMA_VEHICULES: Final[dict[str, str]] = {
    "id_vehicule": "int",
    "nom": "str",
    "capacite_kg": "float",
    "cout_km": "float",
    "disponible": "int",
}

SCHEMA_DEPOT: Final[dict[str, str]] = {
    "id_depot": "int",
    "nom": "str",
    "lat": "float",
    "lon": "float",
}


def verifier_schema(
    dataframe: pd.DataFrame, schema_attendu: dict[str, str], nom_table: str
) -> list[str]:
    """Contrôle la présence des colonnes, l'absence de valeurs nulles et les types."""
    anomalies: list[str] = []

    for colonne, type_attendu in schema_attendu.items():
        if colonne not in dataframe.columns:
            anomalies.append(f"Table '{nom_table}' : colonne obligatoire '{colonne}' absente.")
            continue

        serie = dataframe[colonne]
        if serie.isna().any():
            anomalies.append(f"Table '{nom_table}', colonne '{colonne}' : valeurs manquantes détectées.")

        if type_attendu == "int" and not pd.api.types.is_integer_dtype(serie):
            anomalies.append(f"Table '{nom_table}', colonne '{colonne}' : type entier attendu, reçu {serie.dtype}.")
        elif type_attendu == "float" and not pd.api.types.is_float_dtype(serie):
            anomalies.append(f"Table '{nom_table}', colonne '{colonne}' : type décimal attendu, reçu {serie.dtype}.")
        elif type_attendu == "str" and not pd.api.types.is_string_dtype(serie):
            anomalies.append(f"Table '{nom_table}', colonne '{colonne}' : type texte attendu, reçu {serie.dtype}.")
        elif type_attendu == "datetime" and not pd.api.types.is_datetime64_any_dtype(serie):
            anomalies.append(f"Table '{nom_table}', colonne '{colonne}' : type datetime attendu, reçu {serie.dtype}.")

    return anomalies


def verifier_coordonnees_lome(
    latitudes: pd.Series, longitudes: pd.Series, nom_table: str
) -> list[str]:
    """Vérifie que les coordonnées WGS84 se situent strictement sur le Grand Lomé."""
    dans_bornes = (
        latitudes.between(*BBOX_LATITUDE).all()
        and longitudes.between(*BBOX_LONGITUDE).all()
    )
    if not dans_bornes:
        return [f"Table '{nom_table}' : coordonnées géographiques hors de l'emprise terrestre de Lomé."]
    return []


def valider(dossier_cible: Path) -> int:
    """Valide l'ensemble des fichiers sous dossier_cible. Retourne le nombre d'erreurs."""
    erreurs: list[str] = []

    # 1. Validation de la table clients
    chemin_clients = dossier_cible / "clients.parquet"
    if not chemin_clients.exists():
        erreurs.append(f"Fichier introuvable : {chemin_clients}")
        return len(erreurs)

    clients = pd.read_parquet(chemin_clients)
    erreurs.extend(verifier_schema(clients, SCHEMA_CLIENTS, "clients"))

    if clients["id_client"].duplicated().any():
        erreurs.append("Table 'clients' : les identifiants 'id_client' ne sont pas uniques.")

    types_autorises = set(TYPOLOGIE_CLIENTS.keys())
    types_invalides = set(clients["type_client"].unique()) - types_autorises
    if types_invalides:
        erreurs.append(f"Table 'clients' : types clients non autorisés détectés : {types_invalides}.")

    quartiers_connus = set(QUARTIERS_LOME.keys())
    quartiers_inconnus = set(clients["quartier"].unique()) - quartiers_connus
    if quartiers_inconnus:
        erreurs.append(f"Table 'clients' : quartiers inconnus détectés : {quartiers_inconnus}.")

    erreurs.extend(verifier_coordonnees_lome(clients["lat"], clients["lon"], "clients"))

    # 2. Validation de la table commandes
    chemin_commandes = dossier_cible / "commandes"
    if not chemin_commandes.exists():
        erreurs.append(f"Répertoire introuvable : {chemin_commandes}")
        return len(erreurs)

    commandes = pd.read_parquet(chemin_commandes)
    erreurs.extend(verifier_schema(commandes, SCHEMA_COMMANDES, "commandes"))

    if "id_commande" in commandes and commandes["id_commande"].duplicated().any():
        erreurs.append("Table 'commandes' : les identifiants 'id_commande' ne sont pas uniques.")

    clients_inconnus = set(commandes["id_client"].unique()) - set(clients["id_client"].unique())
    if clients_inconnus:
        erreurs.append(f"Table 'commandes' : {len(clients_inconnus)} client(s) inexistant(s) dans clients.parquet.")

    if "quantite_kg" in commandes and not (commandes["quantite_kg"] > 0).all():
        erreurs.append("Table 'commandes' : charges non strictement positives (quantite_kg <= 0).")

    if "urgente" in commandes and not set(commandes["urgente"].unique()) <= {0, 1}:
        erreurs.append("Table 'commandes' : la colonne 'urgente' contient des valeurs autres que 0 et 1.")

    if {"creneau_debut", "creneau_fin", "date_livraison"} <= set(commandes.columns):
        if not (commandes["creneau_fin"] > commandes["creneau_debut"]).all():
            erreurs.append("Table 'commandes' : creneau_fin n'est pas postérieur à creneau_debut.")

        journee_livraison = commandes["date_livraison"].dt.normalize()
        meme_journee = (
            commandes["creneau_debut"].dt.normalize() == journee_livraison
        ) & (
            commandes["creneau_fin"].dt.normalize() == journee_livraison
        )
        if not meme_journee.all():
            erreurs.append("Table 'commandes' : créneaux de livraison hors de la journée de date_livraison.")

    # 3. Validation de la flotte de véhicules
    chemin_vehicules = dossier_cible / "vehicules.csv"
    if not chemin_vehicules.exists():
        erreurs.append(f"Fichier introuvable : {chemin_vehicules}")
    else:
        vehicules = pd.read_csv(chemin_vehicules)
        erreurs.extend(verifier_schema(vehicules, SCHEMA_VEHICULES, "vehicules"))

        if "disponible" in vehicules and not set(vehicules["disponible"].unique()) <= {0, 1}:
            erreurs.append("Table 'vehicules' : colonne 'disponible' avec valeurs hors {0, 1}.")
        if "id_vehicule" in vehicules and vehicules["id_vehicule"].duplicated().any():
            erreurs.append("Table 'vehicules' : identifiants 'id_vehicule' dupliqués.")

        if "capacite_kg" in vehicules.columns and "disponible" in vehicules.columns:
            vehicules_actifs = vehicules.loc[vehicules["disponible"] == 1, "capacite_kg"]
            if vehicules_actifs.empty:
                erreurs.append("Table 'vehicules' : aucun véhicule disponible dans la flotte.")
            elif "quantite_kg" in commandes.columns:
                capacite_max = vehicules_actifs.max()
                commandes_excessives = int((commandes["quantite_kg"] > capacite_max).sum())
                if commandes_excessives > 0:
                    erreurs.append(
                        f"Table 'commandes' : {commandes_excessives} commande(s) dépassent la capacité "
                        f"du plus gros véhicule disponible ({capacite_max} kg)."
                    )

    # 4. Validation du dépôt central
    chemin_depot = dossier_cible / "depot.csv"
    if not chemin_depot.exists():
        erreurs.append(f"Fichier introuvable : {chemin_depot}")
    else:
        depot = pd.read_csv(chemin_depot)
        erreurs.extend(verifier_schema(depot, SCHEMA_DEPOT, "depot"))
        if {"lat", "lon"} <= set(depot.columns):
            erreurs.extend(verifier_coordonnees_lome(depot["lat"], depot["lon"], "depot"))

    if erreurs:
        for err in erreurs:
            print(f"ERREUR : {err}", file=sys.stderr)
        print(f"Total : {len(erreurs)} anomalie(s) détectée(s).", file=sys.stderr)
        return len(erreurs)

    print(f"SUCCÈS : Données sous '{dossier_cible}' 100% conformes au contrat.")
    return 0


def main() -> int:
    """Point d'entrée CLI pour la validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample", action="store_true", help="Valide l'extrait d'échantillon data/sample/"
    )
    parser.add_argument(
        "--data", type=Path, default=None, help="Dossier de données à valider"
    )
    args = parser.parse_args()
    if args.data:
        dossier_analyse = args.data
    elif args.sample:
        dossier_analyse = DOSSIER_DONNEES_DEFAUT / "sample"
    else:
        dossier_analyse = DOSSIER_DONNEES_DEFAUT

    return 1 if valider(dossier_analyse) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
