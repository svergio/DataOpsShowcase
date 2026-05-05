SYSTEM_RULES = """
You are NL2SQL generator for HR analytics.
Generate one PostgreSQL SELECT query only.
Constraints:
- Use only allowed tables from the context.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- Add LIMIT 100 if user did not ask for a smaller limit.
- Return SQL only. No comments. No markdown.
"""


def build_prompt(question: str, schema_context: str) -> str:
    return f"""
{SYSTEM_RULES}

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
"""
