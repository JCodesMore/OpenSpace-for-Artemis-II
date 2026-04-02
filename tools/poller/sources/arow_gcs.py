"""AROW GCS bucket source adapter — Tier 1 (highest frequency, ~7s updates)."""
import json
import logging
import time
from datetime import datetime, timezone, timedelta

import requests

from poller.models import StateVector, SourceResult, Attitude

logger = logging.getLogger(__name__)

GCS_BASE = "https://storage.googleapis.com/storage/v1/b/p-2-cen1/o"

FT_TO_M = 0.3048  # feet to meters conversion factor

J2000_EPOCH = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# AROW October quaternion params — param2012=q0(w), param2013=q1(x),
# param2014=q2(y), param2015=q3(z). Re-map in Lua orientation script if wrong.
IO_QUATERNION_PARAMS = {"q0": "2012", "q1": "2013", "q2": "2014", "q3": "2015"}

OCTOBER_POSITION_PARAMS = {
    "x": "2003",
    "y": "2004",
    "z": "2005",
    "vx": "2009",
    "vy": "2010",
    "vz": "2011",
}


def _parse_doy_timestamp(doy_str: str) -> float:
    """Parse AROW DOY timestamp 'YYYY:DDD:HH:MM:SS.mmm' to J2000 seconds.

    Args:
        doy_str: Timestamp string like '2026:092:03:10:05.582'

    Returns:
        Epoch in J2000 seconds (seconds since 2000-01-01 12:00:00 UTC).
    """
    # Split into parts: year, day-of-year, hours, minutes, seconds.milliseconds
    parts = doy_str.split(":")
    year = int(parts[0])
    doy = int(parts[1])
    hour = int(parts[2])
    minute = int(parts[3])
    sec_parts = parts[4].split(".")
    sec = int(sec_parts[0])
    microsec = int(sec_parts[1]) * 1000 if len(sec_parts) > 1 else 0
    # Construct datetime from year + day-of-year
    dt = datetime(year, 1, 1, hour, minute, sec, microsec, tzinfo=timezone.utc) + timedelta(days=doy - 1)
    return (dt - J2000_EPOCH).total_seconds()


class ArowGcsSource:
    """Fetches latest state vectors from AROW GCS public bucket."""

    def __init__(self, prefix: str = "October/1/", timeout: int = 10):
        self.prefix = prefix
        self.timeout = timeout
        self._session = requests.Session()

    def list_latest_file(self, listing_data: dict | None = None) -> dict | None:
        """Return metadata of most recently created file under self.prefix.

        If listing_data is provided, uses it instead of making an HTTP request.
        Filters out directory placeholders (size <= 100 bytes).
        Returns None if no real files are found.
        """
        if listing_data is None:
            logger.info(
                "[%s] GCS listing request: prefix=%s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                self.prefix,
            )
            r = self._session.get(
                GCS_BASE, params={"prefix": self.prefix}, timeout=self.timeout
            )
            r.raise_for_status()
            listing_data = r.json()

        items = listing_data.get("items", [])
        real = [i for i in items if int(i.get("size", 0)) > 100]
        if not real:
            return None
        return max(real, key=lambda i: i["timeCreated"])

    def fetch_file(self, media_link: str) -> str:
        """Download file content from a mediaLink URL."""
        logger.info(
            "[%s] GCS file download: %s",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            media_link,
        )
        r = self._session.get(media_link, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    def parse_io_file(self, content: str) -> dict:
        """Parse AROW GCS JSON with nested Parameter_NNNN objects.

        Real format has keys like 'Parameter_2003' containing
        {'Number': '2003', 'Value': '15.204...', 'Time': '2026:092:...'}.

        Returns dict keyed by parameter number string with float values,
        plus '_timestamp' key with J2000 epoch parsed from DOY Time field.
        Returns empty dict on any parse failure (does not raise).
        """
        try:
            raw = json.loads(content)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning(
                "[%s] Failed to parse GCS file content",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            return {}

        result = {}
        timestamp_extracted = False
        for key, value in raw.items():
            if not key.startswith("Parameter_"):
                continue
            if not isinstance(value, dict):
                continue
            param_num = value.get("Number", "")
            param_val = value.get("Value")
            if param_num and param_val is not None:
                try:
                    result[param_num] = float(param_val)
                except (ValueError, TypeError):
                    logger.debug("Non-numeric value for param %s: %s", param_num, param_val)
                    continue
            # Extract timestamp from first parameter with a Time field
            if not timestamp_extracted:
                time_str = value.get("Time")
                if time_str:
                    try:
                        result["_timestamp"] = _parse_doy_timestamp(time_str)
                        timestamp_extracted = True
                    except (ValueError, IndexError) as exc:
                        logger.debug("Failed to parse DOY timestamp %s: %s", time_str, exc)
        return result

    def extract_state_vectors(
        self, params: dict, param_mapping: dict | None = None
    ) -> list[StateVector]:
        """Extract state vectors from parsed parameters using the given mapping.

        Applies feet-to-meters conversion (AROW data is in feet/ft-s).
        Reads epoch from params['_timestamp'] (J2000 seconds from DOY parse).
        Returns empty list if mapping is None or required params are missing.
        """
        if param_mapping is None:
            logger.debug(
                "No parameter mapping configured; cannot extract state vectors"
            )
            return []
        try:
            # Require all position params to be present — missing params mean
            # bad data, not zero position. Using 0 default previously caused
            # origin (0,0,0) state vectors that broke trail rendering.
            x_raw = params.get(param_mapping["x"])
            y_raw = params.get(param_mapping["y"])
            z_raw = params.get(param_mapping["z"])
            if x_raw is None or y_raw is None or z_raw is None:
                logger.warning("Missing position params — skipping state vector")
                return []
            x = float(x_raw) * FT_TO_M
            y = float(y_raw) * FT_TO_M
            z = float(z_raw) * FT_TO_M
            vx = float(params.get(param_mapping.get("vx", ""), 0)) * FT_TO_M
            vy = float(params.get(param_mapping.get("vy", ""), 0)) * FT_TO_M
            vz = float(params.get(param_mapping.get("vz", ""), 0)) * FT_TO_M
            epoch = float(params.get("_timestamp", 0.0))
            if epoch == 0.0:
                logger.warning("Missing timestamp — skipping state vector")
                return []
            return [StateVector(t=epoch, x=x, y=y, z=z, vx=vx, vy=vy, vz=vz)]
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning(
                "[%s] Failed to extract state vectors: %s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                exc,
            )
            return []

    def extract_attitude(self, params: dict) -> "Attitude | None":
        """Extract spacecraft attitude quaternion from October params 2012-2015.

        Returns None if any quaternion param is missing or non-numeric.
        The q0/q1/q2/q3 mapping to w/x/y/z is assumed; the Lua orientation
        script handles reordering if needed at runtime.
        """
        try:
            q0 = float(params[IO_QUATERNION_PARAMS["q0"]])
            q1 = float(params[IO_QUATERNION_PARAMS["q1"]])
            q2 = float(params[IO_QUATERNION_PARAMS["q2"]])
            q3 = float(params[IO_QUATERNION_PARAMS["q3"]])
            return Attitude(q0=q0, q1=q1, q2=q2, q3=q3)
        except (KeyError, ValueError, TypeError):
            logger.debug("Quaternion params 2012-2015 not available or non-numeric")
            return None

    def fetch(self) -> SourceResult:
        """Full fetch cycle: list -> download -> parse -> extract.

        Returns SourceResult (may have empty points on failure). Never raises.
        All fetch operations are logged with timestamps per D-03.
        """
        fetch_time = time.time()
        logger.info(
            "[%s] AROW GCS fetch started (prefix=%s)",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fetch_time)),
            self.prefix,
        )
        try:
            meta = self.list_latest_file()
            if meta is None:
                logger.warning(
                    "[%s] No files found in GCS prefix %s",
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    self.prefix,
                )
                return SourceResult(
                    source_name="arow_gcs",
                    points=[],
                    raw_data="",
                    timestamp=fetch_time,
                )
            content = self.fetch_file(meta["mediaLink"])
            params = self.parse_io_file(content)
            points = self.extract_state_vectors(params, OCTOBER_POSITION_PARAMS)
            attitude = self.extract_attitude(params)
            logger.info(
                "[%s] AROW GCS fetch complete: %d points from %s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fetch_time)),
                len(points),
                meta["name"],
            )
            return SourceResult(
                source_name="arow_gcs",
                points=points,
                raw_data=content,
                timestamp=fetch_time,
                attitude=attitude,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[%s] AROW GCS fetch failed: %s",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                exc,
                exc_info=True,
            )
            return SourceResult(
                source_name="arow_gcs",
                points=[],
                raw_data="",
                timestamp=fetch_time,
            )
