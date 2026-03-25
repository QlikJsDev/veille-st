"""ai_filter.py – scoring des articles via Claude API + tracking des coûts."""
from __future__ import annotations
import json
import re
import anthropic
from core import date_ts

MIN_SCORE  = 6
BATCH_SIZE = 20

# Tarifs Claude Haiku 4.5 ($/1M tokens)
PRICE_INPUT  = 1.00
PRICE_OUTPUT = 5.00
MODEL        = "claude-haiku-4-5"


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


def score_and_filter(articles: list[dict], api_key: str) -> tuple[list[dict], dict]:
    """
    Score tous les articles et retourne (articles_filtrés, cost_info).
    cost_info = {input_tokens, output_tokens, cost_usd, articles_scored, articles_kept, model}
    """
    client = anthropic.Anthropic(api_key=api_key)
    total = len(articles)
    total_input  = 0
    total_output = 0

    print(f"  Scoring {total} articles par lots de {BATCH_SIZE}…")

    for i in range(0, total, BATCH_SIZE):
        batch      = articles[i:i + BATCH_SIZE]
        batch_num  = i // BATCH_SIZE + 1
        n_batches  = (total + BATCH_SIZE - 1) // BATCH_SIZE
        try:
            inp, out = _score_batch(client, batch)
            total_input  += inp
            total_output += out
            kept = sum(1 for a in batch if a.get("ai_score", 0) >= MIN_SCORE)
            cost_batch = _cost(inp, out)
            print(f"    Lot {batch_num}/{n_batches} : {kept}/{len(batch)} conservés "
                  f"| {inp}+{out} tok | ${cost_batch:.4f}")
        except Exception as e:
            print(f"    Lot {batch_num}/{n_batches} erreur : {e}")
            for a in batch:
                a.setdefault("ai_score", 5)
                a.setdefault("ai_reason", "")

    # Filtrage et tri
    kept_articles = [a for a in articles if a.get("ai_score", 0) >= MIN_SCORE]
    kept_articles.sort(key=lambda a: (
        0 if a["lang"] == "fr" else 1,
        -a.get("ai_score", 5),
        -date_ts(a),
    ))

    run_cost = _cost(total_input, total_output)
    cost_info = {
        "model":            MODEL,
        "input_tokens":     total_input,
        "output_tokens":    total_output,
        "cost_usd":         round(run_cost, 5),
        "articles_scored":  total,
        "articles_kept":    len(kept_articles),
        "price_input_per_m":  PRICE_INPUT,
        "price_output_per_m": PRICE_OUTPUT,
    }

    print(f"  Résultat : {len(kept_articles)}/{total} conservés | "
          f"Tokens : {total_input}+{total_output} | Coût : ${run_cost:.4f}")
    return kept_articles, cost_info


def _cost(inp: int, out: int) -> float:
    return (inp / 1_000_000 * PRICE_INPUT) + (out / 1_000_000 * PRICE_OUTPUT)


def _score_batch(client: anthropic.Anthropic, articles: list[dict]) -> tuple[int, int]:
    """Score un lot — modifie les dicts en place. Retourne (input_tokens, output_tokens)."""
    articles_text = "\n\n".join(
        f"[{i}] SOURCE: {a['source']} | CATÉGORIE: {a['category']}\n"
        f"TITRE: {a['title']}\n"
        f"RÉSUMÉ: {(a.get('summary') or '')[:280]}"
        for i, a in enumerate(articles)
    )

    user_msg = (
        "Note chaque article selon la grille. "
        "Réponds UNIQUEMENT en JSON valide :\n"
        '```json\n{"scores":[{"index":0,"score":8,"raison":"1 phrase max"}]}\n```\n\n'
        f"Articles :\n{articles_text}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    inp = response.usage.input_tokens
    out = response.usage.output_tokens

    text = response.content[0].text.strip()
    m = re.search(r'\{[\s\S]*"scores"[\s\S]*\}', text)
    if not m:
        raise ValueError(f"JSON introuvable : {text[:200]}")

    result     = json.loads(m.group(0))
    scores_map = {s["index"]: s for s in result.get("scores", [])}

    for i, article in enumerate(articles):
        info = scores_map.get(i, {})
        article["ai_score"]  = int(info.get("score", 5))
        article["ai_reason"] = str(info.get("raison", ""))

    return inp, out
