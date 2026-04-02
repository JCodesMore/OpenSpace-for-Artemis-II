"""Unit tests for the AROW GCS source adapter."""
import json
import logging
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from poller.sources.arow_gcs import ArowGcsSource
from poller.models import SourceResult, StateVector


# ---------------------------------------------------------------------------
# list_latest_file tests
# ---------------------------------------------------------------------------

def test_list_latest_file_returns_named_file(gcs_listing_response):
    """list_latest_file with fixture listing returns item with name 'October/1/October_108_1.txt'.
    Filters out size=0 placeholder entries."""
    source = ArowGcsSource()
    result = source.list_latest_file(listing_data=gcs_listing_response)
    assert result is not None
    assert result["name"] == "October/1/October_108_1.txt"


def test_list_latest_file_empty_items_returns_none():
    """list_latest_file with empty items list returns None."""
    source = ArowGcsSource()
    result = source.list_latest_file(listing_data={"items": []})
    assert result is None


def test_list_latest_file_missing_items_returns_none():
    """list_latest_file with no 'items' key returns None."""
    source = ArowGcsSource()
    result = source.list_latest_file(listing_data={})
    assert result is None


def test_list_latest_file_returns_latest_by_time():
    """list_latest_file with multiple items returns item with latest timeCreated."""
    source = ArowGcsSource()
    listing = {
        "items": [
            {
                "name": "October/1/October_107_1.txt",
                "size": "15000",
                "timeCreated": "2026-02-15T10:00:00.000Z",
                "mediaLink": "https://example.com/old"
            },
            {
                "name": "October/1/October_108_1.txt",
                "size": "21234",
                "timeCreated": "2026-02-15T10:30:00.000Z",
                "mediaLink": "https://example.com/latest"
            },
            {
                "name": "October/1/October_106_1.txt",
                "size": "18000",
                "timeCreated": "2026-02-15T09:45:00.000Z",
                "mediaLink": "https://example.com/older"
            },
        ]
    }
    result = source.list_latest_file(listing_data=listing)
    assert result is not None
    assert result["name"] == "October/1/October_108_1.txt"


# ---------------------------------------------------------------------------
# parse_io_file tests — RED phase: new nested format
# ---------------------------------------------------------------------------

def test_parse_io_file_nested_format(gcs_io_file_content):
    """parse_io_file extracts Parameter_NNNN values into {number: float_value} dict."""
    source = ArowGcsSource()
    params = source.parse_io_file(gcs_io_file_content)
    assert isinstance(params, dict)
    assert "2003" in params
    assert isinstance(params["2003"], float)
    assert params["2003"] == pytest.approx(15204388.61847, rel=1e-6)


def test_parse_io_file_extracts_timestamp(gcs_io_file_content):
    """parse_io_file extracts DOY timestamp from parameter Time fields."""
    source = ArowGcsSource()
    params = source.parse_io_file(gcs_io_file_content)
    assert "_timestamp" in params
    # 2026:092:03:10:05.582 = April 2 2026 03:10:05.582 UTC
    # J2000 epoch = seconds since 2000-01-01 12:00:00 UTC
    from datetime import datetime, timezone
    expected_utc = datetime(2026, 4, 2, 3, 10, 5, 582000, tzinfo=timezone.utc)
    j2000_ref = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expected_epoch = (expected_utc - j2000_ref).total_seconds()
    assert params["_timestamp"] == pytest.approx(expected_epoch, abs=0.01)


def test_parse_io_file_invalid_json_returns_empty():
    """parse_io_file with invalid JSON returns empty dict, does not raise."""
    source = ArowGcsSource()
    params = source.parse_io_file("not valid json {{{")
    assert params == {}


def test_parse_io_file_empty_string_returns_empty():
    """parse_io_file with empty string returns empty dict."""
    source = ArowGcsSource()
    params = source.parse_io_file("")
    assert params == {}


# ---------------------------------------------------------------------------
# extract_state_vectors tests — RED phase: feet->meters, correct params, epoch
# ---------------------------------------------------------------------------

def test_extract_state_vectors_feet_to_meters(gcs_io_file_content):
    """extract_state_vectors converts feet to meters (* 0.3048)."""
    source = ArowGcsSource()
    params = source.parse_io_file(gcs_io_file_content)
    from poller.sources.arow_gcs import OCTOBER_POSITION_PARAMS
    vectors = source.extract_state_vectors(params, OCTOBER_POSITION_PARAMS)
    assert len(vectors) == 1
    sv = vectors[0]
    # Position: 15204388.61847 ft * 0.3048 = 4634257.398... m
    assert sv.x == pytest.approx(15204388.61847 * 0.3048, rel=1e-6)
    # Velocity: 25685.123 ft/s * 0.3048 = 7828.825... m/s
    assert sv.vx == pytest.approx(25685.123 * 0.3048, rel=1e-6)


def test_extract_state_vectors_has_epoch(gcs_io_file_content):
    """extract_state_vectors sets StateVector.t from DOY timestamp."""
    source = ArowGcsSource()
    params = source.parse_io_file(gcs_io_file_content)
    from poller.sources.arow_gcs import OCTOBER_POSITION_PARAMS
    vectors = source.extract_state_vectors(params, OCTOBER_POSITION_PARAMS)
    assert len(vectors) == 1
    assert vectors[0].t > 828000000  # Must be a real J2000 epoch, not 0.0


# ---------------------------------------------------------------------------
# Prefix and param mapping tests — RED phase
# ---------------------------------------------------------------------------

def test_default_prefix_is_october():
    """ArowGcsSource default prefix is October/1/ not Io/1/."""
    source = ArowGcsSource()
    assert source.prefix == "October/1/"


def test_october_position_params_corrected():
    """OCTOBER_POSITION_PARAMS maps position to 2003-2005, velocity to 2009-2011."""
    from poller.sources.arow_gcs import OCTOBER_POSITION_PARAMS
    assert OCTOBER_POSITION_PARAMS["x"] == "2003"
    assert OCTOBER_POSITION_PARAMS["y"] == "2004"
    assert OCTOBER_POSITION_PARAMS["z"] == "2005"
    assert OCTOBER_POSITION_PARAMS["vx"] == "2009"
    assert OCTOBER_POSITION_PARAMS["vy"] == "2010"
    assert OCTOBER_POSITION_PARAMS["vz"] == "2011"


# ---------------------------------------------------------------------------
# fetch() integration tests (mocked HTTP)
# ---------------------------------------------------------------------------

def test_fetch_returns_source_result_with_correct_name(gcs_listing_response, gcs_io_file_content):
    """fetch() with mocked HTTP returns SourceResult with source_name='arow_gcs'."""
    source = ArowGcsSource()

    mock_listing_resp = MagicMock()
    mock_listing_resp.json.return_value = gcs_listing_response
    mock_listing_resp.raise_for_status.return_value = None

    mock_file_resp = MagicMock()
    mock_file_resp.text = gcs_io_file_content
    mock_file_resp.raise_for_status.return_value = None

    with patch.object(source._session, "get", side_effect=[mock_listing_resp, mock_file_resp]):
        result = source.fetch()

    assert isinstance(result, SourceResult)
    assert result.source_name == "arow_gcs"
    assert isinstance(result.timestamp, float)
    assert result.raw_data == gcs_io_file_content


def test_fetch_logs_at_info_level(gcs_listing_response, gcs_io_file_content, caplog):
    """fetch() logs at INFO level with timestamp format."""
    source = ArowGcsSource()

    mock_listing_resp = MagicMock()
    mock_listing_resp.json.return_value = gcs_listing_response
    mock_listing_resp.raise_for_status.return_value = None

    mock_file_resp = MagicMock()
    mock_file_resp.text = gcs_io_file_content
    mock_file_resp.raise_for_status.return_value = None

    with caplog.at_level(logging.INFO, logger="poller.sources.arow_gcs"):
        with patch.object(source._session, "get", side_effect=[mock_listing_resp, mock_file_resp]):
            source.fetch()

    # At least one INFO message must exist
    info_messages = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(info_messages) >= 1

    # Must contain a timestamp-like string (ISO 8601 T separator)
    all_messages = " ".join(r.message for r in caplog.records)
    assert "T" in all_messages  # ISO 8601 timestamp format


def test_fetch_handles_http_timeout_gracefully(gcs_listing_response):
    """fetch() handles requests.Timeout — returns empty SourceResult, does not raise."""
    source = ArowGcsSource()

    with patch.object(source._session, "get", side_effect=requests.Timeout("timed out")):
        result = source.fetch()

    assert isinstance(result, SourceResult)
    assert result.source_name == "arow_gcs"
    assert result.points == []
    assert result.raw_data == ""


def test_fetch_handles_http_404_gracefully():
    """fetch() handles HTTP 404 error — returns empty SourceResult, does not raise."""
    source = ArowGcsSource()

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

    with patch.object(source._session, "get", return_value=mock_resp):
        result = source.fetch()

    assert isinstance(result, SourceResult)
    assert result.source_name == "arow_gcs"
    assert result.points == []
