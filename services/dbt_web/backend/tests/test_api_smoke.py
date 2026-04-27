from __future__ import annotations

import pytest
from app.main import app

@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_metrics_endpoint(client) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200


def test_login_get(client) -> None:
    r = client.get("/dbt-web/login")
    assert r.status_code == 200
