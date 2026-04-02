"""AROW CCSDS OEM source adapter -- Tier 2 (4-minute intervals, J2K frame)."""
import logging
import re
import time
from datetime import datetime, timezone

import requests
from poller.models import StateVector, SourceResult

logger = logging.getLogger(__name__)

# J2000 epoch as datetime for timestamp conversion
J2000_EPOCH = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# Pattern to match a CCSDS OEM data line:
# YYYY-MM-DDTHH:MM:SS.sss  X Y Z VX VY VZ  (space-separated floats)
_DATA_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)"
    r"\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)"
    r"\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)"
)


class ArowOemSource:
    """Fetches and parses CCSDS OEM ephemeris files from the AROW data service."""

    def __init__(
        self,
        oem_url: str | None = None,
        timeout: int = 15,
    ) -> None:
        self.oem_url = oem_url
        self.timeout = timeout

    def parse_oem(self, text: str) -> list[StateVector]:
        """Parse a CCSDS OEM text block into StateVectors.

        Skips META_START/META_STOP sections, COMMENT lines, and header lines.
        Converts km -> meters and km/s -> m/s.
        No frame conversion needed: OEM frame is J2K (ICRF-equivalent).
        Returns a list of StateVector with t in J2000 seconds.
        """
        if not text or not text.strip():
            return []

        vectors: list[StateVector] = []
        in_meta = False

        for line in text.splitlines():
            stripped = line.strip()

            # Track META_START / META_STOP blocks
            if stripped.startswith("META_START"):
                in_meta = True
                continue
            if stripped.startswith("META_STOP"):
                in_meta = False
                continue
            if in_meta:
                continue

            # Skip header/comment lines
            if not stripped:
                continue
            if stripped.startswith((
                "COMMENT",
                "CCSDS_",
                "CREATION_DATE",
                "ORIGINATOR",
            )):
                continue

            # Try to parse a data line
            match = _DATA_LINE_RE.match(stripped)
            if not match:
                continue

            ts_str, x_s, y_s, z_s, vx_s, vy_s, vz_s = match.groups()

            # Parse timestamp -> J2000 seconds
            # OEM timestamps are UTC; may have 3-digit fractional seconds
            ts_clean = ts_str.rstrip("0").rstrip(".")
            # Ensure we always have a parseable format
            try:
                dt = datetime.fromisoformat(ts_clean).replace(tzinfo=timezone.utc)
            except ValueError:
                # Try without fractional seconds
                base = ts_str[:19]
                dt = datetime.fromisoformat(base).replace(tzinfo=timezone.utc)

            t_j2000 = (dt - J2000_EPOCH).total_seconds()

            # Parse values and convert km -> m, km/s -> m/s
            x_m = float(x_s) * 1000.0
            y_m = float(y_s) * 1000.0
            z_m = float(z_s) * 1000.0
            vx_ms = float(vx_s) * 1000.0
            vy_ms = float(vy_s) * 1000.0
            vz_ms = float(vz_s) * 1000.0

            vectors.append(
                StateVector(
                    t=t_j2000,
                    x=x_m,
                    y=y_m,
                    z=z_m,
                    vx=vx_ms,
                    vy=vy_ms,
                    vz=vz_ms,
                )
            )

        logger.debug("parse_oem: extracted %d state vectors", len(vectors))
        return vectors

    def fetch(self) -> SourceResult:
        """Fetch and parse the CCSDS OEM file from oem_url.

        Returns SourceResult with source_name='arow_oem'. On any error (or
        if oem_url is None), returns an empty SourceResult rather than raising.
        """
        fetch_start = time.time()

        if self.oem_url is None:
            logger.warning(
                "arow_oem fetch skipped: oem_url is None (OEM not yet available pre-launch)"
                " wall=%.3f", fetch_start
            )
            return SourceResult(
                source_name="arow_oem",
                points=[],
                raw_data="",
                timestamp=fetch_start,
            )

        logger.info("arow_oem fetch start: url=%s wall=%.3f", self.oem_url, fetch_start)

        try:
            response = requests.get(self.oem_url, timeout=self.timeout)
            response.raise_for_status()
            raw_text = response.text

            points = self.parse_oem(raw_text)

            fetch_end = time.time()
            logger.info(
                "arow_oem fetch done: %d points, elapsed=%.2fs wall=%.3f",
                len(points),
                fetch_end - fetch_start,
                fetch_end,
            )

            return SourceResult(
                source_name="arow_oem",
                points=points,
                raw_data=raw_text,
                timestamp=fetch_end,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "arow_oem fetch error: %s wall=%.3f", exc, time.time()
            )
            return SourceResult(
                source_name="arow_oem",
                points=[],
                raw_data="",
                timestamp=time.time(),
            )
