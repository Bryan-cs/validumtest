# -*- coding: utf-8 -*-
"""Varias personas en un mismo archivo plano.

Liquidar sigue siendo de a uno: cada quien con su detalle, su total y su
rastro. Lo que se agrupa es el archivo, porque asi se presenta una nomina y
porque el registro tipo 2 se repite tantas veces como cotizantes haya.

El encabezado, en cambio, lleva un solo aportante y un solo periodo. Esa es la
restriccion que manda: no se pueden juntar personas de empresas distintas ni
de meses distintos.
"""
import pytest

from services.pila import plano


def _h(token):
    return {"Authorization": f"Bearer {token}"}


CONJUNTO = (
    ("60011001", "PRIMERA DEL GRUPO"),
    ("60011002", "SEGUNDA DEL GRUPO"),
    ("60011003", "TERCERA DEL GRUPO"),
)


@pytest.fixture(scope="module")
def grupo(client, admin_token):
    """Tres personas de la misma empresa, liquidadas por separado."""
    client.post("/aportantes", headers=_h(admin_token), json={
        "cliente_ref": "GRUPO SA", "razon_social": "GRUPO SA",
        "num_doc": "901111111", "cod_arl": "14-11", "clase_riesgo": "1",
        "cod_depto": "11", "cod_municipio": "001", "cod_sucursal": "001",
    })
    ids = []
    for doc, nombre in CONJUNTO:
        r = client.post("/afiliados", headers=_h(admin_token), json={
            "nombre": nombre, "doc": doc, "tipo_doc": "CC",
            "empresa": "GRUPO SA", "cliente_txt": "GRUPO SA",
            "servicios": ["EPS", "AFP", "CCF", "ARL 1"],
            "fecha_afiliacion": "2026-01-01", "fecha_ingreso": "2024-01-01",
            "ibc": 1750905, "salario_basico": 1750905,
            "tipo_cotizante": "01", "clase_riesgo": "1",
            "cod_eps": "EPS037", "cod_afp": "230201", "cod_ccf": "CCF03",
            "cod_arl": "14-11", "tipo_salario": "F",
            "primer_nombre": nombre.split()[0], "primer_apellido": nombre.split()[-1],
        })
        assert r.status_code in (200, 201), r.text
        liq = client.post("/liquidacion", headers=_h(admin_token),
                          json={"afiliado_id": r.json()["id"], "anio": 2026, "mes": 9})
        assert liq.status_code in (200, 201), liq.text
        ids.append((liq.json()["id"], r.json()["id"]))
    return {"liquidaciones": [x[0] for x in ids],
            "afiliados": [x[1] for x in ids]}


def _bajar(client, admin_token, ids, **extra):
    qs = "&".join([f"ids={','.join(map(str, ids))}"] +
                  [f"{k}={v}" for k, v in extra.items()])
    r = client.get(f"/liquidacion/plano-conjunto?{qs}", headers=_h(admin_token))
    return r


def _lineas(texto):
    return [l for l in texto.splitlines() if l.strip()]


# ─── El archivo ───────────────────────────────────────────────────────────────

def test_las_tres_caben_en_un_solo_archivo(client, admin_token, grupo):
    r = _bajar(client, admin_token, grupo["liquidaciones"])
    assert r.status_code == 200, r.text
    lineas = _lineas(r.text)
    assert len(lineas) == 4                      # un encabezado y tres cotizantes
    assert lineas[0].startswith("01")
    assert all(l.startswith("02") for l in lineas[1:])


def test_los_largos_siguen_siendo_los_del_anexo(client, admin_token, grupo):
    lineas = _lineas(_bajar(client, admin_token, grupo["liquidaciones"]).text)
    assert len(lineas[0]) == plano.LARGO_TIPO_1 == 359
    assert all(len(l) == plano.LARGO_TIPO_2 == 693 for l in lineas[1:])


def test_los_cotizantes_van_numerados_de_corrido(client, admin_token, grupo):
    """Cada liquidacion se guarda con secuencia 1: juntarlas exige renumerar."""
    lineas = _lineas(_bajar(client, admin_token, grupo["liquidaciones"]).text)
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "secuencia")
    secuencias = [l[c.inicio - 1:c.inicio - 1 + c.longitud] for l in lineas[1:]]
    assert secuencias == ["00001", "00002", "00003"]


def test_el_encabezado_cuenta_los_cotizantes(client, admin_token, grupo):
    lineas = _lineas(_bajar(client, admin_token, grupo["liquidaciones"]).text)
    c = next(x for x in plano.CAMPOS_TIPO_1 if x.nombre == "total_cotizantes")
    assert lineas[0][c.inicio - 1:c.inicio - 1 + c.longitud] == "00003"


def test_el_encabezado_suma_la_nomina_de_todos(client, admin_token, grupo):
    lineas = _lineas(_bajar(client, admin_token, grupo["liquidaciones"]).text)
    c = next(x for x in plano.CAMPOS_TIPO_1 if x.nombre == "valor_total_nomina")
    total = int(lineas[0][c.inicio - 1:c.inicio - 1 + c.longitud])
    assert total == 1750905 * 3


def test_el_nombre_del_archivo_dice_cuantos_van(client, admin_token, grupo):
    r = _bajar(client, admin_token, grupo["liquidaciones"])
    assert "3cotizantes" in r.headers["content-disposition"]


def test_una_sola_liquidacion_sigue_saliendo_como_antes(client, admin_token, grupo):
    """El mismo endpoint de siempre no cambia de forma por esto."""
    r = client.get(f"/liquidacion/{grupo['liquidaciones'][0]}/plano", headers=_h(admin_token))
    assert r.status_code == 200
    assert len(_lineas(r.text)) == 2


def test_el_documento_se_puede_forzar_para_todo_el_archivo(client, admin_token, grupo):
    lineas = _lineas(_bajar(client, admin_token, grupo["liquidaciones"], tipo_doc="CE").text)
    assert all(l[7:9] == "CE" for l in lineas[1:])


# ─── Lo que el formato no permite ─────────────────────────────────────────────

def test_no_se_juntan_personas_de_empresas_distintas(client, admin_token, grupo):
    """El encabezado lleva un solo aportante: es la forma del archivo."""
    client.post("/aportantes", headers=_h(admin_token), json={
        "cliente_ref": "OTRA SA", "razon_social": "OTRA SA",
        "num_doc": "901222222", "cod_arl": "14-11", "clase_riesgo": "1",
        "cod_depto": "11", "cod_municipio": "001", "cod_sucursal": "001",
    })
    otro = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "DE OTRA EMPRESA", "doc": "60019999", "tipo_doc": "CC",
        "empresa": "OTRA SA", "cliente_txt": "OTRA SA",
        "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
        "ibc": 1750905, "cod_eps": "EPS037", "tipo_cotizante": "42",
    })
    assert otro.status_code in (200, 201), otro.text
    liq = client.post("/liquidacion", headers=_h(admin_token),
                      json={"afiliado_id": otro.json()["id"], "anio": 2026, "mes": 9})
    assert liq.status_code in (200, 201), liq.text
    r = _bajar(client, admin_token,
               grupo["liquidaciones"] + [liq.json()["id"]])
    assert r.status_code == 409
    assert "un solo aportante" in r.json()["detail"]


def test_no_se_juntan_periodos_distintos(client, admin_token, grupo):
    otro = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": grupo["afiliados"][0], "anio": 2026, "mes": 10})
    assert otro.status_code in (200, 201), otro.text
    r = _bajar(client, admin_token,
               [grupo["liquidaciones"][0], otro.json()["id"]])
    assert r.status_code == 409
    assert "un solo período" in r.json()["detail"]


def test_una_anulada_no_entra_en_el_conjunto(client, admin_token, grupo):
    tercera = grupo["liquidaciones"][2]
    client.post(f"/liquidacion/{tercera}/anular", headers=_h(admin_token))
    r = _bajar(client, admin_token, grupo["liquidaciones"])
    assert r.status_code == 409
    assert "anuladas" in r.json()["detail"]
    # se rehace para no dejar el grupo cojo a los demas tests
    nueva = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": grupo["afiliados"][2], "anio": 2026, "mes": 9})
    if nueva.status_code in (200, 201):
        grupo["liquidaciones"][2] = nueva.json()["id"]


def test_un_id_que_no_existe_se_dice_cual(client, admin_token, grupo):
    r = _bajar(client, admin_token, [grupo["liquidaciones"][0], 999999])
    assert r.status_code == 404
    assert "999999" in r.json()["detail"]


def test_sin_ids_no_se_arma_nada(client, admin_token):
    r = client.get("/liquidacion/plano-conjunto?ids=", headers=_h(admin_token))
    assert r.status_code == 400


def test_ids_que_no_son_numeros(client, admin_token):
    r = client.get("/liquidacion/plano-conjunto?ids=a,b", headers=_h(admin_token))
    assert r.status_code == 400


# ─── El documento se elige por persona ────────────────────────────────────────
#
# En un archivo con varias, una puede ir con cedula de extranjeria por su
# subtipo y las demas con la suya. El selector de cada fila tiene que llegar
# hasta el archivo, no solo el de la primera.

def _docs(pares):
    return ",".join(f"{i}:{d}" for i, d in pares)


def test_cada_persona_lleva_el_documento_que_se_le_eligio(client, admin_token, grupo):
    liqs = grupo["liquidaciones"]
    r = _bajar(client, admin_token, liqs,
               docs=_docs([(liqs[0], "CE"), (liqs[1], "PA"), (liqs[2], "CC")]))
    assert r.status_code == 200, r.text
    lineas = _lineas(r.text)
    assert [l[7:9] for l in lineas[1:]] == ["CE", "PA", "CC"]


def test_quien_no_aparece_en_la_lista_conserva_el_suyo(client, admin_token, grupo):
    liqs = grupo["liquidaciones"]
    lineas = _lineas(_bajar(client, admin_token, liqs,
                            docs=_docs([(liqs[1], "CE")])).text)
    documentos = [l[7:9] for l in lineas[1:]]
    assert documentos[1] == "CE"
    assert documentos[0] == "CC" and documentos[2] == "CC"


def test_lo_elegido_para_una_persona_manda_sobre_lo_pedido_para_el_archivo(
        client, admin_token, grupo):
    liqs = grupo["liquidaciones"]
    lineas = _lineas(_bajar(client, admin_token, liqs, tipo_doc="PA",
                            docs=_docs([(liqs[0], "CE")])).text)
    documentos = [l[7:9] for l in lineas[1:]]
    assert documentos[0] == "CE"          # lo suyo gana
    assert documentos[1] == "PA" and documentos[2] == "PA"


def test_un_documento_invalido_se_rechaza(client, admin_token, grupo):
    liqs = grupo["liquidaciones"]
    r = _bajar(client, admin_token, liqs, docs=_docs([(liqs[0], "XX")]))
    assert r.status_code == 400
    assert "tipo_doc" in r.json()["detail"]


@pytest.mark.parametrize("malo", ["12", "abc:CE", "12-CE"])
def test_una_lista_mal_escrita_se_explica(client, admin_token, grupo, malo):
    r = _bajar(client, admin_token, grupo["liquidaciones"], docs=malo)
    assert r.status_code == 400


def test_el_resto_del_archivo_no_cambia_por_el_documento(client, admin_token, grupo):
    """Se tocan dos posiciones y nada mas."""
    liqs = grupo["liquidaciones"]
    normal = _lineas(_bajar(client, admin_token, liqs).text)
    con_ce = _lineas(_bajar(client, admin_token, liqs,
                            docs=_docs([(l, "CE") for l in liqs])).text)
    assert normal[0] == con_ce[0]                     # el encabezado, igual
    for a, b in zip(normal[1:], con_ce[1:]):
        assert a[:7] == b[:7] and a[9:] == b[9:]
        assert b[7:9] == "CE"
