from core.database import get_live_schema

def get_database_schema():
    """Fetch current schema metadata directly from PostgreSQL."""
    return get_live_schema()
