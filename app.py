from html import escape

import folium
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
import streamlit.components.v1 as components
from folium.plugins import Fullscreen, MiniMap, PolyLineTextPath

from tourneo.optim.api import optimiser
from tourneo.optim.donnees import charger_clients, charger_flotte
from tourneo import dashboard
from tourneo.feuilles_route import generer_pdf
from tourneo.optim.scenarios import simuler

PALETTE = [[230, 25, 75], [60, 180, 75], [0, 130, 200], [245, 130, 48], [145, 30, 180], [70, 200, 200], [240, 50, 230], [128, 128, 0]]
MODES = {"Équilibré": "equilibre", "Ponctuel": "ponctuel", "Coût minimal (ignore les créneaux)": "economique"}
FONDS = {
    "Standard (coloré)": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    "Clair (sobre)": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
}
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
FONDS_FOLIUM = [
    ("OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "© OpenStreetMap"),
    ("Plan des rues (Esri)", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", "Tiles © Esri"),
    ("Satellite (Esri)", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "Imagerie © Esri, Maxar, Earthstar Geographics"),
    ("Clair (Esri)", "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", "Tiles © Esri"),
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


def couleur_ponctualite(retard):
    if retard < 1:
        return [60, 180, 75]
    if retard < 15:
        return [245, 160, 0]
    return [220, 30, 30]


def hex_couleur(rvb):
    return "#%02x%02x%02x" % tuple(int(x) for x in rvb)


def icone_numero(texte, teinte, groupe):
    taille = 36 if groupe else 28
    contenu = (
        f"<div style='background:{teinte};color:#fff;border:2px solid #fff;border-radius:50%;"
        f"width:{taille}px;height:{taille}px;line-height:{taille - 4}px;text-align:center;"
        f"font-weight:bold;font-size:{12 if groupe else 14}px;box-shadow:0 0 4px rgba(0,0,0,.6)'>{escape(str(texte))}</div>"
    )
    return folium.DivIcon(html=contenu, icon_size=(taille, taille), icon_anchor=(taille // 2, taille // 2))


def construire_carte_folium(points, trajets, depart):
    carte = folium.Map(location=[depart[1], depart[0]], zoom_start=13, tiles=None, control_scale=True)
    for i, (nom_fond, url, attribution) in enumerate(FONDS_FOLIUM):
        folium.TileLayer(tiles=url, attr=attribution, name=nom_fond, overlay=False, show=(i == 0)).add_to(carte)
    for trajet in trajets:
        teinte = hex_couleur(trajet["couleur"])
        trace = [[lat, lon] for lon, lat in trajet["chemin"]]
        ligne = folium.PolyLine(trace, color=teinte, weight=5, opacity=0.85)
        ligne.add_to(carte)
        PolyLineTextPath(ligne, "      ►      ", repeat=True, offset=6, attributes={"fill": teinte, "font-size": "16"}).add_to(carte)
    for _, p in points.iterrows():
        detail = (
            f"<b>{escape(str(p['nom']))}</b> ({escape(str(p['quartier']))})<br>"
            f"Véhicule {p['id_vehicule']}, arrêt(s) {p['ordre']}<br>"
            f"Créneau {p['creneau']}<br>Arrivée {p['heure']}, retard {p['retard']} min<br>"
            f"Quantité {p['quantite']} kg"
        )
        folium.Marker(
            [p["lat"], p["lon"]],
            icon=icone_numero(p["numero"], hex_couleur(p["couleur"]), bool(p["groupe"])),
            tooltip=folium.Tooltip(detail),
            popup=folium.Popup(detail, max_width=320),
        ).add_to(carte)
    etiquette = (
        "<div style='display:inline-block;background:#000;color:#fff;padding:3px 9px;border-radius:4px;font-weight:bold;"
        "font-size:12px;white-space:nowrap;transform:translate(-50%,-50%)'>DÉPÔT</div>"
    )
    folium.Marker([depart[1], depart[0]], icon=folium.DivIcon(html=etiquette, icon_size=(0, 0)), tooltip="Dépôt").add_to(carte)
    latitudes = list(points["lat"]) + [depart[1]]
    longitudes = list(points["lon"]) + [depart[0]]
    carte.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])
    Fullscreen().add_to(carte)
    MiniMap(toggle_display=True).add_to(carte)
    folium.LayerControl(collapsed=False).add_to(carte)
    return carte.get_root().render()


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
    nom_fond = st.selectbox("Fond de carte", list(FONDS))
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
            st.session_state["numero_calcul"] = st.session_state.get("numero_calcul", 0) + 1
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
        numero_calcul = st.session_state.get("numero_calcul", 0)

        colorer = st.radio("Colorer les arrêts par", ["Véhicule", "Ponctualité"], horizontal=True)
        type_carte = st.radio("Type de carte", ["Interactive (PyDeck)", "Détaillée (Folium)"], horizontal=True)

        visibles = []
        for colonne, (id_v, groupe) in zip(st.columns(len(groupes)), groupes):
            r, g, b = couleur(id_v)
            colonne.markdown(
                f"<span style='color:rgb({r},{g},{b});font-size:1.5em'>●</span> **Véhicule {id_v}**",
                unsafe_allow_html=True,
            )
            colonne.caption(
                f"{len(groupe)} arrêts, {groupe['quantite_kg'].sum():.0f} kg, {groupe['retard_min'].sum():.0f} min de retard"
            )
            if colonne.checkbox("Afficher", value=True, key=f"vehicule_{numero_calcul}_{id_v}"):
                visibles.append(id_v)

        if colorer == "Ponctualité":
            st.caption("Cercles : vert = à l'heure, orange = moins de 15 minutes de retard, rouge = 15 minutes ou plus. Les lignes gardent la couleur du véhicule.")
        st.caption("Point noir : dépôt. Les numéros indiquent l'ordre de passage ; un grand cercle à plusieurs numéros regroupe des passages au même endroit. Survole un arrêt pour voir le détail.")

        affiche = table[table["id_vehicule"].isin(visibles)]
        if affiche.empty:
            st.info("Aucun véhicule affiché : coche au moins un véhicule dans la légende.")
        else:
            trajets = []
            with st.spinner("Tracé des itinéraires"):
                for id_v, groupe in groupes:
                    if id_v not in visibles:
                        continue
                    points_v = [DEPART] + groupe[["lon", "lat"]].values.tolist() + [DEPART]
                    if routes_reelles:
                        chemin = tracer_route(tuple((round(x, 6), round(y, 6)) for x, y in points_v))
                    else:
                        chemin = points_v
                    trajets.append({"chemin": chemin, "couleur": couleur(id_v)})

            points = affiche.copy()
            debut_creneau = pd.to_datetime(points["creneau_debut"]).dt.strftime("%H:%M")
            fin_creneau = pd.to_datetime(points["creneau_fin"]).dt.strftime("%H:%M")
            points["heure"] = pd.to_datetime(points["heure_arrivee"]).dt.strftime("%H:%M")
            points["creneau"] = debut_creneau + " - " + fin_creneau
            points["retard"] = points["retard_min"].round(0).astype(int).astype(str)
            points["quantite"] = points["quantite_kg"].round(0).astype(int)
            points["numero"] = points["ordre"].astype(str)
            points["cle"] = (
                points["id_vehicule"].astype(str) + "_" + points["lat"].round(5).astype(str) + "_" + points["lon"].round(5).astype(str)
            )
            regroupes = []
            for _, g in points.sort_values("ordre").groupby("cle", sort=False):
                ligne = g.iloc[0].to_dict()
                ligne["numero"] = ",".join(g["numero"])
                ligne["ordre"] = ", ".join(g["numero"])
                ligne["heure"] = " / ".join(g["heure"])
                ligne["creneau"] = " / ".join(g["creneau"])
                ligne["retard"] = " / ".join(g["retard"])
                ligne["quantite"] = int(g["quantite"].sum())
                ligne["retard_max"] = float(g["retard_min"].max())
                ligne["groupe"] = len(g) > 1
                regroupes.append(ligne)
            points = pd.DataFrame(regroupes)
            if colorer == "Ponctualité":
                points["couleur"] = points["retard_max"].map(couleur_ponctualite)
            else:
                points["couleur"] = points["id_vehicule"].map(couleur)
            points = points[["lon", "lat", "couleur", "nom", "quartier", "id_vehicule", "ordre", "numero", "heure", "creneau", "retard", "quantite", "groupe"]]
            simples = points[~points["groupe"]]
            multiples = points[points["groupe"]]

            if type_carte == "Détaillée (Folium)":
                carte_html = construire_carte_folium(points, trajets, DEPART)
                components.html(carte_html, height=650)
                st.download_button("Exporter la carte (page web)", carte_html.encode("utf-8"), "carte_tournees.html", "text/html")
            else:
                couches = [pdk.Layer("PathLayer", trajets, get_path="chemin", get_color="couleur", width_min_pixels=4)]
                for jeu, rayon_min, rayon_max, taille in ((simples, 11, 18, 14), (multiples, 19, 26, 13)):
                    if jeu.empty:
                        continue
                    couches.append(pdk.Layer(
                        "ScatterplotLayer", jeu, get_position=["lon", "lat"], get_fill_color="couleur",
                        get_radius=60, radius_min_pixels=rayon_min, radius_max_pixels=rayon_max, pickable=True,
                    ))
                    couches.append(pdk.Layer(
                        "TextLayer", jeu, get_position=["lon", "lat"], get_text="numero", get_size=taille,
                        get_color=[255, 255, 255], get_alignment_baseline="'center'",
                    ))
                couches.append(pdk.Layer(
                    "ScatterplotLayer", [{"lon": DEPART[0], "lat": DEPART[1]}], get_position=["lon", "lat"],
                    get_fill_color=[0, 0, 0], get_radius=100, radius_min_pixels=13,
                ))
                couches.append(pdk.Layer(
                    "TextLayer", [{"lon": DEPART[0], "lat": DEPART[1], "texte": "DEPOT"}], get_position=["lon", "lat"],
                    get_text="texte", get_size=15, get_color=[0, 0, 0], get_pixel_offset=[0, -26],
                ))
                vue = pdk.data_utils.compute_view([DEPART] + points[["lon", "lat"]].values.tolist())
                infobulle = {
                    "text": "{nom} ({quartier})\nVéhicule {id_vehicule}, arrêt(s) {ordre}\nCréneau {creneau}\nArrivée {heure}, retard {retard} min\nQuantité {quantite} kg"
                }
                st.pydeck_chart(pdk.Deck(layers=couches, initial_view_state=vue, map_style=FONDS[nom_fond], tooltip=infobulle), height=650)

        st.dataframe(affiche)
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