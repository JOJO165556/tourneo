from tourneo.optim.donnees import charger_jour

commandes, total = charger_jour("2026-10-15")
print("commandes du jour :", total)
print("retenues :", len(commandes))
print("demande retenue kg :", round(commandes["quantite_kg"].sum()))
print("urgentes :", int(commandes["urgente"].sum()))
print(commandes[["id_commande", "quartier", "quantite_kg", "creneau_debut", "creneau_fin"]].head())