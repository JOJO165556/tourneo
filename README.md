# Tourneo : Pipeline logistique de Lomé

Génération, validation, stockage et analyse de données de livraison
simulées sur le Grand Lomé. Stack : Python, pandas, PyArrow, DuckDB, PySpark, Plotly, OR-Tools, Streamlit,folium, ReportLab.

Le projet comprend trois modules : les données et le big data (module 1), l'optimisation
des tournées de livraison (module 2) et une application web OptiLomé qui relie le tout (module 3).

<p>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/pandas-2.3-150458?logo=pandas&logoColor=white" alt="pandas" />
  <img src="https://img.shields.io/badge/pyarrow-26-FF8C42?logo=apacheparquet&logoColor=white" alt="PyArrow / Parquet" />
  <img src="https://img.shields.io/badge/duckdb-2.0-FEFF00?logo=duckdb&logoColor=black" alt="DuckDB" />
  <img src="https://img.shields.io/badge/pyspark-4.3-E25A1C?logo=apachespark&logoColor=white" alt="PySpark" />
  <img src="https://img.shields.io/badge/plotly-7.1-3F4F75?logo=plotly&logoColor=white" alt="Plotly" />
  <img src="https://img.shields.io/badge/java-17%2B-ED8B00?logo=openjdk&logoColor=white" alt="Java 17+" />
  <img src="https://img.shields.io/badge/pytest-9-0A9EDC?logo=pytest&logoColor=white" alt="pytest" />
  <img src="https://img.shields.io/badge/ortools-Google-4285F4?logo=google&logoColor=white" alt="OR-Tools" />
  <img src="https://img.shields.io/badge/streamlit-application-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/reportlab-PDF-000000" alt="ReportLab" />
</p>

## Prérequis

- Python 3.11+
- Java (versions 17, 21 ou 25 supportées par PySpark 4.3)
- Une connexion internet pour les itinéraires sur les routes réelles (service OSRM). Sans connexion,
  le module 2 bascule automatiquement sur une estimation à vol d'oiseau.

### Configuration de JAVA_HOME

Le projet détecte automatiquement votre installation de Java (sur Windows, Linux et macOS).
Si vous préférez fixer le chemin manuellement, vous pouvez copier le fichier exemple :
```bash
cp .env.example .env     # sous Windows : copy .env.example .env
```
Puis renseigner votre chemin dans `.env` :
```env
JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.6.7-hotspot
```

## Installation

**Sous Windows (PowerShell) :**
```powershell
cd /chemin/vers/tourneo
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

**Sous Linux / macOS :**
```bash
cd /chemin/vers/tourneo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Le fichier `requirements.txt` doit contenir `ortools`, `requests`, `streamlit`,`folium` et `reportlab`
en plus des dépendances du module 1.

Si le dossier du projet est déplacé ou renommé, relancer `pip install -e .` depuis son nouvel emplacement.

## Structure du projet

```
tourneo/
├── app.py                # application web Streamlit (module 3)
├── src/tourneo/          # package Python
│   ├── referentiel.py    # constantes géo/économiques (Lomé)
│   ├── generate.py       # générateur vectorisé par lots (PyArrow)
│   ├── validate.py       # validation du contrat de données
│   ├── storage.py        # DuckDB embarqué, partition pruning Hive
│   ├── analysis.py       # indicateurs PySpark + repli Pandas
│   ├── dashboard.py      # visualisations Plotly
│   ├── feuilles_route.py # export PDF des feuilles de route (module 3)
│   └── optim/            # moteur d'optimisation (module 2)
│       ├── donnees.py    # commandes du jour, flotte, dépôt
│       ├── matrice.py    # matrices de durées et distances (OSRM + repli)
│       ├── evaluation.py # préparation de l'instance, mesure des tournées
│       ├── baseline.py   # méthode naïve de référence
│       ├── solver.py     # optimiseur OR-Tools
│       ├── scenarios.py  # panne, commande urgente, embouteillage, créneaux
│       └── api.py        # optimiser() et fichiers de sortie
├── data/
│   ├── sample/           # jeu réduit de test (20 clients, 30 commandes)
│   ├── commandes/        # partitions Hive mois=AAAA-MM/
│   ├── indicateurs/      # parquet + html par indicateur
│   ├── tournees/         # sorties du module 2 (non versionné)
│   └── ...
├── essais_module2/       # scripts d'essai du module 2
├── tests/                # 13 tests (100 % passants)
├── docs/contrat.md       # spécification des tables
├── pyproject.toml        # package, scripts CLI
├── .env.example          # exemple de configuration locale (JAVA_HOME)
└── README.md
```

## Pipeline — ordre d'exécution

### 1. Générer les données

```bash
# Volume standard : 1 500 clients, 200 000 commandes, 12 mois
python -m tourneo.generate

# Extrait réduit pour le développement et les tests (data/sample/)
python -m tourneo.generate --sample

# Montée en charge
python -m tourneo.generate --commandes 1000000 --clients 5000 --mois 24
```

Reproductible (graine fixe 42). Produit `clients.parquet`,
`commandes/mois=AAAA-MM/` (Parquet partitionné Hive), `vehicules.csv`, `depot.csv`.

### 2. Valider

```bash
python -m tourneo.validate            # jeu complet
python -m tourneo.validate --sample   # extrait sample/
```

Contrôle : colonnes et types, unicité des identifiants, intégrité
`id_client`, coordonnées WGS84 terrestres (Grand Lomé), `quantite_kg > 0`,
`urgente ∈ {0,1}`, cohérence des créneaux. Code de sortie `1` en cas d'anomalie.

### 3. Stocker et interroger

```bash
python -m tourneo.storage             # test lecture + requête par date
python -m tourneo.storage --bench     # benchmark CSV vs Parquet → bench_temps.txt
```

`obtenir_commandes_par_date(date)` utilise DuckDB en mode embarqué avec
partition pruning Hive : seule la partition du mois concerné est lue.
Résultat mesuré : **~8× plus rapide qu'un scan CSV complet**.

> **Pour l'optimiseur de tournées** : il appelle `obtenir_commandes_par_date("YYYY-MM-DD")`
> et reçoit **toutes les commandes du jour J** issues du jeu complet (pas du sample).
> Le sample (`data/sample/`) n'est utilisé que par `pytest`.

### 4. Calculer les indicateurs

```bash
python -m tourneo.analysis
```

PySpark `local[*]` → `data/indicateurs/*.parquet` :
volume par quartier, demande par jour/heure, évolution mensuelle,
top 20 clients, taux d'urgentes par quartier, heatmap jour × heure.
Repli automatique sur Pandas si Java/Spark est absent.

### 5. Visualiser

```bash
python -m tourneo.dashboard           # HTML -> data/indicateurs/html/
```

Une fonction Plotly par indicateur (`fig_volume_quartier()`,
`fig_demande_jour()`, etc.). Chaque fonction lit `indicateurs/` sans
recalcul.

### 6. Tests automatisés

```bash
pytest tests/
```

La suite vérifie :
- parité Spark ↔ repli Pandas (mêmes résultats à l'arrondi près) ;
- intégrité du contrat et détection des anomalies synthétiques ;
- immunité aux injections SQL sous DuckDB ;
- conformité des axes et libellés des figures Plotly.

### 7. Optimiser les tournées (module 2)

```python
from tourneo.optim.api import optimiser

table, comparaison = optimiser("2026-10-15", quartiers=["tokoin", "hedzranawoe"], mode="equilibre")
```

La date doit être un jour présent dans les données générées. Le calcul dure environ 20 secondes.

**Déroulement :**
1. Lecture des commandes du jour (`obtenir_commandes_par_date`) et jointure avec les coordonnées des clients.
2. Sélection d'au plus 60 commandes : toutes les urgentes, puis un tirage aléatoire reproductible,
   dans la limite de 85 % de la capacité de la flotte. Au-delà, le solveur ne converge plus de façon fiable.
3. Calcul des matrices de durées et de distances : routes réelles via OSRM (données OpenStreetMap),
   repli à vol d'oiseau majoré de 30 % si le service est indisponible, coefficient de trafic selon l'heure.
4. Tournées de référence (méthode naïve) : chaque véhicule, des moins chers aux plus chers,
   va toujours au client le plus proche qui tient dans sa capacité. Les créneaux sont ignorés.
5. Tournées optimisées (OR-Tools) : coût propre à chaque véhicule (distance × coût au km), capacité,
   10 minutes de service par arrêt, créneaux souples pénalisés par minute de retard, commandes écartables
   en dernier recours (100 000 FCFA). Première solution par insertion en parallèle, puis recherche tabou.
6. Comparaison naïf et optimisé, puis écriture des fichiers de sortie.

**Modes de priorité :**

| Mode | Pénalité de retard | Usage |
|------|--------------------|-------|
| `economique` | 0 FCFA par minute | Coût minimal, ignore les créneaux |
| `equilibre` | 20 FCFA par minute | Compromis (mode par défaut) |
| `ponctuel` | 200 FCFA par minute | Priorité à la ponctualité |

**Fichiers produits** (dans `data/tournees/`, non versionnés) :
- `tournees.parquet` : une ligne par arrêt livré (`id_vehicule`, `ordre`, `id_commande`, `id_client`, `nom`,
  `quartier`, `lat`, `lon`, `quantite_kg`, `creneau_debut`, `creneau_fin`, `heure_arrivee`, `retard_min`).
- `comparaison.json` : indicateurs de la méthode naïve et de l'optimisation, gains, commandes retenues
  sur commandes du jour, source de la matrice (`osrm` ou `repli`), commandes non livrées.

**Résultats mesurés** (3 jours de test : 8, 15 et 22 octobre 2026, 60 commandes, 20 secondes de calcul,
données simulées). Les gains sont des ordres de grandeur : le solveur est une méthode approchée.

| Mode | Coût de transport par rapport au naïf | Minutes de retard par rapport au naïf |
|------|---------------------------------------|---------------------------------------|
| `equilibre` | de 1 % à 15 % moins cher | 98 % de moins environ |
| `ponctuel` | équivalent (de −7 % à +7 %) | 99,8 % à 100 % de moins |
| `economique` | de 28 % à 38 % moins cher | non maîtrisé (ignore les créneaux) |

#### Scénarios de simulation

```python
from tourneo.optim.scenarios import simuler

table, comparaison = simuler("2026-10-15", {"type": "panne"})
```

Le plan normal est calculé, la journée est perturbée, puis les tournées sont recalculées à partir du plan existant.

| Scénario | Paramètres | Perturbation |
|----------|------------|--------------|
| Panne | `{"type": "panne"}` ou `{"type": "panne", "id_vehicule": 3}` | Un véhicule est retiré (par défaut, le plus chargé) |
| Commande urgente | `{"type": "urgente", "id_client": 100}` | Une commande urgente est ajoutée |
| Embouteillage | `{"type": "embouteillage", "facteur": 1.8}` | Toutes les durées de trajet sont multipliées |
| Créneaux plus serrés | `{"type": "creneaux", "facteur": 0.5}` | La largeur de chaque créneau est réduite |

La comparaison renvoyée contient `avant`, `apres`, `scenario`, `commandes_du_jour`, `commandes_retenues`,
`source_matrice`, `non_livrees_avant` et `non_livrees_apres`.

### 8. Lancer l'application (module 3)

```bash
streamlit run app.py
```

Les étapes 1 et 4 (génération des données puis calcul des indicateurs) doivent avoir été exécutées au préalable.

**Onglet Planification :**
- choix du jour, des quartiers, de la priorité et du scénario ;
- indicateurs de comparaison (méthode naïve et optimisé, ou avant et après le scénario) ;
- deux cartes au choix : interactive (PyDeck) et détaillée (Folium, avec flèches de direction, plusieurs fonds de carte dont le satellite, plein écran et export en page web) ; un itinéraire par véhicule sur les routes, arrêts numérotés par ordre de passage, légende avec filtre par véhicule ;
- avertissements : commandes non planifiées, distances estimées sans OSRM, commandes non livrées ;
- tableau des arrêts, export CSV et export PDF (une page de synthèse et une feuille de route par véhicule).

**Onglet Analyse de la demande :** les sept graphiques du module 1 (volume par quartier, urgences,
demande par jour et par heure, évolution mensuelle, top clients, carte de chaleur jour et heure).

## Montée en charge

Le générateur traite les commandes par lots de 100 000 lignes et écrit
chaque lot en Parquet via PyArrow sans tout charger en mémoire.

```bash
# 5 000 clients, 1 000 000 commandes, 24 mois d'historique
python -m tourneo.generate --clients 5000 --commandes 1000000 --mois 24
```

Volume estimé : ~400 Mo Parquet (factor ~6 vs CSV), répartis en 24 partitions mensuelles.

## Conformité économique et géographique

Toutes les constantes (coûts, coordonnées, enseignes, typologies) sont
définies dans [`src/tourneo/referentiel.py`](src/tourneo/referentiel.py)
et reflètent le contexte réel de Lomé :

| Paramètre | Source |
|-----------|--------|
| Coordonnées WGS84 | Centroïdes terrain 10 quartiers du Grand Lomé |
| Coût/km véhicule | Modèle 120 + 0,095 × capacité\_kg (FCFA, contexte Togo 2024) |
| Typologies clients | Boutiques, supermarchés, restaurants, grossistes |
| Créneaux livraison | Plages horaires adaptées aux habitudes commerciales |

## Limites connues

- Les données sont simulées : les profils de demande et de trafic reflètent les paramètres du générateur,
  pas des mesures terrain.
- Le trafic est modélisé par un coefficient horaire fixe, sans prédiction par apprentissage automatique.
- L'optimiseur est une méthode approchée : les résultats varient légèrement avec le temps de calcul.
- Un calcul planifie au plus 60 commandes ; un jour plus chargé se traite par quartier.
- La méthode naïve de référence ignore volontairement les créneaux : une part du gain mesuré sur les retards en découle.

## Dépannage

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| `No module named 'tourneo'` | Installation éditable absente ou dossier déplacé | `pip install -e .` depuis la racine du projet |
| Graphique indisponible dans l'application | Indicateurs non calculés | `python -m tourneo.analysis` |
| Avertissement « Service de routes indisponible » | OSRM injoignable | Vérifier la connexion ; le calcul continue en estimation à vol d'oiseau |
| `Aucune commande retenue pour cette date` | Date absente des données générées | Choisir un jour présent dans la période générée |

## Contrat de données

Spécification complète : [`docs/contrat.md`](docs/contrat.md)

Les fichiers produits par le module 2 et les fonctions `optimiser()` et `simuler()` y sont décrits
(sections 5 à 7).