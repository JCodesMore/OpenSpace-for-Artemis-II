-- artemis2_orient.lua — LuaRotation script for real-time Artemis 2 spacecraft orientation.
--
-- IMPORTANT: This entire file is re-executed every frame by OpenSpace's LuaRotation
-- engine. Only global variables persist between frames. All globals use the
-- `rawget(_G, name) or default` idiom (Lua strict mode compliance).
--
-- wallTime is MILLISECONDS since Unix epoch (NOT J2000 seconds).
--
-- Reads the same data file as artemis2_live.lua (position script). The poller
-- writes an optional `attitude = { q0=w, q1=x, q2=y, q3=z }` field when
-- AROW GCS Io params 8-11 are available.
--
-- Quaternion component mapping — CONFIGURABLE. Pre-launch assumption:
--   param 8 = q0 (w), param 9 = q1 (x), param 10 = q2 (y), param 11 = q3 (z)
-- If the model appears misoriented after T+1min, swap these assignments.
-- OpenSpace StaticRotation convention: (w, x, y, z) per staticrotation.cpp line 74.
--
-- Returns: 9-value table (row-major 3x3 rotation matrix) per LuaRotation contract.
-- When no quaternion data is available, returns identity matrix.

-- ── Quaternion component mapping (edit here to fix orientation post-launch) ───
-- These map from the poller file's q0/q1/q2/q3 to OpenSpace's (w, x, y, z).
local QW_KEY = "q0"  -- which data file field is the w (scalar) component
local QX_KEY = "q1"  -- which data file field is the x component
local QY_KEY = "q2"  -- which data file field is the y component
local QZ_KEY = "q3"  -- which data file field is the z component

-- ── Global state (initialized once, persists across frame re-executions) ──────
_orient_data = rawget(_G, "_orient_data") or nil   -- attitude table {q0, q1, q2, q3} or nil
_orient_last_wall = rawget(_G, "_orient_last_wall") or 0  -- wallTime (ms) of last file read

-- Path to the data file written by the Python poller (same file as position script).
_ORIENT_DATA_PATH = rawget(_G, "_ORIENT_DATA_PATH")
    or "C:/Users/jmd50/Documents/Main/Projects/AI/artemis-2-track/poller/artemis2_live.dat"

-- Re-read interval: reload data file at most every 3 wall-clock seconds.
local INTERVAL_MS = 3000

-- Identity rotation matrix (returned when no quaternion data available).
local IDENTITY = { 1, 0, 0, 0, 1, 0, 0, 0, 1 }

-- ── quat_to_matrix ───────────────────────────────────────────────────────────
-- Standard quaternion-to-rotation-matrix conversion.
-- Convention: (w, x, y, z) matching OpenSpace's StaticRotation (glm::mat3_cast).
-- Returns 9-value row-major table.

local function quat_to_matrix(w, x, y, z)
  return {
    1 - 2*(y*y + z*z),     2*(x*y - w*z),     2*(x*z + w*y),
        2*(x*y + w*z), 1 - 2*(x*x + z*z),     2*(y*z - w*x),
        2*(x*z - w*y),     2*(y*z + w*x), 1 - 2*(x*x + y*y)
  }
end

-- ── try_load_attitude ────────────────────────────────────────────────────────
-- Reads the Lua-table data file and extracts the attitude field.
-- Updates _orient_data on success. Returns true if new data loaded.

local function try_load_attitude(path)
  local raw = openspace.readFile(path)
  if not raw or raw == "" then return false end
  local fn, err = load("return " .. raw)
  if not fn then return false end
  local ok, result = pcall(fn)
  if ok and type(result) == "table" and result.attitude then
    _orient_data = result.attitude
    return true
  end
  return false
end

-- ── rotation ─────────────────────────────────────────────────────────────────
-- Entry point called by OpenSpace every frame.
-- Returns 9-value row-major 3x3 rotation matrix.

function rotation(simulationTime, prevSimulationTime, wallTime)
  -- Throttled file re-read
  if (wallTime - _orient_last_wall) > INTERVAL_MS or _orient_data == nil then
    try_load_attitude(_ORIENT_DATA_PATH)
    _orient_last_wall = wallTime
  end

  -- No attitude data: return identity (stable, non-spinning)
  if _orient_data == nil then return IDENTITY end

  -- Extract quaternion components using configurable mapping
  local qw = _orient_data[QW_KEY]
  local qx = _orient_data[QX_KEY]
  local qy = _orient_data[QY_KEY]
  local qz = _orient_data[QZ_KEY]

  if not qw or not qx or not qy or not qz then return IDENTITY end

  return quat_to_matrix(qw, qx, qy, qz)
end
