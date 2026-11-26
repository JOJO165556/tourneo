import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

from tourneo.optim.api import optimiser
from tourneo.optim.donnees import charger_clients, charger_flotte
from tourneo import dashboard
from tourneo.feuilles_route import generer_pdf
from tourneo.optim.scenarios import simuler

PALETTE = [[230, 25, 75], [60, 180, 75], [0, 130, 200], [245, 130, 48], [145, 30, 180], [70, 200, 200], [240, 50, 230], [128, 128, 0]]
MODES = {"Équilibré": "equilibre", "Ponctuel": "ponctuel", "Coût minimal (ignore les créneaux)": "economique"}
FOND = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
OSRM_ROUTE = "https://router.project-osrm.org/route/v1/driving/"
FIGURES = [
    ("Volume par quartier", "fig_volume_quartier"),
    ("Taux de commandes urgentes par quartier", "fig_taux_urgent_quartier"),
    ("Demande par jour", "fig_demande_jour"),
    ("Demande par heure", "fig_demande_heure"),
    ("Évolution mensuelle", "fig_evolution_mois"),
    ("Top 20 clients", "fig_top_clients"),
    ("Carte de chaleur jour et heure", "fig_heatmap_jour_heure"),
]
MESURES = [
    ("Distance (km)", "km"),
    ("Coût de transport (FCFA)", "cout_fcfa"),
    ("Minutes de retard", "retard_min"),
    ("Commandes non livrées", "non_livrees"),
]

st.set_page_config(page_title="OptiLomé", layout="wide")
st.title("OptiLomé")

clients = charger_clients()
_, depot = charger_flotte()
DEPART = [float(depot["lon"]), float(depot["lat"])]


def couleur(id_vehicule):
    return PALETTE[int(id_vehicule) % len(PALETTE)]


def construire_scenario(nom, id_client):
    if nom == "Panne d'un véhicule":
        return {"type": "panne"}
    if nom == "Commande urgente":
        return {"type": "urgente", "id_client": int(id_client)}
    if nom == "Embouteillage":
        return {"type": "embouteillage", "facteur": 1.8}
    if nom == "Créneaux plus serrés":
        return {"type": "creneaux", "facteur": 0.5}
    return None


def formater(valeur):
    return f"{valeur:,}".replace(",", " ")


@st.cache_data(show_spinner=False)
def tracer_route(points):
    trace = ";".join(f"{lon},{lat}" for lon, lat in points)
    try:
        reponse = requests.get(OSRM_ROUTE + trace, params={"overview": "full", "geometries": "geojson"}, timeout=15)
        reponse.raise_for_status()
        donnees = reponse.json()
        if donnees.get("code") == "Ok":
            return donnees["routes"][0]["geometry"]["coordinates"]
    except (requests.RequestException, KeyError, ValueError, IndexError):
        pass
    return [list(p) for p in points]


with st.sidebar:
    jour = st.date_input("Jour à planifier", value=pd.Timestamp("2026-10-15"))
    quartiers = st.multiselect("Quartiers (vide : tous)", sorted(clients["quartier"].unique()))
    mode = st.radio("Priorité", list(MODES))
    nom_scenario = st.selectbox("Scénario", ["Aucun", "Panne d'un véhicule", "Commande urgente", "Embouteillage", "Créneaux plus serrés"])
    id_client = st.number_input("Client de la commande urgente", value=int(clients["id_client"].iloc[0]), step=1)
    routes_reelles = st.checkbox("Tracés sur les routes (OSRM)", value=True)
    lancer = st.button("Calculer", type="primary")

onglet_plan, onglet_demande = st.tabs(["Planification", "Analyse de la demande"])

with onglet_plan:
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

        if comp.get("commandes_du_jour") is not None:
            st.caption(f"{comp['commandes_retenues']} commandes planifiées sur {comp['commandes_du_jour']} prévues ce jour-là.")
            if comp["commandes_retenues"] < comp["commandes_du_jour"]:
                st.info("Un calcul planifie au plus 60 commandes, les urgentes d'abord. Choisis un ou deux quartiers pour planifier les autres.")
        if comp.get("source_matrice") == "repli":
            st.warning("Service de routes indisponible : les distances et durées sont estimées à vol d'oiseau, majorées de 30 %. Les résultats sont approximatifs.")
        non_livrees = comp.get("non_livrees") or comp.get("non_livrees_apres")
        if non_livrees:
            st.error("Commandes non livrées : " + ", ".join(str(x) for x in non_livrees))

        groupes = list(table.sort_values("ordre").groupby("id_vehicule"))

        for colonne, (id_v, groupe) in zip(st.columns(len(groupes)), groupes):
            r, g, b = couleur(id_v)
            colonne.markdown(
                f"<span style='color:rgb({r},{g},{b});font-size:1.5em'>●</span> **Véhicule {id_v}**",
                unsafe_allow_html=True,
            )
            colonne.caption(
                f"{len(groupe)} arrêts, {groupe['quantite_kg'].sum():.0f} kg, {groupe['retard_min'].sum():.0f} min de retard"
            )
        st.caption("Point noir : dépôt. Les numéros indiquent l'ordre de passage.")

        trajets = []
        with st.spinner("Tracé des itinéraires"):
            for id_v, groupe in groupes:
                points_v = [DEPART] + groupe[["lon", "lat"]].values.tolist() + [DEPART]
                if routes_reelles:
                    chemin = tracer_route(tuple((round(x, 6), round(y, 6)) for x, y in points_v))
                else:
                    chemin = points_v
                trajets.append({"chemin": chemin, "couleur": couleur(id_v)})

        points = table.copy()
        points["couleur"] = points["id_vehicule"].map(couleur)
        points["heure"] = pd.to_datetime(points["heure_arrivee"]).dt.strftime("%H:%M")
        points["retard_min"] = points["retard_min"].round(0)
        points["numero"] = points["ordre"].astype(str)
        points = points[["lon", "lat", "couleur", "nom", "id_vehicule", "ordre", "numero", "heure", "retard_min"]]

        couches = [
            pdk.Layer("PathLayer", trajets, get_path="chemin", get_color="couleur", width_min_pixels=3),
            pdk.Layer(
                "ScatterplotLayer", points, get_position=["lon", "lat"], get_fill_color="couleur",
                get_radius=60, radius_min_pixels=9, radius_max_pixels=16, pickable=True,
            ),
            pdk.Layer(
                "TextLayer", points, get_position=["lon", "lat"], get_text="numero", get_size=13,
                get_color=[255, 255, 255], get_alignment_baseline="'center'",
            ),
            pdk.Layer(
                "ScatterplotLayer", [{"lon": DEPART[0], "lat": DEPART[1]}], get_position=["lon", "lat"],
                get_fill_color=[0, 0, 0], get_radius=100, radius_min_pixels=11,
            ),
        ]
        vue = pdk.data_utils.compute_view([DEPART] + points[["lon", "lat"]].values.tolist())
        infobulle = {"text": "{nom}\nVéhicule {id_vehicule}, arrêt {ordre}\nArrivée {heure}, retard {retard_min} min"}
        st.pydeck_chart(pdk.Deck(layers=couches, initial_view_state=vue, map_style=FOND, tooltip=infobulle))

        st.dataframe(table)
        st.download_button("Exporter en CSV", table.to_csv(index=False).encode("utf-8"), "feuille_de_route.csv", "text/csv")
        st.download_button("Exporter les feuilles de route (PDF)", generer_pdf(table, comp), "feuilles_de_route.pdf", "application/pdf")


def afficher_figure(libelle, nom_fonction):
    st.subheader(libelle)
    try:
        st.plotly_chart(getattr(dashboard, nom_fonction)(), key=nom_fonction)
    except Exception as erreur:
        st.warning(f"Graphique indisponible ({erreur}). Lance d'abord : python -m tourneo.analysis")


with onglet_demande:
    st.caption("Analyse de l'historique des commandes (module 1).")
    for gauche, droite in [(0, 1), (2, 3), (4, 5)]:
        for colonne, position in zip(st.columns(2), (gauche, droite)):
            with colonne:
                afficher_figure(*FIGURES[position])
    afficher_figure(*FIGURES[6])