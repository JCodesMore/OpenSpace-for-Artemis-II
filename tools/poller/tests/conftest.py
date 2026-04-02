"""Shared pytest fixtures for poller tests."""
import json
import pathlib
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def gcs_listing_response():
    """Load and return the GCS listing API fixture as a dict."""
    return json.loads((FIXTURES_DIR / "gcs_listing_response.json").read_text())


@pytest.fixture
def gcs_io_file_content():
    """Load and return the GCS Io stream file fixture as a string."""
    return (FIXTURES_DIR / "gcs_io_file.json").read_text()
