"""generate_static.py – génère docs/articles.json pour GitHub Pages."""
import json
import os
from datetime import datetime, timezone
from core import fetch_all


def main():
    print("=" * 55)
    print(" Veille S&T – Génération statique")
    print("=" * 55)

    # 1. Fetch tous les flux RSS
    print("\n[1/3] Récupération des flux RSS…")
    data = fetch_all()
    articles = data["articles"]
    print(f"  {len(articles)} articles bruts récupérés")

    # Distribution par catégorie
    by_cat: dict[str, int] = {}
    for a in articles:
        by_cat[a["category"]] = by_cat.get(a["category"], 0) + 1
    for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")

    # 2. Scoring IA (si clé disponible)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        print("\n[2/3] Scoring et filtrage IA (Claude Haiku)…")
        from ai_filter import score_and_filter
        articles = score_and_filter(articles, api_key)
        data["ai_filtered"] = True
    else:
        print("\n[2/3] Pas de clé ANTHROPIC_API_KEY — scoring IA ignoré")
        # Score neutre pour la compatibilité UI
        for a in articles:
            a.setdefault("ai_score", 5)
            a.setdefault("ai_reason", "")
        data["ai_filtered"] = False

    data["articles"] = articles

    # 3. Écriture du fichier
    print("\n[3/3] Écriture de docs/articles.json…")
    out_path = os.path.join(os.path.dirname(__file__), "docs", "articles.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Fichier : {out_path}")
    print(f"  Taille  : {size_kb:.1f} KB")
    print(f"  Articles: {len(articles)}")
    print(f"  Généré  : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("\nTerminé.")


if __name__ == "__main__":
    main()
