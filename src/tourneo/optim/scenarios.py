import pandas as pd
from tourneo.optim.api import MODES, tournees_en_table
from tourneo.optim.donnees import charger_clients, charger_flotte, charger_jour
from tourneo.optim.evaluation import preparer, resumer
from tourneo.optim.solver import resoudre


def _calcul(commandes, vehicules, depot, mode, temps_limite_s, facteur_duree=1.0, routes_initiales=None):
    inst = preparer(commandes, depot)
    inst["duree"] = inst["duree"] * facteur_duree
    tournees, non_livrees = resoudre(
        inst, vehicules, temps_limite_s=temps_limite_s,
        penalite_retard=MODES[mode], routes_initiales=routes_initiales
    )
    return tournees, non_livrees, inst["source"]


def _ids(commandes, non_livrees):
    return [int(commandes.iloc[n - 1]["id_commande"]) for n in non_livrees]


def _objectif(tournees, non_livrees, mode):
    return sum(t["cout"] + MODES[mode] * t["retard_min"] for t in tournees) + 100000 * len(non_livrees)


def simuler(date, scenario, quartiers=None, mode="equilibre", temps_limite_s=20):
    vehicules, depot = charger_flotte()
    commandes, total = charger_jour(date, quartiers=quartiers)
    avant, nl_avant, source = _calcul(commandes, vehicules, depot, mode, temps_limite_s)
    routes = {t["id_vehicule"]: t["arrets"] for t in avant}

    genre = scenario["type"]
    commandes_apres = commandes
    vehicules_apres = vehicules
    facteur = 1.0
    if genre == "panne":
        id_panne = scenario.get("id_vehicule")
        if id_panne is None:
            id_panne = max(avant, key=lambda t: t["charge_kg"])["id_vehicule"]
        scenario = {**scenario, "id_vehicule": int(id_panne)}
        vehicules_apres = vehicules[vehicules["id_vehicule"] != id_panne].reset_index(drop=True)
    elif genre == "urgente":
        clients = charger_clients()
        c = clients[clients["id_client"] == scenario["id_client"]].iloc[0]
        jour = commandes["date_livraison"].iloc[0].normalize()
        nouvelle = {
            "id_commande": 9000000 + int(scenario["id_client"]),
            "id_client": int(c["id_client"]),
            "date_livraison": jour,
            "quantite_kg": float(scenario.get("quantite_kg", 150)),
            "creneau_debut": jour + pd.Timedelta(hours=scenario.get("heure_debut", 10)),
            "creneau_fin": jour + pd.Timedelta(hours=scenario.get("heure_fin", 12)),
            "urgente": 1,
            "nom": c["nom"],
            "quartier": c["quartier"],
            "lat": float(c["lat"]),
            "lon": float(c["lon"]),
        }
        commandes_apres = pd.concat([commandes, pd.DataFrame([nouvelle])], ignore_index=True)
    elif genre == "embouteillage":
        facteur = float(scenario.get("facteur", 1.5))
    elif genre == "creneaux":
        reduction = float(scenario.get("facteur", 0.5))
        commandes_apres = commandes.copy()
        largeur = commandes_apres["creneau_fin"] - commandes_apres["creneau_debut"]
        commandes_apres["creneau_fin"] = commandes_apres["creneau_debut"] + largeur * reduction
    else:
        raise ValueError(f"Scénario inconnu : {genre}")

    apres, nl_apres, source_apres = _calcul(
        commandes_apres, vehicules_apres, depot, mode, temps_limite_s, facteur, routes_initiales=routes
    )
    if _objectif(apres, nl_apres, mode) < _objectif(avant, nl_avant, mode):
        routes_apres = {t["id_vehicule"]: t["arrets"] for t in apres}
        avant2, nl_avant2, _ = _calcul(commandes, vehicules, depot, mode, temps_limite_s, routes_initiales=routes_apres)
        if _objectif(avant2, nl_avant2, mode) < _objectif(avant, nl_avant, mode):
            avant, nl_avant = avant2, nl_avant2

    comparaison = {
        "date": date,
        "mode": mode,
        "scenario": scenario,
        "commandes_du_jour": int(total),
        "commandes_retenues": int(len(commandes)),
        "source_matrice": "repli" if "repli" in (source, source_apres) else "osrm",
        "avant": resumer(avant, nl_avant),
        "apres": resumer(apres, nl_apres),
        "non_livrees_avant": _ids(commandes, nl_avant),
        "non_livrees_apres": _ids(commandes_apres, nl_apres),
    }
    table = tournees_en_table(apres, date, commandes_apres)
    return table, comparaison