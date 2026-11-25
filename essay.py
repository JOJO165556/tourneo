from tourneo.optim.matrice import construire_matrices

coords = [(6.13, 1.22), (6.17, 1.23), (6.18, 1.20), (6.21, 1.19), (6.16, 1.26)]
for heure in (3, 8):
    m = construire_matrices(coords, heure_depart=heure)
    print(m["source"], heure, "h")
    print(m["duree_min"].round(1))