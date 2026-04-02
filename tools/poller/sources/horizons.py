"""JPL Horizons API source adapter -- Tier 3 (reliable fallback, ~10min resolution)."""
import logging
import math
import re
import time
import requests
from poller.models import StateVector, SourceResult

logger = logging.getLogger(__name__)

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
J2000_UNIX = 946728000.0  # Unix timestamp at J2000 epoch (2000-01-01 12:00:00 UTC)

# IAU76 obliquity of the ecliptic = 23.439291 degrees
_OBLIQUITY_RAD = math.radians(23.439291)
_COS_E = math.cos(_OBLIQUITY_RAD)  # 0.917482137087
_SIN_E = math.sin(_OBLIQUITY_RAD)  # 0.397777155931


def eclipj2000_to_icrf(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Rotate ECLIPJ2000 vector to J2000/ICRF. Rotation around X axis by -obliquity."""
    return (x, _COS_E * y - _SIN_E * z, _SIN_E * y + _COS_E * z)


def j2000_to_utc_str(j2000_s: float) -> str:
    """Convert J2000 seconds to Horizons-compatible UTC time string."""
    dt = time.gmtime(J2000_UNIX + j2000_s)
    return time.strftime("%Y-%m-%dT%H:%M:%S", dt)


class HorizonsSource:
    """Fetches spacecraft ephemeris from the JPL Horizons API."""

    def __init__(
        self,
        spacecraft_id: str = "-1024",
        center: str = "500@399",
        timeout: int = 30,
    ) -> None:
        self.spacecraft_id = spacecraft_id
        self.center = center
        self.timeout = timeout

    def parse_horizons_response(self, text: str) -> list[StateVector]:
        """Parse Horizons text response between $$SOE and $$EOE markers.

        Returns a list of StateVector with positions in J2000/ICRF meters
        and velocities in m/s.
        """
        # Find the $$SOE ... $$EOE block
        soe_match = re.search(r"\$\$SOE(.*?)\$\$EOE", text, re.DOTALL)
        if not soe_match:
            logger.warning("parse_horizons_response: no $$SOE marker found")
            return []

        block = soe_match.group(1)
        lines = block.splitlines()

        vectors: list[StateVector] = []
        i = 0
        # Pattern for the Julian date line
        jd_pattern = re.compile(r"^\s*(\d+\.\d+)\s*=\s*A\.D\.")
        # Pattern to extract floating point numbers (handles E notation and sign)
        num_pattern = re.compile(r"[+-]?\d+\.\d+E[+-]\d+")

        while i < len(lines):
            jd_match = jd_pattern.match(lines[i])
            if jd_match:
                jd_tdb = float(jd_match.group(1))
                # Convert Julian Date TDB to J2000 seconds
                t_j2000 = (jd_tdb - 2451545.0) * 86400.0

                # Next line: X Y Z
                i += 1
                if i >= len(lines):
                    break
                pos_nums = num_pattern.findall(lines[i])
                if len(pos_nums) < 3:
                    i += 1
                    continue
                x_km = float(pos_nums[0])
                y_km = float(pos_nums[1])
                z_km = float(pos_nums[2])

                # Next line: VX VY VZ
                i += 1
                if i >= len(lines):
                    break
                vel_nums = num_pattern.findall(lines[i])
                if len(vel_nums) < 3:
                    i += 1
                    continue
                vx_kms = float(vel_nums[0])
                vy_kms = float(vel_nums[1])
                vz_kms = float(vel_nums[2])

                # Convert km -> meters and km/s -> m/s
                x_m = x_km * 1000.0
                y_m = y_km * 1000.0
                z_m = z_km * 1000.0
                vx_ms = vx_kms * 1000.0
                vy_ms = vy_kms * 1000.0
                vz_ms = vz_kms * 1000.0

                # Rotate ECLIPJ2000 -> J2000/ICRF for both position and velocity
                x_icrf, y_icrf, z_icrf = eclipj2000_to_icrf(x_m, y_m, z_m)
                vx_icrf, vy_icrf, vz_icrf = eclipj2000_to_icrf(vx_ms, vy_ms, vz_ms)

                vectors.append(
                    StateVector(
                        t=t_j2000,
                        x=x_icrf,
                        y=y_icrf,
                        z=z_icrf,
                        vx=vx_icrf,
                        vy=vy_icrf,
                        vz=vz_icrf,
                    )
                )
            i += 1

        logger.debug(
            "parse_horizons_response: extracted %d state vectors", len(vectors)
        )
        return vectors

    def fetch(
        self,
        start_j2000: float,
        stop_j2000: float,
        step_size: str = "10m",
    ) -> SourceResult:
        """Fetch state vectors from JPL Horizons API.

        Returns SourceResult with source_name='horizons'. On any error,
        returns an empty SourceResult rather than raising.
        """
        fetch_start = time.time()
        logger.info(
            "horizons fetch start: start=%.1f stop=%.1f step=%s wall=%.3f",
            start_j2000,
            stop_j2000,
            step_size,
            fetch_start,
        )

        try:
            start_str = j2000_to_utc_str(start_j2000)
            stop_str = j2000_to_utc_str(stop_j2000)

            params = {
                "format": "json",
                "COMMAND": self.spacecraft_id,
                "EPHEM_TYPE": "VECTORS",
                "CENTER": self.center,
                "START_TIME": start_str,
                "STOP_TIME": stop_str,
                "STEP_SIZE": step_size,
                "VEC_TABLE": "3",
            }

            response = requests.get(
                HORIZONS_URL, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            result_text = data.get("result", "")

            points = self.parse_horizons_response(result_text)

            fetch_end = time.time()
            logger.info(
                "horizons fetch done: %d points, elapsed=%.2fs wall=%.3f",
                len(points),
                fetch_end - fetch_start,
                fetch_end,
            )

            return SourceResult(
                source_name="horizons",
                points=points,
                raw_data=result_text,
                timestamp=fetch_end,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "horizons fetch error: %s wall=%.3f", exc, time.time()
            )
            return SourceResult(
                source_name="horizons",
                points=[],
                raw_data="",
                timestamp=time.time(),
            )
