"""core.py – moteur partagé : sources, mots-clés, fetch RSS, catégorisation."""
from __future__ import annotations
import feedparser
import requests
import re
import threading
import hashlib
import time
from datetime import datetime, timezone

# ── Cache ────────────────────────────────────────────────────────────────────
_cache: dict = {}
_lock = threading.Lock()
CACHE_TTL = 3600  # 1 heure


def _get(key):
    with _lock:
        if key in _cache:
            data, ts = _cache[key]
            if time.time() - ts < CACHE_TTL:
                return data
    return None


def _set(key, data):
    with _lock:
        _cache[key] = (data, time.time())


# ── Catégories ───────────────────────────────────────────────────────────────
CATEGORIES = [
    "IA & Tech",
    "Science",
    "Électronique",
    "Géopolitique",
    "Économie & Marchés",
    "Immobilier Belgique",
    "Autres",
]

CATEGORY_ICONS = {
    "IA & Tech":            "🤖",
    "Science":              "🔬",
    "Électronique":         "🔌",
    "Géopolitique":         "🌍",
    "Économie & Marchés":   "📈",
    "Immobilier Belgique":  "🏠",
    "Autres":               "📰",
}

# ── Sources RSS ──────────────────────────────────────────────────────────────
ALL_SOURCES = [
    # ── IA & Tech ─────────────────────────────────────────────────────────
    {"name": "Numerama",              "url": "https://www.numerama.com/feed/",                                                              "lang": "fr", "default": "IA & Tech"},
    {"name": "FrenchWeb",             "url": "https://www.frenchweb.fr/feed",                                                               "lang": "fr", "default": "IA & Tech"},
    {"name": "Korben",                "url": "https://korben.info/feed",                                                                    "lang": "fr", "default": "IA & Tech"},
    {"name": "Le Monde Informatique", "url": "https://www.lemondeinformatique.fr/flux-rss/thematique/actualites/rss.xml",                  "lang": "fr", "default": "IA & Tech"},
    {"name": "01net",                 "url": "https://www.01net.com/feed/",                                                                 "lang": "fr", "default": "IA & Tech"},
    {"name": "Clubic",                "url": "https://www.clubic.com/feed/rss.xml",                                                         "lang": "fr", "default": "IA & Tech"},
    {"name": "Hacker News",           "url": "https://hnrss.org/frontpage",                                                                 "lang": "en", "default": "IA & Tech"},
    {"name": "The Verge",             "url": "https://www.theverge.com/rss/index.xml",                                                      "lang": "en", "default": "IA & Tech"},
    {"name": "MIT Tech Review",       "url": "https://www.technologyreview.com/feed/",                                                      "lang": "en", "default": "IA & Tech"},
    {"name": "Wired",                 "url": "https://www.wired.com/feed/rss",                                                              "lang": "en", "default": "IA & Tech"},
    {"name": "Ars Technica",          "url": "https://feeds.arstechnica.com/arstechnica/index",                                             "lang": "en", "default": "IA & Tech"},
    # ── Science ───────────────────────────────────────────────────────────
    {"name": "Futura Sciences",       "url": "https://www.futura-sciences.com/rss/actualites.xml",                                          "lang": "fr", "default": "Science"},
    {"name": "Sciences et Avenir",    "url": "https://www.sciencesetavenir.fr/rss.xml",                                                     "lang": "fr", "default": "Science"},
    {"name": "Pour La Science",       "url": "https://www.pourlascience.fr/rss.xml",                                                        "lang": "fr", "default": "Science"},
    {"name": "CNRS Le Journal",       "url": "https://lejournal.cnrs.fr/rss",                                                               "lang": "fr", "default": "Science"},
    {"name": "Nature News",           "url": "https://www.nature.com/news.rss",                                                             "lang": "en", "default": "Science"},
    {"name": "Science Daily",         "url": "https://www.sciencedaily.com/rss/all.xml",                                                    "lang": "en", "default": "Science"},
    # ── Électronique ──────────────────────────────────────────────────────
    {"name": "Tom's Hardware FR",     "url": "https://www.tomshardware.fr/feed/",                                                           "lang": "fr", "default": "Électronique"},
    {"name": "Hackaday",              "url": "https://hackaday.com/blog/feed/",                                                             "lang": "en", "default": "Électronique"},
    {"name": "IEEE Spectrum",         "url": "https://spectrum.ieee.org/feeds/feed.rss",                                                    "lang": "en", "default": "Électronique"},
    {"name": "EE Times",              "url": "https://www.eetimes.com/feed/",                                                               "lang": "en", "default": "Électronique"},
    # ── Géopolitique ──────────────────────────────────────────────────────
    {"name": "Courrier International","url": "https://www.courrierinternational.com/feed/all/rss.xml",                                      "lang": "fr", "default": "Géopolitique"},
    {"name": "IRIS France",           "url": "https://www.iris-france.org/feed/",                                                           "lang": "fr", "default": "Géopolitique"},
    {"name": "RTBF International",    "url": "https://www.rtbf.be/rss/info/categorie/international",                                        "lang": "fr", "default": "Géopolitique"},
    {"name": "The Diplomat",          "url": "https://thediplomat.com/feed/",                                                               "lang": "en", "default": "Géopolitique"},
    # ── Économie & Marchés ────────────────────────────────────────────────
    {"name": "BFM Business",          "url": "https://bfmbusiness.bfmtv.com/rss/info/flux-rss/flux-toutes-les-actualites/",                "lang": "fr", "default": "Économie & Marchés"},
    {"name": "La Tribune",            "url": "https://www.latribune.fr/rss/rubriques/economie.xml",                                         "lang": "fr", "default": "Économie & Marchés"},
    {"name": "L'Echo (Belgique)",     "url": "https://www.lecho.be/rss/category/economie.xml",                                             "lang": "fr", "default": "Économie & Marchés"},
    {"name": "Reuters Business",      "url": "https://feeds.reuters.com/reuters/businessNews",                                              "lang": "en", "default": "Économie & Marchés"},
    {"name": "MarketWatch",           "url": "https://feeds.marketwatch.com/marketwatch/topstories/",                                       "lang": "en", "default": "Économie & Marchés"},
    # ── Immobilier Belgique ───────────────────────────────────────────────
    {"name": "Logic-Immo Belgique",   "url": "https://www.logic-immo.be/rss",                                                              "lang": "fr", "default": "Immobilier Belgique"},
    {"name": "Immoweb Actualités",    "url": "https://www.immoweb.be/fr/rss",                                                              "lang": "fr", "default": "Immobilier Belgique"},
    {"name": "L'Echo Immobilier",     "url": "https://www.lecho.be/rss/category/immobilier.xml",                                           "lang": "fr", "default": "Immobilier Belgique"},
    {"name": "RTL Immo",              "url": "https://www.rtl.be/rss/info/belgique.xml",                                                   "lang": "fr", "default": "Immobilier Belgique"},
    # ── Général → Autres ──────────────────────────────────────────────────
    {"name": "Slate.fr",              "url": "https://www.slate.fr/rss.xml",                                                                "lang": "fr", "default": "Autres"},
    {"name": "New Scientist",         "url": "https://www.newscientist.com/feed/home/",                                                     "lang": "en", "default": "Autres"},
]

# ── Mots-clés par catégorie ───────────────────────────────────────────────────
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "IA & Tech": [
        # Produits IA
        "claude", "chatgpt", "gpt-4", "gpt-5", "openai", "gemini", "google ai",
        "anthropic", "mistral", "llama", "deepseek", "grok", "copilot",
        "stable diffusion", "midjourney", "dall-e", "sora", "perplexity",
        # Concepts IA
        "intelligence artificielle", "ia générative", "llm", "grand modèle",
        "deep learning", "machine learning", "apprentissage automatique",
        "réseau de neurones", "multimodal", "agent ia", "agent autonome",
        # Entreprises IA
        "deepmind", "meta ai", "xai", "hugging face", "cohere",
        # Nouvelles fonctionnalités
        "mise à jour", "nouvelle version", "nouveau modèle", "fonctionnalité",
        # Sécurité / Tech
        "cybersécurité", "hacking", "vulnérabilité", "ransomware", "faille",
        # Startups
        "levée de fonds", "startup", "financement", "série a", "série b",
    ],
    "Science": [
        "découverte", "recherche scientifique", "étude", "publication",
        "physique", "chimie", "biologie", "génétique", "adn", "crispr",
        "espace", "astronomie", "nasa", "esa", "james webb", "exoplanète",
        "médecine", "vaccin", "cancer", "thérapie", "immunologie",
        "climat", "réchauffement", "biodiversité", "écosystème",
        "quantique", "quantum", "cern", "particule",
        "neuroscience", "cerveau", "cognition",
        "mathématiques", "algorithme théorique",
    ],
    "Électronique": [
        "raspberry pi", "arduino", "esp32", "microcontrôleur",
        "semi-conducteur", "semiconducteur", "puce", "chip",
        "processeur", "cpu", "gpu", "fpga", "asic",
        "nvidia", "amd", "intel", "arm", "tsmc",
        "circuit imprimé", "pcb", "composant électronique", "transistor",
        "batterie", "lithium", "photovoltaïque",
        "5g", "6g", "wifi", "bluetooth", "iot", "objet connecté",
        "drone", "robotique", "capteur", "electronique",
        "overclocking", "benchmark",
    ],
    "Géopolitique": [
        "belgique", "bruxelles", "wallonie", "flandre",
        "union européenne", "commission européenne", "parlement européen",
        "règlement", "réglementation", "directive", "législation",
        "otan", "nato", "russie", "ukraine", "chine", "taiwan",
        "trump", "macron", "géopolitique", "diplomatie",
        "sanctions", "embargo", "tarifs douaniers", "protectionnisme",
        "conflit", "guerre", "tension",
        "pénurie", "chaîne d'approvisionnement",
        "nouvelles règles", "nouvelles lois", "impact prix",
    ],
    "Économie & Marchés": [
        "énergie", "energie", "pétrole", "brut", "brent",
        "gaz naturel", "gnl",
        "nucléaire", "epr", "réacteur", "centrale nucléaire",
        "renouvelable", "éolien", "solaire", "hydrogène",
        "électricité", "kwh", "mwh", "facture énergie",
        "bourse", "cac 40", "nasdaq", "dow jones", "s&p",
        "action", "obligation", "taux", "inflation", "fed", "bce",
        "bitcoin", "crypto", "ethereum",
        "récession", "croissance", "pib", "chômage",
        "fusion", "acquisition", "ipo",
        "hausse des prix", "pouvoir d'achat",
    ],
    "Immobilier Belgique": [
        "immobilier", "immo", "immoweb",
        "achat appartement", "achat maison", "achat immobilier",
        "location appartement", "location maison", "loyer",
        "prix immobilier", "prix des logements", "marché immobilier",
        "belgique immobilier", "bruxelles immobilier",
        "investissement immobilier", "rendement locatif",
        "hypothèque", "crédit immobilier", "taux hypothécaire",
        "permis de construire", "urbanisme", "rénovation",
        "agent immobilier", "notaire", "compromis de vente",
        "précompte immobilier", "droits d'enregistrement",
        "logement social", "expat logement",
    ],
}

MIN_SCORE = 1  # score minimal pour remplacer le default
LANG_FLAGS = {"fr": "🇫🇷", "en": "🇬🇧"}


# ── Helpers ──────────────────────────────────────────────────────────────────
def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_date(entry) -> str | None:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return None


def date_ts(a: dict) -> float:
    d = a.get("date")
    if not d:
        return 0.0
    try:
        return datetime.fromisoformat(d).timestamp()
    except Exception:
        return 0.0


def extract_image(entry) -> str:
    # 1. media:thumbnail
    for t in getattr(entry, "media_thumbnail", []):
        url = t.get("url", "")
        if url.startswith("http"):
            return url
    # 2. media:content
    for m in getattr(entry, "media_content", []):
        if "image" in m.get("type", "") or m.get("medium") == "image":
            url = m.get("url", "")
            if url.startswith("http"):
                return url
    # 3. enclosures
    for enc in getattr(entry, "enclosures", []):
        if "image" in enc.get("type", ""):
            url = enc.get("href", enc.get("url", ""))
            if url.startswith("http"):
                return url
    # 4. première <img> dans le contenu HTML
    html = ""
    if hasattr(entry, "content") and entry.content:
        html = entry.content[0].get("value", "")
    if not html:
        html = getattr(entry, "summary", "")
    if html:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
        if m and m.group(1).startswith("http"):
            return m.group(1)
    return ""


def categorize(title: str, summary: str, source_default: str) -> str:
    text = (title + " " + summary).lower()
    scores = {
        cat: sum(1 for kw in kws if kw in text)
        for cat, kws in CATEGORY_KEYWORDS.items()
    }
    best_cat = max(scores, key=scores.get)
    if scores[best_cat] >= MIN_SCORE:
        return best_cat
    return source_default


# ── Fetch ────────────────────────────────────────────────────────────────────
def fetch_feed(source: dict) -> list[dict]:
    cache_key = hashlib.md5(source["url"].encode()).hexdigest()
    cached = _get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            source["url"], timeout=8,
            headers={"User-Agent": "VeilleST/1.0"}
        )
        feed = feedparser.parse(resp.content)
        articles = []
        for entry in feed.entries[:20]:
            title = strip_html(entry.get("title", "Sans titre"))
            summary = strip_html(getattr(entry, "summary", ""))[:400]
            if len(summary) == 400:
                summary += "…"
            image = extract_image(entry)
            cat = categorize(title, summary, source["default"])
            articles.append({
                "title":    title,
                "link":     entry.get("link", "#"),
                "summary":  summary,
                "date":     parse_date(entry),
                "source":   source["name"],
                "lang":     source["lang"],
                "flag":     LANG_FLAGS.get(source["lang"], ""),
                "image":    image,
                "category": cat,
            })
        _set(cache_key, articles)
        return articles
    except Exception as e:
        return []


def fetch_all() -> dict:
    """Fetch toutes les sources en parallèle, retourne le JSON complet."""
    results: list[list] = [[] for _ in ALL_SOURCES]

    def worker(idx, src):
        results[idx] = fetch_feed(src)

    threads = [
        threading.Thread(target=worker, args=(i, s), daemon=True)
        for i, s in enumerate(ALL_SOURCES)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    articles = [a for r in results for a in r]

    # Dédoublonnage par URL
    seen: set[str] = set()
    unique = []
    for a in articles:
        if a["link"] not in seen:
            seen.add(a["link"])
            unique.append(a)

    # Tri : FR en premier, puis date décroissante
    unique.sort(key=lambda a: (0 if a["lang"] == "fr" else 1, -date_ts(a)))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": CATEGORIES,
        "icons": CATEGORY_ICONS,
        "articles": unique,
    }
