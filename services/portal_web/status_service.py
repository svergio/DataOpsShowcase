from __future__ import annotations

import logging
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import docker

from catalog import INIT_CONTAINERS

logger = logging.getLogger(__name__)

_RANK = {"healthy": 0, "running": 1, "degraded": 2, "down": 3}


def worst_status(values: list[str]) -> str:
    if not values:
        return "down"
    return max(values, key=lambda s: _RANK.get(s, 3))


PROBE_TIMEOUT_SEC = 2.0


def _state_bucket(state: str, health_status: str, has_health: bool) -> str:
    if state in ("created", "exited", "dead", "paused"):
        return "down"
    if state == "restarting":
        return "degraded"
    if state != "running":
        return "down"
    if not has_health:
        return "running"
    if health_status == "healthy":
        return "healthy"
    if health_status in ("starting",):
        return "degraded"
    if health_status == "unhealthy":
        return "degraded"
    return "running"


def probe_url(url: str | None) -> bool | None:
    if not url:
        return None
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_SEC, context=ctx) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return True
        return False
    except (OSError, urllib.error.URLError, ValueError):
        return False


def container_snapshot(client: docker.DockerClient) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for c in client.containers.list(all=True):
        name = (c.name or "").lstrip("/")
        st = c.attrs.get("State") or {}
        health = st.get("Health") or {}
        has_hc = bool(health)
        hc_status = (health.get("Status") or "none").lower()
        if not has_hc:
            hc_status = "none"
        exit_code = st.get("ExitCode")
        try:
            exit_code_i = int(exit_code) if exit_code is not None else 0
        except (TypeError, ValueError):
            exit_code_i = 0
        out[name] = {
            "state": st.get("Status", "unknown"),
            "health_status": hc_status,
            "has_health": has_hc,
            "exit_code": exit_code_i,
            "bucket": _state_bucket(
                (st.get("Status") or "").lower(),
                hc_status,
                has_hc,
            ),
        }
    return out


def build_service_rows(
    entries: list[dict[str, str | None]],
    snap: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    probe_by_id: dict[str, bool | None] = {}
    keyed: list[tuple[str, str]] = []
    for e in entries:
        eid = str(e["id"])
        probe = str(e.get("probe_url") or "")
        if probe:
            keyed.append((eid, probe))
    if keyed:
        max_workers = min(12, max(1, len(keyed)))
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(probe_url, p): eid for eid, p in keyed}
            for fut in as_completed(futs):
                eid = futs[fut]
                try:
                    probe_by_id[eid] = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("probe failed for %s: %s", eid, exc)
                    probe_by_id[eid] = False

    rows: list[dict[str, Any]] = []
    for e in entries:
        cname = str(e.get("container") or "")
        info = snap.get(cname) if cname else None
        rollup: str
        state: str
        hc: str
        has_hc: bool
        if not cname:
            rollup = "down"
            state = "none"
            hc = "none"
            has_hc = False
        elif not info:
            rollup = "down"
            state = "missing"
            hc = "none"
            has_hc = False
        else:
            st_l = str(info["state"]).lower()
            c_is_init = cname in INIT_CONTAINERS
            if c_is_init and st_l == "exited" and int(info.get("exit_code", 1)) == 0:
                rollup = "completed"
                state = "exited"
                hc = str(info["health_status"])
                has_hc = bool(info["has_health"])
            else:
                rollup = str(info["bucket"])
                state = str(info["state"])
                hc = str(info["health_status"])
                has_hc = bool(info["has_health"])
        eid = str(e["id"])
        probe = str(e.get("probe_url") or "")
        ok: bool | None
        if not probe:
            ok = None
        else:
            ok = probe_by_id.get(eid)
        row: dict[str, Any] = {
            "id": e["id"],
            "name": e["name"],
            "route": e.get("route") or "",
            "purpose": e["purpose"],
            "container": cname,
            "rollup": rollup,
            "indicators": {
                "docker_state": state,
                "healthcheck": hc if has_hc else "none",
                "probe_ok": ok,
            },
        }
        if "kind" in e:
            row["kind"] = e["kind"]
        rows.append(row)
    return rows


def _diagram_indicator_triple(container_names: list[str], snap: dict[str, dict[str, Any]]) -> dict[str, str]:
    states: list[str] = []
    health_flags: list[str] = []
    buckets: list[str] = []
    for cname in container_names:
        inf = snap.get(cname)
        if not inf:
            states.append("missing")
            health_flags.append("missing")
            buckets.append("down")
            continue
        states.append(str(inf["state"]).lower())
        buckets.append(str(inf["bucket"]))
        if not inf["has_health"]:
            health_flags.append("none")
        else:
            health_flags.append(str(inf["health_status"]).lower())

    def docker_cls() -> str:
        if any(s in ("missing", "exited", "dead") for s in states):
            return "bad"
        if any(s == "restarting" for s in states):
            return "warn"
        if states and all(s == "running" for s in states):
            return "ok"
        return "warn"

    def health_cls() -> str:
        if any(h == "unhealthy" for h in health_flags):
            return "bad"
        if any(h == "starting" for h in health_flags):
            return "warn"
        if any(h == "missing" for h in health_flags):
            return "bad"
        return "ok"

    def reach_cls() -> str:
        roll = worst_status(buckets)
        return {"healthy": "ok", "running": "ok", "degraded": "warn", "down": "bad"}.get(roll, "bad")

    return {"docker": docker_cls(), "health": health_cls(), "reach": reach_cls()}


def _graph_node_rollup_and_indicators(
    cname: str,
    is_init: bool,
    snap: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, str]]:
    inf = snap.get(cname)
    if not inf:
        return "down", {"docker": "bad", "health": "bad", "reach": "bad"}
    st = str(inf["state"]).lower()
    if is_init and st == "exited":
        if int(inf.get("exit_code", 1)) == 0:
            return "completed", {"docker": "ok", "health": "ok", "reach": "ok"}
        return "down", _diagram_indicator_triple([cname], snap)
    return str(inf["bucket"]), _diagram_indicator_triple([cname], snap)


def build_graph_payload(
    graph_nodes: list[dict[str, object]],
    graph_links: list[tuple[str, str]],
    snap: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    nodes_out: list[dict[str, Any]] = []
    for n in graph_nodes:
        cid = str(n["id"])
        cname = str(n["container"])
        is_init = bool(n.get("is_init"))
        rollup, indicators = _graph_node_rollup_and_indicators(cname, is_init, snap)
        nodes_out.append(
            {
                "id": cid,
                "label_ru": n["label_ru"],
                "container": cname,
                "shape_kind": n["shape_kind"],
                "group": int(n.get("group", 0)),
                "optional": bool(n.get("optional", False)),
                "is_init": is_init,
                "rollup": rollup,
                "indicators": indicators,
            }
        )
    links_out = [{"source": a, "target": b} for a, b in graph_links]
    return {"nodes": nodes_out, "links": links_out}


def try_snapshots() -> tuple[dict[str, dict[str, Any]], str | None]:
    try:
        client = docker.from_env()
        snap = container_snapshot(client)
        return snap, None
    except Exception as exc:  # noqa: BLE001
        logger.warning("docker status unavailable: %s", exc)
        return {}, str(exc)
