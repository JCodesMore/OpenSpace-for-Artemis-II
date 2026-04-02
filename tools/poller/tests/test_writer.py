"""Tests for poller/writer.py — atomic Lua-table file writer with sliding window."""
import pathlib

import pytest

from poller.models import StateVector


def make_sv(t: float, x: float = 1.0, y: float = 2.0, z: float = 3.0,
            vx: float = 0.1, vy: float = 0.2, vz: float = 0.3) -> StateVector:
    return StateVector(t=t, x=x, y=y, z=z, vx=vx, vy=vy, vz=vz)


# ---------------------------------------------------------------------------
# format_as_lua_table tests
# ---------------------------------------------------------------------------

class TestFormatAsLuaTable:
    def test_contains_points_header(self):
        """Output contains 'points = {' for 2 state vectors."""
        from poller.writer import format_as_lua_table
        svs = [make_sv(1.0), make_sv(2.0)]
        result = format_as_lua_table(svs, source="test_source")
        assert "points = {" in result

    def test_contains_last_updated(self):
        """Output contains 'last_updated =' field."""
        from poller.writer import format_as_lua_table
        svs = [make_sv(1.0), make_sv(2.0)]
        result = format_as_lua_table(svs, source="test_source")
        assert "last_updated =" in result

    def test_valid_lua_braces(self):
        """Output is valid Lua — starts with '{' and ends with '}'."""
        from poller.writer import format_as_lua_table
        svs = [make_sv(100.0), make_sv(200.0)]
        result = format_as_lua_table(svs, source="src")
        stripped = result.strip()
        assert stripped.startswith("{")
        assert stripped.endswith("}")

    def test_contains_source_name(self):
        """Output includes source = 'test_source' field."""
        from poller.writer import format_as_lua_table
        svs = [make_sv(1.0)]
        result = format_as_lua_table(svs, source="test_source")
        assert 'source = "test_source"' in result

    def test_empty_points_produces_valid_table(self):
        """Empty points list produces valid Lua table with 'points = {}'."""
        from poller.writer import format_as_lua_table
        result = format_as_lua_table([], source="empty_src")
        stripped = result.strip()
        assert stripped.startswith("{")
        assert stripped.endswith("}")
        assert "points = {" in result

    def test_point_fields_present(self):
        """Each point line contains all required fields: t, x, y, z, vx, vy, vz."""
        from poller.writer import format_as_lua_table
        sv = StateVector(t=828354240.0, x=-25685000.0, y=-17027000.0, z=-1456979.0,
                         vx=-1571.3, vy=-3698.8, vz=-320.1)
        result = format_as_lua_table([sv], source="arow_gcs")
        assert "t=" in result
        assert "x=" in result
        assert "y=" in result
        assert "z=" in result
        assert "vx=" in result
        assert "vy=" in result
        assert "vz=" in result

    def test_point_values_appear_in_output(self):
        """Values from StateVector appear in formatted output."""
        from poller.writer import format_as_lua_table
        sv = StateVector(t=828354240.0, x=-25685000.0, y=-17027000.0, z=-1456979.0,
                         vx=-1571.3, vy=-3698.8, vz=-320.1)
        result = format_as_lua_table([sv], source="arow_gcs")
        assert "828354240.0" in result
        assert "-25685000.0" in result


# ---------------------------------------------------------------------------
# write_atomic tests
# ---------------------------------------------------------------------------

class TestWriteAtomic:
    def test_creates_target_file(self, tmp_path):
        """write_atomic() creates the target file (not .tmp)."""
        from poller.writer import write_atomic
        target = tmp_path / "artemis2_live.lua"
        svs = [make_sv(1.0)]
        write_atomic(target, svs, source="test")
        assert target.exists()

    def test_no_tmp_file_after_write(self, tmp_path):
        """write_atomic() does not leave .tmp file behind after successful write."""
        from poller.writer import write_atomic
        target = tmp_path / "artemis2_live.lua"
        svs = [make_sv(1.0)]
        write_atomic(target, svs, source="test")
        tmp = target.with_suffix(".tmp")
        assert not tmp.exists()

    def test_file_content_matches_format(self, tmp_path):
        """write_atomic() file content matches format_as_lua_table() output."""
        from poller.writer import write_atomic, format_as_lua_table
        target = tmp_path / "artemis2_live.lua"
        svs = [make_sv(100.0, x=1000.0, y=2000.0, z=3000.0)]
        # write_atomic uses time.time() internally so we just verify structure
        write_atomic(target, svs, source="test_src")
        content = target.read_text(encoding="utf-8")
        assert "points = {" in content
        assert 'source = "test_src"' in content
        assert "t=100.0" in content


# ---------------------------------------------------------------------------
# merge_and_trim tests
# ---------------------------------------------------------------------------

class TestMergeAndTrim:
    def test_trims_to_max_120_keeping_most_recent(self):
        """merge_and_trim() with 150 points trims to max 120, keeping most recent."""
        from poller.writer import merge_and_trim
        existing = [make_sv(float(i)) for i in range(100)]
        new = [make_sv(float(i)) for i in range(100, 150)]
        result = merge_and_trim(existing, new, max_points=120)
        assert len(result) == 120
        # Most recent 120: epochs 30..149
        assert result[0].t == 30.0
        assert result[-1].t == 149.0

    def test_deduplicates_by_epoch(self):
        """merge_and_trim() deduplicates points with same epoch (t value)."""
        from poller.writer import merge_and_trim
        existing = [make_sv(1.0, x=100.0), make_sv(2.0, x=200.0)]
        new = [make_sv(1.0, x=999.0)]  # same epoch, different x — new overwrites
        result = merge_and_trim(existing, new, max_points=120)
        assert len(result) == 2
        t1_point = next(p for p in result if p.t == 1.0)
        assert t1_point.x == 999.0

    def test_sorts_by_epoch_ascending(self):
        """merge_and_trim() sorts output by epoch ascending."""
        from poller.writer import merge_and_trim
        existing = [make_sv(3.0), make_sv(1.0)]
        new = [make_sv(2.0)]
        result = merge_and_trim(existing, new, max_points=120)
        epochs = [sv.t for sv in result]
        assert epochs == sorted(epochs)

    def test_custom_max_points(self):
        """merge_and_trim() respects custom max_points parameter."""
        from poller.writer import merge_and_trim
        existing = [make_sv(float(i)) for i in range(50)]
        result = merge_and_trim(existing, [], max_points=10)
        assert len(result) == 10
        assert result[0].t == 40.0
        assert result[-1].t == 49.0
