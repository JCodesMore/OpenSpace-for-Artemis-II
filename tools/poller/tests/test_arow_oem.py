"""Tests for the AROW CCSDS OEM source adapter."""
import pathlib
import pytest
from datetime import datetime, timezone

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample_oem.txt"

# J2000 epoch for manual verification
J2000_EPOCH = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_extracts_correct_count():
    """Fixture contains 4 data lines; parse_oem should return 4 StateVectors."""
    from poller.sources.arow_oem import ArowOemSource
    src = ArowOemSource()
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    vectors = src.parse_oem(text)
    assert len(vectors) == 4


def test_parse_skips_meta_block():
    """Lines between META_START and META_STOP should not produce StateVectors."""
    from poller.sources.arow_oem import ArowOemSource
    src = ArowOemSource()
    text_with_extra_meta = (
        "META_START\n"
        "OBJECT_NAME = ORION\n"
        "META_STOP\n"
        "2026-04-02T02:00:00.000  -25685.123  -17027.456  -1456.979  -1.5713  -3.6988  -0.3201\n"
    )
    vectors = src.parse_oem(text_with_extra_meta)
    assert len(vectors) == 1


def test_parse_skips_comment_lines():
    """Lines starting with COMMENT should be skipped."""
    from poller.sources.arow_oem import ArowOemSource
    src = ArowOemSource()
    text = (
        "COMMENT This is a comment\n"
        "2026-04-02T02:00:00.000  -25685.123  -17027.456  -1456.979  -1.5713  -3.6988  -0.3201\n"
    )
    vectors = src.parse_oem(text)
    assert len(vectors) == 1


def test_parse_data_line_values():
    """parse_oem parses a single data line correctly (before unit conversion)."""
    from poller.sources.arow_oem import ArowOemSource
    src = ArowOemSource()
    text = "2026-04-02T02:00:00.000  -25685.123  -17027.456  -1456.979  -1.5713  -3.6988  -0.3201\n"
    vectors = src.parse_oem(text)
    assert len(vectors) == 1
    sv = vectors[0]
    # Positions: km * 1000 = m
    assert sv.x == pytest.approx(-25685.123 * 1000.0, abs=1e-3)
    assert sv.y == pytest.approx(-17027.456 * 1000.0, abs=1e-3)
    assert sv.z == pytest.approx(-1456.979 * 1000.0, abs=1e-3)


def test_parse_converts_km_to_meters():
    """Positions should be multiplied by 1000 (km -> m)."""
    from poller.sources.arow_oem import ArowOemSource
    src = ArowOemSource()
    text = "2026-04-02T02:00:00.000  100.0  200.0  300.0  0.1  0.2  0.3\n"
    vectors = src.parse_oem(text)
    assert vectors[0].x == pytest.approx(100_000.0, abs=1e-3)
    assert vectors[0].y == pytest.approx(200_000.0, abs=1e-3)
    assert vectors[0].z == pytest.approx(300_000.0, abs=1e-3)
    # Velocities: km/s * 1000 = m/s
    assert vectors[0].vx == pytest.approx(100.0, abs=1e-6)
    assert vectors[0].vy == pytest.approx(200.0, abs=1e-6)
    assert vectors[0].vz == pytest.approx(300.0, abs=1e-6)


def test_parse_converts_timestamp_to_j2000():
    """J2000 epoch itself should yield t=0.0."""
    from poller.sources.arow_oem import ArowOemSource
    src = ArowOemSource()
    text = "2000-01-01T12:00:00.000  1.0  2.0  3.0  0.1  0.2  0.3\n"
    vectors = src.parse_oem(text)
    assert len(vectors) == 1
    assert vectors[0].t == pytest.approx(0.0, abs=1e-3)


def test_parse_empty_text_returns_empty():
    """Empty text returns empty list."""
    from poller.sources.arow_oem import ArowOemSource
    src = ArowOemSource()
    result = src.parse_oem("")
    assert result == []


def test_fetch_returns_source_result_with_correct_name(monkeypatch):
    """fetch() with mocked HTTP returns SourceResult with source_name='arow_oem'."""
    import requests
    from poller.sources.arow_oem import ArowOemSource
    from poller.models import SourceResult

    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")

    class FakeResponse:
        text = fixture_text
        status_code = 200
        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse())

    src = ArowOemSource(oem_url="https://example.com/fake.oem")
    result = src.fetch()

    assert isinstance(result, SourceResult)
    assert result.source_name == "arow_oem"
    assert len(result.points) == 4


def test_fetch_handles_connection_error_gracefully(monkeypatch):
    """fetch() catches connection errors and returns empty SourceResult (D-04)."""
    import requests
    from poller.sources.arow_oem import ArowOemSource
    from poller.models import SourceResult

    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", fake_get)

    src = ArowOemSource(oem_url="https://example.com/fake.oem")
    result = src.fetch()

    assert isinstance(result, SourceResult)
    assert result.source_name == "arow_oem"
    assert result.points == []


def test_fetch_no_url_returns_empty():
    """fetch() with oem_url=None returns empty SourceResult (pre-launch state)."""
    from poller.sources.arow_oem import ArowOemSource
    from poller.models import SourceResult

    src = ArowOemSource(oem_url=None)
    result = src.fetch()

    assert isinstance(result, SourceResult)
    assert result.source_name == "arow_oem"
    assert result.points == []
