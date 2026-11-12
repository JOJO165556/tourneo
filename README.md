# Tourneo : Pipeline logistique de Lomé

Génération, validation, stockage et analyse de données de livraison
simulées sur le Grand Lomé. Stack : Python, pandas, PyArrow, DuckDB, PySpark, Plotly.

<p>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/pandas-2.3-150458?logo=pandas&logoColor=white" alt="pandas" />
  <img src="https://img.shields.io/badge/pyarrow-26-FF8C42?logo=apacheparquet&logoColor=white" alt="PyArrow / Parquet" />
  <img src="https://img.shields.io/badge/duckdb-2.0-FEFF00?logo=duckdb&logoColor=black" alt="DuckDB" />
  <img src="https://img.shields.io/badge/pyspark-4.3-E25A1C?logo=apachespark&logoColor=white" alt="PySpark" />
  <img src="https://img.shields.io/badge/plotly-7.1-3F4F75?logo=plotly&logoColor=white" alt="Plotly" />
  <img src="https://img.shields.io/badge/java-17%2B-ED8B00?logo=openjdk&logoColor=white" alt="Java 17+" />
  <img src="https://img.shields.io/badge/pytest-9-0A9EDC?logo=pytest&logoColor=white" alt="pytest" />
</p>

## Prérequis

- Python 3.11+
- Java (versions 17, 21 ou 25 supportées par PySpark 4.3)

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

## Structure du projet

```
tourneo/
├── src/tourneo/          # package Python
│   ├── referentiel.py    # constantes géo/économiques (Lomé)
│   ├── generate.py       # générateur vectorisé par lots (PyArrow)
│   ├── validate.py       # validation du contrat de données
│   ├── storage.py        # DuckDB embarqué, partition pruning Hive
│   ├── analysis.py       # indicateurs PySpark + repli Pandas
│   └── dashboard.py      # visualisations Plotly
├── data/
│   ├── sample/           # jeu réduit de test (20 clients, 30 commandes)
│   ├── commandes/        # partitions Hive mois=AAAA-MM/
│   ├── indicateurs/      # parquet + html par indicateur
│   └── ...
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

## Contrat de données

Spécification complète : [`docs/contrat.md`](docs/contrat.md)
