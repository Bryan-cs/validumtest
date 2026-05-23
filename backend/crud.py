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

# Privados expuestos a routers (el resto queda en crud_* vía import *)
from crud_helpers import _log, _factura_to_dict, _planilla
