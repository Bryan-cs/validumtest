# -*- coding: utf-8 -*-
"""Traduce el subtipo del formulario a lo que PILA necesita.

El formulario de afiliados tiene un campo `subtipo` con cinco valores que son
del negocio, no del anexo: 0, 3, 4, 20 y 22. Cada uno dice algo sobre la
pensión de esa persona, y eso es justo lo que el registro tipo 2 no puede
deducir solo con el tipo de cotizante.

    0    cotiza a pensión, y la tiene contratada
    3    exonerada de pensión — no obligada por edad
    4    exonerada de pensión — requisitos cumplidos
    20   se liquida con cédula de extranjería y sin pensión ni caja
    22   extranjera no obligada a cotizar a pensión

Los números 3 y 4 coinciden con los subtipos de cotizante del anexo que
significan lo mismo (campo 6), así que se mapean directo.

El 20 usa el subtipo de cotizante 04 y sale con cédula de extranjería, que es
la forma que el operador acepta y la que usa el sistema con el que se
contrastó. Se probó contra su validador cambiando una variable a la vez: con
el campo 7 y subtipo 00 devuelve "días cotizados a riesgos y parafiscales
deben ser iguales"; con subtipo 04 y el campo 7 en blanco, los mismos datos
pasan sin un error.

Eso es lo contrario de lo que parecía. El campo 7 exime solo de pensión —lo
dice su propia sección del anexo— y deja intactas las obligaciones de salud,
riesgos y caja. El 04 es el que permite liquidar sin caja.

El 22 conserva el campo 7, que es lo suyo: gente con documento de extranjería
de verdad, donde la marca describe su situación y el operador la valida
contra su propio registro.
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
    "20": Perfil(subtipo_cotizante="04", tipo_doc="CE",
                 descripcion="Se liquida con cédula de extranjería, sin pensión ni caja"),
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

    Devuelve cadena vacía cuando no hay nada que cambiar. Lo que el perfil
    pide no es "cédula de extranjería" sino "un documento que el operador
    acepte con la marca del campo 7", y hay siete que sirven. Si la persona ya
    tiene uno de esos —un permiso por protección temporal, un pasaporte— se
    respeta: es su documento real y cambiarlo por CE sería empeorarlo.
    """
    from .obligaciones import DOCS_EXTRANJERO

    pedido = perfil(subtipo).tipo_doc
    actual = (tipo_doc_actual or "").strip().upper()
    if not pedido or actual == pedido or actual in DOCS_EXTRANJERO:
        return ""
    return pedido
