"""Configuration loaded from environment variables / .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
PG_DB = os.getenv("POSTGRES_DB", "aviation_safety")
PG_USER = os.getenv("POSTGRES_USER", "pipeline")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "changeme")

PG_DSN = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# Data paths
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
AVALL_MDB = DATA_DIR / os.getenv("AVALL_MDB", "avall.mdb")
PRE2008_MDB = DATA_DIR / os.getenv("PRE2008_MDB", "Pre2008.mdb")
PRE1982_MDB = DATA_DIR / os.getenv("PRE1982_MDB", "PRE1982.MDB")

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", PROJECT_ROOT / "outputs"))
