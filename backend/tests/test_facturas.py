"""Tests del módulo de facturación."""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import app

client = TestClient(app)


@pytest.fixture
def auth():
    res = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_list_facturas(auth):
    res = client.get("/facturas", headers=auth)
    assert res.status_code == 200


def test_list_facturas_pagination(auth):
    res = client.get("/facturas?skip=0&limit=5", headers=auth)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data


def test_dashboard(auth):
    res = client.get("/dashboard", headers=auth)
    assert res.status_code == 200
    data = res.json()
    assert "activos" in data


def test_cobro(auth):
    res = client.get("/cobro", headers=auth)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_dashboard_meses(auth):
    res = client.get("/dashboard/meses", headers=auth)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 6
