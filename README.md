# Outil de prospection B2B — France & Portugal

Application Streamlit qui, à partir d'un nom d'entreprise, agrège des
données publiques (légales, financières, effectif, actualités) et génère
un email de prospection + un blueprint d'appel personnalisés via l'API
Claude.

## Pourquoi pas de scraping LinkedIn ?

Ce n'était pas prévu dans cette version, volontairement. En janvier 2025,
LinkedIn/Microsoft a poursuivi en justice Proxycurl — l'API de scraping
LinkedIn la plus utilisée du marché — pour avoir fait fonctionner des
centaines de milliers de faux comptes afin de collecter des données de
profil. Proxycurl a fermé en juillet 2025, alors même que l'entreprise
affirmait ne récupérer que des données publiques. Le risque (bannissement
de compte, exposition juridique) touche autant les gros services que les
projets perso automatisés.

À la place, l'outil s'appuie sur :

| Module | Source | Statut |
|---|---|---|
| Légal & financier (FR) | [recherche-entreprises.api.gouv.fr](https://recherche-entreprises.api.gouv.fr/docs/) | Gratuit, officiel, sans clé |
| Légal & financier (PT) | [nif.pt](https://www.nif.pt/) | Gratuit, clé API à demander |
| Effectif | Même source que ci-dessus (tranche officielle) | Gratuit |
| Veille médias | Flux RSS Google News | Gratuit, sans clé |
| Contact décisionnaire | Dirigeants officiels (FR) + lien de recherche LinkedIn pré-rempli + hypothèses d'email | Gratuit, recherche manuelle pour le nom précis d'un poste |
| Génération de la stratégie | API Claude (Anthropic) | Facturé à l'usage (pas d'abonnement) |

## Installation

```bash
git clone <ce-repo>
cd prospection-tool
python -m venv venv && source venv/bin/activate  # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # puis renseigne ANTHROPIC_API_KEY dedans
```

Tu peux aussi laisser `.env` vide et saisir les clés directement dans la
barre latérale de l'application au lancement.

## Lancement

```bash
streamlit run app.py
```

L'application s'ouvre sur `http://localhost:8501`.

## Tests

Un test rapide valide le parsing des données (avec un vrai payload capturé
de l'API française, sans appel réseau) :

```bash
python test_parsing.py
```

## Utilisation

1. Renseigne ton offre et le poste visé dans la barre latérale (utilisés
   par l'IA pour personnaliser l'email).
2. Entre le nom de l'entreprise ciblée et son pays, clique sur
   **Analyser l'entreprise**.
3. Consulte la fiche entreprise, les actualités récentes et la piste de
   contact générée.
4. Clique sur **Générer l'email et le blueprint d'appel**.

## Déployer en ligne (accessible depuis un téléphone)

Voir la section "Déploiement" du message de conversation pour la marche à
suivre complète (GitHub + Streamlit Community Cloud, gratuit). En résumé :
le code est poussé sur un dépôt GitHub, connecté à
[share.streamlit.io](https://share.streamlit.io), qui déploie l'app sur une
URL publique en quelques minutes. Les clés (`ANTHROPIC_API_KEY`,
`NIF_PT_API_KEY`) se collent au format TOML dans les "Secrets" de l'app
déployée - **jamais** dans le dépôt Git (`.env` et `.streamlit/secrets.toml`
sont dans `.gitignore`).

## Limites connues

- **Portugal** : nif.pt n'expose pas gratuitement les dirigeants nommés ni
  les comptes annuels (contrairement à la France). Pour aller plus loin,
  il faudra une source payante (ex. Informa D&B / eInforma) ou une
  recherche manuelle via [racius.com](https://www.racius.com/) ou le
  Portal da Justiça.
- **Effectif France** : la tranche INSEE est déclarative et peut être
  décalée d'un à deux ans par rapport à la réalité.
- **Emails hypothétiques** : ce sont des suppositions basées sur des
  formats courants (prénom.nom@, etc.), non vérifiées. À confirmer avant
  tout envoi.
- **Postes précis** (Head of Sales, DAF...) : au-delà du dirigeant légal,
  seule la recherche manuelle sur LinkedIn permet de trouver le bon nom -
  l'outil ne fait que générer le lien de recherche pré-rempli.

## Licence

MIT — voir [LICENSE](LICENSE). Fais-en ce que tu veux, contributions
bienvenues.
