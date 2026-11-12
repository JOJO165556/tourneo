"""Accès aux données et exécution de requêtes analytiques avec DuckDB.

Ce module exploite DuckDB en mode embarqué pour interroger le stockage
colonnaire Parquet avec partitionnement Hive ('mois=AAAA-MM'). Il fournit
la fonction de filtrage par date pour la planification des tournées.

Usage :
    python -m tourneo.storage            # Teste la lecture et une requête de démonstration
    python -m tourneo.storage --bench    # Exécute le banc d'essai comparatif CSV vs Parquet
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Final

import duckdb
import pandas as pd

DOSSIER_RACINE: Final[Path] = Path(__file__).resolve().parents[2]
DOSSIER_DONNEES_DEFAUT: Final[Path] = DOSSIER_RACINE / "data"


def creer_connexion() -> duckdb.DuckDBPyConnection:
    """Instancie une connexion DuckDB en mémoire."""
    return duckdb.connect()


def charger_clients(
    dossier_donnees: Path | None = None, data_dir: Path | None = None
) -> pd.DataFrame:
    """Charge l'intégralité du fichier clients.parquet en mémoire."""
    dossier = dossier_donnees or data_dir or DOSSIER_DONNEES_DEFAUT
    return pd.read_parquet(dossier / "clients.parquet")


def charger_commandes(
    dossier_donnees: Path | None = None,
    data_dir: Path | None = None,
    mois: str | None = None,
) -> pd.DataFrame:
    """Charge les partitions mensuelles du dossier commandes.

    `mois` ('AAAA-MM') active le partition pruning : seule la partition
    demandée est lue, sans scan des autres mois.
    """
    dossier = dossier_donnees or data_dir or DOSSIER_DONNEES_DEFAUT
    filtres = [("mois", "==", mois)] if mois else None
    return pd.read_parquet(dossier / "commandes", filters=filtres)


def obtenir_commandes_par_date(
    date_livraison_iso: str,
    dossier_donnees: Path | None = None,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Retourne les commandes pour une date de livraison donnée (format YYYY-MM-DD).

    La requête utilise le filtrage partitionné de DuckDB pour éviter le scan
    complet des données.
    """
    dossier = dossier_donnees or data_dir or DOSSIER_DONNEES_DEFAUT
    motif_fichiers = str(dossier / "commandes" / "*" / "*.parquet")
    requete_sql = """
        SELECT *
        FROM read_parquet(?, hive_partitioning = true)
        WHERE CAST(date_livraison AS DATE) = TRY_CAST(? AS DATE)
        ORDER BY id_commande
    """
    connexion = creer_connexion()
    try:
        return connexion.execute(
            requete_sql, [motif_fichiers, date_livraison_iso]
        ).df()
    finally:
        connexion.close()


def executer_banc_essai_performance(
    dossier_donnees: Path | None = None,
    nombre_repetitions: int = 5,
    data_dir: Path | None = None,
) -> Path:
    """Compare le temps d'exécution d'une même agrégation en CSV vs Parquet."""
    dossier = dossier_donnees or data_dir or DOSSIER_DONNEES_DEFAUT
    chemin_parquet = str(dossier / "commandes" / "*" / "*.parquet")
    connexion = creer_connexion()
    try:
        return _executer_banc_essai(
            connexion, dossier, chemin_parquet, nombre_repetitions
        )
    finally:
        connexion.close()


def _executer_banc_essai(
    connexion: duckdb.DuckDBPyConnection,
    dossier: Path,
    chemin_parquet: str,
    nombre_repetitions: int,
) -> Path:
    # Sélection de la date la plus dense en commandes
    date_cible = (
        connexion.execute(
            """
            SELECT CAST(date_livraison AS DATE) AS d
            FROM read_parquet(?, hive_partitioning = true)
            GROUP BY d
            ORDER BY count(*) DESC
            LIMIT 1
            """,
            [chemin_parquet],
        )
        .df()["d"]
        .iloc[0]
    )

    # Export CSV temporaire sans partitionnement pour la comparaison
    fichier_csv_temporaire = dossier / "_bench_commandes.csv"
    try:
        connexion.execute(
            """
            COPY (
                SELECT * FROM read_parquet(?, hive_partitioning = true)
            ) TO ? (HEADER, DELIMITER ',')
            """,
            [chemin_parquet, str(fichier_csv_temporaire)],
        )

        resultats: dict[str, float] = {}
        sources = [
            ("csv", str(fichier_csv_temporaire)),
            ("parquet", chemin_parquet),
        ]

        for etiquette, chemin_source in sources:
            connexion.execute(
                """
                SELECT count(*), sum(quantite_kg)
                FROM read_parquet(?, hive_partitioning = true)
                WHERE CAST(date_livraison AS DATE) = ?
                """ if etiquette == "parquet" else """
                SELECT count(*), sum(quantite_kg)
                FROM read_csv_auto(?)
                WHERE CAST(date_livraison AS DATE) = ?
                """,
                [chemin_source, date_cible],
            ).fetchone()

            chrono_debut = time.perf_counter()
            for _ in range(nombre_repetitions):
                connexion.execute(
                    """
                    SELECT count(*), sum(quantite_kg)
                    FROM read_parquet(?, hive_partitioning = true)
                    WHERE CAST(date_livraison AS DATE) = ?
                    """ if etiquette == "parquet" else """
                    SELECT count(*), sum(quantite_kg)
                    FROM read_csv_auto(?)
                    WHERE CAST(date_livraison AS DATE) = ?
                    """,
                    [chemin_source, date_cible],
                ).fetchone()
            resultats[etiquette] = (time.perf_counter() - chrono_debut) / nombre_repetitions
    finally:
        fichier_csv_temporaire.unlink(missing_ok=True)

    ratio = resultats["csv"] / resultats["parquet"] if resultats["parquet"] > 0 else 1.0
    lignes_rapport = [
        f"Requête : commandes du {date_cible} (count + somme quantite_kg)",
        f"Répétitions : {nombre_repetitions}",
        f"CSV    : {resultats['csv'] * 1000:.1f} ms",
        f"Parquet: {resultats['parquet'] * 1000:.1f} ms",
        f"Ratio CSV/Parquet : {ratio:.1f}x plus rapide",
    ]

    fichier_sortie = dossier / "bench_temps.txt"
    fichier_sortie.write_text("\n".join(lignes_rapport) + "\n", encoding="utf-8")
    print("\n".join(lignes_rapport))
    return fichier_sortie


# Alias de compatibilité
load_clients = charger_clients
load_commandes = charger_commandes
commandes_par_date = obtenir_commandes_par_date
benchmark = executer_banc_essai_performance


def main() -> int:
    """Point d'entrée CLI pour tourneo.storage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", action="store_true", help="Lance le benchmark CSV vs Parquet")
    parser.add_argument("--data", type=Path, default=DOSSIER_DONNEES_DEFAUT, help="Chemin des données")
    args = parser.parse_args()

    if args.bench:
        executer_banc_essai_performance(args.data)
        return 0

    clients = charger_clients(args.data)
    print(f"Clients chargés : {len(clients)} lignes")
    commandes = charger_commandes(args.data)
    print(
        f"Commandes chargées : {len(commandes)} lignes réparties sur "
        f"{commandes['mois'].nunique()} partitions mensuelles."
    )
    derniere_date = commandes["date_livraison"].max().strftime("%Y-%m-%d")
    extrait = obtenir_commandes_par_date(derniere_date, args.data)
    print(f"commandes_par_date('{derniere_date}') : {len(extrait)} lignes récupérées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
