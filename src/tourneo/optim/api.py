import json
import pandas as pd
from tourneo.optim.donnees import charger_jour, charger_flotte, DATA_DIR
from tourneo.optim.evaluation import preparer, resumer
from tourneo.optim.baseline import tournees_naives
from tourneo.optim.solver import resoudre

MODES = {"economique": 0, "equilibre": 20, "ponctuel": 200}
SORTIE_DIR = DATA_DIR / "tournees"


def gain(naif, opti):
    return round((1 - opti / naif) * 100, 1) if naif else 0.0


def tournees_en_table(tournees, date, commandes):
    lignes = []
    for t in tournees:
        for ordre, (noeud, heure) in enumerate(zip(t["arrets"], t["livraisons"]), start=1):
            c = commandes.iloc[noeud - 1]
            arrivee = pd.Timestamp(date) + pd.to_timedelta(float(heure), unit="m")
            lignes.append({
                "id_vehicule": t["id_vehicule"],
                "ordre": ordre,
                "id_commande": int(c["id_commande"]),
                "id_client": int(c["id_client"]),
                "nom": c["nom"],
                "quartier": c["quartier"],
                "lat": float(c["lat"]),
                "lon": float(c["lon"]),
                "quantite_kg": float(c["quantite_kg"]),
                "creneau_debut": c["creneau_debut"],
                "creneau_fin": c["creneau_fin"],
                "heure_arrivee": arrivee,
                "retard_min": max(0.0, (arrivee - c["creneau_fin"]).total_seconds() / 60),
            })
    return pd.DataFrame(lignes)


def optimiser(date, quartiers=None, mode="equilibre", temps_limite_s=20, ecrire=True):
    vehicules, depot = charger_flotte()
    commandes, total = charger_jour(date, quartiers=quartiers)
    if commandes.empty:
        raise ValueError("Aucune commande retenue pour cette date")
    inst = preparer(commandes, depot)
    tn, nl_n = tournees_naives(inst, vehicules)
    to, nl_o = resoudre(inst, vehicules, temps_limite_s=temps_limite_s, penalite_retard=MODES[mode])
    table = tournees_en_table(to, date, commandes)
    rn = resumer(tn, nl_n)
    ro = resumer(to, nl_o)
    comparaison = {
        "date": date,
        "mode": mode,
        "penalite_retard": MODES[mode],
        "commandes_du_jour": int(total),
        "commandes_retenues": int(len(commandes)),
        "source_matrice": inst["source"],
        "naif": rn,
        "optimise": ro,
        "gain_cout_transport_pct": gain(rn["cout_fcfa"], ro["cout_fcfa"]),
        "gain_retard_min_pct": gain(rn["retard_min"], ro["retard_min"]),
        "gain_cout_total_pct": gain(rn["cout_total_fcfa"], ro["cout_total_fcfa"]),
        "non_livrees": [int(commandes.iloc[n - 1]["id_commande"]) for n in nl_o],
    }
    if ecrire:
        SORTIE_DIR.mkdir(parents=True, exist_ok=True)
        table.to_parquet(SORTIE_DIR / "tournees.parquet", index=False)
        (SORTIE_DIR / "comparaison.json").write_text(
            json.dumps(comparaison, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return table, comparaison