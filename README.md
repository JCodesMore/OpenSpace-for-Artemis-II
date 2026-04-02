![OpenSpace Logo](/data/openspace-horiz-logo-crop.png)

<h1 align="center">Artemis II Real-Time Mission Tracker</h1>

<p align="center">
  <b>Track NASA's first crewed lunar mission in 50 years — live, in 3D, on your desktop.</b>
</p>

<p align="center">
  <a href="LICENSE.md"><img src="https://img.shields.io/badge/License-MIT-purple.svg?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/Mission-Artemis%20II-orange?style=flat-square" alt="Artemis II">
  <img src="https://img.shields.io/badge/Telemetry-Live%20~7s-brightgreen?style=flat-square" alt="Live Telemetry">
  <img src="https://img.shields.io/badge/Built%20on-OpenSpace-blue?style=flat-square" alt="OpenSpace">
</p>

---

This is a custom fork of [OpenSpace](http://openspaceproject.com) purpose-built to visualize the **Artemis II mission** — the first crewed flight around the Moon since Apollo 17 in 1972. It pulls live spacecraft telemetry, renders a 3D Orion capsule with real-time orientation, and lets you fly alongside the crew from launch to splashdown.

> **Artemis II mission window:** April 1 -- 11, 2026 | **Crew:** Reid Wiseman, Victor Glover, Christina Koch, Jeremy Hansen

## What This Fork Adds

- **Live spacecraft tracking** — Position updates every ~7 seconds from NASA's AROW telemetry system
- **3D Orion capsule** with real-time attitude (orientation follows live quaternion data)
- **Three-tier data pipeline** — Automatic failover ensures continuous tracking (see [Data Sources](#data-sources))
- **Pre-computed trajectory** for the full 10-day mission via JPL Horizons
- **10 mission milestone shortcuts** — Jump to any key moment with one click:

  | Event | Date (UTC) |
  |-------|-----------|
  | Launch | Apr 1, 22:24 |
  | Liftoff | Apr 1, 22:35 |
  | ICPS Separation | Apr 2, 01:59 |
  | Trans-Lunar Injection | Apr 3, 00:12 |
  | Lunar SOI Entry | Apr 6, 05:34 |
  | Closest Lunar Approach | Apr 6, 23:58 |
  | Max Distance from Earth | Apr 7, 00:01 |
  | Lunar SOI Exit | Apr 7, 18:22 |
  | Entry Interface (peak heating) | Apr 11, 00:08 |
  | Splashdown (Pacific, off San Diego) | Apr 11, 00:21 |

- **Camera presets** — Overview, Follow, and Close-up views
- **Zero manual steps** after initial setup — select the profile and go

## Data Sources

The tracking pipeline automatically pulls from the best available source and fails over gracefully:

| Priority | Source | Latency | Description |
|----------|--------|---------|-------------|
| 1 (primary) | AROW GCS | ~7 seconds | Real-time telemetry from NASA's public Google Cloud Storage bucket |
| 2 (fallback) | AROW OEM | ~4 minutes | Orbital Ephemeris Messages with smoothed trajectory |
| 3 (backup) | JPL Horizons | Pre-computed | On-demand query to NASA/JPL ephemeris service |

You don't need to configure anything — the poller starts automatically with OpenSpace and picks the best source available.

## Quick Setup

### Prerequisites

- **OpenSpace built from source** — Follow the [OpenSpace build instructions](https://docs.openspaceproject.com) for your platform
  - Windows: Visual Studio 2022+, CMake 4.0+, Qt
  - Linux: GCC 13+, CMake 4.0+, Qt
- **Python 3.10+** with `requests` library

### Steps

1. **Clone this repo** (instead of the main OpenSpace repo):
   ```bash
   git clone --recursive https://github.com/JCodesMore/OpenSpace-for-Artemis-II.git
   cd OpenSpace-for-Artemis-II
   ```

2. **Build OpenSpace** following the [standard build docs](https://docs.openspaceproject.com)

3. **Install the poller dependency:**
   ```bash
   pip install requests
   ```

4. **Launch OpenSpace** and select the **`artemis2`** profile (under `missions/`) — the Artemis II profile

That's it. The live tracking poller starts automatically. During the Artemis II mission window (Apr 1--11, 2026), you'll see Orion's position and orientation update in real time.

### Pre-Mission

Before the mission starts, the pre-computed JPL Horizons trajectory is available. You can scrub the timeline to explore the planned flight path and jump to mission milestones via the Actions menu.

---

## About OpenSpace

<p align="center">
  <em>An open-source interactive data visualization software designed to visualize the entire known universe</em>
</p>

<p align="center">
  <a href="https://docs.openspaceproject.com"><b>Docs</b></a> &middot; <a href="https://join.slack.com/t/openspacesupport/shared_invite/zt-24uhn3wvo-gCGHgjg2m9tHzKUEb_FyMQ"><b>Slack</b></a> &middot; <a href="http://openspaceproject.com"><b>Website</b></a> &middot; <a href="https://www.youtube.com/@OpenSpaceProj"><b>YouTube</b></a>
</p>

[OpenSpace](http://openspaceproject.com) is an open source, non-commercial, and freely available interactive data visualization software designed to visualize the entire known universe and portray our ongoing efforts to investigate the cosmos. Bringing the latest techniques from data visualization research to the general public, OpenSpace supports interactive presentation of dynamic data from observations, simulations, and space mission planning and operations.

[![System Paper](https://img.shields.io/badge/System%20Paper-10.1109%2FTVCG.2019.2934259-blue?style=flat-square)](https://doi.org/10.1109/TVCG.2019.2934259)
[![GlobeBrowsing Paper](https://img.shields.io/badge/GlobeBrowsing%20Paper-https%3A%2F%2Fdoi.org%2F10.1109%2FTVCG.2017.2743958-blue?style=flat-square)](https://doi.org/10.1109/TVCG.2017.2743958)

### Background

OpenSpace started as a collaboration between Sweden's [Linköping University](https://immvis.github.io) (LiU) and the [American Museum of Natural History](https://www.amnh.org). Development of the software began several years ago through a close collaboration with NASA Goddard's [Community Coordinated Modeling Center](https://ccmc.gsfc.nasa.gov) (CCMC) to model space weather forecasting and continued with visualizations of NASA's New Horizons mission to Pluto and ESA's Rosetta mission to 67P/Churyumov-Gerasimenko.

### Features

Some of the high-level features supported in OpenSpace:

- AMNH's Digital Universe catalog of extrasolar datasets (stars, galaxies, quasars, ...)
- High-resolution planetary images for major objects in the solar system
- Animated 3D models representing space missions (ISS, New Horizons, JWST, ...)
- Support for custom profiles with arbitrary user-defined content
- Ability to drive any type of display environment (flat screen, multi-projector, planetariums, ...)
- Lua, JavaScript, and Python interfaces into the engine
- Native support to export sessions as individual frames for video export

OpenSpace requires support for [OpenGL](https://www.opengl.org/) version 4.6.

### Asking Questions

Feel free to create issues for missing features, bug reports, or compile problems or contact the OpenSpace team via [email](mailto:support@openspaceproject.com?subject=OpenSpace:). You are also welcome on the [Slack support channel](https://join.slack.com/t/openspacesupport/shared_invite/zt-24uhn3wvo-gCGHgjg2m9tHzKUEb_FyMQ).

### Contributing

Contributions are welcome in many forms — bug reports, bug fixes, new content, new features, and sharing images and videos you've made with the software. Share in the #showcase channel on Slack.

## License

OpenSpace is under a permissive [MIT license](LICENSE.md).

## Support

OpenSpace is grateful for the support from the following institutions:

<p align="center">
  <img src="https://docs.openspaceproject.com/latest/_static/logos/sponsors.png" alt="Supporters">
</p>
