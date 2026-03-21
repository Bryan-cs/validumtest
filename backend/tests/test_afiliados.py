"""Tests del módulo de afiliados."""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import app

client = TestClient(app)


@pytest.fixture
def token():
    res = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    return res.json()["access_token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_list_afiliados(auth):
    res = client.get("/afiliados", headers=auth)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data


def test_list_afiliados_pagination(auth):
    res = client.get("/afiliados?skip=0&limit=5", headers=auth)
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) <= 5


def test_create_and_delete_afiliado(auth):
    payload = {
        "nombre": "TEST USUARIO PYTEST",
        "doc": "9999999999",
        "tipo_doc": "CC",
        "empresa": "TEST",
        "servicios": ["EPS"],
        "estado": "ACTIVO",
        "estado_srv": "ACTIVO",
        "subtipo": "0",
        "eps": "", "arl": "", "ccf": "", "afp": "",
        "cargo": "", "tel": "", "email": "",
        "cliente_txt": "", "novedades": "",
    }
    # Create
    res = client.post("/afiliados", json=payload, headers=auth)
    assert res.status_code == 201
    created_id = res.json()["id"]

    # Verify exists
    res2 = client.get(f"/afiliados/{created_id}", headers=auth)
    assert res2.status_code == 200
    assert res2.json()["nombre"] == "TEST USUARIO PYTEST"

    # Delete
    res3 = client.delete(f"/afiliados/{created_id}", headers=auth)
    assert res3.status_code == 200


def test_create_duplicate_doc(auth):
    # First get an existing doc
    res = client.get("/afiliados?limit=1", headers=auth)
    items = res.json().get("items", [])
    if not items:
        pytest.skip("No hay afiliados para probar duplicado")
    existing_doc = items[0]["doc"]

    payload = {
        "nombre": "DUPLICADO TEST",
        "doc": existing_doc,
        "tipo_doc": "CC",
        "empresa": "TEST",
        "servicios": [],
        "estado": "ACTIVO",
        "estado_srv": "ACTIVO",
        "subtipo": "0",
        "eps": "", "arl": "", "ccf": "", "afp": "",
        "cargo": "", "tel": "", "email": "",
        "cliente_txt": "", "novedades": "",
    }
    res2 = client.post("/afiliados", json=payload, headers=auth)
    assert res2.status_code == 400
