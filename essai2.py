from tourneo.optim.donnees import charger_jour, charger_flotte

vehicules, depot = charger_flotte()
tout, total = charger_jour("2026-10-15", max_commandes=10000)
print("commandes du jour :", total)
print(tout["quartier"].value_counts())
print("demande totale kg :", round(tout["quantite_kg"].sum()))
print("capacité totale kg :", round(vehicules["capacite_kg"].sum()))
print(vehicules[["id_vehicule", "capacite_kg", "cout_km"]])
print(depot["lat"], depot["lon"])