"""
Outil de prospection B2B - France & Portugal.

Sources 100% publiques et gratuites. Pas de scraping LinkedIn : voir
data_sources.py pour le détail des connecteurs et le raisonnement derrière
ce choix (LinkedIn/Microsoft a fait fermer plusieurs services de scraping
en 2025, même ceux qui prétendaient ne récupérer que des données publiques).

Lancement : streamlit run app.py
"""
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # no-op si .env absent (ex: sur Streamlit Cloud, où les secrets
                # sont déjà injectés dans os.environ)

from data_sources import (
    search_company_france,
    search_company_portugal,
    search_companies_by_criteria,
    search_news,
    suggest_contact_leads,
    NAF_SECTIONS,
    REGIONS_FR,
)
from ai_strategy import generate_prospecting_strategy

st.set_page_config(page_title="Outil de prospection", page_icon="🎯", layout="wide")

st.title("🎯 Outil de prospection B2B")
st.caption(
    "France & Portugal · sources publiques et gratuites uniquement · "
    "aucun scraping LinkedIn (voir le README)."
)

# --- Barre latérale : configuration et offre du vendeur -------------------
with st.sidebar:
    st.header("Configuration")
    anthropic_key = st.text_input(
        "Clé API Anthropic", type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="https://console.anthropic.com/ - nécessaire pour la génération IA.",
    )
    nif_pt_key = st.text_input(
        "Clé API nif.pt (optionnelle)", type="password",
        value=os.environ.get("NIF_PT_API_KEY", ""),
        help="https://www.nif.pt/contactos/api/ - pour l'enrichissement auto Portugal.",
    )
    st.divider()
    st.subheader("Ton offre")
    offer_description = st.text_area(
        "Que vends-tu ?", height=120,
        placeholder="Ex : logiciel de gestion des notes de frais pour PME de 20 à 200 salariés...",
    )
    target_role = st.text_input(
        "Poste visé chez le prospect",
        placeholder="Ex : Directeur Administratif et Financier",
    )

# --- Recherche entreprise ---------------------------------------------------
tab_nom, tab_criteres = st.tabs(["🔎 Recherche par nom", "🧭 Recherche par critères (France)"])

with tab_nom:
    col1, col2 = st.columns([3, 1])
    with col1:
        company_name = st.text_input("Nom de l'entreprise à prospecter")
    with col2:
        country = st.selectbox("Pays", ["France", "Portugal"])

    if st.button("Analyser l'entreprise", type="primary", key="btn_nom"):
        if not company_name:
            st.warning("Entre un nom d'entreprise.")
        else:
            with st.spinner("Récupération des données publiques..."):
                if country == "France":
                    company = search_company_france(company_name)
                    news = search_news(company_name, country="FR")
                else:
                    company = search_company_portugal(company_name, api_key=nif_pt_key or None)
                    news = search_news(company_name, country="PT")

            if not company:
                st.error("Aucune entreprise trouvée avec ce nom. Essaie le nom légal complet.")
                st.session_state.pop("company", None)
            elif company.get("erreur"):
                st.error(f"Erreur lors de la récupération des données : {company['erreur']}")
            else:
                st.session_state["company"] = company
                st.session_state["news"] = news
                st.session_state["company_name"] = company.get("nom") or company_name

with tab_criteres:
    st.caption(
        "Basé sur les données ouvertes françaises (recherche-entreprises.api.gouv.fr). "
        "Le Portugal n'a pas d'équivalent gratuit filtrable à ce jour - voir le README."
    )
    fc1, fc2 = st.columns(2)
    with fc1:
        sector_label = st.selectbox("Secteur d'activité", ["(Tous)"] + list(NAF_SECTIONS.values()))
        region_label = st.selectbox("Région", ["(Toutes)"] + list(REGIONS_FR.values()))
    with fc2:
        naf_precis = st.text_input("Code NAF précis (optionnel, prioritaire sur le secteur)", placeholder="ex : 62.01Z")
        departement = st.text_input("Département (optionnel)", placeholder="ex : 75 ou 75,92,93")
    fc3, fc4 = st.columns(2)
    with fc3:
        effectif_min = st.number_input("Effectif minimum", min_value=0, value=0, step=10)
    with fc4:
        effectif_max = st.number_input("Effectif maximum (0 = pas de plafond)", min_value=0, value=0, step=10)
    keyword = st.text_input("Mot-clé dans le nom (optionnel)", placeholder="ex : conseil")

    if st.button("Rechercher les entreprises correspondantes", type="primary", key="btn_criteres"):
        sector_code = None
        for code, label in NAF_SECTIONS.items():
            if label == sector_label:
                sector_code = code
        region_code = None
        for code, label in REGIONS_FR.items():
            if label == region_label:
                region_code = code

        with st.spinner("Recherche en cours..."):
            resultats = search_companies_by_criteria(
                sector=sector_code,
                naf_code=naf_precis or None,
                region=region_code,
                departement=departement or None,
                keyword=keyword or None,
                effectif_min=effectif_min or None,
                effectif_max=effectif_max or None,
                max_results=25,
            )

        if resultats and resultats[0].get("erreur"):
            st.error(f"Erreur : {resultats[0]['erreur']}")
            st.session_state.pop("funnel_results", None)
        elif not resultats:
            st.warning("Aucune entreprise ne correspond à ces critères - essaie d'élargir la recherche.")
            st.session_state.pop("funnel_results", None)
        else:
            st.session_state["funnel_results"] = resultats

    if st.session_state.get("funnel_results"):
        resultats = st.session_state["funnel_results"]
        st.success(f"{len(resultats)} entreprise(s) trouvée(s) (limité à 25 par recherche).")
        st.dataframe(
            [
                {
                    "Nom": e.get("nom"),
                    "Ville": e.get("ville") or "—",
                    "Effectif": e.get("effectif_libelle"),
                    "Catégorie": e.get("categorie_entreprise") or "—",
                }
                for e in resultats
            ],
            use_container_width=True,
            hide_index=True,
        )
        noms = [e.get("nom") for e in resultats]
        choix = st.selectbox("Choisir une entreprise à analyser en détail", noms, key="choix_funnel")
        if st.button("Analyser cette entreprise", key="btn_analyser_funnel"):
            entreprise_choisie = next(e for e in resultats if e.get("nom") == choix)
            st.session_state["company"] = entreprise_choisie
            st.session_state["company_name"] = entreprise_choisie.get("nom")
            with st.spinner("Récupération des actualités..."):
                st.session_state["news"] = search_news(entreprise_choisie.get("nom"), country="FR")

# --- Affichage des résultats -------------------------------------------------
if "company" in st.session_state:
    company = st.session_state["company"]
    news = st.session_state.get("news", [])
    display_name = company.get("nom") or st.session_state.get("company_name", "")

    st.subheader(f"📋 {display_name}")

    if company.get("manuel_requis"):
        st.info(company.get("note", ""))
        st.link_button("Rechercher manuellement sur nif.pt", company["lien_recherche"])
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Identifiant", company.get("siren") or company.get("nif") or "—")
        c2.metric("Effectif", company.get("effectif_libelle") or "non renseigné")

        finances = company.get("finances") or {}
        derniere_annee = max(finances.keys()) if finances else None
        ca = finances.get(derniere_annee, {}).get("ca") if derniere_annee else None
        ca_txt = f"{ca:,} €".replace(",", " ") if ca else "—"
        c3.metric(f"CA {derniere_annee or ''}".strip(), ca_txt)

        dirigeants = company.get("dirigeants") or []
        if dirigeants:
            st.write("**Dirigeants identifiés (source officielle) :**")
            for d in dirigeants:
                st.write(f"- {d['nom']} — {d['role']}")
        elif company.get("pays") == "Portugal":
            st.caption(
                "Pas de dirigeants nommés disponibles gratuitement pour le "
                "Portugal - utilise la piste de contact ci-dessous."
            )

        with st.expander("Détails complets (JSON brut)"):
            st.json(company)

    st.subheader("📰 Actualités récentes")
    if news:
        for n in news:
            st.write(f"- [{n['titre']}]({n['lien']}) · {n.get('source', '')}")
    else:
        st.caption("Aucune actualité récente trouvée pour ce nom.")

    st.subheader("🔍 Piste de contact")
    st.caption(
        "Pas de scraping LinkedIn : un lien de recherche pré-rempli (recherche "
        "manuelle, 100% conforme aux CGU) + des hypothèses d'email à vérifier."
    )
    domain = st.text_input("Domaine email de l'entreprise (si connu)", placeholder="exemple.fr")
    if target_role:
        leads = suggest_contact_leads(display_name, domain or None, target_role)
        st.link_button(f"Chercher « {target_role} » sur LinkedIn", leads["lien_recherche_linkedin"])
        if leads.get("emails_hypothetiques"):
            st.caption("Hypothèses d'email : " + ", ".join(leads["emails_hypothetiques"]))
            st.caption(leads.get("note", ""))
    else:
        st.caption("Renseigne le poste visé dans la barre latérale pour générer le lien de recherche LinkedIn.")

    st.subheader("✉️ Stratégie de prospection générée par IA")
    if st.button("Générer l'email et le blueprint d'appel"):
        if not offer_description:
            st.warning("Décris ton offre dans la barre latérale pour une génération pertinente.")
        else:
            try:
                with st.spinner("Génération en cours..."):
                    strategy = generate_prospecting_strategy(
                        company_data=company,
                        news=news,
                        offer_description=offer_description,
                        target_role=target_role or "un décideur pertinent",
                        api_key=anthropic_key or None,
                    )
                st.markdown(strategy)
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Erreur lors de l'appel à l'API Claude : {e}")
