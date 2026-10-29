"""Contract tests against the configured serving database (skipped when it is unreachable)."""
import pytest
from fastapi.testclient import TestClient

from app.db import get_engine
from app.main import app


@pytest.fixture(scope="module")
def client():
    try:
        with get_engine().connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"serving database unreachable: {exc}")
    return TestClient(app)


BR_ENDPOINTS = [
    "/api/v1/volume/daily", "/api/v1/volume/weekly", "/api/v1/volume/summary", "/api/v1/volume/peaks",
    "/api/v1/issues/ranking", "/api/v1/issues/trends", "/api/v1/issues/detail?issue=Charging%20Failure",
    "/api/v1/emerging/alerts", "/api/v1/emerging/series?issue=Charging%20Failure", "/api/v1/emerging/heatmap",
    "/api/v1/sentiment/timeline", "/api/v1/sentiment/by-issue", "/api/v1/sentiment/by-model",
    "/api/v1/features/matrix", "/api/v1/complaints", "/api/v1/compare/options",
    "/api/v1/compare/models?models=iPhone%2017,iPhone%2016", "/api/v1/compare/ios?versions=iOS%2018,iOS%2026",
    "/api/v1/recurring", "/api/v1/support/demand", "/api/v1/pipeline/evidence", "/api/v1/meta/filters",
]


@pytest.mark.parametrize("path", BR_ENDPOINTS)
def test_endpoint_returns_envelope(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body


def test_cross_mart_totals_agree(client):
    """Data-correctness evidence: the same 13.8k posts are counted identically in every mart."""
    ev = client.get("/api/v1/pipeline/evidence").json()["data"]
    failed = [c for c in ev["checks"] if not c["passed"]]
    assert not failed, failed


def test_volume_summary_matches_daily_sum(client):
    daily = client.get("/api/v1/volume/daily").json()["data"]
    summary = client.get("/api/v1/volume/summary").json()["data"][0]
    assert sum(d["total_posts"] for d in daily) == summary["current"]["posts"]


def test_model_filter_folds_variants(client):
    """Filtering by a canonical model must include raw spelling variants."""
    variants = client.get("/api/v1/meta/variants").json()["data"]["models"]
    name, raws = max(variants.items(), key=lambda kv: len(kv[1]))
    assert len(raws) > 1
    s = client.get(f"/api/v1/volume/summary?model={name}").json()["data"][0]
    assert s["current"]["posts"] > 0


def test_complaints_pagination_and_filter(client):
    page1 = client.get("/api/v1/complaints?limit=5&offset=0&include_non_defect=false").json()
    page2 = client.get("/api/v1/complaints?limit=5&offset=5&include_non_defect=false").json()
    assert len(page1["data"]) == 5 and len(page2["data"]) == 5
    assert {d["post_id"] for d in page1["data"]}.isdisjoint({d["post_id"] for d in page2["data"]})
    assert all(d["issue_category"] != "Non-Defect / General Inquiry" for d in page1["data"])


def test_emerging_default_matches_gold_rule(client):
    body = client.get("/api/v1/emerging/alerts?limit=1000").json()
    assert all(d["matches_gold_rule"] for d in body["data"])


def test_bad_sort_rejected(client):
    assert client.get("/api/v1/complaints?sort=drop%20table").status_code == 422
