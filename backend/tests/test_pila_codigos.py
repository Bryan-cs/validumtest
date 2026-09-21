"""Tests catálogos PILA — contenido, siembra idempotente, derogación y endpoint."""
import models
from services.pila import catalogos


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Contenido del catálogo normativo (anexo) ─────────────────────────────────

def test_catalogos_del_anexo_completos():
    assert len(catalogos.TIPO_APORTANTE) == 17
    assert len(catalogos.TIPO_PLANILLA) == 18
    assert len(catalogos.TIPO_COTIZANTE) >= 50
    assert catalogos.ANEXO_VERSION == "30"


def test_codigos_de_la_resolucion_1529_de_2026():
    """Los que agregó la última reforma: si faltan, el anexo quedó viejo."""
    assert catalogos.TIPO_APORTANTE["17"] == "Pagador Recicladores de Oficio"
    assert catalogos.TIPO_COTIZANTE["74"] == "Reciclador de Oficio"
    assert "76" in catalogos.TIPO_COTIZANTE
    assert catalogos.TIPO_PLANILLA["W"].startswith("Planilla Reliquidaciones")


def test_sin_codigos_vacios_ni_duplicados():
    for tipo, datos in catalogos.CATALOGOS.items():
        assert all(c.strip() and n.strip() for c, n in datos.items()), tipo


# ─── Datos de referencia (UGPP y DANE) ────────────────────────────────────────

def test_administradoras_por_subsistema():
    # 8 administradoras de pensiones del archivo de la UGPP, mas FSP001, que no
    # es una AFP pero ocupa el campo 31 del regimen exceptuado.
    assert len(catalogos.ADMINISTRADORAS["AFP"]) == 9
    assert len(catalogos.ADMINISTRADORAS["ARL"]) == 10
    assert len(catalogos.ADMINISTRADORAS["EPS"]) >= 25
    assert len(catalogos.ADMINISTRADORAS["CCF"]) >= 40


def test_administradoras_conocidas():
    """Códigos cruzados contra dos fuentes: la lista de la UGPP y el portal ADAX."""
    assert catalogos.ADMINISTRADORAS["AFP"]["230301"].endswith("PORVENIR")
    assert catalogos.ADMINISTRADORAS["AFP"]["230201"].endswith("PROTECCION")
    assert "COLPENSIONES" in catalogos.ADMINISTRADORAS["AFP"]["25-14"]
    assert "Solidaridad" in catalogos.ADMINISTRADORAS["AFP"]["FSP001"]
    assert "SURA" in catalogos.ADMINISTRADORAS["ARL"]["14-11"]


def test_eps_liquidadas_son_historicas_no_vigentes():
    """Cafesalud y Coomeva no operan: no deben poder elegirse, pero su nombre
    debe poder resolverse al abrir una planilla vieja."""
    historicas = catalogos.HISTORICOS["EPS"]
    assert "EPS003" in historicas          # Cafesalud
    assert "EPS016" in historicas          # Coomeva
    assert "EPS003" not in catalogos.ADMINISTRADORAS["EPS"]


def test_dane_completo_y_consistente():
    assert len(catalogos.DEPTO) == 33
    assert len(catalogos.MUNICIPIO) == 1122
    assert catalogos.DEPTO["05"] == "ANTIOQUIA"
    assert catalogos.MUNICIPIO["05001"] == "MEDELLÍN"
    # Cada municipio pertenece al departamento que dicen sus dos primeros dígitos.
    assert all(cod[:2] == dep for cod, dep in catalogos.MUNICIPIO_DEPTO.items())
    assert all(dep in catalogos.DEPTO for dep in catalogos.MUNICIPIO_DEPTO.values())


# ─── Modelo ───────────────────────────────────────────────────────────────────

def test_afiliado_expone_los_campos_del_registro_tipo_2():
    """Sin estas columnas no se puede armar un registro tipo 2, y su ausencia no
    rompe ningún otro test: por eso se comprueban aquí explícitamente."""
    cols = {c.name for c in models.Afiliado.__table__.columns}
    faltan = {
        # nombre partido en cuatro (campos 11-14)
        "primer_apellido", "segundo_apellido", "primer_nombre", "segundo_nombre",
        # clasificación y ubicación
        "tipo_cotizante", "subtipo_cotizante", "cod_depto_labor", "cod_municipio_labor",
        # administradoras por código, no por nombre
        "cod_eps", "cod_afp", "cod_ccf", "cod_arl",
        # salario y riesgo
        "clase_riesgo", "tarifa_arl", "tipo_salario", "salario_basico", "centro_trabajo",
    } - cols
    assert not faltan, f"faltan columnas PILA en Afiliado: {sorted(faltan)}"


def test_tablas_de_liquidacion_existen():
    for modelo in (models.PilaCodigo, models.AportantePila,
                   models.PlanillaLiquidacion, models.PlanillaDetalle):
        assert modelo.__tablename__

# ─── Siembra ──────────────────────────────────────────────────────────────────

def test_siembra_es_idempotente(client, db):
    catalogos.sembrar(db)
    segunda = catalogos.sembrar(db)
    assert segunda == {"creados": 0, "actualizados": 0, "derogados": 0, "historicos": 0}


def test_siembra_deja_el_total_esperado(client, db):
    catalogos.sembrar(db)
    esperado = sum(len(v) for v in catalogos.CATALOGOS.values())
    vigentes = db.query(models.PilaCodigo).filter_by(vigente=True).count()
    assert vigentes == esperado


def test_municipios_quedan_con_su_departamento_como_padre(client, db):
    catalogos.sembrar(db)
    fila = db.query(models.PilaCodigo).filter_by(tipo="MUNICIPIO", codigo="05001").first()
    assert fila.padre == "05"


def test_historicas_se_siembran_no_vigentes(client, db):
    catalogos.sembrar(db)
    fila = db.query(models.PilaCodigo).filter_by(tipo="EPS", codigo="EPS003").first()
    assert fila is not None
    assert fila.vigente is False


def test_codigo_fuera_del_catalogo_se_deroga_pero_no_se_borra(client, db):
    catalogos.sembrar(db)
    db.add(models.PilaCodigo(tipo="TIPO_PLANILLA", codigo="Q",
                             nombre="Planilla de un anexo viejo", vigente=True))
    db.commit()

    resumen = catalogos.sembrar(db)
    assert resumen["derogados"] == 1

    fila = db.query(models.PilaCodigo).filter_by(tipo="TIPO_PLANILLA", codigo="Q").first()
    assert fila is not None, "una planilla histórica todavía puede apuntar a este código"
    assert fila.vigente is False


def test_nombre_cambiado_se_actualiza(client, db):
    catalogos.sembrar(db)
    fila = db.query(models.PilaCodigo).filter_by(tipo="TIPO_PLANILLA", codigo="E").first()
    fila.nombre = "Nombre viejo"
    db.commit()

    resumen = catalogos.sembrar(db)
    assert resumen["actualizados"] >= 1
    db.refresh(fila)
    assert fila.nombre == catalogos.TIPO_PLANILLA["E"]


# ─── Endpoint ─────────────────────────────────────────────────────────────────

def test_listar_todos(client, admin_token):
    r = client.get("/pila/codigos", headers=_h(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["anexo_version"] == "30"
    assert body["total"] >= 1300
    assert "UGPP" in body["fuente_administradoras"]


def test_filtrar_por_tipo(client, admin_token):
    r = client.get("/pila/codigos?tipo=TIPO_APORTANTE", headers=_h(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 17
    assert all(i["tipo"] == "TIPO_APORTANTE" for i in items)
    assert any(i["codigo"] == "01" and i["nombre"] == "Empleador" for i in items)


def test_filtrar_municipios_por_departamento(client, admin_token):
    """Sin el filtro por padre habría que traer los 1.122 municipios del país."""
    r = client.get("/pila/codigos?tipo=MUNICIPIO&padre=05", headers=_h(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert 100 < len(items) < 200          # Antioquia tiene 125 municipios
    assert all(i["codigo"].startswith("05") for i in items)


def test_tipo_desconocido_rechazado(client, admin_token):
    r = client.get("/pila/codigos?tipo=INVENTADO", headers=_h(admin_token))
    assert r.status_code == 400
    assert "Catálogo desconocido" in r.json()["detail"]


def test_derogados_ocultos_por_defecto(client, admin_token):
    vigentes = client.get("/pila/codigos?tipo=EPS", headers=_h(admin_token)).json()["items"]
    assert all(i["codigo"] != "EPS003" for i in vigentes)

    todos = client.get("/pila/codigos?tipo=EPS&incluir_derogados=true",
                       headers=_h(admin_token)).json()["items"]
    assert any(i["codigo"] == "EPS003" for i in todos)


def test_empleado_puede_leer(client, empleado_token):
    assert client.get("/pila/codigos", headers=_h(empleado_token)).status_code == 200


def test_requiere_autenticacion(client):
    assert client.get("/pila/codigos").status_code in (401, 403)
