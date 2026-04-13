"""
Download NTSB aviation data from https://data.ntsb.gov/avdata.

Downloads MDB zip files in parallel, extracts them, and returns paths.
Skips downloads if files already exist (idempotent).
"""

import logging
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_URL = "https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5C"

# Data files: (zip_filename, expected_mdb_inside)
DATA_FILES = [
    ("avall.zip", "avall.mdb"),
    ("Pre2008.zip", "Pre2008.mdb"),
    ("PRE1982.zip", "PRE1982.MDB"),
]

# Schema documentation (downloaded in parallel, non-blocking)
DOC_FILES = [
    "eadmspub.pdf",
    "eadmspub_legacy.pdf",
    "codman.pdf",
    "MDB_Release_Notes.pdf",
]

# 64KB chunks for faster I/O
_CHUNK_SIZE = 65536


def _download_file(url: str, dest: Path) -> bool:
    """Download a file. Skips if already present. Uses large chunks for speed."""
    if dest.exists() and dest.stat().st_size > 0:
        logger.info(f"  Cached: {dest.name} ({dest.stat().st_size / 1048576:.1f} MB)")
        return True

    logger.info(f"  Downloading {dest.name}...")
    req = urllib.request.Request(url, headers={
        "User-Agent": "aviation-safety-pipeline/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            with open(dest, "wb") as f:
                while chunk := resp.read(_CHUNK_SIZE):
                    f.write(chunk)
        logger.info(f"  Done: {dest.name} ({dest.stat().st_size / 1048576:.1f} MB)")
        return True
    except Exception as e:
        logger.error(f"  Failed: {dest.name} — {e}")
        if dest.exists():
            dest.unlink()
        return False


def _download_and_extract(data_dir: Path, zip_name: str, mdb_name: str) -> tuple:
    """Download a zip and extract the MDB. Returns (mdb_name, Path or None)."""
    mdb_path = data_dir / mdb_name
    if mdb_path.exists() and mdb_path.stat().st_size > 0:
        logger.info(f"  MDB cached: {mdb_name} ({mdb_path.stat().st_size / 1048576:.1f} MB)")
        return mdb_name, mdb_path

    zip_path = data_dir / zip_name
    if not _download_file(BASE_URL + zip_name, zip_path):
        return mdb_name, None

    logger.info(f"  Extracting {zip_name}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(data_dir)

    if mdb_path.exists():
        # Clean up zip to save disk space
        zip_path.unlink()
        logger.info(f"  Ready: {mdb_name}")
        return mdb_name, mdb_path

    # Search for MDB with different casing
    for f in data_dir.iterdir():
        if f.suffix.lower() == ".mdb" and f.stem.lower() == mdb_name.replace(".mdb", "").lower():
            logger.info(f"  Ready: {f.name}")
            return mdb_name, f

    logger.error(f"  No MDB found after extracting {zip_name}")
    return mdb_name, None


def download_ntsb_data(data_dir: Path) -> dict:
    """
    Download and extract NTSB data files in parallel.

    Returns dict mapping source label to MDB file path:
        {"avall.mdb": Path(...), "Pre2008.mdb": Path(...)}
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    mdb_paths = {}

    logger.info(f"Data directory: {data_dir}")
    logger.info("Downloading NTSB aviation data (parallel)...")

    # Download MDB zips in parallel
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_download_and_extract, data_dir, zn, mn): mn
            for zn, mn in DATA_FILES
        }
        for future in as_completed(futures):
            mdb_name, mdb_path = future.result()
            if mdb_path:
                mdb_paths[mdb_name] = mdb_path

    # Download docs in parallel (non-blocking, best-effort)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for doc in DOC_FILES:
            pool.submit(_download_file, BASE_URL + doc, data_dir / doc)

    logger.info(f"Download complete: {len(mdb_paths)} MDB files ready")
    return mdb_paths
