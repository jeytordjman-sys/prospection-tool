"""
Génération de la stratégie de prospection via l'API Claude (Anthropic).

Nécessite une clé API Anthropic (https://console.anthropic.com/). Ce n'est
pas un abonnement : c'est facturé à l'usage, de l'ordre de quelques
centimes par génération pour ce cas d'usage (voir la tarification
officielle sur la console avant de lancer un gros volume).
"""
import os
import json
from typing import Optional, List, Dict

import anthropic

# Modèle recommandé pour ce cas d'usage (rédaction + raisonnement court).
# Voir https://docs.claude.com pour la liste à jour des modèles disponibles.
MODEL = "claude-sonnet-5"

PROMPT_TEMPLATE = """Tu es un assistant commercial B2B. Voici les informations \
publiques collectées sur une entreprise cible, et l'offre du vendeur qui \
souhaite la contacter.

DONNÉES ENTREPRISE (JSON) :
{context_json}

OFFRE DU VENDEUR :
{offer_description}

POSTE DU CONTACT VISÉ :
{target_role}

Rédige, en français et en Markdown, sans préambule :

1. Un email de prospection court (120 à 150 mots), personnalisé avec au \
moins un élément concret tiré des données ci-dessus (actualité récente, \
taille, secteur, dirigeant...), qui relie l'offre à un besoin plausible de \
cette entreprise. Ton direct, factuel, sans superlatifs creux.
2. Un "blueprint" d'appel de découverte : une accroche d'ouverture (une \
phrase), trois questions de qualification pertinentes pour ce profil \
d'entreprise, et deux objections probables avec une réponse courte pour \
chacune.

Si les données sont incomplètes (ex : pas d'actualité récente), dis-le \
explicitement plutôt que d'inventer un fait.
"""


def generate_prospecting_strategy(
    company_data: Dict,
    news: List[Dict],
    offer_description: str,
    target_role: str,
    api_key: Optional[str] = None,
) -> str:
    """Appelle l'API Claude avec le contexte agrégé et renvoie le texte
    généré (email + blueprint d'appel) en Markdown."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "Clé API Anthropic manquante. Renseigne la variable "
            "d'environnement ANTHROPIC_API_KEY ou saisis-la dans la barre "
            "latérale de l'application."
        )

    context = {"entreprise": company_data, "actualites_recentes": news[:5]}
    prompt = PROMPT_TEMPLATE.format(
        context_json=json.dumps(context, ensure_ascii=False, indent=2),
        offer_description=offer_description,
        target_role=target_role,
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")
