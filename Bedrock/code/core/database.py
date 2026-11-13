import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_SCHEMA, STATEMENT_TIMEOUT_MS

def get_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
        sslmode="require", connect_timeout=10
    )

def get_live_schema():
    """Return tables, columns, primary keys and foreign keys from PostgreSQL."""
    query = """
    SELECT c.table_name, c.column_name, c.data_type,
           CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key
    FROM information_schema.columns c
    LEFT JOIN (
        SELECT kcu.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s
    ) pk ON pk.table_name = c.table_name AND pk.column_name = c.column_name
    WHERE c.table_schema = %s
    ORDER BY c.table_name, c.ordinal_position
    """
    fk_query = """
    SELECT kcu.table_name, kcu.column_name,
           ccu.table_name AS referenced_table,
           ccu.column_name AS referenced_column
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
      ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
    ORDER BY kcu.table_name, kcu.column_name
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (DB_SCHEMA, DB_SCHEMA))
            columns = cur.fetchall()
            cur.execute(fk_query, (DB_SCHEMA,))
            fks = cur.fetchall()
    result = {"schema": DB_SCHEMA, "tables": {}, "foreign_keys": [dict(x) for x in fks]}
    for row in columns:
        result["tables"].setdefault(row["table_name"], []).append({
            "column": row["column_name"], "type": row["data_type"],
            "primary_key": row["is_primary_key"]
        })
    if not result["tables"]:
        raise RuntimeError(f"No tables found in schema {DB_SCHEMA!r}")
    return result

def run_readonly_query(sql, max_rows):
    """Execute one validated SELECT inside a read-only, time-limited transaction."""
    conn = get_connection()
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT set_config('statement_timeout', %s, true)", (f"{STATEMENT_TIMEOUT_MS}ms",))
            cur.execute(sql)
            rows = cur.fetchmany(max_rows)
            columns = [d.name for d in cur.description] if cur.description else []
        conn.commit()
        return {"columns": columns, "rows": [dict(r) for r in rows], "row_count_returned": len(rows)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
