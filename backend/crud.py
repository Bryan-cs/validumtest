"""Shim — re-exporta todo desde los submódulos crud_*.
Los routers importan 'crud' como antes; este archivo delega.
"""
from crud_cache import *
from crud_helpers import *
from crud_usuarios import *
from crud_afiliados import *
from crud_facturas import *
from crud_retiros import *
from crud_empleados import *
from crud_gastos import *
from crud_config import *
from crud_actividad import *
from crud_nomina import *
from crud_dashboard import *
from crud_cobro import *
from crud_tareas import *

# Privados usados por routers vía import crud._xxx o acceso directo
from crud_cache import _cache_get, _cache_set, _redis_disponible
from crud_helpers import (
    _log, _get_rol_usuario, _afiliado_to_dict, _factura_to_dict,
    _planilla, _get_ibc, _get_pct, _ceil100, _servicios_afiliado,
)
from crud_afiliados import _split_csv
from crud_tareas import _tarea_to_dict, _load_comments_map, _ESTADO_LABEL
