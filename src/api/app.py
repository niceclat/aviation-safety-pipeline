"""
FastAPI application — main entry point.

Usage:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000
    # or via Docker: docker-compose up api
"""

import logging

from fastapi import FastAPI

from src.api.routers import health, pipeline, quality, governance, gold, search, bronze, silver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(
    title="Aviation Safety Pipeline API",
    description=(
        "REST API for NTSB aviation incident data pipeline. "
        "Query risk profiles, run quality checks, search narratives semantically."
    ),
    version="1.0.0",
)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
app.include_router(quality.router, prefix="/quality", tags=["Quality"])
app.include_router(governance.router, prefix="/governance", tags=["Governance"])
app.include_router(gold.router, prefix="/gold", tags=["Gold Layer"])
app.include_router(bronze.router, prefix="/bronze", tags=["Bronze Layer"])
app.include_router(silver.router, prefix="/silver", tags=["Silver Layer"])
app.include_router(search.router, prefix="/search", tags=["Semantic Search"])
