import numpy as np
import requests

OSRM_URL = "https://router.project-osrm.org/table/v1/driving/"
FACTEUR_DETOUR = 1.3
VITESSE_REPLI_KMH = 30.0
MAX_POINTS = 100

PROFIL_TRAFIC = {h: 1.0 for h in range(24)}
PROFIL_TRAFIC.update({7: 1.5, 8: 1.8, 9: 1.4, 12: 1.2, 13: 1.2, 17: 1.6, 18: 1.9, 19: 1.5})


def facteur_trafic(heure):
    return PROFIL_TRAFIC[int(heure) % 24]


def matrices_repli(coords):
    pts = np.radians(np.asarray(coords, dtype=float))
    lat = pts[:, 0][:, None]
    lon = pts[:, 1][:, None]
    dlat = lat - lat.T
    dlon = lon - lon.T
    a = np.sin(dlat / 2) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlon / 2) ** 2
    distance_km = 2 * 6371.0 * np.arcsin(np.sqrt(a)) * FACTEUR_DETOUR
    duree_min = distance_km / VITESSE_REPLI_KMH * 60
    return duree_min, distance_km


def matrices_osrm(coords, timeout=20):
    if len(coords) > MAX_POINTS:
        raise ValueError(f"{len(coords)} points, maximum {MAX_POINTS}")
    trace = ";".join(f"{lon},{lat}" for lat, lon in coords)
    reponse = requests.get(OSRM_URL + trace, params={"annotations": "duration,distance"}, timeout=timeout)
    reponse.raise_for_status()
    data = reponse.json()
    if data.get("code") != "Ok":
        raise RuntimeError(data.get("code"))
    duree_min = np.array(data["durations"], dtype=float) / 60
    distance_km = np.array(data["distances"], dtype=float) / 1000
    duree_repli, distance_repli = matrices_repli(coords)
    manquant = np.isnan(duree_min) | np.isnan(distance_km)
    duree_min[manquant] = duree_repli[manquant]
    distance_km[manquant] = distance_repli[manquant]
    return duree_min, distance_km


def construire_matrices(coords, heure_depart=8.0, utiliser_osrm=True):
    source = "osrm"
    try:
        if not utiliser_osrm:
            raise RuntimeError("osrm désactivé")
        duree_min, distance_km = matrices_osrm(coords)
    except (requests.RequestException, RuntimeError, ValueError, KeyError):
        duree_min, distance_km = matrices_repli(coords)
        source = "repli"
    duree_min = duree_min * facteur_trafic(heure_depart)
    return {"duree_min": duree_min, "distance_km": distance_km, "source": source}