SYSTEM_RULES = """
You are NL2SQL generator for HR analytics.
Generate one PostgreSQL SELECT query only.
Constraints:
- Use only allowed tables from the context.
- Prefer fully-qualified table names exactly as in context (schema.table).
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- Add LIMIT 100 if user did not ask for a smaller limit.
- Return SQL only. No comments. No markdown.
- Do not wrap SQL in ```sql fences.
- Do not add explanations before or after SQL.
"""

FEW_SHOT = """
Examples:
Question: Сколько женщин работает в компании?
SQL:
SELECT COUNT(*) AS employees_total
FROM raw.oltp_employees
LIMIT 100;

Question: Сколько сотрудников в каждом отделе?
SQL:
SELECT department, COUNT(*) AS employee_count
FROM raw.oltp_employees
GROUP BY department
ORDER BY employee_count DESC
LIMIT 100;

Question: Сколько активных сотрудников?
SQL:
SELECT COUNT(*) AS active_employees
FROM raw.oltp_employees
WHERE employment_status = 'active'
LIMIT 100;
"""


def build_prompt(question: str, schema_context: str) -> str:
    return f"""
{SYSTEM_RULES}
{FEW_SHOT}

Relevant schema:
{schema_context}

Question:
{question}
"""


def build_correction_prompt(
    question: str,
    schema_context: str,
    invalid_sql: str,
    error: str,
) -> str:
    return f"""
{SYSTEM_RULES}

Relevant schema:
{schema_context}

Question:
{question}

Previous SQL failed validation.
Error: {error}
Invalid SQL:
{invalid_sql}

Return only one corrected PostgreSQL SELECT that fixes the error.
Do not use markdown. Return SQL only.
"""


def build_execution_correction_prompt(
    question: str,
    schema_context: str,
    failed_sql: str,
    error: str,
) -> str:
    return f"""
{SYSTEM_RULES}

Relevant schema:
{schema_context}

Question:
{question}

The following SELECT failed at execution time against PostgreSQL.
Error: {error}
Failed SQL:
{failed_sql}

Return only one corrected PostgreSQL SELECT that fixes the execution error.
Use only allowed tables from the context.
Do not use markdown. Return SQL only.
"""
