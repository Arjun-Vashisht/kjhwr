import pytest
from fastapi.testclient import TestClient

from app import main
from tests.test_analysis import fake  # noqa: F401  (fixture)


@pytest.fixture
def client(fake, monkeypatch):  # noqa: F811
    monkeypatch.setattr(main, "get_data", lambda: fake)
    return TestClient(main.app)


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["default_gate"] == "09:20"
    assert body["first_delivery_day"] == "2026-01-02"


def test_decision_rejects_out_of_range_day(client):
    assert client.get("/api/decision?day=2025-12-01").status_code == 400


def test_decision_rejects_unknown_gate(client):
    assert client.get("/api/decision?day=2026-01-10&gate=12:00").status_code == 400


def test_accuracy_needs_exactly_one_mode(client):
    assert client.get("/api/accuracy").status_code == 400
    assert client.get("/api/accuracy?horizon=4&gate=09:20").status_code == 400


def test_accuracy_by_gate(client):
    body = client.get("/api/accuracy?gate=09:20").json()
    assert body["metrics"]["n"] > 0
    assert body["histogram"]


def test_horizons(client):
    rows = client.get("/api/horizons").json()
    assert rows[0]["horizon"] == 0
