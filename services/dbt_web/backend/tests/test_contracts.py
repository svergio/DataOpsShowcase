from __future__ import annotations

from app.schemas.contracts import RunJobRequest, RunJobResponse


def test_run_job_contract_roundtrip() -> None:
    payload = RunJobRequest(selectors=["tag:staging"], vars={"env": "dev"})
    assert payload.selectors == ["tag:staging"]
    response = RunJobResponse(run_id="abc123", status="queued", target="staging")
    assert response.run_id == "abc123"
