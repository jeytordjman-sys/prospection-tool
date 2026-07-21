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
    search_news,
    suggest_contact_leads,
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
col1, col2 = st.columns([3, 1])
with col1:
    company_name = st.text_input("Nom de l'entreprise à prospecter")
with col2:
    country = st.selectbox("Pays", ["France", "Portugal"])

if st.button("Analyser l'entreprise", type="primary"):
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
            st.session_state["company_name"] = company_name

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
