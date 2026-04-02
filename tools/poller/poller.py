"""Artemis 2 live data poller — fetches spacecraft position from tiered sources."""
import argparse
import logging
import logging.handlers
import pathlib
import time

from poller.models import StateVector
from poller.sources.arow_gcs import ArowGcsSource
from poller.sources.arow_oem import ArowOemSource
from poller.sources.horizons import HorizonsSource
from poller.writer import write_atomic, merge_and_trim
from poller.archive import archive_response

logger = logging.getLogger("poller")

# Horizons coverage starts at 2026-Apr-02 01:49 TDB
# = (JD 2461132.575208 - 2451545.0) * 86400 = approximately 828366498 J2000 seconds
HORIZONS_START_J2000 = 828366498.0

# Default poll interval per tier (seconds)
GCS_INTERVAL = 7
OEM_INTERVAL = 240   # 4 minutes
HORIZONS_INTERVAL = 600  # 10 minutes


class Poller:
    """Orchestrates all three source tiers with tier-based fallback logic."""

    def __init__(
        self,
        output_path: pathlib.Path,
        archive_dir: pathlib.Path,
        poll_interval: float = 7.0,
    ) -> None:
        self.output_path = output_path
        self.archive_dir = archive_dir
        self.poll_interval = poll_interval
        self._points: list[StateVector] = []
        self._last_source = "none"
        self._attitude = None

        # Initialize sources
        self.gcs = ArowGcsSource()
        self.oem = ArowOemSource()
        self.horizons = HorizonsSource()

        # Track last poll times per tier
        self._last_oem_poll = 0.0
        self._last_horizons_poll = 0.0

    def get_current_sim_time(self) -> float:
        """Estimate current simulation time as J2000 seconds from wall clock.

        J2000 epoch = 2000-01-01 12:00:00 UTC = Unix 946728000.
        """
        return time.time() - 946728000.0

    def poll_cycle(self, simulation_time: float | None = None) -> None:
        """Execute one poll cycle: try tiers in priority order, write results."""
        if simulation_time is None:
            simulation_time = self.get_current_sim_time()
        now = time.time()
        cycle_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        logger.info(
            "[%s] Poll cycle start (sim_time=%.1f)", cycle_start, simulation_time
        )

        new_points: list[StateVector] = []
        source_used = "none"

        # Tier 1: AROW GCS (always try, highest frequency)
        gcs_result = self.gcs.fetch()
        if gcs_result.points:
            new_points.extend(gcs_result.points)
            source_used = "arow_gcs"
            if gcs_result.attitude is not None:
                self._attitude = gcs_result.attitude
            archive_response(self.archive_dir, gcs_result)

        # Tier 2: AROW OEM (if available, every OEM_INTERVAL seconds)
        if (now - self._last_oem_poll) >= OEM_INTERVAL:
            oem_result = self.oem.fetch()
            if oem_result.points:
                new_points.extend(oem_result.points)
                if source_used == "none":
                    source_used = "arow_oem"
                archive_response(self.archive_dir, oem_result)
            self._last_oem_poll = now

        # Tier 3: Horizons (fallback, only after coverage starts, every HORIZONS_INTERVAL)
        if (
            simulation_time >= HORIZONS_START_J2000
            and (now - self._last_horizons_poll) >= HORIZONS_INTERVAL
            and not new_points
        ):
            # Query for recent window around current sim time
            start = simulation_time - 3600  # 1 hour before
            stop = simulation_time + 3600   # 1 hour ahead
            hz_result = self.horizons.fetch(start, stop, step_size="10m")
            if hz_result.points:
                new_points.extend(hz_result.points)
                source_used = "horizons"
                archive_response(self.archive_dir, hz_result)
            self._last_horizons_poll = now

        # Merge and write
        if new_points:
            self._points = merge_and_trim(self._points, new_points)
            self._last_source = source_used
            write_atomic(self.output_path, self._points, source=source_used, attitude=self._attitude)

        cycle_end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))
        logger.info(
            "[%s] Poll cycle end: source=%s, total_points=%d, new=%d",
            cycle_end,
            source_used,
            len(self._points),
            len(new_points),
        )

    def run(self, max_iterations: int | None = None) -> None:
        """Run poll loop. If max_iterations is set, stop after that many cycles."""
        logger.info(
            "Poller started. Output: %s, Archive: %s, Interval: %.1fs",
            self.output_path,
            self.archive_dir,
            self.poll_interval,
        )
        iteration = 0
        try:
            while max_iterations is None or iteration < max_iterations:
                self.poll_cycle()
                iteration += 1
                if max_iterations is None or iteration < max_iterations:
                    time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("Poller stopped by user (Ctrl+C)")


def setup_logging(log_dir: pathlib.Path, level: str = "INFO") -> None:
    """Configure logging with console + rotating file handler."""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(console)
    # Rotating file handler (10 MB max, keep 5 backups)
    fh = logging.handlers.RotatingFileHandler(
        log_dir / "poller.log", maxBytes=10_000_000, backupCount=5
    )
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(fh)


def main() -> None:
    """Entry point for the Artemis 2 live data poller."""
    parser = argparse.ArgumentParser(description="Artemis 2 Live Data Poller")
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("artemis2_live.lua"),
        help="Path to output data file",
    )
    parser.add_argument(
        "--archive-dir",
        type=pathlib.Path,
        default=pathlib.Path("archive"),
        help="Directory for raw data archival",
    )
    parser.add_argument(
        "--log-dir",
        type=pathlib.Path,
        default=pathlib.Path("logs"),
        help="Directory for log files",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=7.0,
        help="Poll interval in seconds",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    setup_logging(args.log_dir, args.log_level)
    poller = Poller(args.output, args.archive_dir, args.interval)
    poller.run()


if __name__ == "__main__":
    main()
