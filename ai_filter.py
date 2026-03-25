"""ai_filter.py – scoring des articles via Claude API (Haiku pour l'efficacité coût)."""
from __future__ import annotations
import json
import re
import anthropic
from core import date_ts

MIN_SCORE  = 6    # seuil pour garder un article
BATCH_SIZE = 20   # articles par appel API


SYSTEM_PROMPT = """Tu es un expert en veille technologique et stratégique.
Tu notes des articles de 1 à 10 selon leur utilité pour :
1. Prendre des DÉCISIONS D'ORIENTATION TECHNOLOGIQUE (choisir des outils, plateformes, langages)
2. Identifier de NOUVEAUX PRODUITS À TESTER (IA, logiciels, hardware, services)
3. Anticiper des IMPACTS SUR LES PRIX ou le marché (énergie, immobilier belge, marchés boursiers)
4. Suivre les NOUVELLES RÈGLES ET RÉGLEMENTATIONS (Belgique, UE) avec effet concret

Grille de notation :
9-10 = Incontournable
  • Nouvelle fonctionnalité/modèle IA (Claude, GPT, Gemini, Mistral, open-source...)
  • Nouveau produit concret à tester immédiatement
  • Changement réglementaire Belgique/UE avec impact business direct et daté
  • Données chiffrées marché énergie, immobilier belge ou bourse avec tendance claire
  • Rupture technologique (nouveau paradigme, Raspberry Pi majeur, semi-conducteur clé)

7-8 = Recommandé
  • Comparatif ou benchmark d'outils avec conclusions actionnables
  • Mise à jour significative d'un produit existant (nouvelles fonctions, changement prix)
  • Analyse de marché avec chiffres et tendance exploitable
  • Nouveau standard/protocole avec adoption réelle

5-6 = Intérêt limité
  • Article général sans nouveauté concrète
  • Opinion/analyse sans données précises
  • Sujet connu rediscuté sans apport nouveau

1-4 = Non pertinent
  • Célébrités, sports, politique sans lien tech
  • Fait divers, catastrophe sans impact marché
  • Publicité déguisée, contenu sponsorisé évident
  • Article vague sans information actionnable"""


def score_and_filter(articles: list[dict], api_key: str) -> list[dict]:
    """Score tous les articles et retourne les plus pertinents triés."""
    client = anthropic.Anthropic(api_key=api_key)
    total = len(articles)
    print(f"  Scoring {total} articles par lot de {BATCH_SIZE}…")

    for i in range(0, total, BATCH_SIZE):
        batch = articles[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        try:
            _score_batch(client, batch)
            kept = sum(1 for a in batch if a.get("ai_score", 0) >= MIN_SCORE)
            print(f"    Lot {batch_num}/{total_batches} : {kept}/{len(batch)} conservés")
        except Exception as e:
            print(f"    Lot {batch_num}/{total_batches} erreur : {e} — score neutre appliqué")
            for a in batch:
                a.setdefault("ai_score", 5)
                a.setdefault("ai_reason", "")

    # Filtrage
    kept = [a for a in articles if a.get("ai_score", 0) >= MIN_SCORE]

    # Tri : FR en premier, puis score décroissant, puis date
    kept.sort(key=lambda a: (
        0 if a["lang"] == "fr" else 1,
        -a.get("ai_score", 5),
        -date_ts(a),
    ))

    print(f"  Résultat : {len(kept)}/{total} articles conservés (score ≥ {MIN_SCORE})")
    return kept


def _score_batch(client: anthropic.Anthropic, articles: list[dict]) -> None:
    """Score un lot d'articles en place — modifie les dicts directement."""
    articles_text = "\n\n".join(
        f"[{i}] SOURCE: {a['source']} | CATÉGORIE: {a['category']}\n"
        f"TITRE: {a['title']}\n"
        f"RÉSUMÉ: {(a.get('summary') or '')[:280]}"
        for i, a in enumerate(articles)
    )

    user_msg = (
        f"Note chaque article selon la grille. "
        f"Réponds UNIQUEMENT en JSON valide :\n"
        f'```json\n{{"scores":[{{"index":0,"score":8,"raison":"1 phrase max"}}]}}\n```\n\n'
        f"Articles :\n{articles_text}"
    )

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text.strip()

    # Extraire le JSON même entouré de backticks ou de texte
    m = re.search(r'\{[\s\S]*"scores"[\s\S]*\}', text)
    if not m:
        raise ValueError(f"JSON introuvable dans la réponse : {text[:200]}")

    result = json.loads(m.group(0))
    scores_map = {s["index"]: s for s in result.get("scores", [])}

    for i, article in enumerate(articles):
        info = scores_map.get(i, {})
        article["ai_score"]  = int(info.get("score", 5))
        article["ai_reason"] = str(info.get("raison", ""))
