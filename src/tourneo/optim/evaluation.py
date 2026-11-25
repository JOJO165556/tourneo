import numpy as np
from tourneo.optim.matrice import construire_matrices

SERVICE_MIN = 10
HEURE_DEBUT_MIN = 420


def minutes(serie):
    return (serie.dt.hour * 60 + serie.dt.minute).to_numpy()


def preparer(commandes, depot, heure_debut_min=HEURE_DEBUT_MIN):
    coords = [(float(depot["lat"]), float(depot["lon"]))] + list(zip(commandes["lat"], commandes["lon"]))
    matrices = construire_matrices(coords, heure_depart=heure_debut_min / 60)
    return {
        "duree": matrices["duree_min"],
        "distance": matrices["distance_km"],
        "source": matrices["source"],
        "demande": np.concatenate([[0.0], commandes["quantite_kg"].to_numpy(dtype=float)]),
        "debut": np.concatenate([[0], minutes(commandes["creneau_debut"])]),
        "fin": np.concatenate([[1440], minutes(commandes["creneau_fin"])]),
        "heure_debut_min": heure_debut_min,
    }

def evaluer_tournee(inst, arrets, cout_km):
    t = float(inst["heure_debut_min"])
    position = 0
    distance = 0.0
    retards = 0
    retard_min = 0.0
    livraisons = []
    for n in arrets:
        t += inst["duree"][position][n]
        distance += inst["distance"][position][n]
        if t > inst["fin"][n]:
            retards += 1
            retard_min += t - inst["fin"][n]
        t = max(t, inst["debut"][n])
        livraisons.append(t)
        t += SERVICE_MIN
        position = n
    t += inst["duree"][position][0]
    distance += inst["distance"][position][0]
    return {
        "arrets": list(arrets),
        "livraisons": livraisons,
        "distance_km": float(distance),
        "duree_min": float(t - inst["heure_debut_min"]),
        "charge_kg": float(sum(inst["demande"][n] for n in arrets)),
        "retards": retards,
        "retard_min": float(retard_min),
        "cout": float(distance * cout_km),
    }


def resumer(tournees, non_livrees, penalite_retard=200):
    cout = sum(t["cout"] for t in tournees)
    retard_min = sum(t["retard_min"] for t in tournees)
    return {
        "km": round(sum(t["distance_km"] for t in tournees), 1),
        "cout_fcfa": round(cout),
        "retards": sum(t["retards"] for t in tournees),
        "retard_min": round(retard_min),
        "cout_total_fcfa": round(cout + penalite_retard * retard_min),
        "non_livrees": len(non_livrees),
        "vehicules_utilises": sum(1 for t in tournees if t["arrets"]),
    }