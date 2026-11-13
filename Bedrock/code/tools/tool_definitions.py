TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "get_database_schema",
                "description": "Retrieve the current PostgreSQL public schema, including tables, columns, data types, primary keys, and foreign-key relationships. Call this before generating SQL when schema context is needed.",
                "inputSchema": {"json": {"type": "object", "properties": {}, "additionalProperties": False}}
            }
        },
        {
            "toolSpec": {
                "name": "execute_sql_query",
                "description": "Execute one read-only PostgreSQL SELECT query. The backend independently validates the SQL, enforces the public schema, applies a maximum row limit, and uses a statement timeout. Supply the SQL query in the sql argument.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"sql": {"type": "string", "description": "A single PostgreSQL SELECT query."}},
                        "required": ["sql"],
                        "additionalProperties": False
                    }
                }
            }
        }
    ]
}
