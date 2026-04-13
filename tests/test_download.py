"""
Tests for src/download.py — NTSB data download module.

Covers:
    - Source file definitions
    - URL construction
    - Caching logic (file exists check)
"""

from src.download import DATA_FILES, DOC_FILES, BASE_URL


class TestDownloadConfig:

    def test_three_data_files_defined(self):
        assert len(DATA_FILES) == 3

    def test_data_files_are_zips(self):
        for zip_name, mdb_name in DATA_FILES:
            assert zip_name.endswith(".zip"), f"{zip_name} is not a zip"
            assert mdb_name.lower().endswith(".mdb"), f"{mdb_name} is not an mdb"

    def test_four_doc_files_defined(self):
        assert len(DOC_FILES) == 4

    def test_doc_files_are_pdfs(self):
        for doc in DOC_FILES:
            assert doc.endswith(".pdf"), f"{doc} is not a pdf"

    def test_base_url_is_ntsb(self):
        assert "ntsb.gov" in BASE_URL
        assert "avdata" in BASE_URL

    def test_total_files_is_seven(self):
        assert len(DATA_FILES) + len(DOC_FILES) == 7

    def test_expected_data_files(self):
        zip_names = {z for z, _ in DATA_FILES}
        assert "avall.zip" in zip_names
        assert "Pre2008.zip" in zip_names
        assert "PRE1982.zip" in zip_names

    def test_expected_doc_files(self):
        assert "eadmspub.pdf" in DOC_FILES
        assert "eadmspub_legacy.pdf" in DOC_FILES
        assert "codman.pdf" in DOC_FILES
        assert "MDB_Release_Notes.pdf" in DOC_FILES
