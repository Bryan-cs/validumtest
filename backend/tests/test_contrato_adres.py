"""Test de contrato contra ADRES real. NO corre en CI.

    pytest -m red tests/test_contrato_adres.py

Para que sirve: el scraping de un WebForms ajeno se rompe en silencio. El dia
que ADRES le cambie el nombre a un campo o mueva el captcha, `iniciar()` empieza
a fallar en produccion y nadie se entera hasta que un empleado lo reporta.

Este test hace UNA peticion de solo lectura (GET de la pagina publica + GET de
la imagen del captcha) y verifica que el contrato sigue en pie. No envia ningun
documento ni resuelve ningun captcha: no consulta datos de nadie.

Correrlo semanal (cron local o Action manual) avisa antes que el usuario.
"""
import asyncio

import pytest

from services.consultas.adres import ConsultaADRES, FuenteNoDisponible

pytestmark = pytest.mark.red


def test_contrato_formulario_adres_sigue_vigente():
    """GET de la pagina: ViewState, EventValidation y GUID del captcha presentes."""
    try:
        estado, png = asyncio.run(ConsultaADRES.iniciar("CC", "1"))
    except FuenteNoDisponible as e:
        pytest.fail(
            "El contrato de ADRES cambio o la fuente esta caida: " + str(e) +
            "\nRevisar services/consultas/adres.py contra "
            "https://aplicaciones.adres.gov.co/bdua_internet/Pages/ConsultarAfiliadoWeb.aspx"
        )

    assert estado.viewstate, "__VIEWSTATE vacio: cambio el formulario"
    assert estado.event_validation, "__EVENTVALIDATION vacio: cambio el formulario"
    assert len(estado.captcha_guid) == 36, "El GUID del captcha cambio de formato"
    assert estado.cookies, "ADRES no entrego cookies de sesion"

    # El captcha debe llegar como imagen real, no como una pagina de error.
    assert len(png) > 500, "La imagen del captcha llego vacia o truncada"
    assert png[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"GIF8"), \
        "El captcha ya no viene como PNG/JPEG/GIF"
