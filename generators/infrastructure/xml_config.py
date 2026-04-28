from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _parse_float(s: str) -> float:
    return float(s.strip())


def _parse_int(s: str) -> int:
    return int(s.strip())


def _child_text(el: ET.Element, tag: str, default: str = "") -> str:
    c = el.find(tag)
    if c is None or c.text is None:
        return default
    return c.text.strip()


def _child_dict_float(parent: ET.Element, group_tag: str, item_tag: str, key_attr: str = "name") -> dict[str, float]:
    out: dict[str, float] = {}
    g = parent.find(group_tag)
    if g is None:
        return out
    for item in g.findall(item_tag):
        k = item.get(key_attr)
        v = item.get("value") or item.get("p")
        if k and v is not None:
            out[k] = float(v)
    return out


def _child_tuples(parent: ET.Element, group_tag: str, item_tag: str) -> list[tuple[str, float, float]]:
    out: list[tuple[str, float, float]] = []
    g = parent.find(group_tag)
    if g is None:
        return out
    for item in g.findall(item_tag):
        name = item.get("name")
        lo = item.get("min")
        hi = item.get("max")
        if name and lo is not None and hi is not None:
            out.append((name, float(lo), float(hi)))
    return out


def _string_list(node: ET.Element | None) -> list[str]:
    if node is None:
        return []
    return [c.text.strip() for c in node.findall("item") if c.text and c.text.strip()]


def _nested_benchmarks(parent: ET.Element) -> dict[str, dict[str, tuple[float, float]]]:
    pb = parent.find("performance_benchmarks")
    if pb is None:
        return {}
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for ct in pb.findall("campaign_type"):
        name = ct.get("name")
        if not name:
            continue
        inner: dict[str, tuple[float, float]] = {}
        for child in ct:
            lo, hi = child.get("min"), child.get("max")
            if lo is not None and hi is not None:
                inner[child.tag] = (float(lo), float(hi))
        out[name] = inner
    return out


def _duration_buckets(parent: ET.Element) -> list[dict[str, Any]]:
    dur = parent.find("duration")
    if dur is None:
        return []
    rows: list[dict[str, Any]] = []
    for b in dur.findall("bucket"):
        rows.append({
            "name": b.get("name", ""),
            "days_min": int(b.get("days_min", 1)),
            "days_max": int(b.get("days_max", 7)),
            "weight": float(b.get("weight", 0.33)),
        })
    return rows


def _seasonality_map(parent: ET.Element) -> dict[int, float]:
    season = parent.find("seasonality")
    if season is None:
        return {}
    out: dict[int, float] = {}
    for m in season.findall("month"):
        n = m.get("n")
        if n is not None:
            out[int(n)] = float(m.get("mult", "1"))
    return out


def _bounce_rates(parent: ET.Element) -> dict[str, float]:
    br = parent.find("bounce_rates")
    if br is None:
        return {}
    out: dict[str, float] = {}
    for p in br.findall("page"):
        path = p.get("path") or p.get("name")
        r = p.get("rate")
        if path and r is not None:
            out[path] = float(r)
    return out


def _conversion_rates(parent: ET.Element) -> dict[str, float]:
    cr = parent.find("conversion_rates")
    if cr is None:
        return {}
    out: dict[str, float] = {}
    for p in cr.findall("intent"):
        k = p.get("name") or p.get("type")
        r = p.get("rate")
        if k and r is not None:
            out[k] = float(r)
    return out


def _connection_multipliers(parent: ET.Element) -> dict[str, float]:
    cm = parent.find("connection_multipliers")
    if cm is None:
        return {}
    out: dict[str, float] = {}
    for c in cm.findall("connection"):
        n = c.get("name") or c.get("type")
        m = c.get("mult")
        if n and m is not None:
            out[n] = float(m)
    return out


def _web_vitals_benchmarks(parent: ET.Element) -> dict[str, dict[str, tuple[float, float]]]:
    wb = parent.find("device_benchmarks")
    if wb is None:
        return {}
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for dev in wb.findall("device"):
        dname = dev.get("name")
        if not dname:
            continue
        inner: dict[str, tuple[float, float]] = {}
        for metric in dev:
            lo, hi = metric.get("min"), metric.get("max")
            if lo is not None and hi is not None:
                inner[metric.tag] = (float(lo), float(hi))
        out[dname] = inner
    return out


def _error_weights(parent: ET.Element, group_tag: str) -> dict[str, float]:
    return _child_dict_float(parent, group_tag, "weight")


def _feature_flag_rows(parent: ET.Element) -> tuple[list[dict[str, Any]], int, int]:
    fg = parent.find("flags")
    extra_count = 0
    extra_rollout_max = 60
    if fg is None:
        return [], 0, 60
    rows: list[dict[str, Any]] = []
    for fl in fg.findall("flag"):
        tgt = fl.find("targeting")
        targeting = tgt.text.strip() if tgt is not None and tgt.text else "{}"
        rows.append({
            "key": fl.get("key", ""),
            "flag_name": fl.get("name", ""),
            "description": fl.get("description", ""),
            "enabled": str(fl.get("enabled", "true")).lower() in ("true", "1", "yes"),
            "rollout": int(fl.get("rollout", "0")),
            "targeting": targeting,
        })
    extras = fg.find("extra_random_flags")
    if extras is not None:
        if extras.get("count"):
            extra_count = int(extras.get("count", "0"))
        if extras.get("rollout_max"):
            extra_rollout_max = int(extras.get("rollout_max", "60"))
    return rows, extra_count, extra_rollout_max


def _salary_ranges(parent: ET.Element) -> dict[str, dict[str, tuple[float, float]]]:
    sr = parent.find("salary_ranges")
    if sr is None:
        return {}
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for dept in sr.findall("department"):
        dname = dept.get("name")
        if not dname:
            continue
        out[dname] = {}
        for lv in dept.findall("level"):
            ln = lv.get("name")
            lo, hi = lv.get("min"), lv.get("max")
            if ln and lo is not None and hi is not None:
                out[dname][ln] = (float(lo), float(hi))
    return out


def load_generator_xml(name: str, config_dir: str | None = None) -> dict[str, Any]:
    base = Path(config_dir or os.getenv("GENERATOR_CONFIG_DIR", "/app/configs/generators"))
    path = base / f"{name}.xml"
    if not path.is_file():
        return {}
    tree = ET.parse(path)
    root = tree.getroot()
    out: dict[str, Any] = {"_name": root.get("name", name)}
    vol = root.find("volume")
    if vol is not None:
        out["total"] = _parse_int(_child_text(vol, "total", "500"))
        out["monthly_new_min"] = _parse_int(_child_text(vol, "monthly_new_min", "10"))
        out["monthly_new_max"] = _parse_int(_child_text(vol, "monthly_new_max", "20"))
        out["rows_min"] = _parse_int(_child_text(vol, "rows_min", "80"))
        out["rows_max"] = _parse_int(_child_text(vol, "rows_max", "200"))
        out["total_entries"] = _parse_int(_child_text(vol, "total_entries", "2000"))
    out["weights"] = _child_dict_float(root, "weights", "weight")
    br_raw = _child_tuples(root, "budget_ranges", "range")
    out["budget_ranges"] = [(t[0], t[1], t[2]) for t in br_raw]
    edge = root.find("edge_cases")
    if edge is not None:
        out["edge_cases"] = {c.tag: _parse_float(c.text or "0") for c in edge}
    lim = root.find("limits")
    if lim is not None:
        for c in lim:
            if c.text:
                out[f"limit_{c.tag}"] = _parse_int(c.text)
        et = lim.find("emit_every_ticks")
        if et is not None and et.text:
            out["emit_every_ticks"] = _parse_int(et.text)
        rpe = lim.find("records_per_emit")
        if rpe is not None and rpe.text:
            out["records_per_emit"] = _parse_int(rpe.text)
        lpe = lim.find("lines_per_emit")
        if lpe is not None and lpe.text:
            out["lines_per_emit"] = _parse_int(lpe.text)
        rpe = lim.find("reviews_per_emit")
        if rpe is not None and rpe.text:
            out["reviews_per_emit"] = _parse_int(rpe.text)
        rint = lim.find("redis_aggregate_every_ticks")
        if rint is not None and rint.text:
            out["redis_aggregate_every_ticks"] = _parse_int(rint.text)
        fe = lim.find("feature_eval_every_ticks")
        if fe is not None and fe.text:
            out["feature_eval_every_ticks"] = _parse_int(fe.text)
    perf = root.find("throughput")
    if perf is not None:
        out["events_per_tick_min"] = _parse_int(_child_text(perf, "events_per_tick_min", "5"))
        out["events_per_tick_max"] = _parse_int(_child_text(perf, "events_per_tick_max", "30"))

    dw = _child_dict_float(root, "department_weights", "weight")
    if dw:
        out["department_weights"] = dw
    lw = _child_dict_float(root, "level_weights", "weight")
    if lw:
        out["level_weights"] = lw
    em = _child_dict_float(root, "email_client_weights", "weight")
    if em:
        out["email_client_weights"] = em
    eng = _child_dict_float(root, "engineering_level_weights", "weight")
    if eng:
        out["engineering_level_weights"] = eng
    rem = _child_dict_float(root, "remote_status_weights", "weight")
    if rem:
        out["remote_status_weights"] = rem
    rat = _child_dict_float(root, "rating_weights", "weight")
    if rat:
        out["rating_weights"] = rat

    ctm = _child_dict_float(root, "campaign_type_mix", "weight")
    if ctm:
        out["campaign_type_mix"] = ctm
    kw_weights = _child_dict_float(root, "keyword_category_weights", "weight")
    if kw_weights:
        out["keyword_category_weights"] = kw_weights
    rk_dist = _child_dict_float(root, "rank_distribution", "weight")
    if rk_dist:
        out["rank_distribution"] = rk_dist

    dbuckets = _duration_buckets(root)
    if dbuckets:
        out["duration_buckets"] = dbuckets
    smap = _seasonality_map(root)
    if smap:
        out["seasonality"] = smap

    nb = _nested_benchmarks(root)
    if nb:
        out["performance_benchmarks"] = nb

    wvb = _web_vitals_benchmarks(root)
    if wvb:
        out["device_benchmarks"] = wvb

    br = _bounce_rates(root)
    if br:
        out["bounce_rates"] = br
    cr = _conversion_rates(root)
    if cr:
        out["conversion_rates"] = cr
    cm = _connection_multipliers(root)
    if cm:
        out["connection_multipliers"] = cm

    etw = _error_weights(root, "error_type_weights")
    if etw:
        out["error_type_weights"] = etw
    sew = _error_weights(root, "severity_weights")
    if sew:
        out["severity_weights"] = sew

    sr = _salary_ranges(root)
    if sr:
        out["salary_ranges"] = sr

    frows, fextra, fextra_max = _feature_flag_rows(root)
    if frows:
        out["flag_definitions"] = frows
    if fextra > 0 or fextra_max != 60:
        out["extra_random_flags"] = fextra
        out["extra_random_rollout_max"] = fextra_max

    sv = root.find("search_volume_lognormal")
    if sv is not None:
        out["search_volume_mean"] = float(sv.get("mean", "7"))
        out["search_volume_sigma"] = float(sv.get("sigma", "1.5"))

    gl = root.find("gl_edge_cases")
    if gl is not None:
        out["gl_edge_cases"] = {c.tag: _parse_float(c.text or "0") for c in gl}

    for list_tag in (
        "age_ranges",
        "countries_pool",
        "interests_pool",
        "customer_segments",
        "device_preferences",
        "keyword_prefixes",
        "email_event_types",
        "bounce_reasons",
        "office_codes",
        "time_event_types",
        "landing_pages",
        "organic_keywords",
        "page_urls_sample",
        "common_error_messages",
        "first_names",
        "last_names",
    ):
        node = root.find(list_tag)
        if node is not None:
            out[list_tag] = _string_list(node)

    _g = root.find("search_engine_weights")
    if _g is not None:
        se_out: dict[str, float] = {}
        for w in _g.findall("weight"):
            k = w.get("name")
            v = w.get("value")
            if k and v is not None:
                se_out[k] = float(v)
        if se_out:
            out["search_engine_weights"] = se_out

    _d = root.find("device_type_weights")
    if _d is not None:
        dt_out: dict[str, float] = {}
        for w in _d.findall("weight"):
            k = w.get("name")
            v = w.get("value")
            if k and v is not None:
                dt_out[k] = float(v)
        if dt_out:
            out["device_type_weights"] = dt_out

    seo_edge = root.find("seo_rank_edge_cases")
    if seo_edge is not None:
        out["seo_rank_edge_cases"] = {c.tag: _parse_float(c.text or "0") for c in seo_edge}

    perf_edge = root.find("campaign_perf_edge_cases")
    if perf_edge is not None:
        out["campaign_perf_edge_cases"] = {c.tag: _parse_float(c.text or "0") for c in perf_edge}
    web_perf_edge = root.find("perf_edge_cases")
    if web_perf_edge is not None:
        out["perf_edge_cases"] = {c.tag: _parse_float(c.text or "0") for c in web_perf_edge}
    dmw = _child_dict_float(root, "device_mix_weights", "weight")
    if dmw:
        out["device_mix_weights"] = dmw

    paths = root.find("minio_paths")
    if paths is not None:
        for c in paths:
            if c.text:
                out[f"path_{c.tag}"] = c.text.strip()

    notes = root.find("documentation")
    if notes is not None and notes.text:
        out["documentation"] = notes.text.strip()

    iup = root.find("identified_user_probability")
    if iup is not None and iup.text:
        out["identified_user_probability"] = float(iup.text.strip())

    return out


def load_all_maps(config_dir: str | None = None) -> dict[str, dict[str, Any]]:
    base = Path(config_dir or os.getenv("GENERATOR_CONFIG_DIR", "/app/configs/generators"))
    if not base.is_dir():
        return {}
    merged: dict[str, dict[str, Any]] = {}
    for p in sorted(base.glob("*.xml")):
        key = p.stem
        merged[key] = load_generator_xml(key, str(base))
    return merged
