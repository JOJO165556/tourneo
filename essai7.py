from tourneo.optim.api import optimiser

for date in ("2026-10-08", "2026-10-15", "2026-10-22"):
    for mode in ("economique", "equilibre", "ponctuel"):
        try:
            table, comp = optimiser(date, mode=mode, temps_limite_s=10)
        except ValueError as e:
            print(date, mode, e)
            continue
        print(date, mode, "transport", comp["gain_cout_transport_pct"], "% | retards", comp["gain_retard_min_pct"], "% | total", comp["gain_cout_total_pct"], "%")

print(table[["id_vehicule", "ordre", "id_commande", "quartier", "heure_arrivee", "retard_min"]].head(8))