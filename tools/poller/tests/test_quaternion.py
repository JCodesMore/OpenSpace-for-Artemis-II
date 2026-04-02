"""Tests for quaternion/attitude support in the data pipeline."""
from poller.models import Attitude, StateVector
from poller.writer import format_as_lua_table
from poller.sources.arow_gcs import ArowGcsSource


def test_attitude_dataclass():
    att = Attitude(q0=1.0, q1=0.0, q2=0.0, q3=0.0)
    assert att.q0 == 1.0
    assert att.q1 == 0.0
    assert att.q2 == 0.0
    assert att.q3 == 0.0


def test_format_lua_table_without_attitude():
    points = [StateVector(t=100.0, x=1.0, y=2.0, z=3.0, vx=0.1, vy=0.2, vz=0.3)]
    output = format_as_lua_table(points, source="test")
    assert "attitude" not in output
    assert "points" in output


def test_format_lua_table_with_attitude():
    points = [StateVector(t=100.0, x=1.0, y=2.0, z=3.0, vx=0.1, vy=0.2, vz=0.3)]
    att = Attitude(q0=0.6056, q1=-0.3648, q2=-0.6061, q3=-0.3642)
    output = format_as_lua_table(points, source="test", attitude=att)
    assert "attitude = { q0=0.6056, q1=-0.3648, q2=-0.6061, q3=-0.3642 }" in output
    assert "points" in output


def test_format_lua_table_attitude_before_points():
    points = [StateVector(t=100.0, x=1.0, y=2.0, z=3.0, vx=0.1, vy=0.2, vz=0.3)]
    att = Attitude(q0=1.0, q1=0.0, q2=0.0, q3=0.0)
    output = format_as_lua_table(points, source="test", attitude=att)
    att_pos = output.index("attitude")
    pts_pos = output.index("points")
    assert att_pos < pts_pos, "attitude block should appear before points block"


def test_extract_attitude_valid():
    src = ArowGcsSource()
    params = {"2012": "0.6056", "2013": "-0.3648", "2014": "-0.6061", "2015": "-0.3642"}
    att = src.extract_attitude(params)
    assert att is not None
    assert att.q0 == 0.6056
    assert att.q1 == -0.3648
    assert att.q2 == -0.6061
    assert att.q3 == -0.3642


def test_extract_attitude_missing_param():
    src = ArowGcsSource()
    params = {"2013": "-0.3648", "2014": "-0.6061", "2015": "-0.3642"}  # missing "2012"
    att = src.extract_attitude(params)
    assert att is None


def test_extract_attitude_non_numeric():
    src = ArowGcsSource()
    params = {"2012": "bad", "2013": "0.1", "2014": "0.2", "2015": "0.3"}
    att = src.extract_attitude(params)
    assert att is None


def test_extract_attitude_empty_params():
    src = ArowGcsSource()
    att = src.extract_attitude({})
    assert att is None
