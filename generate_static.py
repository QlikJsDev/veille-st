"""generate_static.py – génère docs/articles.json pour GitHub Pages."""
import json
import os
from core import fetch_all

def main():
    print("Fetching all RSS feeds…")
    data = fetch_all()
    total = len(data["articles"])
    print(f"  {total} articles récupérés")

    by_cat = {}
    for a in data["articles"]:
        by_cat.setdefault(a["category"], 0)
        by_cat[a["category"]] += 1
    for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")

    out_path = os.path.join(os.path.dirname(__file__), "docs", "articles.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nFichier écrit : {out_path}")
    print(f"Généré à : {data['generated_at']}")

if __name__ == "__main__":
    main()
