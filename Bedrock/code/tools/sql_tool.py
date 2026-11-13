from core.sql_validator import validate_sql
from core.database import run_readonly_query
from config import MAX_ROWS

def execute_sql_query(sql: str):
    safe_sql = validate_sql(sql)
    result = run_readonly_query(safe_sql, MAX_ROWS)
    return {"executed_sql": safe_sql, **result}
