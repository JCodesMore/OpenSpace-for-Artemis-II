"""Tests for the JPL Horizons source adapter."""
import math
import pathlib
import pytest

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "horizons_response.txt"

# ---- frame conversion tests ------------------------------------------------

def test_frame_conversion_x_axis():
    """X axis is unchanged in ECLIPJ2000 -> ICRF rotation."""
    from poller.sources.horizons import eclipj2000_to_icrf
    x, y, z = eclipj2000_to_icrf(1.0, 0.0, 0.0)
    assert x == pytest.approx(1.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)
    assert z == pytest.approx(0.0, abs=1e-6)


def test_frame_conversion_y_axis():
    """Y axis rotates by obliquity: (0, cos(e), sin(e))."""
    from poller.sources.horizons import eclipj2000_to_icrf
    obliquity = math.radians(23.439291)
    x, y, z = eclipj2000_to_icrf(0.0, 1.0, 0.0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(math.cos(obliquity), abs=1e-6)
    assert z == pytest.approx(math.sin(obliquity), abs=1e-6)


def test_frame_conversion_z_axis():
    """Z axis rotates by obliquity: (0, -sin(e), cos(e))."""
    from poller.sources.horizons import eclipj2000_to_icrf
    obliquity = math.radians(23.439291)
    x, y, z = eclipj2000_to_icrf(0.0, 0.0, 1.0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(-math.sin(obliquity), abs=1e-6)
    assert z == pytest.approx(math.cos(obliquity), abs=1e-6)


# ---- parse_horizons_response tests -----------------------------------------

def test_parse_extracts_correct_count():
    """Fixture contains 3 data points; parse should return 3 StateVectors."""
    from poller.sources.horizons import HorizonsSource
    src = HorizonsSource()
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    vectors = src.parse_horizons_response(text)
    assert len(vectors) == 3


def test_parse_converts_to_icrf():
    """Parsed position should NOT equal raw ECLIPJ2000 value due to frame rotation."""
    from poller.sources.horizons import HorizonsSource, eclipj2000_to_icrf
    src = HorizonsSource()
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    vectors = src.parse_horizons_response(text)
    # First point raw Y_eclip = -1.789012345E+04 km -> should be rotated
    # The ICRF Y != raw ECLIPJ2000 Y (unless z==0, but z is non-zero here)
    # Just verify the conversion happened: y_icrf != y_eclip_raw_meters
    raw_y_m = -1.789012345e+04 * 1000.0
    assert vectors[0].y != pytest.approx(raw_y_m, abs=1e-3), \
        "Y should be rotated from ECLIPJ2000 to ICRF"


def test_parse_converts_km_to_meters():
    """Values should be in meters (not km)."""
    from poller.sources.horizons import HorizonsSource, eclipj2000_to_icrf
    src = HorizonsSource()
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    vectors = src.parse_horizons_response(text)
    # First point X = 1.234567890E+04 km -> 1.234567890E+07 m
    # X axis unchanged by rotation
    expected_x_m = 1.234567890e+04 * 1000.0
    assert vectors[0].x == pytest.approx(expected_x_m, abs=1e-3)


def test_parse_missing_soe_returns_empty():
    """Text without $$SOE marker returns empty list."""
    from poller.sources.horizons import HorizonsSource
    src = HorizonsSource()
    result = src.parse_horizons_response("No SOE marker here\n")
    assert result == []


def test_parse_converts_velocity_km_s_to_m_s():
    """Velocities should be in m/s (not km/s)."""
    from poller.sources.horizons import HorizonsSource, eclipj2000_to_icrf
    src = HorizonsSource()
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    vectors = src.parse_horizons_response(text)
    # First point VX = 2.345678901E+00 km/s -> 2345.678901 m/s (X axis unchanged by rotation)
    expected_vx_ms = 2.345678901e+00 * 1000.0
    assert vectors[0].vx == pytest.approx(expected_vx_ms, abs=1e-3)


# ---- j2000_to_utc_str tests -------------------------------------------------

def test_j2000_to_utc_str():
    """J2000 epoch (0.0 seconds) should map to 2000-01-01T12:00:00."""
    from poller.sources.horizons import j2000_to_utc_str
    result = j2000_to_utc_str(0.0)
    assert result == "2000-01-01T12:00:00"


def test_j2000_to_utc_str_offset():
    """86400 J2000 seconds should map to 2000-01-02T12:00:00."""
    from poller.sources.horizons import j2000_to_utc_str
    result = j2000_to_utc_str(86400.0)
    assert result == "2000-01-02T12:00:00"


# ---- fetch() tests ----------------------------------------------------------

def test_fetch_returns_source_result_with_correct_name(monkeypatch):
    """fetch() with mocked HTTP returns SourceResult with source_name='horizons'."""
    import time
    from poller.sources.horizons import HorizonsSource
    from poller.models import SourceResult

    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
    # Wrap fixture in a fake JSON response
    import json
    # The fixture already contains the bare text; simulate horizons API JSON response
    fake_json = {"result": fixture_text}

    class FakeResponse:
        status_code = 200
        def json(self):
            return fake_json
        def raise_for_status(self):
            pass

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse())

    src = HorizonsSource()
    start_j2000 = 828_268_800.0  # some J2000 epoch
    stop_j2000 = start_j2000 + 86400.0
    result = src.fetch(start_j2000, stop_j2000)

    assert isinstance(result, SourceResult)
    assert result.source_name == "horizons"
    assert len(result.points) == 3


def test_fetch_logs_with_timestamp(monkeypatch, caplog):
    """fetch() logs at INFO level with timestamps."""
    import logging
    import requests
    from poller.sources.horizons import HorizonsSource

    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
    fake_json = {"result": fixture_text}

    class FakeResponse:
        def json(self):
            return fake_json
        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse())

    src = HorizonsSource()
    with caplog.at_level(logging.INFO, logger="poller.sources.horizons"):
        src.fetch(0.0, 86400.0)

    assert len(caplog.records) >= 1


def test_fetch_handles_http_error_gracefully(monkeypatch):
    """fetch() catches HTTP errors and returns empty SourceResult."""
    import requests
    from poller.sources.horizons import HorizonsSource
    from poller.models import SourceResult

    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", fake_get)

    src = HorizonsSource()
    result = src.fetch(0.0, 86400.0)

    assert isinstance(result, SourceResult)
    assert result.source_name == "horizons"
    assert result.points == []
