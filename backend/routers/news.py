from fastapi import APIRouter
import urllib.request
import xml.etree.ElementTree as ET
import re
import time

router = APIRouter(tags=["news"])

_cache: dict = {"data": [], "ts": 0.0}
CACHE_TTL = 600  # 10 min

# Google News siempre retorna resultados — el query es el filtro
FEEDS = [
    ("Google News", "https://news.google.com/rss/search?q=seguridad+social+Colombia&hl=es-419&gl=CO&ceid=CO:es-419"),
    ("Google News", "https://news.google.com/rss/search?q=eps+colombia+salud&hl=es-419&gl=CO&ceid=CO:es-419"),
    ("Google News", "https://news.google.com/rss/search?q=reforma+laboral+colombia&hl=es-419&gl=CO&ceid=CO:es-419"),
]

# Filtro secundario para descartar irrelevantes
KW = re.compile(
    r"seguridad social|pension|eps|arl|salud|trabajo|empleo|aporte|"
    r"parafiscal|ugpp|colpensiones|minsalud|mintrabajo|laboral|"
    r"n[oó]mina|cesant|reforma|afilia|cotiza|ss |prestaci",
    re.IGNORECASE,
)


def _parse_source(text: str) -> str:
    """Extrae nombre de fuente del campo <title> de Google News: 'Título - Fuente'"""
    parts = text.rsplit(" - ", 1)
    return parts[-1].strip() if len(parts) > 1 else "Colombia"


def _fetch(url: str) -> list[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BBC-File/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        out = []
        for item in root.findall(".//item"):
            full  = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            if not full or not link:
                continue
            # Google News format: "Título - Fuente"
            title  = full.rsplit(" - ", 1)[0].strip()
            source = _parse_source(full)
            out.append({"title": title, "source": source, "link": link})
        return out[:8]
    except Exception:
        return []


@router.get("/news/ticker")
def news_ticker():
    now = time.time()
    if now - _cache["ts"] < CACHE_TTL and _cache["data"]:
        return _cache["data"]

    seen: set[str] = set()
    results: list[dict] = []
    for _, url in FEEDS:
        for item in _fetch(url):
            k = item["title"][:80].lower()
            if k not in seen:
                seen.add(k)
                results.append(item)

    _cache["data"] = results[:12]
    _cache["ts"] = now
    return _cache["data"]
