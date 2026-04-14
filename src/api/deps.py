"""Shared dependencies for API routers."""

import psycopg2
from src.config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD


def get_db():
    """Yield a PostgreSQL connection, close on exit."""
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )
    try:
        yield conn
    finally:
        conn.close()
