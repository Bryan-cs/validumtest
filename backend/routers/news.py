from fastapi import APIRouter
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import time

router = APIRouter(tags=["news"])

_cache: dict = {"data": [], "ts": 0.0}
CACHE_TTL = 600  # 10 min
MAX_AGE_H = 72   # solo noticias de las últimas 72 horas

FEEDS = [
    "https://news.google.com/rss/search?q=seguridad+social+Colombia&hl=es-419&gl=CO&ceid=CO:es-419",
    "https://news.google.com/rss/search?q=eps+colombia+salud&hl=es-419&gl=CO&ceid=CO:es-419",
    "https://news.google.com/rss/search?q=reforma+laboral+pensiones+colombia&hl=es-419&gl=CO&ceid=CO:es-419",
]


def _fetch(url: str) -> list[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BBC-File/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        cutoff = time.time() - MAX_AGE_H * 3600
        out = []
        for item in root.findall(".//item"):
            full = (item.findtext("title") or "").strip()
            link = (item.findtext("link")  or "").strip()
            pub  = (item.findtext("pubDate") or "").strip()
            if not full or not link:
                continue
            # Filtrar por fecha — descartar noticias viejas
            if pub:
                try:
                    ts = parsedate_to_datetime(pub).timestamp()
                    if ts < cutoff:
                        continue
                except Exception:
                    pass
            # Google News format: "Título - Fuente"
            parts  = full.rsplit(" - ", 1)
            title  = parts[0].strip()
            source = parts[-1].strip() if len(parts) > 1 else "Colombia"
            out.append({"title": title, "source": source, "link": link, "ts": pub})
        return out
    except Exception:
        return []


@router.get("/news/ticker")
def news_ticker():
    now = time.time()
    if now - _cache["ts"] < CACHE_TTL and _cache["data"]:
        return _cache["data"]

    seen: set[str] = set()
    results: list[dict] = []
    for url in FEEDS:
        for item in _fetch(url):
            k = item["title"][:80].lower()
            if k not in seen:
                seen.add(k)
                results.append(item)

    # Ordenar más recientes primero
    def _ts(item: dict) -> float:
        try:
            return parsedate_to_datetime(item["ts"]).timestamp()
        except Exception:
            return 0.0

    results.sort(key=_ts, reverse=True)

    # Quitar campo ts antes de devolver
    clean = [{"title": r["title"], "source": r["source"], "link": r["link"]} for r in results[:12]]
    _cache["data"] = clean
    _cache["ts"] = now
    return clean
