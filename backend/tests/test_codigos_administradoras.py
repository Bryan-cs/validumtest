# -*- coding: utf-8 -*-
"""El codigo PILA sale del nombre de la administradora.

El formulario guarda el nombre —"Compensar"— y el archivo plano necesita el
codigo —"EPS008"—. Son campos distintos, y el formulario solo llena el
primero. Quien lo llenaba bien se encontraba con que el campo del archivo
salia vacio y el operador rechazaba la planilla con "El codigo de la EPS es
obligatorio cuando hay aporte a salud".
"""
import pytest

from services.pila.catalogos import buscar_codigo, _normalizar


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── La busqueda ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre,esperado", [
    ("Nueva EPS", "EPS037"),
    ("Compensar", "EPS008"),
    ("Famisanar", "EPS017"),
    ("Salud Total", "EPS002"),
    ("Sanitas", "EPS005"),
])
def test_las_eps_del_formulario_encuentran_su_codigo(nombre, esperado):
    assert buscar_codigo("EPS", nombre) == esperado


def test_compensar_es_distinta_segun_el_subsistema():
    """El mismo nombre es una EPS y una caja, con codigos distintos."""
    assert buscar_codigo("EPS", "Compensar") == "EPS008"
    assert buscar_codigo("CCF", "Compensar") == "CCF24"


@pytest.mark.parametrize("nombre,esperado", [
    ("Porvenir", "230301"),
    ("Colpensiones", "25-14"),
    ("Proteccion", "230201"),
])
def test_las_afp_tambien(nombre, esperado):
    assert buscar_codigo("AFP", nombre) == esperado


def test_no_importan_tildes_ni_mayusculas():
    assert buscar_codigo("AFP", "protección") == buscar_codigo("AFP", "PROTECCION")


def test_las_siglas_del_subsistema_no_estorban():
    """El catalogo dice "NUEVA EPS SA." y el formulario "Nueva EPS"."""
    assert _normalizar("NUEVA EPS SA.") == _normalizar("Nueva EPS")


@pytest.mark.parametrize("nombre", ["", "   ", "N/A", "Sin EPS", "Ninguna"])
def test_lo_que_no_nombra_una_administradora_no_devuelve_codigo(nombre):
    assert buscar_codigo("EPS", nombre) == ""


def test_un_nombre_ambiguo_no_adivina():
    """Un codigo equivocado manda los aportes a otra administradora.

    Es mejor dejarlo vacio y que la liquidacion avise, que es lo que hace.
    """
    assert buscar_codigo("EPS", "EPS") == ""


def test_un_tipo_que_no_existe_no_revienta():
    assert buscar_codigo("INVENTADO", "Compensar") == ""


# ─── Al guardar el afiliado ───────────────────────────────────────────────────

def test_elegir_la_eps_en_el_formulario_deja_el_codigo_puesto(client, admin_token):
    r = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "CODIGO AUTOMATICO", "doc": "97000111", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS", "CCF", "AFP"],
        "eps": "Nueva EPS", "ccf": "Compensar", "afp": "Porvenir",
    })
    assert r.status_code in (200, 201), r.text
    quedo = client.get(f"/afiliados/{r.json()['id']}", headers=_h(admin_token)).json()
    assert quedo["cod_eps"] == "EPS037"
    assert quedo["cod_ccf"] == "CCF24"
    assert quedo["cod_afp"] == "230301"


def test_cambiar_la_eps_desde_el_formulario_no_deja_el_codigo_viejo(client, admin_token):
    creado = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "CODIGO CAMBIA", "doc": "97000222", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS"], "eps": "Sanitas",
    })
    id_ = creado.json()["id"]
    assert client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()["cod_eps"] == "EPS005"

    client.put(f"/afiliados/{id_}", headers=_h(admin_token), json={
        "nombre": "CODIGO CAMBIA", "doc": "97000222", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS"],
        "eps": "Famisanar", "cod_eps": "",
    })
    assert client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()["cod_eps"] == "EPS017"


def test_un_codigo_puesto_a_mano_manda(client, admin_token):
    """Alguien pudo tener una razon para elegir otro: no se le pisa."""
    r = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "CODIGO A MANO", "doc": "97000333", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS"],
        "eps": "Nueva EPS", "cod_eps": "EPS002",
    })
    quedo = client.get(f"/afiliados/{r.json()['id']}", headers=_h(admin_token)).json()
    assert quedo["cod_eps"] == "EPS002"


def test_sin_nombre_de_eps_no_se_inventa_codigo(client, admin_token):
    r = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "SIN EPS", "doc": "97000444", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["ARL 4"], "eps": "",
    })
    quedo = client.get(f"/afiliados/{r.json()['id']}", headers=_h(admin_token)).json()
    assert not quedo["cod_eps"]


# ─── Las listas del formulario salen del catalogo ─────────────────────────────
#
# Se mantenian a mano y se desincronizaron: el formulario ofrecia "Coomeva",
# que ya no esta vigente, y le faltaban decenas de administradoras que si lo
# estan. Y sus nombres no coincidian con los del catalogo, asi que elegir uno
# correcto dejaba el codigo del archivo vacio.

from services.pila.catalogos import nombres_para_listas


@pytest.mark.parametrize("tipo", ["EPS", "AFP", "CCF"])
def test_toda_entrada_de_lista_resuelve_a_un_codigo(tipo):
    """Es el punto entero: no puede haber opciones sin codigo."""
    entradas = nombres_para_listas(tipo)
    assert entradas
    sin_codigo = [e for e in entradas if not buscar_codigo(tipo, e)]
    assert sin_codigo == []


@pytest.mark.parametrize("tipo", ["EPS", "AFP", "CCF"])
def test_cada_entrada_lleva_a_un_codigo_distinto(tipo):
    """Dos opciones que apunten al mismo codigo confundirian a quien elige."""
    entradas = nombres_para_listas(tipo)
    codigos = [buscar_codigo(tipo, e) for e in entradas]
    assert len(set(codigos)) == len(codigos)


def test_las_que_se_llaman_igual_se_desempatan_con_su_codigo():
    """Dos AFP Skandia: sin el codigo, elegir una dejaria el campo vacio."""
    skandia = [e for e in nombres_para_listas("AFP") if "SKANDIA" in e]
    assert len(skandia) == 2
    assert {buscar_codigo("AFP", e) for e in skandia} == {"230901", "230904"}


def test_un_codigo_escrito_tal_cual_se_acepta():
    assert buscar_codigo("EPS", "EPS037") == "EPS037"
    assert buscar_codigo("AFP", "230301") == "230301"


def test_sincronizar_deja_las_listas_alineadas(client, admin_token):
    r = client.post("/listas/sincronizar-pila", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    cambios = r.json()
    assert set(cambios) == {"eps", "afp", "ccf"}

    listas = client.get("/listas", headers=_h(admin_token)).json()
    for lista, tipo in (("eps", "EPS"), ("afp", "AFP"), ("ccf", "CCF")):
        entradas = listas[lista]
        assert entradas[0] == "N/A"          # para poder dejarlo sin administradora
        for e in entradas[1:]:
            assert buscar_codigo(tipo, e), f"{lista}: {e!r} no resuelve"


def test_sincronizar_dice_que_entro_y_que_salio(client, admin_token):
    client.put("/listas/eps", headers=_h(admin_token),
               json={"items": ["Coomeva", "Cafesalud"]})
    cambios = client.post("/listas/sincronizar-pila", headers=_h(admin_token)).json()
    assert "Coomeva" in cambios["eps"]["retiradas"]
    assert cambios["eps"]["total"] > 20


def test_sincronizar_dos_veces_no_cambia_nada(client, admin_token):
    client.post("/listas/sincronizar-pila", headers=_h(admin_token))
    segunda = client.post("/listas/sincronizar-pila", headers=_h(admin_token)).json()
    for lista in ("eps", "afp", "ccf"):
        assert segunda[lista]["agregadas"] == []
        assert segunda[lista]["retiradas"] == []
