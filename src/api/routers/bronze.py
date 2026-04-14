"""Bronze layer inspection endpoints."""

from fastapi import APIRouter, Depends, Query
from src.api.deps import get_db

router = APIRouter()


@router.get("/schemas")
def list_schemas(conn=Depends(get_db)):
    """List all bronze schemas and their table counts."""
    schemas = {}
    for schema in ["bronze_avall", "bronze_pre2008", "bronze_pre1982"]:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s ORDER BY table_name",
                    (schema,),
                )
                tables = [r[0] for r in cur.fetchall()]
                schemas[schema] = {"tables": len(tables), "table_names": tables}
        except Exception:
            conn.rollback()
            schemas[schema] = {"error": "not found"}
    return schemas


@router.get("/{schema}/{table}")
def inspect_table(
    schema: str, table: str,
    limit: int = 20, offset: int = 0,
    conn=Depends(get_db),
):
    """Inspect rows from any bronze table."""
    valid_schemas = {"bronze_avall", "bronze_pre2008", "bronze_pre1982"}
    if schema not in valid_schemas:
        return {"error": f"Invalid schema. Choose from: {valid_schemas}"}

    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {schema}.{table} LIMIT %s OFFSET %s", (limit, offset))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            total = cur.fetchone()[0]
        return {"schema": schema, "table": table, "total": total, "rows": rows}
    except Exception as e:
        return {"error": str(e)}


@router.get("/{schema}/{table}/stats")
def table_stats(schema: str, table: str, conn=Depends(get_db)):
    """Get column count, row count, and sample values for a bronze table."""
    valid_schemas = {"bronze_avall", "bronze_pre2008", "bronze_pre1982"}
    if schema not in valid_schemas:
        return {"error": f"Invalid schema. Choose from: {valid_schemas}"}

    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            row_count = cur.fetchone()[0]
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position",
                (schema, table),
            )
            columns = [r[0] for r in cur.fetchall()]
        return {
            "schema": schema, "table": table,
            "row_count": row_count, "column_count": len(columns),
            "columns": columns,
        }
    except Exception as e:
        return {"error": str(e)}
