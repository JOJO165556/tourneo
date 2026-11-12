"""Référentiel géographique, économique et logistique de Lomé.

Ce module constitue la source unique de vérité pour le paramétrage
métier : coordonnées géographiques terrestres, réseau
commercial, flotte de véhicules et coûts d'exploitation réels à Lomé.
"""

from __future__ import annotations

from typing import Final, NamedTuple


class Quartier(NamedTuple):
    """Caractéristiques géographiques et commerciales d'un quartier de Lomé."""

    lat: float
    lon: float
    poids: float


# Boîte englobante stricte du Grand Lomé (WGS84, terre ferme uniquement)
# La ligne de côte atlantique est à 6.120 N. Les latitudes < 6.118 correspondent à la mer
BBOX_LATITUDE: Final[tuple[float, float]] = (6.1200, 6.2800)
BBOX_LONGITUDE: Final[tuple[float, float]] = (1.1200, 1.3400)

# Coordonnées WGS84 et coefficients de densité commerciale des quartiers de Lomé
QUARTIERS_LOME: Final[dict[str, Quartier]] = {
    # Sud-Ouest : frontière d'Aflao (Ghana) et commerces frontaliers
    "kodjoviakope": Quartier(lat=6.1260, lon=1.2060, poids=1.1),
    "nyekonakpoe": Quartier(lat=6.1360, lon=1.2080, poids=1.0),
    # Sud-Centre : grand marché de Bè et zone lagunaire
    "be": Quartier(lat=6.1380, lon=1.2360, poids=1.6),
    "be_kpota": Quartier(lat=6.1550, lon=1.2520, poids=1.1),
    # Centre administratif, hospitalier (CHU) et carrefours majeurs
    "tokoin": Quartier(lat=6.1620, lon=1.2220, poids=1.5),
    "djidjole": Quartier(lat=6.1780, lon=1.1960, poids=1.2),
    # Ouest : axe commercial de Kpalimé et carrefour Douane
    "adidogome": Quartier(lat=6.1760, lon=1.1550, poids=1.3),
    # Est : pôle commercial autour du marché de Hédzranawoé
    "hedzranawoe": Quartier(lat=6.1750, lon=1.2680, poids=1.2),
    # Nord : carrefour et banlieue en très forte croissance démographique
    "agoe": Quartier(lat=6.2250, lon=1.2050, poids=1.4),
    # Littoral Est : commune périurbaine sur la route nationale 2
    "baguida": Quartier(lat=6.1580, lon=1.3250, poids=0.7),
}

# Dépôt central de distribution dans la zone logistique du Port Autonome de Lomé
DEPOT_CENTRAL: Final[dict[str, int | str | float]] = {
    "id_depot": 1,
    "nom": "depot_port_lome",
    "lat": 6.1420,
    "lon": 1.2650,
}

# Typologie des points de vente : part de marché, commande médiane (kg) et variance
TYPOLOGIE_CLIENTS: Final[dict[str, tuple[float, float, float]]] = {
    "boutique": (0.40, 45.0, 0.55),
    "supermarche": (0.25, 130.0, 0.50),
    "restaurant": (0.20, 85.0, 0.60),
    "grossiste": (0.15, 280.0, 0.45),
}

# Capacités standards de la flotte de livraison urbaine à Lomé (en kg)
# Du tricycle motorisé (500 kg) au camion lourd de distribution (8 000 kg)
CAPACITES_FLOTTE_KG: Final[list[float]] = [
    500.0, 800.0, 1200.0, 1500.0, 2000.0,
    3000.0, 4000.0, 5000.0, 6500.0, 8000.0,
]

# Modèle de coût kilométrique réaliste à Lomé (carburant à ~850 FCFA/L, chauffeur, usure des pistes)
# Coût = base fixe + part proportionnelle au tonnage transporté
COUT_KM_BASE_FCFA: Final[float] = 120.0
COUT_KM_PAR_KG_FCFA: Final[float] = 0.095

# Créneaux horaires de livraison (début en min, fin en min, probabilité)
CRENEAUX_LIVRAISON: Final[tuple[tuple[int, int, float], ...]] = (
    (7 * 60, 11 * 60, 0.35),   # Matinée (avant les fortes chaleurs)
    (13 * 60, 17 * 60, 0.35),  # Après-midi
    (8 * 60, 16 * 60, 0.30),   # Journée continue
)

# Préfixes et enseignes caractéristiques du tissu commercial togolais à Lomé
PREFIXES_ENSEIGNES: Final[dict[str, list[str]]] = {
    "boutique": ["Alimentation", "Boutique", "Établissement", "Mini-Alimentation"],
    "supermarche": ["Supermarché", "Supérette", "Espace Distribution", "Libre Service"],
    "restaurant": ["Bar-Restaurant", "Maquis", "Cafétéria", "Restaurant"],
    "grossiste": ["Dépôt Central", "Comptoir Commercial", "Grossiste", "Éts Import-Export"],
}

ENSEIGNES_LOCALES: Final[list[str]] = [
    "La Grâce", "La Bénédiction", "Sainte-Rita", "Saint-Michel", "Espérance",
    "Le Progrès", "Akofa", "Afiwa", "Koffi & Frères", "Mensah Distribution",
    "Golfe 4", "Assigamé", "Le Champion", "Concorde", "La Paix",
    "Épiphanie", "Miséricorde", "Le Palmier", "Mon Bonheur", "La Providence",
    "Sainte-Anne", "Solidarité", "Victoire", "Kékéli", "Notre-Dame",
    "L'Éternel Pourvoit", "Source de Vie", "Détente du Golfe", "Le Relais de Lomé",
]
