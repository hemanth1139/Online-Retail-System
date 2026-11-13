import json
from tools.schema_tool import get_database_schema
from tools.sql_tool import execute_sql_query

def dispatch_tool(name, arguments):
    if name == "get_database_schema":
        if arguments:
            raise ValueError("get_database_schema takes no arguments.")
        return get_database_schema()
    if name == "execute_sql_query":
        sql = arguments.get("sql")
        if not sql:
            raise ValueError("Missing required argument: sql")
        return execute_sql_query(sql)
    raise ValueError(f"Unknown tool requested by model: {name}")

def execute_tool_use(tool_use):
    name = tool_use["name"]
    tool_use_id = tool_use["toolUseId"]
    try:
        args = tool_use.get("input", {})
        output = dispatch_tool(name, args)
        payload = {"ok": True, "result": output}
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
    return {
        "toolResult": {
            "toolUseId": tool_use_id,
            "content": [{"json": payload}],
            "status": "success" if payload["ok"] else "error"
        }
    }
