import sqlglot
from sqlglot import exp
from config import DB_SCHEMA, MAX_ROWS

FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop,
    exp.Alter, exp.Merge, exp.Command, exp.Transaction
)
DANGEROUS_FUNCTIONS = {"PG_SLEEP", "PG_READ_FILE", "PG_WRITE_FILE", "DBLINK", "LO_IMPORT", "LO_EXPORT"}

def validate_sql(sql: str) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL query is empty.")
    statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement is allowed.")
    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise ValueError("Only SELECT queries are allowed.")
    for node_type in FORBIDDEN_NODES:
        if next(tree.find_all(node_type), None) is not None:
            raise ValueError("Modifying or administrative SQL is not allowed.")
    if tree.args.get("into") is not None:
        raise ValueError("SELECT INTO is not allowed.")
    if tree.args.get("locks"):
        raise ValueError("SELECT FOR UPDATE/SHARE is not allowed.")
    for func in tree.find_all(exp.Func):
        name = func.sql_name().upper()
        if name in DANGEROUS_FUNCTIONS:
            raise ValueError(f"Function {name} is not allowed.")
    for table in tree.find_all(exp.Table):
        if table.catalog:
            raise ValueError("Cross-database references are not allowed.")
        if table.db and table.db.lower() != DB_SCHEMA.lower():
            raise ValueError(f"Only the {DB_SCHEMA} schema may be queried.")
    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_ROWS)
    else:
        try:
            value = int(limit.expression.this)
            if value < 1:
                raise ValueError("LIMIT must be positive.")
            if value > MAX_ROWS:
                tree = tree.limit(MAX_ROWS)
        except (AttributeError, TypeError, ValueError):
            raise ValueError(f"LIMIT must be a positive integer no greater than {MAX_ROWS}.")
    return tree.sql(dialect="postgres")
