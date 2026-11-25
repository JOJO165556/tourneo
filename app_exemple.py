import pandas as pd
import pydeck as pdk
import streamlit as st

from tourneo.optim.api import optimiser
from tourneo.optim.donnees import charger_clients, charger_flotte
from tourneo.optim.scenarios import simuler

PALETTE = [[230, 25, 75], [60, 180, 75], [0, 130, 200], [245, 130, 48], [145, 30, 180], [70, 200, 200], [240, 50, 230], [128, 128, 0]]
MODES = {"Équilibré": "equilibre", "Ponctuel": "ponctuel", "Coût minimal (ignore les créneaux)": "economique"}
FOND = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
MESURES = [
    ("Distance (km)", "km"),
    ("Coût de transport (FCFA)", "cout_fcfa"),
    ("Minutes de retard", "retard_min"),
    ("Commandes non livrées", "non_livrees"),
]

st.set_page_config(page_title="OptiLomé", layout="wide")
st.title("OptiLomé")

clients = charger_clients()
vehicules, depot = charger_flotte()


def construire_scenario(nom, id_client):
    if nom == "Panne d'un véhicule":
        return {"type": "panne"}
    if nom == "Commande urgente":
        return {"type": "urgente", "id_client": int(id_client)}
    if nom == "Embouteillage":
        return {"type": "embouteillage", "facteur": 1.8}
    return None


def formater(valeur):
    return f"{valeur:,}".replace(",", " ")


with st.sidebar:
    jour = st.date_input("Jour à planifier", value=pd.Timestamp("2026-10-15"))
    quartiers = st.multiselect("Quartiers (vide : tous)", sorted(clients["quartier"].unique()))
    mode = st.radio("Priorité", list(MODES))
    nom_scenario = st.selectbox("Scénario", ["Aucun", "Panne d'un véhicule", "Commande urgente", "Embouteillage"])
    id_client = st.number_input("Client de la commande urgente", value=int(clients["id_client"].iloc[0]), step=1)
    lancer = st.button("Calculer", type="primary")

if lancer:
    scenario = construire_scenario(nom_scenario, id_client)
    try:
        with st.spinner("Calcul en cours, environ 20 secondes"):
            if scenario is None:
                resultat = optimiser(str(jour), quartiers=quartiers or None, mode=MODES[mode])
            else:
                resultat = simuler(str(jour), scenario, quartiers=quartiers or None, mode=MODES[mode])
        st.session_state["resultat"] = resultat
    except ValueError as erreur:
        st.error(str(erreur))

if "resultat" in st.session_state:
    table, comp = st.session_state["resultat"]
    cle_ref, cle_opt = ("naif", "optimise") if "naif" in comp else ("avant", "apres")
    ref, opt = comp[cle_ref], comp[cle_opt]
    st.subheader("Méthode naïve contre optimisé" if cle_ref == "naif" else "Avant et après le scénario")
    for colonne, (libelle, cle) in zip(st.columns(4), MESURES):
        ecart = round(opt[cle] - ref[cle], 1)
        colonne.metric(libelle, formater(opt[cle]), delta=f"{ecart:+,}".replace(",", " "), delta_color="inverse")

    points = table.copy()
    points["couleur"] = points["id_vehicule"].map(lambda v: PALETTE[int(v) % len(PALETTE)])
    points["heure"] = pd.to_datetime(points["heure_arrivee"]).dt.strftime("%H:%M")
    points["retard_min"] = points["retard_min"].round(0)
    points = points[["lon", "lat", "couleur", "nom", "id_vehicule", "ordre", "heure", "retard_min"]]

    depart = [float(depot["lon"]), float(depot["lat"])]
    trajets = []
    for id_v, groupe in table.sort_values("ordre").groupby("id_vehicule"):
        chemin = [depart] + groupe[["lon", "lat"]].values.tolist() + [depart]
        trajets.append({"chemin": chemin, "couleur": PALETTE[int(id_v) % len(PALETTE)]})

    couches = [
        pdk.Layer("PathLayer", trajets, get_path="chemin", get_color="couleur", width_min_pixels=3),
        pdk.Layer("ScatterplotLayer", points, get_position=["lon", "lat"], get_fill_color="couleur", get_radius=90, pickable=True),
        pdk.Layer("ScatterplotLayer", [{"lon": depart[0], "lat": depart[1]}], get_position=["lon", "lat"], get_fill_color=[0, 0, 0], get_radius=180),
    ]
    vue = pdk.ViewState(latitude=depart[1], longitude=depart[0], zoom=11)
    infobulle = {"text": "{nom}\nVéhicule {id_vehicule}, arrêt {ordre}\nArrivée {heure}, retard {retard_min} min"}
    st.pydeck_chart(pdk.Deck(layers=couches, initial_view_state=vue, map_style=FOND, tooltip=infobulle))

    st.dataframe(table)
    st.download_button("Exporter en CSV", table.to_csv(index=False).encode("utf-8"), "feuille_de_route.csv", "text/csv")