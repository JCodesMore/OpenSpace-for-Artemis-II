-- artemis2_live.lua — LuaTranslation script for real-time Artemis 2 spacecraft position.
--
-- IMPORTANT: This entire file is re-executed every frame by OpenSpace's LuaTranslation
-- engine (ghoul::lua::runScriptFile). Only global variables persist between frames.
-- All globals use the `_var = _var or default` idiom to initialize once and survive
-- across frames without resetting.
--
-- wallTime is MILLISECONDS since Unix epoch (NOT J2000 seconds).
-- Confirmed from luatranslation.cpp: high_resolution_clock::now().time_since_epoch() in ms.
--
-- Data file format (written by Python poller, Lua table syntax):
--   {
--     last_updated = 828354300.0,  -- J2000 epoch seconds
--     source = "arow_gcs",
--     points = {
--       { t=828354240.0, x=-25685000.0, y=-17027000.0, z=-1456979.0,
--                        vx=-1571.3, vy=-3698.8, vz=-320.1 },
--       ...
--     }
--   }
--   t: J2000 seconds, x/y/z: meters (J2000/ICRF frame), vx/vy/vz: m/s
--
-- Coordinate frame: J2000/ICRF meters. This node sits under EarthInertial which
-- applies the J2000->Galactic SPICE rotation. Do NOT place under EarthCenter.
--
-- Sandbox note: io, os, package are removed. Use openspace.readFile().

-- ── Global state (initialized once, persists across frame re-executions) ──────
-- NOTE: OpenSpace enables Lua strict mode (ghoul StrictState::Yes), which forbids
-- reading undeclared globals. Use rawget(_G, name) to check existence without
-- triggering the __index metamethod error "variable 'X' is not declared".

_data = rawget(_G, "_data") or {}               -- cached array of data points from file
_last_wall = rawget(_G, "_last_wall") or 0      -- wallTime (ms) when file was last read
_last_pos = rawget(_G, "_last_pos") or {0, 0, 0}  -- last successfully interpolated position

-- Path to the data file written by the Python poller.
-- Change this path to match your local poller output location.
_DATA_PATH = rawget(_G, "_DATA_PATH") or "C:/Users/jmd50/Documents/Main/Projects/AI/artemis-2-track/poller/artemis2_live.dat"

-- Re-read interval: reload data file at most every 3 wall-clock seconds.
local INTERVAL_MS = 3000

-- ── try_load_data ─────────────────────────────────────────────────────────────
-- Reads and parses the Lua-table data file. Updates _data on success.
-- Returns true if new data was loaded, false otherwise.

local function try_load_data(path)
  local raw = openspace.readFile(path)
  if not raw or raw == "" then return false end
  -- Parse Lua table syntax safely via load() + pcall()
  local fn, err = load("return " .. raw)
  if not fn then return false end
  local ok, result = pcall(fn)
  if ok and type(result) == "table" and result.points and #result.points > 0 then
    _data = result.points
    return true
  end
  return false
end

-- ── find_bracket ──────────────────────────────────────────────────────────────
-- Binary search: finds indices lo, hi such that data[lo].t <= t < data[hi].t.
-- Returns (1, 1) when fewer than 2 points exist (caller handles degenerate case).

local function find_bracket(t, data)
  if #data < 2 then return 1, 1 end
  local lo, hi = 1, #data
  while lo < hi - 1 do
    local mid = math.floor((lo + hi) / 2)
    if data[mid].t <= t then lo = mid else hi = mid end
  end
  return lo, hi
end

-- ── hermite ───────────────────────────────────────────────────────────────────
-- Cubic Hermite interpolation between two position/velocity data points.
-- p0, p1: {x, y, z} in meters
-- v0, v1: {vx, vy, vz} in m/s
-- dt: interval duration in seconds (used to scale tangents to dimensionless form)
-- s:  normalized parameter in [0, 1] (0 = p0, 1 = p1)
--
-- Standard Hermite basis functions:
--   h00 = (1 + 2s)(1-s)^2       h10 = s(1-s)^2
--   h01 = s^2(3 - 2s)           h11 = s^2(s - 1)

local function hermite(p0, v0, p1, v1, dt, s)
  local h00 = (1 + 2*s) * (1-s)^2
  local h10 = s * (1-s)^2
  local h01 = s^2 * (3 - 2*s)
  local h11 = s^2 * (s - 1)
  return {
    h00*p0[1] + h10*dt*v0[1] + h01*p1[1] + h11*dt*v1[1],
    h00*p0[2] + h10*dt*v0[2] + h01*p1[2] + h11*dt*v1[2],
    h00*p0[3] + h10*dt*v0[3] + h01*p1[3] + h11*dt*v1[3]
  }
end

-- ── translation ───────────────────────────────────────────────────────────────
-- Entry point called by OpenSpace every frame.
-- simulationTime: seconds past J2000 epoch (2000-01-01 12:00:00 UTC)
-- prevSimulationTime: same, for previous frame
-- wallTime: milliseconds since Unix epoch (NOT J2000)
-- Returns: {x, y, z} in meters in J2000/ICRF frame

function translation(simulationTime, prevSimulationTime, wallTime)
  -- Throttled file re-read: reload every INTERVAL_MS of wall-clock time
  if (wallTime - _last_wall) > INTERVAL_MS or #_data == 0 then
    try_load_data(_DATA_PATH)
    _last_wall = wallTime
  end

  -- No data available: return last known position (R3.6 graceful degradation)
  if #_data == 0 then return _last_pos end

  -- Clamp to data range (before first or after last known point)
  if simulationTime <= _data[1].t then
    _last_pos = {_data[1].x, _data[1].y, _data[1].z}
    return _last_pos
  end
  if simulationTime >= _data[#_data].t then
    local d = _data[#_data]
    _last_pos = {d.x, d.y, d.z}
    return _last_pos
  end

  -- Find bracketing data points and Hermite interpolate
  local i, j = find_bracket(simulationTime, _data)
  local d0, d1 = _data[i], _data[j]
  local dt = d1.t - d0.t
  if dt <= 0 then
    -- Degenerate interval: return start point
    _last_pos = {d0.x, d0.y, d0.z}
    return _last_pos
  end
  local s = (simulationTime - d0.t) / dt

  local pos = hermite(
    {d0.x, d0.y, d0.z}, {d0.vx, d0.vy, d0.vz},
    {d1.x, d1.y, d1.z}, {d1.vx, d1.vy, d1.vz},
    dt, s
  )
  _last_pos = pos
  return pos
end
