"""Tests de autenticación."""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

client = TestClient(app)


def test_login_admin():
    res = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["rol"] == "admin"


def test_login_wrong_password():
    res = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_login_nonexistent_user():
    res = client.post("/auth/login", json={"username": "noexiste", "password": "pass"})
    assert res.status_code == 401


def test_me_requires_auth():
    res = client.get("/auth/me")
    assert res.status_code == 403


def test_me_with_valid_token():
    login = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login.json()["access_token"]
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["sub"] == "admin"


def test_refresh_token():
    login = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    data = login.json()
    assert "refresh_token" in data
    refresh = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert refresh.status_code == 200
    assert "access_token" in refresh.json()


def test_refresh_token_invalid():
    res = client.post("/auth/refresh", json={"refresh_token": "invalid.token.here"})
    assert res.status_code == 401
