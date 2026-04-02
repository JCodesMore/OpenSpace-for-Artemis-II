"""Tests for poller/archive.py and poller/poller.py — archive module and orchestrator."""
import pathlib
import time

import pytest

from poller.models import StateVector, SourceResult


def make_sv(t: float, x: float = 1.0, y: float = 2.0, z: float = 3.0,
            vx: float = 0.1, vy: float = 0.2, vz: float = 0.3) -> StateVector:
    return StateVector(t=t, x=x, y=y, z=z, vx=vx, vy=vy, vz=vz)


def make_result(source: str, points=None, raw_data="raw content") -> SourceResult:
    return SourceResult(
        source_name=source,
        points=points if points is not None else [make_sv(1.0)],
        raw_data=raw_data,
        timestamp=time.time(),
    )


# ---------------------------------------------------------------------------
# archive_response tests
# ---------------------------------------------------------------------------

class TestArchiveResponse:
    def test_creates_file_in_archive_dir(self, tmp_path):
        """archive_response() creates a file in the archive directory."""
        from poller.archive import archive_response
        archive_dir = tmp_path / "archive"
        result = make_result("arow_gcs", raw_data="test data")
        archived = archive_response(archive_dir, result)
        assert archived is not None
        assert archived.exists()
        assert archived.parent == archive_dir

    def test_filename_contains_source_and_timestamp(self, tmp_path):
        """archive_response() file contains timestamp in filename."""
        from poller.archive import archive_response
        archive_dir = tmp_path / "archive"
        result = make_result("horizons", raw_data="horizons data")
        archived = archive_response(archive_dir, result)
        assert archived is not None
        # Filename format: {source_name}_{timestamp}.txt
        assert archived.name.startswith("horizons_")
        assert archived.name.endswith(".txt")
        # Contains a timestamp pattern (digits)
        import re
        assert re.search(r"\d{8}T\d{6}Z", archived.name)

    def test_file_contains_raw_data(self, tmp_path):
        """archive_response() file contains the raw_data from SourceResult."""
        from poller.archive import archive_response
        archive_dir = tmp_path / "archive"
        raw = "CCSDS OEM data block"
        result = make_result("arow_oem", raw_data=raw)
        archived = archive_response(archive_dir, result)
        assert archived is not None
        assert archived.read_text(encoding="utf-8") == raw

    def test_returns_none_for_empty_raw_data(self, tmp_path):
        """archive_response() returns None when raw_data is empty string."""
        from poller.archive import archive_response
        archive_dir = tmp_path / "archive"
        result = make_result("arow_gcs", raw_data="")
        archived = archive_response(archive_dir, result)
        assert archived is None

    def test_creates_archive_dir_if_missing(self, tmp_path):
        """archive_response() creates archive directory if it doesn't exist."""
        from poller.archive import archive_response
        archive_dir = tmp_path / "nested" / "archive"
        assert not archive_dir.exists()
        result = make_result("test_src", raw_data="data")
        archive_response(archive_dir, result)
        assert archive_dir.exists()


# ---------------------------------------------------------------------------
# Poller orchestrator tests
# ---------------------------------------------------------------------------

class TestPollerPollCycle:
    def _make_poller(self, tmp_path):
        """Helper: create Poller with mocked sources and temp paths."""
        from poller.poller import Poller
        output = tmp_path / "live.lua"
        archive = tmp_path / "archive"
        poller = Poller(output_path=output, archive_dir=archive, poll_interval=0.0)
        return poller

    def test_poll_cycle_calls_gcs_first(self, tmp_path, monkeypatch):
        """poll_cycle() calls GCS source first (Tier 1 priority)."""
        poller = self._make_poller(tmp_path)
        call_order = []

        def fake_gcs_fetch():
            call_order.append("gcs")
            return make_result("arow_gcs", points=[make_sv(1.0)])

        def fake_oem_fetch():
            call_order.append("oem")
            return make_result("arow_oem", points=[])

        monkeypatch.setattr(poller.gcs, "fetch", fake_gcs_fetch)
        monkeypatch.setattr(poller.oem, "fetch", fake_oem_fetch)

        # Use sim_time well past Horizons start to allow Horizons check
        from poller.poller import HORIZONS_START_J2000
        poller.poll_cycle(simulation_time=HORIZONS_START_J2000 - 1000)

        assert "gcs" in call_order
        assert call_order[0] == "gcs"

    def test_poll_cycle_falls_back_to_horizons_when_gcs_empty(self, tmp_path, monkeypatch):
        """poll_cycle() falls back to Horizons when GCS returns empty points."""
        poller = self._make_poller(tmp_path)
        horizons_called = []

        def fake_gcs_fetch():
            return make_result("arow_gcs", points=[], raw_data="")

        def fake_oem_fetch():
            return make_result("arow_oem", points=[], raw_data="")

        def fake_hz_fetch(start, stop, step_size="10m"):
            horizons_called.append(True)
            return make_result("horizons", points=[make_sv(100.0)])

        monkeypatch.setattr(poller.gcs, "fetch", fake_gcs_fetch)
        monkeypatch.setattr(poller.oem, "fetch", fake_oem_fetch)
        monkeypatch.setattr(poller.horizons, "fetch", fake_hz_fetch)

        # Force OEM interval to have elapsed
        poller._last_oem_poll = 0.0
        poller._last_horizons_poll = 0.0

        from poller.poller import HORIZONS_START_J2000
        # Sim time past Horizons start
        poller.poll_cycle(simulation_time=HORIZONS_START_J2000 + 1000)

        assert len(horizons_called) == 1

    def test_poll_cycle_does_not_call_horizons_before_coverage(self, tmp_path, monkeypatch):
        """poll_cycle() does NOT query Horizons when simulation_time < HORIZONS_START_J2000."""
        poller = self._make_poller(tmp_path)
        horizons_called = []

        def fake_gcs_fetch():
            return make_result("arow_gcs", points=[], raw_data="")

        def fake_oem_fetch():
            return make_result("arow_oem", points=[], raw_data="")

        def fake_hz_fetch(start, stop, step_size="10m"):
            horizons_called.append(True)
            return make_result("horizons", points=[make_sv(100.0)])

        monkeypatch.setattr(poller.gcs, "fetch", fake_gcs_fetch)
        monkeypatch.setattr(poller.oem, "fetch", fake_oem_fetch)
        monkeypatch.setattr(poller.horizons, "fetch", fake_hz_fetch)

        poller._last_oem_poll = 0.0
        poller._last_horizons_poll = 0.0

        from poller.poller import HORIZONS_START_J2000
        # Sim time BEFORE Horizons coverage starts
        poller.poll_cycle(simulation_time=HORIZONS_START_J2000 - 1000)

        assert len(horizons_called) == 0

    def test_poll_cycle_calls_write_atomic_with_merged_points(self, tmp_path, monkeypatch):
        """poll_cycle() calls write_atomic when new points exist."""
        poller = self._make_poller(tmp_path)
        written_data = []

        def fake_gcs_fetch():
            return make_result("arow_gcs", points=[make_sv(10.0)])

        import poller.poller as poller_module

        original_write = poller_module.write_atomic

        def fake_write_atomic(path, points, source="unknown", attitude=None):
            written_data.append((path, list(points), source))

        monkeypatch.setattr(poller.gcs, "fetch", fake_gcs_fetch)
        monkeypatch.setattr(poller_module, "write_atomic", fake_write_atomic)

        poller.poll_cycle(simulation_time=0.0)

        assert len(written_data) == 1
        assert len(written_data[0][1]) == 1
        assert written_data[0][1][0].t == 10.0

    def test_poll_cycle_archives_non_empty_results(self, tmp_path, monkeypatch):
        """poll_cycle() calls archive_response for non-empty SourceResult."""
        poller = self._make_poller(tmp_path)
        archived = []

        def fake_gcs_fetch():
            return make_result("arow_gcs", points=[make_sv(1.0)], raw_data="gcs raw")

        import poller.poller as poller_module

        def fake_archive(archive_dir, result):
            archived.append(result.source_name)
            return None

        monkeypatch.setattr(poller.gcs, "fetch", fake_gcs_fetch)
        monkeypatch.setattr(poller_module, "archive_response", fake_archive)

        poller.poll_cycle(simulation_time=0.0)

        assert "arow_gcs" in archived

    def test_poll_cycle_logs_start_and_end(self, tmp_path, monkeypatch, caplog):
        """poll_cycle() logs cycle start and end with source and point count."""
        import logging
        poller = self._make_poller(tmp_path)

        def fake_gcs_fetch():
            return make_result("arow_gcs", points=[make_sv(1.0)])

        monkeypatch.setattr(poller.gcs, "fetch", fake_gcs_fetch)

        with caplog.at_level(logging.INFO, logger="poller"):
            poller.poll_cycle(simulation_time=0.0)

        log_text = " ".join(caplog.messages)
        assert "Poll cycle start" in log_text or "cycle start" in log_text.lower()
        assert "Poll cycle end" in log_text or "cycle end" in log_text.lower()


class TestPollerRun:
    def test_run_with_max_iterations_stops(self, tmp_path, monkeypatch):
        """run() with max_iterations=1 completes one cycle and stops."""
        from poller.poller import Poller
        output = tmp_path / "live.lua"
        archive = tmp_path / "archive"
        poller = Poller(output_path=output, archive_dir=archive, poll_interval=0.0)

        cycles = []

        def fake_poll_cycle(simulation_time=None):
            cycles.append(1)

        monkeypatch.setattr(poller, "poll_cycle", fake_poll_cycle)

        poller.run(max_iterations=1)

        assert len(cycles) == 1

    def test_run_with_two_iterations(self, tmp_path, monkeypatch):
        """run() with max_iterations=2 executes exactly two cycles."""
        from poller.poller import Poller
        output = tmp_path / "live.lua"
        archive = tmp_path / "archive"
        poller = Poller(output_path=output, archive_dir=archive, poll_interval=0.0)

        cycles = []

        def fake_poll_cycle(simulation_time=None):
            cycles.append(1)

        monkeypatch.setattr(poller, "poll_cycle", fake_poll_cycle)

        poller.run(max_iterations=2)

        assert len(cycles) == 2
