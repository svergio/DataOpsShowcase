from __future__ import annotations

from datetime import datetime, timezone

from app.observability.metrics import BROKEN_TESTS_TOTAL, FRESHNESS_LAG_SECONDS


class FreshnessService:
    def summarize(self, run_results: dict) -> dict:
        results = run_results.get("results", [])
        failed_tests = [r for r in results if r.get("status") not in {"pass", "success"}]
        BROKEN_TESTS_TOTAL.set(len(failed_tests))
        lag_sec = 0.0
        metadata = run_results.get("metadata", {})
        generated_at = metadata.get("generated_at")
        if generated_at:
            try:
                ts = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
                lag_sec = (datetime.now(timezone.utc) - ts).total_seconds()
            except Exception:  # noqa: BLE001
                lag_sec = 0.0
        FRESHNESS_LAG_SECONDS.labels(source="aggregate", table="aggregate").set(max(0.0, lag_sec))
        return {"broken_tests": len(failed_tests), "freshness_lag_seconds": max(0.0, lag_sec)}
