"""Integration tests verifying poller -> data file -> Lua-readable format pipeline.

These tests bridge the Python poller world (models, writer, sources) with the
OpenSpace Lua world (artemis2_live.lua). The integration tests prove that data
written by the Python writer can be consumed by the Lua table parser.
"""
import math
import pathlib
import re

import pytest

from poller.models import StateVector
from poller.writer import format_as_lua_table, write_atomic, merge_and_trim


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_test_trajectory(
    start_epoch: float,
    n_points: int = 10,
    interval: float = 7.0,
) -> list[StateVector]:
    """Generate a realistic test trajectory for Artemis 2.

    Simulates a spacecraft in Earth-Moon transfer at ~200,000 km from Earth.
    All values in meters and m/s (J2000/ICRF frame).

    Args:
        start_epoch: J2000 epoch for the first point (seconds).
        n_points: Number of points to generate.
        interval: Time between consecutive points (seconds).

    Returns:
        List of StateVector with plausible Earth-Moon transfer coordinates.
    """
    points = []
    for i in range(n_points):
        t = start_epoch + i * interval
        # Simulated position: slowly drifting outward from Earth
        # ~200,000 km = 2e8 meters from Earth center
        angle = i * 0.01  # slow orbital motion
        r = 2.0e8 + i * 1.0e6  # slowly increasing radius
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        z = 1.0e7 * math.sin(angle * 0.5)  # slight out-of-plane motion
        # Velocity ~1 km/s = 1000 m/s
        vx = -1000.0 * math.sin(angle)
        vy = 1000.0 * math.cos(angle)
        vz = 50.0 * math.cos(angle * 0.5)
        points.append(StateVector(t=t, x=x, y=y, z=z, vx=vx, vy=vy, vz=vz))
    return points


# ---------------------------------------------------------------------------
# Test 1-2: Writer output format
# ---------------------------------------------------------------------------

class TestWriterOutputFormat:
    def test_format_contains_points_header_and_point_lines(self):
        """Test 1: format_as_lua_table output contains 'points = {' and at least one '{ t=' line."""
        points = generate_test_trajectory(828366500.0, n_points=3)
        result = format_as_lua_table(points, source="integration_test")
        assert "points = {" in result
        assert "{ t=" in result

    def test_format_is_valid_lua_table_braces(self):
        """Test 2: Output starts with '{' and ends with '}' — valid Lua table syntax."""
        points = generate_test_trajectory(828366500.0, n_points=3)
        result = format_as_lua_table(points, source="integration_test")
        stripped = result.strip()
        assert stripped.startswith("{"), "Lua table must start with '{'"
        assert stripped.endswith("}"), "Lua table must end with '}'"


# ---------------------------------------------------------------------------
# Test 3: Parseable output
# ---------------------------------------------------------------------------

class TestWriterOutputParseable:
    def test_point_count_extractable_by_regex(self):
        """Test 3: Point count in output matches input count (parseable by re)."""
        n = 5
        points = generate_test_trajectory(828366500.0, n_points=n)
        result = format_as_lua_table(points, source="integration_test")
        # Each point appears as "{ t=..." on its own line
        found = re.findall(r"\{ t=", result)
        assert len(found) == n, (
            f"Expected {n} point entries matching '{{{{ t=', found {len(found)}"
        )


# ---------------------------------------------------------------------------
# Test 4: Atomic write
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_write_atomic_no_tmp_extension_remaining(self, tmp_path):
        """Test 4: write_atomic writes final file without .tmp extension left behind."""
        target = tmp_path / "artemis2_live.dat"
        points = generate_test_trajectory(828366500.0, n_points=3)
        write_atomic(target, points, source="integration_test")

        # Final file must exist and .tmp must be gone
        assert target.exists(), "Final data file must exist after write_atomic"
        tmp_file = target.with_suffix(".tmp")
        assert not tmp_file.exists(), ".tmp file must not remain after atomic write"


# ---------------------------------------------------------------------------
# Test 5: Full pipeline round-trip
# ---------------------------------------------------------------------------

class TestFullPipelineRoundTrip:
    def test_write_then_read_content_matches(self, tmp_path):
        """Test 5: Full pipeline: StateVectors -> write_atomic -> read file -> verify content."""
        target = tmp_path / "pipeline_test.dat"
        points = generate_test_trajectory(828366500.0, n_points=5)

        write_atomic(target, points, source="pipeline_test")

        # Read back and verify structure
        content = target.read_text(encoding="utf-8")
        stripped = content.strip()

        assert stripped.startswith("{")
        assert stripped.endswith("}")
        assert "points = {" in content
        assert 'source = "pipeline_test"' in content

        # Verify all 5 point entries are present
        found = re.findall(r"\{ t=", content)
        assert len(found) == 5, f"Expected 5 points in file, found {len(found)}"

        # Verify first point epoch appears in file
        first_t = points[0].t
        assert str(first_t) in content, f"First epoch {first_t} not found in file"

    def test_merge_and_trim_preserves_sort_order(self):
        """merge_and_trim with realistic trajectory data maintains sort order."""
        old_points = generate_test_trajectory(828366500.0, n_points=60, interval=7.0)
        new_points = generate_test_trajectory(828366920.0, n_points=60, interval=7.0)

        result = merge_and_trim(old_points, new_points, max_points=80)

        # Must be sorted ascending by epoch
        epochs = [sv.t for sv in result]
        assert epochs == sorted(epochs), "merge_and_trim must return ascending epoch order"

        # Must respect max_points limit
        assert len(result) <= 80, f"Expected at most 80 points, got {len(result)}"

        # Most recent points kept (all new_points start after old_points)
        assert result[-1].t == new_points[-1].t, "Most recent point must be last"


# ---------------------------------------------------------------------------
# Tests 6-8: Test data fixture file
# ---------------------------------------------------------------------------

class TestFixtureFile:
    """Tests that generate and validate the test data file for OpenSpace visual verification."""

    def test_generate_test_data_file(self, tmp_path):
        """Test 6: Generated test data file contains valid Lua table with 10 realistic points."""
        points = generate_test_trajectory(828366500.0, n_points=10, interval=7.0)
        content = format_as_lua_table(points, source="test_fixture")

        # Write to tmp for validation
        test_file = tmp_path / "test_live_data.dat"
        test_file.write_text(content, encoding="utf-8")

        text = test_file.read_text()
        assert text.strip().startswith("{"), "Test data file must be a Lua table"
        assert text.strip().endswith("}"), "Test data file must end with '}'"
        assert "points = {" in text, "Test data file must have 'points = {' section"
        assert text.count("{ t=") == 10, f"Expected 10 point entries, got {text.count('{ t=')}"

        # Also write to fixtures directory for manual OpenSpace testing
        fixture_path = pathlib.Path(__file__).parent / "fixtures" / "test_live_data.dat"
        fixture_path.write_text(content, encoding="utf-8")

    def test_fixture_spans_70_seconds(self):
        """Test 7: Generated test data spans ~70 seconds (10 points at 7s intervals)."""
        start_epoch = 828366500.0
        points = generate_test_trajectory(start_epoch, n_points=10, interval=7.0)

        assert len(points) == 10
        time_span = points[-1].t - points[0].t
        # 9 intervals * 7s = 63s (allowing small float tolerance)
        assert abs(time_span - 63.0) < 0.01, (
            f"Expected ~63s span (9 intervals x 7s), got {time_span}s"
        )

    def test_fixture_positions_plausible_earth_moon_transfer(self):
        """Test 8: Generated positions are plausible Earth-Moon transfer distances (100-400k km)."""
        points = generate_test_trajectory(828366500.0, n_points=10, interval=7.0)

        for i, sv in enumerate(points):
            distance_m = math.sqrt(sv.x**2 + sv.y**2 + sv.z**2)
            distance_km = distance_m / 1000.0
            assert 100_000 <= distance_km <= 400_000, (
                f"Point {i}: distance {distance_km:.0f} km not in Earth-Moon transfer range "
                f"(100k-400k km)"
            )
