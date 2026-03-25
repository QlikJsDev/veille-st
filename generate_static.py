"""generate_static.py – génère docs/articles.json et met à jour docs/costs.json."""
import json
import os
from datetime import datetime, timezone
from core import fetch_all

DOCS_DIR    = os.path.join(os.path.dirname(__file__), "docs")
COSTS_FILE  = os.path.join(DOCS_DIR, "costs.json")
MAX_HISTORY = 60   # garder les 60 derniers runs (~5 jours à 12/jour)


# ── Historique des coûts ──────────────────────────────────────────────────────
def load_costs() -> dict:
    if os.path.exists(COSTS_FILE):
        try:
            with open(COSTS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"runs": []}


def save_costs(history: dict, run_info: dict) -> None:
    history["runs"].append(run_info)
    history["runs"] = history["runs"][-MAX_HISTORY:]   # garder les N derniers
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(COSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print(" Veille S&T – Génération statique")
    print("=" * 55)

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Fetch tous les flux RSS
    print("\n[1/3] Récupération des flux RSS…")
    data = fetch_all()
    articles = data["articles"]
    print(f"  {len(articles)} articles bruts récupérés")

    by_cat: dict[str, int] = {}
    for a in articles:
        by_cat[a["category"]] = by_cat.get(a["category"], 0) + 1
    for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")

    # 2. Scoring IA
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cost_info: dict = {}

    if api_key:
        print("\n[2/3] Scoring et filtrage IA (Claude Haiku)…")
        from ai_filter import score_and_filter
        articles, cost_info = score_and_filter(articles, api_key)
        data["ai_filtered"] = True

        # Historique des coûts
        history = load_costs()
        cost_info["timestamp"] = now_iso
        save_costs(history, cost_info)
        print(f"  Historique : {len(history['runs'])} runs enregistrés → costs.json")
    else:
        print("\n[2/3] Pas de clé ANTHROPIC_API_KEY — scoring IA ignoré")
        for a in articles:
            a.setdefault("ai_score", 5)
            a.setdefault("ai_reason", "")
        data["ai_filtered"] = False

    data["articles"] = articles
    data["cost_info"] = cost_info

    # 3. Écriture articles.json
    print("\n[3/3] Écriture des fichiers…")
    os.makedirs(DOCS_DIR, exist_ok=True)

    articles_path = os.path.join(DOCS_DIR, "articles.json")
    with open(articles_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(articles_path) / 1024
    print(f"  articles.json : {size_kb:.1f} KB  ({len(articles)} articles)")
    if cost_info:
        print(f"  costs.json    : {len(load_costs()['runs'])} runs")
    print(f"  Généré à      : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("\nTerminé.")


if __name__ == "__main__":
    main()
