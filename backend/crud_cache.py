"""Capa de caché — Redis en producción, dict en memoria para dev."""
import json, time as _time, threading as _threading, os as _os

TTL_COBRO     = 600
TTL_DASHBOARD = 300
TTL_AFILIADOS = 180
TTL_CONFIG    = 600
TTL_LISTAS    = 1800

_redis_client = None
try:
    _redis_url = _os.getenv("REDIS_URL")
    if _redis_url:
        import redis as _redis_mod
        _redis_client = _redis_mod.from_url(_redis_url, decode_responses=True)
        _redis_client.ping()
except Exception as _redis_err:
    _redis_client = None
    from logger import logger as _rlog
    _rlog.warning(f"Redis no disponible, usando cache en memoria: {_redis_err}")

_mem_cache: dict = {}
_cache_lock = _threading.Lock()


def _ns(key: str) -> str:
    """Prefija la clave con la organización activa para aislar la caché por tenant.
    Sin organización activa (login, tareas de sistema) se usa la clave tal cual."""
    try:
        from tenant import current_org_id
        org = current_org_id.get()
    except Exception:
        org = None
    return f"o{org}:{key}" if org is not None else key

_cb_failures   = 0
_cb_open_until = 0.0
_CB_MAX_FAILS  = 5
_CB_COOLDOWN   = 30


def _redis_disponible() -> bool:
    global _cb_failures, _cb_open_until
    if not _redis_client:
        return False
    if _cb_failures >= _CB_MAX_FAILS:
        if _time.time() < _cb_open_until:
            return False
    return True


def _redis_on_success():
    global _cb_failures
    _cb_failures = 0


def _redis_on_failure():
    global _cb_failures, _cb_open_until
    _cb_failures += 1
    if _cb_failures >= _CB_MAX_FAILS:
        _cb_open_until = _time.time() + _CB_COOLDOWN
        from logger import logger as _cblog
        _cblog.warning(f"Redis circuit breaker abierto — {_CB_COOLDOWN}s de pausa")


def _use_mem_cache() -> bool:
    return _redis_client is None


def _cache_get(key: str):
    key = _ns(key)
    if _redis_disponible():
        try:
            raw = _redis_client.get(key)
            _redis_on_success()
            if raw:
                return json.loads(raw)
        except Exception:
            _redis_on_failure()
        return None
    if not _use_mem_cache():
        return None
    with _cache_lock:
        entry = _mem_cache.get(key)
        if entry and (_time.time() - entry["ts"]) < entry["ttl"]:
            return entry["data"]
        return None


def _cache_set(key: str, data, ttl: int = TTL_COBRO):
    key = _ns(key)
    if _redis_disponible():
        try:
            _redis_client.setex(key, ttl, json.dumps(data, default=str))
            _redis_on_success()
        except Exception:
            _redis_on_failure()
        return
    if not _use_mem_cache():
        return
    with _cache_lock:
        _mem_cache[key] = {"data": data, "ts": _time.time(), "ttl": ttl}
        if len(_mem_cache) > 500:
            now = _time.time()
            expired = [k for k, v in list(_mem_cache.items()) if (now - v["ts"]) >= v["ttl"]]
            for k in expired:
                _mem_cache.pop(k, None)
            if len(_mem_cache) > 500:
                oldest = sorted(_mem_cache.items(), key=lambda x: x[1]["ts"])[:100]
                for k, _ in oldest:
                    _mem_cache.pop(k, None)


def cache_invalidar(prefijo: str = ""):
    prefijo = _ns(prefijo)
    if _redis_disponible():
        try:
            cursor = 0
            while True:
                cursor, keys = _redis_client.scan(cursor, match=f"{prefijo}*", count=100)
                if keys:
                    _redis_client.delete(*keys)
                if cursor == 0:
                    break
            _redis_on_success()
        except Exception:
            _redis_on_failure()
        return
    with _cache_lock:
        keys = [k for k in _mem_cache if k.startswith(prefijo)]
        for k in keys:
            del _mem_cache[k]
