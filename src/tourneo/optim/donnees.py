from pathlib import Path
import pandas as pd
from tourneo.storage import obtenir_commandes_par_date

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def charger_flotte():
    vehicules = pd.read_csv(DATA_DIR / "vehicules.csv")
    vehicules = vehicules[vehicules["disponible"] == 1].reset_index(drop=True)
    depot = pd.read_csv(DATA_DIR / "depot.csv").iloc[0]
    return vehicules, depot

def charger_jour(date, quartiers=None, max_commandes=60, taux_capacite=0.85):
    commandes = obtenir_commandes_par_date(date)
    clients = pd.read_parquet(DATA_DIR / "clients.parquet")
    commandes = commandes.merge(
        clients[["id_client", "nom", "quartier", "lat", "lon"]], on="id_client", how="left"
    )
    if quartiers:
        commandes = commandes[commandes["quartier"].isin(quartiers)]
    total = len(commandes)
    commandes = commandes.sort_values("id_commande")
    urgentes = commandes[commandes["urgente"] == 1]
    autres = commandes[commandes["urgente"] == 0].sample(frac=1, random_state=42)
    commandes = pd.concat([urgentes, autres]).reset_index(drop=True)
    if taux_capacite is not None:
        vehicules, _ = charger_flotte()
        limite = vehicules["capacite_kg"].sum() * taux_capacite
        commandes = commandes[commandes["quantite_kg"].cumsum() <= limite]
    commandes = commandes.head(max_commandes).reset_index(drop=True)
    return commandes, total
def charger_clients():
    return pd.read_parquet(DATA_DIR / "clients.parquet")