# Contrat de données

Conventions communes de l'équipe : noms de colonnes et fichiers en minuscules,
sans accents ; coordonnées en WGS84 (EPSG:4326) ; dates et heures au format ISO
8601 ; identifiants entiers.

## 1. `clients.parquet`

| Colonne     | Type     | Contenu                                        |
| ----------- | -------- | ---------------------------------------------- |
| id_client   | entier   | Identifiant unique                             |
| nom         | texte    | Nom du point de vente                          |
| quartier    | texte    | Quartier de Lomé                              |
| lat         | décimal | Latitude WGS84                                 |
| lon         | décimal | Longitude WGS84                                |
| type_client | texte    | boutique, supermarche, restaurant ou grossiste |

## 2. `commandes/` (répertoire Parquet partitionné)

Partitionné par mois (`commandes/mois=AAAA-MM/*.parquet`, partitionnement
Hive). `date_livraison` est stockée en `date et heure` à minuit : le jour
calendaire porte le sens métier (jour à planifier).

| Colonne        | Type          | Contenu                                                           |
| -------------- | ------------- | ----------------------------------------------------------------- |
| id_commande    | entier        | Identifiant unique                                                |
| id_client      | entier        | Doit exister dans `clients`                                     |
| date_commande  | date et heure | Moment de la commande (analyse par heure)                         |
| date_livraison | date et heure | Jour de livraison demandé, stocké à minuit (jour à planifier) |
| quantite_kg    | décimal      | Charge de la commande, strictement > 0                            |
| creneau_debut  | date et heure | Début de la fenêtre de livraison, le jour de `date_livraison` |
| creneau_fin    | date et heure | Fin de la fenêtre, `> creneau_debut`, même jour               |
| urgente        | entier        | 0 ou 1                                                            |

## 3. `vehicules.csv`

| Colonne     | Type     | Contenu                      |
| ----------- | -------- | ---------------------------- |
| id_vehicule | entier   | Identifiant unique           |
| nom         | texte    | Libellé du véhicule        |
| capacite_kg | décimal | Charge maximale              |
| cout_km     | décimal | Coût au kilomètre, en FCFA |
| disponible  | entier   | 0 ou 1                       |

## 4. `depot.csv`

| Colonne  | Type     | Contenu         |
| -------- | -------- | --------------- |
| id_depot | entier   | Identifiant     |
| nom      | texte    | Nom du dépôt  |
| lat      | décimal | Latitude WGS84  |
| lon      | décimal | Longitude WGS84 |
