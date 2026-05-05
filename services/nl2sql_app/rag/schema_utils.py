from __future__ import annotations

import re

_SCHEMA_LINE = re.compile(r"^table\s+([\w.]+)\s*:", re.IGNORECASE)


def parse_table_name(doc_line: str) -> str | None:
    match = _SCHEMA_LINE.match(doc_line.strip())
    if not match:
        return None
    full = match.group(1).lower()
    return full.split(".")[-1]


def columns_from_doc(doc_line: str) -> list[str]:
    line = doc_line.strip()
    idx = line.lower().find("columns ")
    if idx < 0:
        return []
    rest = line[idx + len("columns ") :]
    out: list[str] = []
    for part in rest.split(","):
        part = part.strip()
        if not part:
            continue
        name = part.split("(", 1)[0].strip()
        if name:
            out.append(name)
    return out


def tables_from_docs(docs: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for doc in docs:
        name = parse_table_name(doc)
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered
