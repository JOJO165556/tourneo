from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MESURES = [
    ("Distance (km)", "km"),
    ("Coût de transport (FCFA)", "cout_fcfa"),
    ("Minutes de retard", "retard_min"),
    ("Commandes non livrées", "non_livrees"),
]
LARGEURS = [1.0 * cm, 5.2 * cm, 3.0 * cm, 1.8 * cm, 2.7 * cm, 1.8 * cm, 1.5 * cm]


def _styles():
    base = getSampleStyleSheet()
    titre = ParagraphStyle("titre", parent=base["Title"], fontName="Helvetica-Bold", fontSize=16, textColor=colors.black, spaceAfter=10)
    corps = ParagraphStyle("corps", parent=base["Normal"], fontName="Helvetica", fontSize=10, textColor=colors.black, leading=14)
    cellule = ParagraphStyle("cellule", parent=corps, fontSize=9, leading=11)
    entete = ParagraphStyle("entete", parent=cellule, fontName="Helvetica-Bold")
    return titre, corps, cellule, entete


def _grille():
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.black),
    ])


def _pied(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.black)
    canvas.drawCentredString(A4[0] / 2, 1.1 * cm, f"OptiLomé - page {doc.page}")
    canvas.restoreState()


def _heure(serie):
    return pd.to_datetime(serie).dt.strftime("%H:%M")


def _synthese(comparaison, titre, corps, cellule, entete):
    cle_ref, cle_opt, noms = ("naif", "optimise", ("Méthode naïve", "Optimisé")) if "naif" in comparaison else ("avant", "apres", ("Avant", "Après"))
    elements = [Paragraph("Plan de livraison", titre)]
    lignes = [f"<b>Jour :</b> {comparaison.get('date', '')}", f"<b>Priorité :</b> {comparaison.get('mode', '')}"]
    if "scenario" in comparaison:
        lignes.append(f"<b>Scénario :</b> {comparaison['scenario'].get('type', '')}")
    for ligne in lignes:
        elements.append(Paragraph(ligne, corps))
    elements.append(Spacer(1, 0.5 * cm))
    donnees = [[Paragraph("Indicateur", entete), Paragraph(noms[0], entete), Paragraph(noms[1], entete)]]
    for libelle, cle in MESURES:
        donnees.append([Paragraph(libelle, cellule), Paragraph(f"{comparaison[cle_ref][cle]:,}".replace(",", " "), cellule), Paragraph(f"{comparaison[cle_opt][cle]:,}".replace(",", " "), cellule)])
    tableau = Table(donnees, colWidths=[7 * cm, 4.5 * cm, 4.5 * cm])
    tableau.setStyle(_grille())
    elements.append(tableau)
    return elements


def _page_vehicule(id_vehicule, groupe, titre, corps, cellule, entete):
    groupe = groupe.sort_values("ordre")
    elements = [Paragraph(f"Feuille de route - Véhicule {id_vehicule}", titre)]
    resume = (
        f"<b>Arrêts :</b> {len(groupe)} &nbsp;&nbsp; <b>Charge :</b> {groupe['quantite_kg'].sum():.0f} kg "
        f"&nbsp;&nbsp; <b>Premier arrêt :</b> {_heure(groupe['heure_arrivee']).iloc[0]} "
        f"&nbsp;&nbsp; <b>Dernier arrêt :</b> {_heure(groupe['heure_arrivee']).iloc[-1]}"
    )
    elements.append(Paragraph(resume, corps))
    elements.append(Paragraph("Départ et retour au dépôt.", corps))
    elements.append(Spacer(1, 0.4 * cm))
    en_tetes = ["N°", "Client", "Quartier", "Quantité (kg)", "Créneau", "Arrivée", "Retard (min)"]
    donnees = [[Paragraph(t, entete) for t in en_tetes]]
    debuts = _heure(groupe["creneau_debut"]).tolist()
    fins = _heure(groupe["creneau_fin"]).tolist()
    arrivees = _heure(groupe["heure_arrivee"]).tolist()
    for i, (_, ligne) in enumerate(groupe.iterrows()):
        retard = round(float(ligne["retard_min"]))
        donnees.append([
            Paragraph(str(int(ligne["ordre"])), cellule),
            Paragraph(str(ligne["nom"]), cellule),
            Paragraph(str(ligne["quartier"]), cellule),
            Paragraph(f"{ligne['quantite_kg']:.0f}", cellule),
            Paragraph(f"{debuts[i]} - {fins[i]}", cellule),
            Paragraph(arrivees[i], cellule),
            Paragraph(f"<b>{retard}</b>" if retard > 0 else "0", cellule),
        ])
    tableau = Table(donnees, colWidths=LARGEURS, repeatRows=1)
    tableau.setStyle(_grille())
    elements.append(tableau)
    return elements


def generer_pdf(table, comparaison):
    titre, corps, cellule, entete = _styles()
    tampon = BytesIO()
    document = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm, title="Feuilles de route")
    elements = _synthese(comparaison, titre, corps, cellule, entete)
    for id_vehicule, groupe in table.groupby("id_vehicule"):
        elements.append(PageBreak())
        elements.extend(_page_vehicule(int(id_vehicule), groupe, titre, corps, cellule, entete))
    document.build(elements, onFirstPage=_pied, onLaterPages=_pied)
    return tampon.getvalue()
