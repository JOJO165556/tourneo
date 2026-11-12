"""Génération reproductible des données de transport et livraison de Lomé.

Ce module simule l'activité logistique du Grand Lomé pour alimenter le pipeline
d'analyse : points de vente, historique de commandes, flotte de véhicules
et dépôt central.

Usage :
    python -m tourneo.generate                                  # Volume standard (~200 000 commandes)
    python -m tourneo.generate --sample                         # Extrait réduit pour développement et CI
    python -m tourneo.generate --commandes 1000000 --clients 5000 # Montée en charge Big Data
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from tourneo.referentiel import (
    BBOX_LATITUDE,
    BBOX_LONGITUDE,
    CAPACITES_FLOTTE_KG,
    COUT_KM_BASE_FCFA,
    COUT_KM_PAR_KG_FCFA,
    CRENEAUX_LIVRAISON,
    DEPOT_CENTRAL,
    ENSEIGNES_LOCALES,
    PREFIXES_ENSEIGNES,
    QUARTIERS_LOME,
    TYPOLOGIE_CLIENTS,
)

GRAINE_ALEATOIRE_DEFAUT: int = 42
DOSSIER_RACINE: Path = Path(__file__).resolve().parents[2]
DOSSIER_DONNEES_DEFAUT: Path = DOSSIER_RACINE / "data"

# Multiplicateurs d'activité de commande selon le type de point de vente
FACTEUR_ACTIVITE_TYPE: dict[str, float] = {
    "boutique": 1.0,
    "supermarche": 1.6,
    "restaurant": 0.9,
    "grossiste": 2.2,
}


@dataclass(frozen=True)
class ParametresGeneration:
    """Paramètres dimensionnant la génération des données."""

    nombre_clients: int = 1500
    nombre_commandes: int = 200_000
    nombre_mois: int = 12
    plage_vehicules: tuple[int, int] = (6, 10)
    taux_urgentes: float = 0.05
    dossier_sortie: Path = DOSSIER_DONNEES_DEFAUT
    taille_lot: int = 100_000


PARAMETRES_SAMPLE: ParametresGeneration = ParametresGeneration(
    nombre_clients=20,
    nombre_commandes=30,
    nombre_mois=3,
    plage_vehicules=(3, 3),
    dossier_sortie=DOSSIER_DONNEES_DEFAUT / "sample",
    taille_lot=1_000,
)


def _obtenir_poids_quartiers() -> tuple[list[str], np.ndarray]:
    """Retourne la liste des quartiers et leurs poids normalisés."""
    noms_quartiers = list(QUARTIERS_LOME.keys())
    poids = np.array([QUARTIERS_LOME[q].poids for q in noms_quartiers], dtype=float)
    return noms_quartiers, poids / poids.sum()


def _choisir_types_clients(
    generateur: np.random.Generator, nombre_clients: int
) -> np.ndarray:
    """Tire les types de clients selon la distribution de référence."""
    types = list(TYPOLOGIE_CLIENTS.keys())
    parts = np.array([TYPOLOGIE_CLIENTS[t][0] for t in types], dtype=float)
    return generateur.choice(types, size=nombre_clients, p=parts / parts.sum())


def _generer_nom_etablissement(
    generateur: np.random.Generator, type_client: str, indice: int
) -> str:
    """Compose une enseigne réaliste pour un point de vente."""
    prefixe = generateur.choice(PREFIXES_ENSEIGNES[type_client])
    enseigne = generateur.choice(ENSEIGNES_LOCALES)
    return f"{prefixe} {enseigne} n°{indice}"


def generer_clients(
    generateur: np.random.Generator, nombre_clients: int
) -> pd.DataFrame:
    """Génère la base de clients localisés sur la terre ferme de Lomé."""
    noms_quartiers, poids_quartiers = _obtenir_poids_quartiers()
    indices_quartiers = generateur.choice(
        len(noms_quartiers), size=nombre_clients, p=poids_quartiers
    )
    types_attribues = _choisir_types_clients(generateur, nombre_clients)

    centres_coordonnees = np.array(
        [[QUARTIERS_LOME[noms_quartiers[i]].lat, QUARTIERS_LOME[noms_quartiers[i]].lon]
         for i in indices_quartiers]
    )

    # Dispersion spatiale locale (~200 à 600 mètres) bornée sur la terre ferme de Lomé
    ecart_type_dispersion = generateur.uniform(0.0020, 0.0055, size=(nombre_clients, 1))
    coordonnees = centres_coordonnees + generateur.normal(0.0, 1.0, size=(nombre_clients, 2)) * ecart_type_dispersion
    coordonnees[:, 0] = np.clip(coordonnees[:, 0], *BBOX_LATITUDE)
    coordonnees[:, 1] = np.clip(coordonnees[:, 1], *BBOX_LONGITUDE)

    poids_quartier = np.array([QUARTIERS_LOME[noms_quartiers[i]].poids for i in indices_quartiers])
    poids_type = np.array([FACTEUR_ACTIVITE_TYPE[t] for t in types_attribues])
    score_activite = poids_quartier * poids_type

    noms = [
        _generer_nom_etablissement(generateur, types_attribues[i], i + 1)
        for i in range(nombre_clients)
    ]

    return pd.DataFrame(
        {
            "id_client": np.arange(1, nombre_clients + 1, dtype=np.int64),
            "nom": noms,
            "quartier": [noms_quartiers[i] for i in indices_quartiers],
            "lat": coordonnees[:, 0].round(6),
            "lon": coordonnees[:, 1].round(6),
            "type_client": types_attribues,
            "_activite": score_activite,
        }
    )


def generer_flotte_vehicules(
    generateur: np.random.Generator, nombre_min: int, nombre_max: int
) -> pd.DataFrame:
    """Génère la flotte de distribution avec des coûts kilométriques proportionnés."""
    nombre_vehicules = int(generateur.integers(nombre_min, nombre_max + 1))
    capacites_choisies = generateur.choice(
        CAPACITES_FLOTTE_KG,
        size=nombre_vehicules,
        replace=nombre_vehicules > len(CAPACITES_FLOTTE_KG),
    )

    # Modèle économique de coût au km indexé sur la capacité du véhicule à Lomé
    couts_km = np.round(
        COUT_KM_BASE_FCFA
        + (COUT_KM_PAR_KG_FCFA * capacites_choisies)
        + generateur.uniform(-15.0, 15.0, size=nombre_vehicules),
        0,
    )
    disponibilites = (generateur.random(nombre_vehicules) < 0.85).astype(np.int64)

    return pd.DataFrame(
        {
            "id_vehicule": np.arange(1, nombre_vehicules + 1, dtype=np.int64),
            "nom": [f"vehicule_{i}" for i in range(1, nombre_vehicules + 1)],
            "capacite_kg": capacites_choisies.astype(float),
            "cout_km": couts_km.astype(float),
            "disponible": disponibilites,
        }
    )


def _calculer_poids_jours(
    date_debut: pd.Timestamp, date_fin: pd.Timestamp
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Calcule la saisonnalité hebdomadaire et mensuelle sur la période."""
    jours = pd.date_range(date_debut, date_fin, freq="D")
    poids_semaine = np.array([1.25, 1.20, 1.10, 1.00, 0.90, 0.65, 0.50])
    poids = poids_semaine[jours.day_of_week]

    # Effets de fin et début de mois
    poids = poids * np.where(jours.day >= 25, 1.55, 1.0)
    poids = poids * np.where(jours.day <= 3, 1.15, 1.0)
    return jours, poids / poids.sum()


def generer_lot_commandes(
    generateur: np.random.Generator,
    clients: pd.DataFrame,
    nombre_commandes_lot: int,
    offset_identifiant: int,
    jours: pd.DatetimeIndex,
    poids_jours: np.ndarray,
    capacite_maximale_kg: float,
    taux_urgentes: float,
    types_clients_par_id: pd.Series | None = None,
) -> pd.DataFrame:
    """Génère un sous-ensemble (lot) de commandes vectorisées pour le passage à l'échelle."""
    probabilites_clients = clients["_activite"].to_numpy(dtype=float, copy=True)
    somme_probabilites = probabilites_clients.sum()
    if somme_probabilites <= 0:
        raise ValueError(
            "Les scores d'activité de l'ensemble des clients sont nuls ou négatifs."
        )
    probabilites_clients = probabilites_clients / somme_probabilites

    identifiants_clients = generateur.choice(
        clients["id_client"].to_numpy(),
        size=nombre_commandes_lot,
        p=probabilites_clients,
    )

    indices_jours_livraison = generateur.choice(
        len(jours), size=nombre_commandes_lot, p=poids_jours
    )
    jours_livraison = jours[indices_jours_livraison]

    delais_jours = generateur.integers(1, 4, size=nombre_commandes_lot)
    minutes_commande = generateur.integers(6 * 60, 19 * 60, size=nombre_commandes_lot)
    dates_commande = jours_livraison - pd.to_timedelta(delais_jours, unit="D") + pd.to_timedelta(minutes_commande, unit="m")

    if types_clients_par_id is None:
        types_clients_par_id = clients.set_index("id_client")["type_client"]
    types_clients = types_clients_par_id.loc[identifiants_clients].to_numpy()
    moyennes_log = np.array([np.log(TYPOLOGIE_CLIENTS[t][1]) for t in types_clients])
    ecarts_log = np.array([TYPOLOGIE_CLIENTS[t][2] for t in types_clients])
    charges_kg = generateur.lognormal(moyennes_log, ecarts_log)
    charges_kg = np.clip(charges_kg, 5.0, capacite_maximale_kg * 0.90).round(1)

    poids_creneaux = np.array([c[2] for c in CRENEAUX_LIVRAISON], dtype=float)
    poids_creneaux /= poids_creneaux.sum()
    indices_creneaux = generateur.choice(
        len(CRENEAUX_LIVRAISON), size=nombre_commandes_lot, p=poids_creneaux
    )
    minutes_debut_fenetre = np.array([CRENEAUX_LIVRAISON[i][0] for i in indices_creneaux])
    minutes_fin_fenetre = np.array([CRENEAUX_LIVRAISON[i][1] for i in indices_creneaux])

    largeurs_fenetres = minutes_fin_fenetre - minutes_debut_fenetre
    decalages_debut = generateur.integers(0, largeurs_fenetres - 45, size=nombre_commandes_lot)
    durees_livraison = generateur.integers(45, 76, size=nombre_commandes_lot)

    debuts_minutes = minutes_debut_fenetre + decalages_debut
    fins_minutes = np.minimum(debuts_minutes + durees_livraison, minutes_fin_fenetre)

    creneaux_debut = jours_livraison + pd.to_timedelta(debuts_minutes, unit="m")
    creneaux_fin = jours_livraison + pd.to_timedelta(fins_minutes, unit="m")
    urgentes = (generateur.random(nombre_commandes_lot) < taux_urgentes).astype(np.int64)

    return pd.DataFrame(
        {
            "id_commande": np.arange(
                offset_identifiant + 1,
                offset_identifiant + nombre_commandes_lot + 1,
                dtype=np.int64,
            ),
            "id_client": identifiants_clients.astype(np.int64),
            "date_commande": dates_commande,
            "date_livraison": jours_livraison,
            "quantite_kg": charges_kg,
            "creneau_debut": creneaux_debut,
            "creneau_fin": creneaux_fin,
            "urgente": urgentes,
            "mois": jours_livraison.strftime("%Y-%m"),
        }
    )


def generer_et_sauvegarder(parametres: ParametresGeneration) -> None:
    """Point d'entrée principal : génère et sauvegarde les tables du contrat."""
    generateur = np.random.default_rng(GRAINE_ALEATOIRE_DEFAUT)
    dossier = parametres.dossier_sortie
    dossier.mkdir(parents=True, exist_ok=True)

    clients = generer_clients(generateur, parametres.nombre_clients)
    vehicules = generer_flotte_vehicules(generateur, *parametres.plage_vehicules)

    vehicules_disponibles = vehicules.loc[vehicules["disponible"] == 1, "capacite_kg"]
    capacite_maximale_kg = float(vehicules_disponibles.max()) if not vehicules_disponibles.empty else 1000.0

    # Écriture dans un répertoire temporaire puis bascule atomique :
    # un échec en cours de génération ne doit pas détruire les données existantes
    dossier_commandes = dossier / "commandes"
    dossier_temporaire = dossier / "commandes.tmp"
    if dossier_temporaire.exists():
        shutil.rmtree(dossier_temporaire)

    date_fin = pd.Timestamp.now().normalize().replace(day=1) - pd.Timedelta(days=1)
    date_debut = (date_fin - pd.DateOffset(months=parametres.nombre_mois - 1)).replace(day=1)
    jours, poids_jours = _calculer_poids_jours(date_debut, date_fin)

    commandes_restantes = parametres.nombre_commandes
    offset_courant = 0
    types_clients_par_id = clients.set_index("id_client")["type_client"]

    while commandes_restantes > 0:
        taille_courante = min(commandes_restantes, parametres.taille_lot)
        lot = generer_lot_commandes(
            generateur=generateur,
            clients=clients,
            nombre_commandes_lot=taille_courante,
            offset_identifiant=offset_courant,
            jours=jours,
            poids_jours=poids_jours,
            capacite_maximale_kg=capacite_maximale_kg,
            taux_urgentes=parametres.taux_urgentes,
            types_clients_par_id=types_clients_par_id,
        )
        table_lot = pa.Table.from_pandas(lot)
        pq.write_to_dataset(
            table_lot,
            root_path=str(dossier_temporaire),
            partition_cols=["mois"],
            use_dictionary=True,
            compression="snappy",
        )
        offset_courant += taille_courante
        commandes_restantes -= taille_courante

    if dossier_temporaire.exists():
        if dossier_commandes.exists():
            shutil.rmtree(dossier_commandes)
        dossier_temporaire.rename(dossier_commandes)

    clients.drop(columns=["_activite"]).to_parquet(
        dossier / "clients.parquet", index=False
    )
    vehicules.to_csv(dossier / "vehicules.csv", index=False)
    pd.DataFrame([DEPOT_CENTRAL]).to_csv(dossier / "depot.csv", index=False)

    print(
        f"Génération terminée ({dossier}) : {len(clients)} clients, "
        f"{parametres.nombre_commandes} commandes, {len(vehicules)} véhicules."
    )


def main() -> None:
    """Interprète la ligne de commande et déclenche la génération."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample", action="store_true", help="Génère l'extrait réduit dans data/sample/"
    )
    parser.add_argument(
        "--clients", type=int, default=1500, help="Nombre de clients (défaut : 1500)"
    )
    parser.add_argument(
        "--commandes", type=int, default=200_000, help="Nombre de commandes (défaut : 200 000)"
    )
    parser.add_argument(
        "--mois", type=int, default=12, help="Nombre de mois d'historique (défaut : 12)"
    )
    parser.add_argument(
        "--data", type=Path, default=None, help="Dossier de sortie personnalisé"
    )
    args = parser.parse_args()

    if args.sample:
        config = PARAMETRES_SAMPLE
    elif args.data:
        config = ParametresGeneration(
            nombre_clients=args.clients,
            nombre_commandes=args.commandes,
            nombre_mois=args.mois,
            dossier_sortie=args.data,
        )
    else:
        config = ParametresGeneration(
            nombre_clients=args.clients,
            nombre_commandes=args.commandes,
            nombre_mois=args.mois,
        )

    generer_et_sauvegarder(config)


if __name__ == "__main__":
    main()
