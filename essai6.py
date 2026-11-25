from tourneo.optim.donnees import charger_jour, charger_flotte
from tourneo.optim.evaluation import preparer, resumer
from tourneo.optim.baseline import tournees_naives
from tourneo.optim.solver import resoudre

vehicules, depot = charger_flotte()
commandes, total = charger_jour("2026-10-15")
inst = preparer(commandes, depot)

tn, nl_n = tournees_naives(inst, vehicules)
print("naif          :", resumer(tn, nl_n))
for penalite in (0, 20, 200):
    to, nl_o = resoudre(inst, vehicules, temps_limite_s=15, penalite_retard=penalite)
    print("optimise", penalite, ":", resumer(to, nl_o))
    