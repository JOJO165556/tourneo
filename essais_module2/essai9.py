import pandas as pd
from tourneo.optim.api import optimiser
from tourneo.optim.donnees import DATA_DIR

table, comp = optimiser("2026-10-15", quartiers=["tokoin", "hedzranawoe"], mode="equilibre")
print(comp["commandes_du_jour"], comp["commandes_retenues"], comp["source_matrice"])
print("naif    :", comp["naif"])
print("optimise:", comp["optimise"])
print("gains   :", comp["gain_cout_transport_pct"], "% transport,", comp["gain_retard_min_pct"], "% retard")
print(table.columns.tolist())
print(pd.read_parquet(DATA_DIR / "tournees" / "tournees.parquet").shape)