"""Package d'analyse logistique à Lomé.

API publique exposée par ce package :

    from tourneo import generer_et_sauvegarder, valider, obtenir_commandes_par_date
    from tourneo import executer_calcul_indicateurs, ParametresGeneration

Chaque sous-module reste importable directement pour un usage avancé :
    tourneo.generate, tourneo.validate, tourneo.storage,
    tourneo.analysis, tourneo.dashboard, tourneo.referentiel
"""

from tourneo.generate import ParametresGeneration, generer_et_sauvegarder
from tourneo.validate import valider
from tourneo.storage import (
    charger_clients,
    charger_commandes,
    obtenir_commandes_par_date,
)
from tourneo.analysis import executer_calcul_indicateurs

__version__ = "0.1.0"
__all__ = [
    "ParametresGeneration",
    "generer_et_sauvegarder",
    "valider",
    "charger_clients",
    "charger_commandes",
    "obtenir_commandes_par_date",
    "executer_calcul_indicateurs",
]
