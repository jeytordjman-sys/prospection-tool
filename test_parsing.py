"""Test local du parsing avec une vraie réponse capturée de l'API
(recherche-entreprises.api.gouv.fr?q=ALUSAGE), sans appel réseau."""
import json
from unittest.mock import patch, MagicMock

import data_sources as ds

REAL_SAMPLE_RESPONSE = {
    "results": [
        {
            "siren": "919891770",
            "nom_complet": "ALUSAGE (AL)",
            "nom_raison_sociale": "ALUSAGE",
            "activite_principale": "70.22Z",
            "categorie_entreprise": "PME",
            "date_creation": "2022-08-01",
            "tranche_effectif_salarie": "01",
            "dirigeants": [
                {"nom": "DORNIER (DORNIER)", "prenoms": "CHRISTINE",
                 "qualite": "Président de SAS", "type_dirigeant": "personne physique"},
                {"nom": "JEUDY (JEUDY)", "prenoms": "NICOLAS ADRIEN DOMINIQUE",
                 "qualite": "Directeur Général", "type_dirigeant": "personne physique"},
            ],
            "finances": {"2024": {"ca": 112623, "resultat_net": 6046}},
            "tva": ["FR05919891770"],
            "siege": {"siret": "91989177000019", "adresse": "104 RUE BATTANT 25000 BESANCON"},
        }
    ]
}


def test_search_company_france():
    mock_resp = MagicMock()
    mock_resp.json.return_value = REAL_SAMPLE_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch("data_sources.requests.get", return_value=mock_resp) as mock_get:
        result = ds.search_company_france("ALUSAGE")

    assert result["nom"] == "ALUSAGE (AL)"
    assert result["siren"] == "919891770"
    assert result["effectif_libelle"] == "1 à 2 salariés"
    assert len(result["dirigeants"]) == 2
    assert result["dirigeants"][0]["nom"] == "CHRISTINE DORNIER (DORNIER)"
    assert result["dirigeants"][0]["role"] == "Président de SAS"
    assert result["finances"]["2024"]["ca"] == 112623
    assert result["tva"] == "FR05919891770"
    mock_get.assert_called_once()
    print("OK  search_company_france: parsing correct sur un vrai payload")


def test_search_company_france_no_result():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status.return_value = None
    with patch("data_sources.requests.get", return_value=mock_resp):
        result = ds.search_company_france("ENTREPRISE_QUI_N_EXISTE_PAS_XYZ")
    assert result is None
    print("OK  search_company_france: renvoie None si aucun résultat")


def test_suggest_contact_leads():
    leads = ds.suggest_contact_leads("Alusage", "alusage.fr", "Directeur Commercial")
    assert "linkedin.com/search" in leads["lien_recherche_linkedin"]
    assert "Directeur" in leads["lien_recherche_linkedin"] or "Commercial" in leads["lien_recherche_linkedin"]
    assert leads["emails_hypothetiques"] == [
        "prenom.nom@alusage.fr", "p.nom@alusage.fr", "prenom@alusage.fr",
    ]
    print("OK  suggest_contact_leads: lien LinkedIn + hypothèses email corrects")
    print("    ->", leads["lien_recherche_linkedin"])


def test_search_company_portugal_no_key():
    result = ds.search_company_portugal("Alguma Empresa")
    assert result["manuel_requis"] is True
    assert "nif.pt" in result["lien_recherche"]
    print("OK  search_company_portugal: lien manuel si pas de clé API")


def test_news_url_construction():
    # On vérifie juste que feedparser reçoit une URL bien formée (pas d'appel réel)
    with patch("data_sources.feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[])
        ds.search_news("Alusage", country="FR")
        called_url = mock_parse.call_args[0][0]
    assert called_url.startswith("https://news.google.com/rss/search?q=Alusage")
    assert "hl=fr" in called_url and "gl=FR" in called_url
    print("OK  search_news: URL Google News RSS bien construite ->", called_url)


MULTI_RESULT_RESPONSE = {
    "results": [
        {
            "siren": "111111111", "nom_complet": "PETITE BOITE TECH", "categorie_entreprise": "PME",
            "section_activite_principale": "J", "tranche_effectif_salarie": "12",  # 20-49
            "siege": {"libelle_commune": "Lyon"}, "dirigeants": [], "finances": {},
        },
        {
            "siren": "222222222", "nom_complet": "GROS GROUPE TECH", "categorie_entreprise": "GE",
            "section_activite_principale": "J", "tranche_effectif_salarie": "53",  # 10000+
            "siege": {"libelle_commune": "Paris"}, "dirigeants": [], "finances": {},
        },
        {
            "siren": "333333333", "nom_complet": "BOITE SANS EFFECTIF CONNU", "categorie_entreprise": "PME",
            "section_activite_principale": "J", "tranche_effectif_salarie": "NN",
            "siege": {"libelle_commune": "Marseille"}, "dirigeants": [], "finances": {},
        },
    ]
}


def test_search_companies_by_criteria_params():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status.return_value = None
    with patch("data_sources.requests.get", return_value=mock_resp) as mock_get:
        ds.search_companies_by_criteria(sector="J", region="84", departement="69", keyword="conseil")
    params = mock_get.call_args.kwargs["params"]
    assert params["section_activite_principale"] == "J"
    assert params["region"] == "84"
    assert params["departement"] == "69"
    assert params["q"] == "conseil"
    assert params["etat_administratif"] == "A"
    print("OK  search_companies_by_criteria: paramètres envoyés à l'API corrects ->", params)


def test_search_companies_by_criteria_naf_precis_prioritaire():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status.return_value = None
    with patch("data_sources.requests.get", return_value=mock_resp) as mock_get:
        ds.search_companies_by_criteria(sector="J", naf_code="62.01Z")
    params = mock_get.call_args.kwargs["params"]
    assert params["code_naf"] == "62.01Z"
    assert "section_activite_principale" not in params
    print("OK  search_companies_by_criteria: code NAF précis prioritaire sur le secteur")


def test_search_companies_by_criteria_filtre_effectif_client():
    mock_resp = MagicMock()
    mock_resp.json.return_value = MULTI_RESULT_RESPONSE
    mock_resp.raise_for_status.return_value = None
    with patch("data_sources.requests.get", return_value=mock_resp):
        # Sans filtre effectif : les 3 remontent
        tous = ds.search_companies_by_criteria(sector="J")
        assert len(tous) == 3
        # Avec un plancher de 100 : seule GROS GROUPE TECH (10000+) doit rester
        gros_seulement = ds.search_companies_by_criteria(sector="J", effectif_min=100)
        noms = [e["nom"] for e in gros_seulement]
        assert noms == ["GROS GROUPE TECH"]
        # Avec un plafond de 50 : seule PETITE BOITE TECH (20-49) doit rester
        petites_seulement = ds.search_companies_by_criteria(sector="J", effectif_max=50)
        noms2 = [e["nom"] for e in petites_seulement]
        assert noms2 == ["PETITE BOITE TECH"]
    print("OK  search_companies_by_criteria: filtre effectif min/max appliqué côté client")


if __name__ == "__main__":
    test_search_company_france()
    test_search_company_france_no_result()
    test_suggest_contact_leads()
    test_search_company_portugal_no_key()
    test_news_url_construction()
    test_search_companies_by_criteria_params()
    test_search_companies_by_criteria_naf_precis_prioritaire()
    test_search_companies_by_criteria_filtre_effectif_client()
    print("\nTous les tests sont passés.")
