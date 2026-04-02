"""Shared data models for the Artemis 2 position poller."""
from dataclasses import dataclass, field


@dataclass
class StateVector:
    """Single spacecraft state in J2000/ICRF frame."""
    t: float    # epoch in J2000 seconds (seconds past 2000-01-01 12:00:00 UTC)
    x: float    # position X in meters
    y: float    # position Y in meters
    z: float    # position Z in meters
    vx: float   # velocity X in m/s
    vy: float   # velocity Y in m/s
    vz: float   # velocity Z in m/s


@dataclass
class Attitude:
    """Spacecraft attitude quaternion (w, x, y, z convention).

    OpenSpace StaticRotation convention: (w, x, y, z).
    Source: AROW GCS Io params 8-11.
    The exact param-to-component mapping (which param is w vs x) is
    configurable in the Lua orientation script — this dataclass stores
    the raw values as q0/q1/q2/q3 without assuming ordering.
    """
    q0: float  # quaternion component (assumed w)
    q1: float  # quaternion component (assumed x)
    q2: float  # quaternion component (assumed y)
    q3: float  # quaternion component (assumed z)


@dataclass
class SourceResult:
    """Container for adapter fetch results."""
    source_name: str            # e.g., "arow_gcs", "horizons", "arow_oem"
    points: list[StateVector]
    raw_data: str               # raw response for archival (D-05)
    timestamp: float            # wall-clock time of fetch (time.time())
    attitude: "Attitude | None" = None  # spacecraft quaternion if available
