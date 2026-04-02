---
phase: quick
plan: 260402-4tk
subsystem: tools/poller, artemis2-assets
tags: [poller, lua, openspace, auto-start, self-contained]
dependency-graph:
  requires: []
  provides: [tools/poller package, poller_launcher.asset, SandboxedLua=false]
  affects: [artemis2.asset, artemis2_live.lua, artemis2_orient.lua, openspace.cfg]
tech-stack:
  added: [Python poller package at tools/poller/, OpenSpace Lua asset lifecycle callbacks]
  patterns: [os.execute background launch, openspace.absPath dynamic path resolution]
key-files:
  created:
    - tools/poller/ (entire package: poller.py, writer.py, models.py, archive.py, sources/, tests/, fixtures/)
    - tools/poller/requirements.txt
    - tools/poller/start_poller.bat
    - tools/poller/start_poller.sh
    - data/assets/scene/solarsystem/missions/artemis2/poller_launcher.asset
  modified:
    - data/assets/scene/solarsystem/missions/artemis2/artemis2_live.lua
    - data/assets/scene/solarsystem/missions/artemis2/artemis2_orient.lua
    - data/assets/scene/solarsystem/missions/artemis2/artemis2.asset
    - openspace.cfg
    - .gitignore
decisions:
  - "Use cd to tools/ (parent of poller package) in launcher scripts so python -m poller.poller resolves correctly"
  - "SandboxedLua = false required to allow os.execute in asset onInitialize/onDeinitialize callbacks"
  - "start /B cmd /c pattern on Windows ensures poller runs detached from OpenSpace process"
  - "Runtime artifacts (artemis2_live.dat, archive/, logs/, __pycache__/) excluded from git"
metrics:
  duration: "3 minutes"
  completed: "2026-04-02"
  tasks-completed: 2
  tasks-total: 2
  files-created: 33
  files-modified: 5
---

# Quick Task 260402-4tk: Move Poller Into OpenSpace-for-Artemis-II Summary

**One-liner:** Moved Python poller into tools/poller/ with start_poller.bat/sh launchers, created poller_launcher.asset for OpenSpace lifecycle auto-start/stop, updated Lua paths to use openspace.absPath("${BASE}/tools/poller/artemis2_live.dat"), and set SandboxedLua=false.

## What Was Built

The OpenSpace-for-Artemis-II repo is now fully self-contained for live Artemis 2 tracking:

1. **tools/poller/ package** — Full Python poller copied from ../poller/ with all source files, tests (87 passing), fixtures, and launchers. No changes to source logic.

2. **start_poller.bat / start_poller.sh** — Launcher scripts that cd to tools/ (the package parent directory) before running `python -m poller.poller`, ensuring proper module resolution. Output goes to tools/poller/artemis2_live.dat.

3. **poller_launcher.asset** — OpenSpace asset with onInitialize/onDeinitialize callbacks. On init: `start /B cmd /c` launches the poller as a background process. On deinit: taskkill (Windows) or pkill (Unix) terminates it. Wired into artemis2.asset via `asset.require("./poller_launcher")`.

4. **Lua path updates** — Both artemis2_live.lua and artemis2_orient.lua now use `openspace.absPath("${BASE}/tools/poller/artemis2_live.dat")` instead of hardcoded user-specific paths. No jmd50 paths remain in any tracked file.

5. **openspace.cfg** — Single change: `SandboxedLua = false` to allow os.execute in asset callbacks.

6. **.gitignore** — Added entries for poller runtime artifacts (artemis2_live.dat, archive/, logs/, __pycache__/).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Copy poller package and create launcher scripts | 75610cf08 | tools/poller/ (28 files) |
| 2 | Wire Lua paths, create launcher asset, enable unsandboxed Lua | 86518676b | 6 files modified/created |

## Verification Results

- All 87 poller tests pass from the new location: `cd tools && python -m pytest poller/tests/ -x -q`
- No hardcoded user paths remain: `grep -r "jmd50" data/assets/scene/solarsystem/missions/artemis2/` returns nothing
- All key files exist with correct content
- SandboxedLua = false confirmed in openspace.cfg
- poller_launcher.asset has os.execute calls and is required by artemis2.asset

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. The poller_launcher.asset is fully wired. The artemis2_live.dat will be generated at runtime by the poller process; it is intentionally absent from the repo (gitignored as a runtime artifact).

## Self-Check: PASSED

Files verified:
- tools/poller/poller.py: FOUND
- tools/poller/requirements.txt: FOUND
- tools/poller/start_poller.bat: FOUND
- tools/poller/start_poller.sh: FOUND
- data/assets/scene/solarsystem/missions/artemis2/poller_launcher.asset: FOUND
- Commits 75610cf08 and 86518676b: FOUND
