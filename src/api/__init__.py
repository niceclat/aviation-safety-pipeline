"""
REST API for the Aviation Safety Pipeline.

Routers:
    /health         — readiness and liveness checks
    /pipeline       — trigger runs, check status
    /quality        — data quality checks
    /governance     — run history, table freshness
    /gold           — risk profile queries
    /search         — semantic search via pgvector
"""
