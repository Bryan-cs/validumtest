"""Lecturas del mes PILA: cierre, rechazos, novedades, conciliación y el porqué.

No liquida ni pisa fichas. Clasifica lo que el motor y el operador ya dijeron.
"""
from decimal import Decimal


_ROJO = (
    "lo rechaza como error",
    "el operador lo rechaza",
    "exige salud",
    "no coinciden entre subsistemas",
    "no tiene servicios contratados",
    "no tiene aportante",
    "no está en el sistema",
    "no autocorrige",
)


def nivel_de_avisos(avisos) -> str:
    """Rojo bloquea el número de planilla. Amarillo no."""
    textos = [str(a) for a in (avisos or [])]
    if any(_es_rojo(a) for a in textos):
        return "rojo"
    if textos:
        return "amarillo"
    return "listo"


def _es_rojo(aviso: str) -> bool:
    t = aviso.lower()
    return any(marca in t for marca in _ROJO)


def accion_de_avisos(avisos, nivel: str) -> str:
    texto = " ".join(str(a) for a in (avisos or [])).lower()
    if "no está en el sistema" in texto:
        return "La factura no tiene ficha activa. No se puede liquidar."
    if "aportante" in texto:
        return "Crea el aportante de esa empresa antes de liquidar."
    if "código de la administradora" in texto or "lo rechaza como error" in texto:
        return "Completa el código en la ficha y liquida. El operador lo rechaza."
    if "subsistemas" in texto or "exige salud" in texto:
        return "Revisa ARL y caja contratadas: los días tienen que salir parejos."
    if nivel == "amarillo" and ("ingreso" in texto or "planilla en" in texto):
        return "Aviso amarillo: no bloquea el número. Decide si marcas la novedad de ingreso."
    if "ibc 100" in texto or "declaración mínima" in texto:
        return "La caja en 100 es lo esperado cuando no hay caja contratada. No cambia el IBC."
    if nivel == "listo":
        return "Se puede liquidar."
    return "Revisa el aviso antes de enviar. Si es amarillo, no impide numerar."


def nota_caja_minima(ibc_ccf) -> str:
    if int(ibc_ccf or 0) == 100:
        return ("Caja con IBC 100: no hay caja contratada. Es la declaración "
                "mínima y no bloquea el envío.")
    return ""


def accion_rechazo(descripcion: str) -> str:
    t = (descripcion or "").lower()
    if "actividad" in t or "768" in t:
        return ("Anula y vuelve a liquidar. La línea enviada conserva la "
                "actividad con la que salió.")
    if "sucursal" in t:
        return "Asocia la sucursal en el portal de Simple. La API no puede hacerlo."
    if "documento" in t:
        return "Descarga el plano con el tipo de documento que tiene el operador."
    if "bdua" in t:
        return "Aviso de BDUA: no bloquea el número. Compara la EPS de la ficha."
    if "ibc" in t and "100" in t:
        return "La caja en 100 es la declaración mínima cuando no hay caja contratada."
    return "Corrige la ficha y vuelve a enviar, o pide la corrección del operador."


def mismo_nombre(tipo: str, a: str, b: str) -> bool:
    """Si dos textos de administradora apuntan a la misma del catálogo."""
    from services.pila.catalogos import _normalizar, buscar_codigo
    if not (a or "").strip() or not (b or "").strip():
        return False
    na, nb = _normalizar(a), _normalizar(b)
    if na == nb or na in nb or nb in na:
        return True
    ca, cb = buscar_codigo(tipo, a), buscar_codigo(tipo, b)
    return bool(ca and ca == cb)


def _pesos(valor) -> str:
    try:
        n = int(Decimal(str(valor or 0)))
    except Exception:
        n = 0
    return f"${n:,}".replace(",", ".")


def explicar_monto(detalle, exonerado_hoy: bool) -> list:
    """Por qué salieron esos valores, leídos de la línea congelada."""
    ibc = _pesos(getattr(detalle, "ibc_salud", 0))
    tarifa = Decimal(str(getattr(detalle, "tarifa_salud", 0) or 0))
    notas = []
    if tarifa and tarifa <= Decimal("0.05"):
        notas.append(
            f"Salud salió al 4% sobre IBC {ibc}. La línea quedó exonerada "
            f"(art. 114-1): SENA e ICBF van en 0.")
        exonerada = True
    elif tarifa >= Decimal("0.12"):
        notas.append(
            f"Salud salió al 12,5% sobre IBC {ibc}. En esta línea no aplicó "
            f"exoneración.")
        exonerada = False
    else:
        exonerada = None
        if ibc != "$0":
            notas.append(f"IBC de salud {ibc}.")

    if exonerada is not None and bool(exonerado_hoy) != exonerada:
        hoy = "activa" if exonerado_hoy else "apagada"
        notas.append(
            f"La empresa hoy tiene la exoneración {hoy}. Esta planilla quedó "
            f"con la otra, porque el cálculo se congela al liquidar.")

    caja = nota_caja_minima(getattr(detalle, "ibc_ccf", 0))
    if caja:
        notas.append(caja + f" CCF {getattr(detalle, 'cod_ccf', '') or ''}.")

    linea = getattr(detalle, "linea_plana", "") or ""
    if len(linea) >= 693:
        notas.append(
            f"Clase de riesgo reportada {linea[512:513] or '—'}, "
            f"actividad {linea[686:693].strip() or '—'}.")

    notas.append(
        f"Pensión {_pesos(getattr(detalle, 'cot_pension', 0))}, "
        f"riesgos {_pesos(getattr(detalle, 'cot_arl', 0))} "
        f"(tarifa {getattr(detalle, 'tarifa_arl', 0)}), "
        f"caja {_pesos(getattr(detalle, 'valor_ccf', 0))}, "
        f"SENA {_pesos(getattr(detalle, 'valor_sena', 0))}, "
        f"ICBF {_pesos(getattr(detalle, 'valor_icbf', 0))}.")
    return notas
