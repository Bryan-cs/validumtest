# -*- coding: utf-8 -*-
"""Traduce el subtipo del formulario a lo que PILA necesita.

El formulario de afiliados tiene un campo `subtipo` con cinco valores que son
del negocio, no del anexo: 0, 3, 4, 20 y 22. Cada uno dice algo sobre la
pensión de esa persona, y eso es justo lo que el registro tipo 2 no puede
deducir solo con el tipo de cotizante.

    0    cotiza a pensión, y la tiene contratada
    3    exonerada de pensión — no obligada por edad
    4    exonerada de pensión — requisitos cumplidos
    20   obligada a pensión, sin liquidez para pagarla
    22   extranjera no obligada a cotizar a pensión

Los números 3 y 4 coinciden con los subtipos de cotizante del anexo que
significan lo mismo (campo 6), así que se mapean directo.

El 22 usa la marca del campo 7, que es para quien de verdad tiene documento
de extranjería: el operador la valida contra su propio registro, no contra el
documento del archivo.

El 20 no tiene regla. Son personas obligadas a cotizar a pensión, y la falta
de liquidez del aportante no las exime: marcarlas como extranjeras declara
algo falso y el que se queda sin semanas es el trabajador. Además el operador
ya no lo permite —rechaza la marca cuando su registro dice cédula de
ciudadanía—, así que tampoco funcionaría. Para la falta de liquidez está la
mora: se presenta la planilla completa y se paga después, con los intereses
que el mismo operador calcula.
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
    "20": Perfil(descripcion="Obligada a pensión: se liquida como cualquiera"),
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
