"""Tests for poller.models — RED phase for Task 1 TDD."""
import json
import pathlib
import pytest


def test_import_state_vector():
    """StateVector and SourceResult must be importable from poller.models."""
    from poller.models import StateVector, SourceResult  # noqa: F401


def test_state_vector_construction():
    """StateVector can be constructed with all required fields."""
    from poller.models import StateVector
    sv = StateVector(t=0.0, x=1.0, y=2.0, z=3.0, vx=0.1, vy=0.2, vz=0.3)
    assert sv.t == 0.0
    assert sv.x == 1.0
    assert sv.y == 2.0
    assert sv.z == 3.0
    assert sv.vx == 0.1
    assert sv.vy == 0.2
    assert sv.vz == 0.3


def test_source_result_construction():
    """SourceResult can be constructed with all required fields."""
    from poller.models import StateVector, SourceResult
    sv = StateVector(t=0.0, x=1.0, y=2.0, z=3.0, vx=0.0, vy=0.0, vz=0.0)
    result = SourceResult(
        source_name="test_source",
        points=[sv],
        raw_data='{"test": 1}',
        timestamp=1234567890.0
    )
    assert result.source_name == "test_source"
    assert len(result.points) == 1
    assert result.raw_data == '{"test": 1}'
    assert result.timestamp == 1234567890.0


def test_fixtures_are_valid_json():
    """Fixture files must be loadable as valid JSON."""
    fixtures_dir = pathlib.Path(__file__).parent / "fixtures"
    listing = json.loads((fixtures_dir / "gcs_listing_response.json").read_text())
    assert "items" in listing
    assert any(item["name"] == "October/1/October_108_1.txt" for item in listing["items"])

    io_file = json.loads((fixtures_dir / "gcs_io_file.json").read_text())
    # New nested Parameter_NNNN format — no flat "timestamp" or numbered keys
    assert "File" in io_file
    assert "Parameter_2003" in io_file
