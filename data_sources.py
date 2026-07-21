"""
Connecteurs de données pour l'outil de prospection.

Choix assumé : aucune fonction ici ne scrape LinkedIn ou une autre
plateforme qui l'interdit dans ses conditions d'utilisation. LinkedIn a
attaqué en justice (et fait fermer) plusieurs services qui scrapaient ses
profils, même en prétendant ne récupérer que des données publiques - le
risque (bannissement de compte, poursuites) n'en vaut pas la peine.

À la place :
- France  -> recherche-entreprises.api.gouv.fr (officiel, gratuit, sans clé)
- Portugal -> nif.pt (gratuit, nécessite une clé API gratuite sur nif.pt)
- Actualités -> flux RSS Google News (gratuit, sans clé)
- Contacts -> génération d'un lien de recherche LinkedIn (recherche manuelle,
  100% légale) + hypothèses d'email non vérifiées
"""
from typing import Optional, List, Dict
from urllib.parse import quote_plus

import requests
import feedparser

FRANCE_API = "https://recherche-entreprises.api.gouv.fr/search"
PORTUGAL_API = "https://www.nif.pt/api/"

# Codes officiels INSEE pour la tranche d'effectif salarié
TRANCHE_EFFECTIF_FR = {
    "NN": "Non renseigné", "00": "0 salarié", "01": "1 à 2 salariés",
    "02": "3 à 5 salariés", "03": "6 à 9 salariés", "11": "10 à 19 salariés",
    "12": "20 à 49 salariés", "21": "50 à 99 salariés", "22": "100 à 199 salariés",
    "31": "200 à 249 salariés", "32": "250 à 499 salariés", "41": "500 à 999 salariés",
    "42": "1 000 à 1 999 salariés", "51": "2 000 à 4 999 salariés",
    "52": "5 000 à 9 999 salariés", "53": "10 000 salariés et plus",
}


NAF_SECTIONS = {
    "A": "Agriculture, sylviculture et pêche",
    "B": "Industries extractives",
    "C": "Industrie manufacturière",
    "D": "Énergie (électricité, gaz, vapeur)",
    "E": "Eau, assainissement, déchets",
    "F": "Construction",
    "G": "Commerce, réparation automobile",
    "H": "Transports et entreposage",
    "I": "Hébergement et restauration",
    "J": "Information et communication",
    "K": "Activités financières et d'assurance",
    "L": "Activités immobilières",
    "M": "Activités spécialisées, scientifiques et techniques",
    "N": "Services administratifs et de soutien",
    "O": "Administration publique",
    "P": "Enseignement",
    "Q": "Santé humaine et action sociale",
    "R": "Arts, spectacles et activités récréatives",
    "S": "Autres activités de services",
    "T": "Activités des ménages employeurs",
    "U": "Activités extra-territoriales",
}

REGIONS_FR = {
    "11": "Île-de-France", "24": "Centre-Val de Loire", "27": "Bourgogne-Franche-Comté",
    "28": "Normandie", "32": "Hauts-de-France", "44": "Grand Est",
    "52": "Pays de la Loire", "53": "Bretagne", "75": "Nouvelle-Aquitaine",
    "76": "Occitanie", "84": "Auvergne-Rhône-Alpes", "93": "Provence-Alpes-Côte d'Azur",
    "94": "Corse",
}

# code -> (effectif_min, effectif_max) ; max=None signifie "et plus"
TRANCHE_EFFECTIF_BOUNDS = {
    "00": (0, 0), "01": (1, 2), "02": (3, 5), "03": (6, 9), "11": (10, 19),
    "12": (20, 49), "21": (50, 99), "22": (100, 199), "31": (200, 249),
    "32": (250, 499), "41": (500, 999), "42": (1000, 1999), "51": (2000, 4999),
    "52": (5000, 9999), "53": (10000, None),
}


def _parse_france_result(r: Dict) -> Dict:
    """Factorise le parsing d'un résultat brut de l'API vers notre format
    interne commun (utilisé par la recherche par nom et par critères)."""
    siege = r.get("siege") or {}
    effectif_code = r.get("tranche_effectif_salarie")
    return {
        "pays": "France",
        "nom": r.get("nom_complet"),
        "siren": r.get("siren"),
        "siret_siege": siege.get("siret"),
        "adresse": siege.get("adresse"),
        "ville": siege.get("libelle_commune"),
        "activite_naf": r.get("activite_principale"),
        "section_activite": r.get("section_activite_principale"),
        "categorie_entreprise": r.get("categorie_entreprise"),
        "date_creation": r.get("date_creation"),
        "effectif_code": effectif_code,
        "effectif_libelle": TRANCHE_EFFECTIF_FR.get(effectif_code, "Inconnu"),
        "dirigeants": [
            {
                "nom": f"{d.get('prenoms', '')} {d.get('nom', '')}".strip(),
                "role": d.get("qualite"),
            }
            for d in (r.get("dirigeants") or [])
            if d.get("type_dirigeant") == "personne physique"
        ],
        "finances": r.get("finances") or {},
        "tva": (r.get("tva") or [None])[0],
        "source": "recherche-entreprises.api.gouv.fr (officiel, gratuit, sans clé)",
    }


def search_company_france(name: str) -> Optional[Dict]:
    """Recherche une entreprise française : identité, effectif, dirigeants
    (personnes physiques) et finances récentes, via l'API publique gratuite
    et sans authentification recherche-entreprises.api.gouv.fr (agrège
    Sirene/INSEE + RNE/INPI, mise à jour hebdomadaire)."""
    try:
        resp = requests.get(FRANCE_API, params={"q": name, "per_page": 1}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        return _parse_france_result(results[0])
    except requests.RequestException as e:
        return {"erreur": str(e)}


def search_companies_by_criteria(
    sector: Optional[str] = None,
    naf_code: Optional[str] = None,
    region: Optional[str] = None,
    departement: Optional[str] = None,
    categorie_entreprise: Optional[str] = None,
    keyword: Optional[str] = None,
    effectif_min: Optional[int] = None,
    effectif_max: Optional[int] = None,
    max_results: int = 20,
) -> List[Dict]:
    """Recherche « en entonnoir » : liste les entreprises françaises actives
    correspondant à des critères (secteur, localisation, taille...), via la
    même API officielle et gratuite. L'effectif est filtré côté client car
    l'API ne filtre que par tranche exacte, pas par seuil min/max."""
    params: Dict = {"per_page": min(max_results, 25), "etat_administratif": "A"}
    if keyword:
        params["q"] = keyword
    if naf_code:
        params["code_naf"] = naf_code  # ex: "62.01Z" - plus précis qu'une section
    elif sector:
        params["section_activite_principale"] = sector
    if region:
        params["region"] = region
    if departement:
        params["departement"] = departement
    if categorie_entreprise:
        params["categorie_entreprise"] = categorie_entreprise

    try:
        resp = requests.get(FRANCE_API, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except requests.RequestException as e:
        return [{"erreur": str(e)}]

    parsed = [_parse_france_result(r) for r in results]

    if effectif_min or effectif_max:
        def _dans_bornes(entreprise: Dict) -> bool:
            bounds = TRANCHE_EFFECTIF_BOUNDS.get(entreprise.get("effectif_code"))
            if not bounds:
                return False
            lo, hi = bounds
            if effectif_min and (hi if hi is not None else lo) < effectif_min:
                return False
            if effectif_max and lo > effectif_max:
                return False
            return True
        parsed = [e for e in parsed if _dans_bornes(e)]

    return parsed


def search_company_portugal(name: str, api_key: Optional[str] = None) -> Optional[Dict]:
    """Recherche une entreprise portugaise via l'API gratuite de nif.pt.
    Nécessite une clé API gratuite (inscription sur nif.pt/contactos/api/).
    Sans clé : renvoie un lien de recherche manuelle en secours, car nif.pt
    expose moins de données ouvertes que le registre français (pas de
    dirigeants nommés en accès gratuit à ce jour)."""
    if not api_key:
        return {
            "pays": "Portugal",
            "nom": name,
            "manuel_requis": True,
            "lien_recherche": f"https://www.nif.pt/?q={quote_plus(name)}",
            "note": ("Clé API nif.pt absente : ajoute NIF_PT_API_KEY (gratuite, "
                     "inscription sur nif.pt/contactos/api/) pour les données "
                     "automatiques, ou utilise le lien ci-dessus."),
        }
    try:
        resp = requests.get(PORTUGAL_API, params={"q": name, "key": api_key}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result") or {}
        place = result.get("place") or {}
        return {
            "pays": "Portugal",
            "nom": result.get("name", name),
            "nif": result.get("nif"),
            "adresse": place.get("address"),
            "atividade_cae": result.get("cae"),
            "estrutura": result.get("structure") or {},
            "contacts": result.get("contacts") or {},
            "dirigeants": [],  # non disponible gratuitement pour le Portugal
            "finances": {},  # IES/comptes non disponibles gratuitement
            "source": "nif.pt (gratuit avec clé API)",
        }
    except requests.RequestException as e:
        return {"erreur": str(e)}


def search_news(company_name: str, country: str = "FR", max_items: int = 8) -> List[Dict]:
    """Veille médiatique via le flux RSS gratuit de Google News (aucune clé)."""
    lang_map = {"FR": ("fr", "FR"), "PT": ("pt-PT", "PT")}
    hl, gl = lang_map.get(country, ("fr", "FR"))
    hl_short = hl.split("-")[0]
    url = (
        f"https://news.google.com/rss/search?q={quote_plus(company_name)}"
        f"&hl={hl}&gl={gl}&ceid={gl}:{hl_short}"
    )
    feed = feedparser.parse(url)
    return [
        {
            "titre": e.get("title", ""),
            "source": (e.get("source") or {}).get("title", ""),
            "date": e.get("published", ""),
            "lien": e.get("link", ""),
        }
        for e in feed.entries[:max_items]
    ]


def suggest_contact_leads(company_name: str, domain: Optional[str], target_role: str) -> Dict:
    """Pas de scraping LinkedIn : génère un lien de recherche pré-rempli
    (recherche manuelle, 100% conforme aux CGU) et des hypothèses d'email
    à vérifier avant tout envoi."""
    li_query = quote_plus(f"{target_role} {company_name}")
    result = {
        "lien_recherche_linkedin": f"https://www.linkedin.com/search/results/people/?keywords={li_query}",
        "emails_hypothetiques": [],
        "note": "",
    }
    if domain:
        domain = domain.strip().lower().lstrip("@")
        result["emails_hypothetiques"] = [
            f"prenom.nom@{domain}",
            f"p.nom@{domain}",
            f"prenom@{domain}",
        ]
        result["note"] = (
            "Hypothèses non vérifiées, basées sur des formats courants - "
            "à confirmer avant tout envoi (vérification manuelle ou outil dédié)."
        )
    return result
