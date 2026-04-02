"""Atomic Lua-table file writer with sliding window management."""
import logging
import os
import pathlib
import time

from poller.models import StateVector, Attitude

logger = logging.getLogger(__name__)

MAX_POINTS = 120  # ~14 minutes of 7-second AROW data


def format_as_lua_table(
    points: list[StateVector],
    source: str = "unknown",
    attitude: "Attitude | None" = None,
) -> str:
    """Format state vectors as a Lua table expression.

    Output is parseable by Lua: load("return " .. content)
    Positions in meters, velocities in m/s, epochs in J2000 seconds.
    When attitude is provided, emits an attitude block before the points array.
    """
    lines = ["{"]
    lines.append(f"  last_updated = {time.time()},")
    lines.append(f'  source = "{source}",')
    if attitude is not None:
        lines.append(
            f"  attitude = {{ q0={attitude.q0}, q1={attitude.q1},"
            f" q2={attitude.q2}, q3={attitude.q3} }},"
        )
    lines.append("  points = {")
    for sv in points:
        lines.append(
            f"    {{ t={sv.t}, x={sv.x}, y={sv.y}, z={sv.z},"
            f" vx={sv.vx}, vy={sv.vy}, vz={sv.vz} }},"
        )
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def merge_and_trim(
    existing: list[StateVector],
    new: list[StateVector],
    max_points: int = MAX_POINTS,
) -> list[StateVector]:
    """Merge new points into existing, deduplicate by epoch, sort ascending,
    trim to max_points keeping the most recent.

    New points overwrite existing at the same epoch (t value).
    """
    combined = {sv.t: sv for sv in existing}
    for sv in new:
        combined[sv.t] = sv  # new overwrites existing at same epoch
    # Filter out origin points (0,0,0) — these are bad data from missing GCS params
    sorted_points = sorted(
        (sv for sv in combined.values() if sv.x != 0.0 or sv.y != 0.0 or sv.z != 0.0),
        key=lambda sv: sv.t,
    )
    if len(sorted_points) > max_points:
        sorted_points = sorted_points[-max_points:]  # keep most recent
    return sorted_points


def write_atomic(
    path: pathlib.Path,
    points: list[StateVector],
    source: str = "unknown",
    attitude: "Attitude | None" = None,
) -> None:
    """Write data file atomically: write to .tmp, then os.replace().

    Prevents Lua from reading a partially-written file.
    """
    content = format_as_lua_table(points, source, attitude=attitude)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    logger.info("Wrote %d points to %s (source: %s)", len(points), path, source)
