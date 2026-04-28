"""
FarmShield Chat — SQL Tools (Phase 5).

Correction from PRD verification (Error 2):
  Do NOT use create_sql_agent nested inside a tool. Instead return
  InfoSQLDatabaseTool and QuerySQLDataBaseTool directly. The outer
  FarmShieldAgent LLM writes and executes SQL itself — no agent nesting.

Tables visible: sensor_readings, alerts (sample_rows=3).
Tables hidden:  ml_inferences, alembic_version (not in include_tables).
Connection:     psycopg2 sync driver (postgresql://) required by SQLDatabase.
"""

import structlog
from langchain_community.tools.sql_database.tool import (
    InfoSQLDatabaseTool,
    QuerySQLDataBaseTool,
)
from langchain_community.utilities import SQLDatabase

logger = structlog.get_logger(__name__)


def build_sql_tools(settings) -> list:
    """
    Build and return the two LangChain SQL tools for the FarmShield agent.

    Returns:
        [InfoSQLDatabaseTool, QuerySQLDataBaseTool]
        The outer agent receives these two tools directly and writes SQL itself.

    Connection uses psycopg2 (postgresql://) not asyncpg — LangChain SQLDatabase
    is synchronous-only. This is a separate URL from the main asyncpg engine.
    """
    logger.info(
        "sql_tools_init",
        url_prefix=settings.chat_db_readonly_url.split("@")[-1],  # host/db only, no password
    )

    db = SQLDatabase.from_uri(
        settings.chat_db_readonly_url,
        include_tables=["sensor_readings", "alerts"],
        sample_rows_in_table_info=3,
    )

    logger.info("sql_tools_db_connected", dialect=db.dialect)

    return [
        InfoSQLDatabaseTool(db=db),
        QuerySQLDataBaseTool(db=db),
    ]
