"""Un solo limitador para login y para el resto de la API.

Antes había dos instancias de SlowAPI. Los decoradores de auth no compartían
estado con `app.state.limiter`, y los tests tenían que apagar las dos.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
