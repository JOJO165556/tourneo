from tourneo.optim.donnees import charger_jour, charger_flotte
from tourneo.optim.evaluation import preparer, resumer
from tourneo.optim.baseline import tournees_naives

vehicules, depot = charger_flotte()
commandes, total = charger_jour("2026-10-15")
inst = preparer(commandes, depot)
tournees, non_livrees = tournees_naives(inst, vehicules)
print("source matrice :", inst["source"])
for t in tournees:
    print(t["id_vehicule"], len(t["arrets"]), "arrêts", round(t["distance_km"], 1), "km", round(t["charge_kg"]), "kg", t["retards"], "retards")
print(resumer(tournees, non_livrees))