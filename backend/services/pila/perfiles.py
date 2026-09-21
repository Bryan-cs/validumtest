# -*- coding: utf-8 -*-
"""Traduce el subtipo del formulario a lo que PILA necesita.

El formulario de afiliados tiene un campo `subtipo` con cinco valores que son
del negocio, no del anexo: 0, 3, 4, 20 y 22. Cada uno dice algo sobre la
pensión de esa persona, y eso es justo lo que el registro tipo 2 no puede
deducir solo con el tipo de cotizante.

    0    cotiza a pensión, y la tiene contratada
    3    exonerada de pensión — no obligada por edad
    4    exonerada de pensión — requisitos cumplidos
    20   obligada a pensión por su tipo de cotizante, pero no la paga aquí
    22   extranjera no obligada a cotizar a pensión

Los números 3 y 4 coinciden con los subtipos de cotizante del anexo que
significan lo mismo (campo 6), así que se mapean directo.

Los grupos 20 y 22 son los que se identifican ante el operador con cédula de
extranjería, y ninguno de los dos liquida pensión. La diferencia entre ellos
es de negocio, no de archivo: los dos salen con la marca del campo 7, que es
lo que hace que el operador no exija el aporte a pensión de alguien cuyo tipo
de cotizante sí lo exigiría.
"""
from typing import NamedTuple, Optional


class Perfil(NamedTuple):
    # Subtipo de cotizante del anexo que se escribe en el campo 6.
    subtipo_cotizante: str = ""
    # Marca del campo 7.
    extranjero_no_pension: bool = False
    # Documento con el que sale al operador, si el grupo exige uno distinto.
    tipo_doc: Optional[str] = None
    descripcion: str = ""


PERFILES = {
    "0":  Perfil(descripcion="Cotiza a pensión con el servicio contratado"),
    "3":  Perfil(subtipo_cotizante="03",
                 descripcion="Exonerada de pensión: no obligada por edad"),
    "4":  Perfil(subtipo_cotizante="04",
                 descripcion="Exonerada de pensión: requisitos cumplidos"),
    "20": Perfil(extranjero_no_pension=True, tipo_doc="CE",
                 descripcion="Obligada a pensión por su tipo de cotizante, no la paga aquí"),
    "22": Perfil(extranjero_no_pension=True, tipo_doc="CE",
                 descripcion="Extranjera no obligada a cotizar a pensión"),
}


def perfil(subtipo) -> Perfil:
    """El perfil de ese subtipo; uno neutro si no está mapeado.

    Un subtipo desconocido no debe cambiar nada: es preferible liquidar como
    siempre a aplicar una regla inventada sobre la pensión de alguien.
    """
    clave = str(subtipo or "").strip()
    if not clave:
        clave = "0"
    return PERFILES.get(clave, Perfil(descripcion=f"Subtipo {clave} sin regla PILA"))


def documento_sugerido(subtipo, tipo_doc_actual: str = "") -> str:
    """Con qué documento conviene mandar a esta persona al operador.

    Devuelve cadena vacía cuando el subtipo no pide uno distinto del que ya
    tiene el afiliado, para que el resto del sistema no haga nada.
    """
    pedido = perfil(subtipo).tipo_doc
    if not pedido or pedido == (tipo_doc_actual or "").strip().upper():
        return ""
    return pedido
