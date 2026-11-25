from tourneo.optim.scenarios import simuler

scenarios = [
    {"type": "panne"},
    {"type": "urgente", "id_client": 100, "quantite_kg": 150, "heure_debut": 10, "heure_fin": 12},
    {"type": "embouteillage", "facteur": 1.8},
]
for s in scenarios:
    table, comp = simuler("2026-10-15", s, temps_limite_s=15)
    print(s)
    print("  avant :", comp["avant"])
    print("  apres :", comp["apres"])
    print("  non livrées après :", comp["non_livrees_apres"])