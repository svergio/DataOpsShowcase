from __future__ import annotations

import json
import logging
import threading
from typing import Any, get_args

from flask import Blueprint, current_app, jsonify, request

from app.observability.metrics import WEBHOOK_EVENTS_TOTAL
from app.schemas.contracts import ArtifactName, EventPayload, ModelSearchResponse, RunJobRequest, TargetName
from app.services.validators import validate_manifest
from app.state import AppState

logger = logging.getLogger(__name__)

bp = Blueprint("api_v1", __name__)


def get_ctx() -> AppState:
    return current_app.extensions["dbt_ctx"]


def _json_model(obj: object) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


@bp.route("/health", methods=["GET"])
def health() -> Any:
    return jsonify({"status": "ok"})


@bp.route("/runs/<target>", methods=["POST"])
def run_job(target: str) -> Any:
    state = get_ctx()
    body = request.get_json(silent=True) or {}
    payload = RunJobRequest.model_validate(body)
    if target not in get_args(TargetName):
        return jsonify({"error": "invalid target"}), 400
    data = state.dbt_rest.run_job(target, payload)  # type: ignore[arg-type]
    return jsonify(_json_model(data)), 200


@bp.route("/runs/<run_id>", methods=["GET"])
def run_status(run_id: str) -> Any:
    state = get_ctx()
    data = state.dbt_rest.get_run_status(run_id)
    return jsonify(_json_model(data)), 200


@bp.route("/runs/<run_id>/logs", methods=["GET"])
def run_logs(run_id: str) -> Any:
    state = get_ctx()
    data = state.dbt_rest.get_run_logs(run_id)
    return jsonify(_json_model(data)), 200


@bp.route("/runs", methods=["GET"])
def list_runs() -> Any:
    state = get_ctx()
    status = request.args.get("status")
    target = request.args.get("target")
    limit = int(request.args.get("limit", 50))
    limit = max(1, min(500, limit))
    targets = [target] if target else ["staging", "vault", "marts"]
    items: list[dict[str, Any]] = []
    for tgt in targets:
        latest = state.storage.get_json(f"dbt-artifacts/latest-success/{tgt}/run_results.json") or {}
        meta = latest.get("metadata", {}) or {}
        results = latest.get("results", []) or []
        passed = sum(1 for r in results if r.get("status") in {"pass", "success"})
        failed = len(results) - passed
        run_st = "success" if failed == 0 and results else ("failed" if failed > 0 else "unknown")
        if status and status != run_st:
            continue
        items.append(
            {
                "target": tgt,
                "run_id": meta.get("invocation_id"),
                "generated_at": meta.get("generated_at"),
                "dbt_version": meta.get("dbt_version"),
                "elapsed_time": latest.get("elapsed_time"),
                "results_total": len(results),
                "results_passed": passed,
                "results_failed": failed,
                "status": run_st,
            }
        )
    return jsonify({"total": len(items[:limit]), "items": items[:limit]}), 200


@bp.route("/tests/summary", methods=["GET"])
def tests_summary() -> Any:
    state = get_ctx()
    target = request.args.get("target")
    severity = request.args.get("severity")
    targets = [target] if target else ["staging", "vault", "marts"]
    failed: list[dict[str, Any]] = []
    summary: dict[str, dict[str, int]] = {}
    for tgt in targets:
        latest = state.storage.get_json(f"dbt-artifacts/latest-success/{tgt}/run_results.json") or {}
        results = latest.get("results", []) or []
        for r in results:
            unique_id = r.get("unique_id", "")
            if not str(unique_id).startswith("test."):
                continue
            sev = (r.get("config", {}) or {}).get("severity") or r.get("severity") or "error"
            status_str = r.get("status", "unknown")
            ok = status_str in {"pass", "success"}
            bucket = summary.setdefault(tgt, {"total": 0, "passed": 0, "failed": 0})
            bucket["total"] += 1
            if ok:
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
                if severity and severity != sev:
                    continue
                failed.append(
                    {
                        "target": tgt,
                        "unique_id": unique_id,
                        "status": status_str,
                        "severity": sev,
                        "message": r.get("message"),
                        "execution_time": r.get("execution_time"),
                    }
                )
    return jsonify({"summary": summary, "failed": failed, "failed_total": len(failed)}), 200


@bp.route("/models", methods=["GET"])
def search_models() -> Any:
    state = get_ctx()
    query = request.args.get("query", "")
    tags = request.args.get("tags", "")
    resource_type = request.args.get("resource_type", "")
    schema = request.args.get("schema", "")
    package_name = request.args.get("package_name", "")
    items: list[dict[str, Any]] = []
    for uid, item in state.model_index.items():
        row: dict[str, Any] = {**item, "unique_id": uid}
        if query and query.lower() not in str(row.get("name", "")).lower():
            continue
        if tags:
            tag_set = {t.strip() for t in tags.split(",") if t.strip()}
            if not tag_set.intersection(set(row.get("tags", []))):
                continue
        if resource_type and row.get("resource_type") != resource_type:
            continue
        if schema and row.get("schema") != schema:
            continue
        if package_name and row.get("package_name") != package_name:
            continue
        items.append(row)
    resp = ModelSearchResponse(total=len(items), items=items)
    return jsonify(_json_model(resp)), 200


@bp.route("/models/<path:unique_id>/dependencies", methods=["GET"])
def dependencies(unique_id: str) -> Any:
    state = get_ctx()
    return jsonify(state.lineage.get_dependencies(state.model_index, unique_id)), 200


@bp.route("/exposures", methods=["GET"])
def exposures() -> Any:
    state = get_ctx()
    items = [x for x in state.model_index.values() if x.get("resource_type") == "exposure"]
    return jsonify({"total": len(items), "items": items}), 200


@bp.route("/freshness", methods=["GET"])
def freshness() -> Any:
    state = get_ctx()
    latest = state.storage.get_json("dbt-artifacts/latest-success/marts/run_results.json") or {}
    return jsonify(state.freshness.summarize(latest)), 200


@bp.route("/lineage", methods=["GET"])
def lineage_graph() -> Any:
    state = get_ctx()
    resource_type = request.args.get("resource_type")
    schema = request.args.get("schema")
    package_name = request.args.get("package_name")
    tag = request.args.get("tag")
    nodes: list[dict] = []
    edges: list[dict] = []
    for uid, item in state.model_index.items():
        if resource_type and item.get("resource_type") != resource_type:
            continue
        if schema and item.get("schema") != schema:
            continue
        if package_name and item.get("package_name") != package_name:
            continue
        if tag and tag not in (item.get("tags") or []):
            continue
        nodes.append(
            {
                "id": uid,
                "name": item.get("name"),
                "resource_type": item.get("resource_type"),
                "schema": item.get("schema"),
                "package_name": item.get("package_name"),
                "tags": item.get("tags", []),
            }
        )
        for dep in item.get("depends_on", []):
            edges.append({"source": dep, "target": uid})
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]
    return jsonify(
        {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }
    ), 200


@bp.route("/lineage/<path:unique_id>", methods=["GET"])
def lineage(unique_id: str) -> Any:
    state = get_ctx()
    node = state.model_index.get(unique_id)
    if node is None:
        return jsonify({"unique_id": unique_id, "upstream": [], "downstream": []}), 200
    upstream = node.get("depends_on", [])
    downstream = [uid for uid, item in state.model_index.items() if unique_id in item.get("depends_on", [])]
    return jsonify({"unique_id": unique_id, "node": node, "upstream": upstream, "downstream": downstream}), 200


def _latest(state: AppState, target: str, name: str) -> dict:
    return state.storage.get_json(f"dbt-artifacts/latest-success/{target}/{name}") or {}


@bp.route("/docs/manifest", methods=["GET"])
def docs_manifest() -> Any:
    return jsonify(_latest(get_ctx(), "marts", "manifest.json")), 200


@bp.route("/docs/catalog", methods=["GET"])
def docs_catalog() -> Any:
    return jsonify(_latest(get_ctx(), "marts", "catalog.json")), 200


@bp.route("/docs/run_results", methods=["GET"])
def docs_run_results() -> Any:
    return jsonify(_latest(get_ctx(), "marts", "run_results.json")), 200


@bp.route("/docs/graph", methods=["GET"])
def docs_graph() -> Any:
    state = get_ctx()
    manifest = _latest(state, "marts", "manifest.json")
    return jsonify(
        state.docs.docs_payload(manifest, _latest(state, "marts", "catalog.json"), _latest(state, "marts", "run_results.json"))["graph"]
    ), 200


@bp.route("/docs/refresh", methods=["POST"])
def docs_refresh() -> Any:
    state = get_ctx()
    payload = request.get_json(silent=True) or {}
    run_id = str(payload.get("run_id", "latest"))
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        artifact = state.dbt_rest.get_artifact(run_id, name)  # type: ignore[arg-type]
        state.cache.save_cached(run_id, "marts", artifact)
    manifest = _latest(state, "marts", "manifest.json")
    validate_manifest(manifest)
    state.model_index = state.lineage.build_index(manifest)
    return jsonify({"status": "ok", "source": payload.get("source", "manual")}), 200


@bp.route("/docs/reload", methods=["POST"])
def docs_reload() -> Any:
    state = get_ctx()
    for target in ("marts", "vault", "staging"):
        manifest = _latest(state, target, "manifest.json")
        if manifest:
            state.model_index = state.lineage.build_index(manifest)
            return jsonify({"status": "ok", "source": target, "models": len(state.model_index)}), 200
    state.model_index = {}
    return jsonify({"status": "empty", "source": None, "models": 0}), 200


_VALID_ARTIFACT: set[str] = set(get_args(ArtifactName))


@bp.route("/runs/<run_id>/artifacts/<path:name>", methods=["GET"])
def get_artifact(run_id: str, name: str) -> Any:
    if name not in _VALID_ARTIFACT:
        return jsonify({"error": "invalid artifact name"}), 400
    name_t = name  # type: ignore[assignment]
    state = get_ctx()
    target = request.args.get("target", "manual")
    cached = state.cache.get_cached(run_id, name, target=target)  # type: ignore[arg-type]
    if cached is not None:
        return jsonify(_json_model(cached)), 200
    artifact = state.dbt_rest.get_artifact(run_id, name_t)  # type: ignore[arg-type]
    state.cache.save_cached(run_id, target, artifact)
    return jsonify(_json_model(artifact)), 200


def _refresh_for_target(state: AppState, run_id: str, target: str) -> None:
    for aname in ("manifest.json", "catalog.json", "run_results.json"):
        try:
            artifact = state.dbt_rest.get_artifact(run_id, aname)  # type: ignore[arg-type]
            state.cache.save_cached(run_id, target, artifact)
        except Exception:  # noqa: BLE001
            continue
    manifest = state.storage.get_json(f"dbt-artifacts/latest-success/{target}/manifest.json") or {}
    state.model_index = state.lineage.build_index(manifest)


def _handle_event(*, event: str, target: str, payload: EventPayload, state: AppState) -> dict:
    if payload.event_id in state.seen_events:
        WEBHOOK_EVENTS_TOTAL.labels(event=event, status="duplicate").inc()
        return {"status": "ignored", "event": event, "event_id": payload.event_id}
    state.seen_events.add(payload.event_id)
    WEBHOOK_EVENTS_TOTAL.labels(event=event, status="accepted").inc()
    run_id = payload.run_id or "latest"

    def _bg() -> None:
        try:
            _refresh_for_target(state, str(run_id), target)
        except Exception:  # noqa: BLE001
            logger.exception("event refresh failed")

    threading.Thread(target=_bg, daemon=True).start()
    return {"status": "accepted", "event": event, "event_id": payload.event_id}


@bp.route("/events/ingestion_completed", methods=["POST"])
def ingestion_completed() -> Any:
    payload = EventPayload.model_validate(request.get_json() or {})
    return jsonify(
        _handle_event(event="ingestion_completed", target="staging", payload=payload, state=get_ctx())
    ), 200


@bp.route("/events/datavault_completed", methods=["POST"])
def datavault_completed() -> Any:
    payload = EventPayload.model_validate(request.get_json() or {})
    return jsonify(
        _handle_event(event="datavault_completed", target="vault", payload=payload, state=get_ctx())
    ), 200


@bp.route("/events/marts_completed", methods=["POST"])
def marts_completed() -> Any:
    payload = EventPayload.model_validate(request.get_json() or {})
    return jsonify(
        _handle_event(event="marts_completed", target="marts", payload=payload, state=get_ctx())
    ), 200
