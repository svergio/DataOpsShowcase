from __future__ import annotations

CANONICAL_TABLES = ("raw.oltp_employees",)

# Keep legacy aliases to avoid runtime breakage from stale prompts/model priors.
TABLE_ALIASES = {
    "oltp_employees": "raw.oltp_employees",
    "public.oltp_employees": "raw.oltp_employees",
    "employees": "raw.oltp_employees",
    "public.employees": "raw.oltp_employees",
    "hr_employees": "raw.oltp_employees",
    "public.hr_employees": "raw.oltp_employees",
}
