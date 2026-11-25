from tourneo.optim.evaluation import evaluer_tournee


def tournees_naives(inst, vehicules):
    restants = set(range(1, len(inst["demande"])))
    tournees = []
    for _, v in vehicules.sort_values("cout_km").iterrows():
        capacite = float(v["capacite_kg"])
        position = 0
        charge = 0.0
        arrets = []
        while True:
            candidats = [n for n in restants if charge + inst["demande"][n] <= capacite]
            if not candidats:
                break
            suivant = min(candidats, key=lambda n: inst["distance"][position][n])
            arrets.append(suivant)
            restants.discard(suivant)
            charge += inst["demande"][suivant]
            position = suivant
        tournee = evaluer_tournee(inst, arrets, float(v["cout_km"]))
        tournee["id_vehicule"] = int(v["id_vehicule"])
        tournees.append(tournee)
    return tournees, sorted(restants)