"""Calcul des indicateurs logistiques et spatio-temporels de la demande.

Ce module agrège l'historique volumineux de commandes pour produire les tables
synthétiques prêtes à être affichées par le tableau de bord sans recalcul.
Moteur par défaut : PySpark (traitement distribué local).
Moteur de repli : Pandas (en cas d'absence d'environnement Java/Spark).

Indicateurs produits sous data/indicateurs/*.parquet :
    - volume_quartier.parquet    : Volume total de commandes et tonnage par quartier
    - demande_jour.parquet       : Répartition hebdomadaire selon la norme ISO (lun-dim)
    - demande_heure.parquet      : Distribution horaire des livraisons (0h-23h)
    - evolution_mois.parquet     : Tendance mensuelle du nombre de commandes et du poids
    - top_clients.parquet        : 20 clients les plus actifs et leur typologie
    - urgent_quartier.parquet    : Taux de commandes urgentes par zone
    - heatmap_jour_heure.parquet : Matrice de densité jour x créneau horaire

Usage :
    python -m tourneo.analysis
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Final

import pandas as pd

DOSSIER_RACINE: Final[Path] = Path(__file__).resolve().parents[2]
DOSSIER_DONNEES_DEFAUT: Final[Path] = DOSSIER_RACINE / "data"
JOURS_SEMAINE_ISO: Final[list[str]] = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
HEURES_JOURNEE: Final[list[int]] = list(range(24))

# Alias pour compatibilité
DATA_DIR = DOSSIER_DONNEES_DEFAUT
JOURS = JOURS_SEMAINE_ISO
HEURES = HEURES_JOURNEE


def configurer_java_home_spark() -> None:
    """Configure l'environnement d'execution de PySpark (JAVA_HOME et interpreteur Python)."""
    # Garantit que les workers Spark utilisent le même interpréteur Python que le driver
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    if os.environ.get("JAVA_HOME"):
        return

    # Lecture prioritaire d'un fichier .env à la racine s'il existe
    fichier_env = DOSSIER_RACINE / ".env"
    if fichier_env.exists():
        for ligne in fichier_env.read_text(encoding="utf-8").splitlines():
            ligne_nettoyee = ligne.strip()
            if ligne_nettoyee and not ligne_nettoyee.startswith("#") and "=" in ligne_nettoyee:
                cle, valeur = ligne_nettoyee.split("=", 1)
                if cle.strip() == "JAVA_HOME":
                    chemin_declare = Path(valeur.strip().strip('"').strip("'"))
                    if chemin_declare.exists():
                        os.environ["JAVA_HOME"] = str(chemin_declare)
                        return

    motifs_versions = ("*21*", "*17*", "*25*")
    dossiers_racines: list[Path] = []

    if sys.platform == "win32":
        dossiers_racines = [
            Path("C:/Program Files/Eclipse Adoptium"),
            Path("C:/Program Files/Java"),
            Path("C:/Program Files/Microsoft"),
            Path("C:/Program Files/Amazon Corretto"),
        ]
    elif sys.platform == "darwin":
        dossiers_racines = [Path("/Library/Java/JavaVirtualMachines")]
    else:
        dossiers_racines = [Path("/usr/lib/jvm")]

    for racine in dossiers_racines:
        if racine.exists():
            for motif in motifs_versions:
                for chemin in sorted(racine.glob(motif)):
                    if chemin.is_dir():
                        os.environ["JAVA_HOME"] = str(chemin)
                        return

    # Repli sur le binaire java présent dans le PATH
    import shutil

    binaire = shutil.which("java")
    if binaire:
        chemin_resolu = Path(binaire).resolve()
        if chemin_resolu.parent.name == "bin":
            os.environ["JAVA_HOME"] = str(chemin_resolu.parent.parent)


def sauvegarder_indicateurs(
    indicateurs: dict[str, pd.DataFrame], dossier_sortie: Path
) -> None:
    """Enregistre chaque tableau d'indicateurs au format Parquet."""
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    for nom_indicateur, table in indicateurs.items():
        chemin_fichier = dossier_sortie / f"{nom_indicateur}.parquet"
        table.to_parquet(chemin_fichier, index=False)
        print(f"  {nom_indicateur}.parquet : {len(table)} lignes enregistrées.")


def calculer_indicateurs_pandas(dossier_donnees: Path) -> dict[str, pd.DataFrame]:
    """Calcule tous les indicateurs de demande avec Pandas."""
    clients = pd.read_parquet(dossier_donnees / "clients.parquet")
    commandes = pd.read_parquet(dossier_donnees / "commandes")

    donnees = commandes.merge(
        clients[["id_client", "quartier", "type_client"]],
        on="id_client",
        how="left",
    )
    donnees["jour"] = donnees["date_livraison"].dt.day_of_week
    donnees["heure"] = donnees["creneau_debut"].dt.hour
    donnees["mois"] = donnees["date_livraison"].dt.strftime("%Y-%m")

    volume_quartier = (
        donnees.groupby("quartier")
        .agg(nb_commandes=("id_commande", "count"), kg=("quantite_kg", "sum"))
        .reset_index()
    )

    demande_jour = (
        donnees.groupby("jour")
        .size()
        .reindex(range(7), fill_value=0)
        .rename("nb")
        .reset_index()
    )
    demande_jour["jour"] = demande_jour["jour"].map(lambda i: JOURS_SEMAINE_ISO[i])

    demande_heure = (
        donnees.groupby("heure")
        .size()
        .reindex(HEURES_JOURNEE, fill_value=0)
        .rename("nb")
        .reset_index()
    )

    evolution_mois = (
        donnees.groupby("mois")
        .agg(nb_commandes=("id_commande", "count"), kg=("quantite_kg", "sum"))
        .reset_index()
        .sort_values("mois")
    )

    top_clients = (
        donnees.groupby(["id_client", "type_client"])
        .agg(nb_commandes=("id_commande", "count"), kg=("quantite_kg", "sum"))
        .reset_index()
        .sort_values("nb_commandes", ascending=False)
        .head(20)
    )
    noms_clients = clients.set_index("id_client")["nom"]
    top_clients["nom"] = top_clients["id_client"].map(noms_clients)

    urgent_quartier = (
        donnees.groupby("quartier")
        .agg(
            nb_commandes=("id_commande", "count"),
            taux_urgent=("urgente", "mean"),
        )
        .reset_index()
    )

    matrice_chaleur = (
        donnees.groupby(["jour", "heure"]).size().unstack(fill_value=0)
    )
    matrice_chaleur = matrice_chaleur.reindex(index=range(7), columns=HEURES_JOURNEE, fill_value=0)
    matrice_chaleur.index = [JOURS_SEMAINE_ISO[i] for i in matrice_chaleur.index]
    table_heatmap = matrice_chaleur.stack().rename("nb").reset_index()
    table_heatmap.columns = ["jour", "heure", "nb"]

    return {
        "volume_quartier": volume_quartier,
        "demande_jour": demande_jour[["jour", "nb"]],
        "demande_heure": demande_heure,
        "evolution_mois": evolution_mois,
        "top_clients": top_clients,
        "urgent_quartier": urgent_quartier,
        "heatmap_jour_heure": table_heatmap,
    }


def calculer_indicateurs_pyspark(dossier_donnees: Path) -> dict[str, pd.DataFrame]:
    """Exécute les agrégations Big Data en local avec PySpark."""
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    configurer_java_home_spark()
    session_spark = (
        SparkSession.builder.master("local[*]")
        .appName("tourneo-analyse-logistique")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

    try:
        clients_spark = session_spark.read.parquet(str(dossier_donnees / "clients.parquet"))
        commandes_spark = session_spark.read.parquet(str(dossier_donnees / "commandes"))

        donnees_spark = (
            commandes_spark.join(
                clients_spark.select("id_client", "quartier", "type_client"),
                on="id_client",
                how="left",
            )
            .withColumn("jour", (F.dayofweek("date_livraison") + 5) % 7)
            .withColumn("heure", F.hour("creneau_debut"))
        )

        resultats_spark = {
            "volume_quartier": donnees_spark.groupBy("quartier").agg(
                F.count("id_commande").alias("nb_commandes"),
                F.sum("quantite_kg").alias("kg"),
            ),
            "demande_jour": donnees_spark.groupBy("jour").count().withColumnRenamed("count", "nb"),
            "demande_heure": donnees_spark.groupBy("heure").count().withColumnRenamed("count", "nb"),
            "evolution_mois": donnees_spark.groupBy("mois").agg(
                F.count("id_commande").alias("nb_commandes"),
                F.sum("quantite_kg").alias("kg"),
            ),
            "urgent_quartier": donnees_spark.groupBy("quartier").agg(
                F.count("id_commande").alias("nb_commandes"),
                F.avg("urgente").alias("taux_urgent"),
            ),
            "heatmap_jour_heure": donnees_spark.groupBy("jour", "heure").count().withColumnRenamed("count", "nb"),
        }

        top_clients_spark = (
            donnees_spark.join(
                clients_spark.select("id_client", "nom"),
                on="id_client",
                how="left",
            )
            .groupBy("id_client", "nom", "type_client")
            .agg(
                F.count("id_commande").alias("nb_commandes"),
                F.sum("quantite_kg").alias("kg"),
            )
            .orderBy(F.desc("nb_commandes"))
            .limit(20)
        )
        resultats_spark["top_clients"] = top_clients_spark

        return {nom: df_spark.toPandas() for nom, df_spark in resultats_spark.items()}
    finally:
        session_spark.stop()


def normaliser_indicateurs(
    resultats_bruts: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """Harmonise les types et libellés textuels des sorties Spark."""
    resultats = dict(resultats_bruts)

    if "demande_jour" in resultats:
        dj = resultats["demande_jour"].copy()
        if pd.api.types.is_numeric_dtype(dj["jour"]):
            dj = dj.set_index("jour").reindex(range(7), fill_value=0).reset_index()
            dj["jour"] = dj["jour"].map(lambda i: JOURS_SEMAINE_ISO[int(i)])
            dj["nb"] = dj["nb"].astype("int64")
        resultats["demande_jour"] = dj[["jour", "nb"]]

    # Spark ne retourne que les heures observées : réindexation 0-23
    # pour la parité avec le moteur pandas
    if "demande_heure" in resultats:
        dh = resultats["demande_heure"].copy()
        dh = (
            dh.set_index("heure")
            .reindex(HEURES_JOURNEE, fill_value=0)
            .reset_index()
        )
        dh["nb"] = dh["nb"].astype("int64")
        resultats["demande_heure"] = dh[["heure", "nb"]]

    if "heatmap_jour_heure" in resultats:
        hm = resultats["heatmap_jour_heure"].copy()
        if pd.api.types.is_numeric_dtype(hm["jour"]):
            hm["jour"] = hm["jour"].map(lambda i: JOURS_SEMAINE_ISO[int(i)])
        resultats["heatmap_jour_heure"] = hm[["jour", "heure", "nb"]]

    return resultats


def executer_calcul_indicateurs(dossier_donnees: Path = DOSSIER_DONNEES_DEFAUT) -> Path:
    """Calcule et sauvegarde l'ensemble des indicateurs de demande."""
    dossier_sortie = dossier_donnees / "indicateurs"
    moteur_utilise = "PySpark"

    try:
        donnees_calculees = normaliser_indicateurs(calculer_indicateurs_pyspark(dossier_donnees))
        donnees_calculees["evolution_mois"] = donnees_calculees["evolution_mois"].sort_values("mois")
    except Exception as erreur_spark:
        print(
            f"Basculement sur Pandas (Spark non disponible : {erreur_spark})",
            file=sys.stderr,
        )
        moteur_utilise = "Pandas"
        donnees_calculees = calculer_indicateurs_pandas(dossier_donnees)

    sauvegarder_indicateurs(donnees_calculees, dossier_sortie)
    print(f"Indicateurs générés dans '{dossier_sortie}' avec succès (moteur : {moteur_utilise}).")
    return dossier_sortie


# Alias pour rétro-compatibilité
_calcul_pandas = calculer_indicateurs_pandas
_calcul_spark = calculer_indicateurs_pyspark
_normaliser = normaliser_indicateurs
run = executer_calcul_indicateurs


def main() -> int:
    """Point d'entrée CLI pour tourneo.analysis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, default=DOSSIER_DONNEES_DEFAUT, help="Chemin du dossier de données"
    )
    args = parser.parse_args()
    executer_calcul_indicateurs(args.data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
