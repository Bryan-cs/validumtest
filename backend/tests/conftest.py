"""Configuración de pytest.

Si TEST_DATABASE_URL está definida (PostgreSQL), se usan tests de integración reales.
Si no, se usa SQLite local para tests unitarios rápidos.

Uso:
  TEST_DATABASE_URL=postgresql://user:pass@localhost/bbcfile_test pytest   # integración
  pytest                                                                     # SQLite (default)
"""
import os
import sys

# Permite `from conftest import TestingSession` en tests aunque tests/ sea un package
_tests_dir = os.path.dirname(__file__)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

_pg_url = os.environ.get("TEST_DATABASE_URL")
TEST_DB_URL = _pg_url if _pg_url else "sqlite:///./test_bbcfile.db"

os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-testing")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db

_connect_args = {} if _pg_url else {"check_same_thread": False}
engine_test = create_engine(TEST_DB_URL, connect_args=_connect_args)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    import models  # noqa: F401 — registra modelos en Base
    Base.metadata.create_all(bind=engine_test)

    # Seed mínimo: admin + empleado1
    from database import _seed
    db = TestingSession()
    try:
        _seed(db)
    finally:
        db.close()

    from main import app
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine_test)
    engine_test.dispose()
    if not _pg_url:
        try:
            os.remove("./test_bbcfile.db")
        except (FileNotFoundError, PermissionError):
            pass


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def empleado_token(client):
    r = client.post("/auth/login", json={"username": "empleado1", "password": "emp1234"})
    return r.json()["access_token"]


@pytest.fixture
def db():
    """Sesión DB directa para tests de scheduler/modelos (no pasa por FastAPI)."""
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
