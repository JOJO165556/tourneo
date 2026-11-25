from tourneo.optim.donnees import charger_jour, charger_flotte
from tourneo.optim.evaluation import preparer, resumer
from tourneo.optim.baseline import tournees_naives
from tourneo.optim.solver import resoudre

vehicules, depot = charger_flotte()
commandes, total = charger_jour("2026-10-15")
inst = preparer(commandes, depot)

tn, nl_n = tournees_naives(inst, vehicules)
to, nl_o = resoudre(inst, vehicules, temps_limite_s=20)
rn = resumer(tn, nl_n)
ro = resumer(to, nl_o)

print("naif     :", rn)
print("optimise :", ro)
for cle in ("km", "temps_min", "cout_fcfa"):
    print(cle, "gain :", round((1 - ro[cle] / rn[cle]) * 100, 1), "%")
print("retards :", rn["retards"], "->", ro["retards"])
for t in to:
    print(t["id_vehicule"], len(t["arrets"]), "arrêts", round(t["distance_km"], 1), "km", round(t["charge_kg"]), "kg", t["retards"], "retards")