"""Tests for the public investigation API and persistence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.graph.deps import ResearchOrchestrationDeps
from app.graph.graph import build_investigation_graph
from app.llm.local import LocalLLMProvider
from app.main import create_app
from app.services.investigation import InvestigationService
from app.services.investigation_app import InvestigationAppService

SAMPLE_QUERY = (
    "Is Sector 62, Noida a good location for a cloud kitchen targeting office workers?"
)


def _client(settings_env: None) -> TestClient:
    application = create_app()
    test_client = TestClient(application)
    test_client.__enter__()
    graph = build_investigation_graph(
        llm=LocalLLMProvider(),
        deps=ResearchOrchestrationDeps.mock(),
    )
    runner = InvestigationService(graph=graph)
    application.state.investigation_service = runner
    application.state.investigation_app_service = InvestigationAppService(
        store=application.state.investigation_store,
        runner=runner,
    )
    return test_client


def test_create_and_retrieve_investigation(settings_env: None) -> None:
    client = _client(settings_env)
    try:
        created = client.post("/investigations", json={"query": SAMPLE_QUERY})
        assert created.status_code == 202
        payload = created.json()
        assert payload["id"]
        assert payload["status"] == "CREATED"
        investigation_id = payload["id"]

        status = client.get(f"/investigations/{investigation_id}/status")
        assert status.status_code == 200
        assert status.json()["status"] == "COMPLETED"
        assert status.json()["id"] == investigation_id

        detail = client.get(f"/investigations/{investigation_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["query"] == SAMPLE_QUERY
        assert "agent_runs" not in body
        assert "metadata" not in body
        assert body["recommendation"]
        assert body["plan"]

        evidence = client.get(f"/investigations/{investigation_id}/evidence")
        assert evidence.status_code == 200
        items = evidence.json()["items"]
        assert items
        assert "source_name" in items[0]
        assert "allowed_tools" not in items[0]

        report = client.get(f"/investigations/{investigation_id}/report")
        assert report.status_code == 200
        report_body = report.json()
        assert report_body["investigation_id"] == investigation_id
        assert report_body["report"]
        assert report_body["recommendation"]
        assert report_body["critic"] is not None
    finally:
        client.__exit__(None, None, None)


def test_get_unknown_investigation_returns_404(settings_env: None) -> None:
    client = _client(settings_env)
    try:
        response = client.get("/investigations/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "not_found"
        assert "message" in body
    finally:
        client.__exit__(None, None, None)


def test_create_investigation_rejects_empty_query(settings_env: None) -> None:
    client = _client(settings_env)
    try:
        response = client.post("/investigations", json={"query": "   "})
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_request"

        missing = client.post("/investigations", json={})
        assert missing.status_code == 400
        assert missing.json()["code"] == "invalid_request"
    finally:
        client.__exit__(None, None, None)


def test_additional_research_endpoint(settings_env: None) -> None:
    client = _client(settings_env)
    try:
        created = client.post("/investigations", json={"query": SAMPLE_QUERY})
        investigation_id = created.json()["id"]
        follow_up = client.post(
            f"/investigations/{investigation_id}/research",
            json={"tasks": ["competition"]},
        )
        assert follow_up.status_code == 202
        report = client.get(f"/investigations/{investigation_id}/report")
        assert report.status_code == 200
        assert report.json()["status"] == "COMPLETED"
    finally:
        client.__exit__(None, None, None)
