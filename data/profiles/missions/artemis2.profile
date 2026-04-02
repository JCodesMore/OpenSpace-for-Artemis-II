{
  "assets": [
    "base",
    "base_keybindings",
    "events/toggle_sun",
    "scene/solarsystem/planets/earth/earth",
    "scene/solarsystem/planets/earth/satellites/satellites",
    "scene/solarsystem/missions/artemis2/artemis2",
    "scene/solarsystem/missions/artemis2/toggle_trail"
  ],
  "camera": {
    "aim": "",
    "anchor": "Artemis2Model",
    "frame": "Root",
    "pitch": 0.008681,
    "position": {
      "x": 364.907409,
      "y": -65.898746,
      "z": 361.510673
    },
    "type": "setNavigationState",
    "up": {
      "x": -0.128611,
      "y": 0.94459,
      "z": 0.302006
    },
    "yaw": -0.003474
  },
  "delta_times": [
    1.0, 5.0, 30.0, 60.0, 300.0, 1800.0, 3600.0, 43200.0,
    86400.0, 604800.0, 1209600.0, 2592000.0, 5184000.0,
    7776000.0, 15552000.0, 31536000.0, 63072000.0,
    157680000.0, 315360000.0, 630720000.0
  ],
  "mark_nodes": [
    "Artemis2Model",
    "Earth",
    "Moon",
    "Sun"
  ],
  "meta": {
    "author": "Custom",
    "description": "Artemis 2 Profile. Adds the Orion capsule (Artemis-2) model with its trajectory around the Moon.",
    "license": "MIT License",
    "name": "Artemis 2",
    "url": "https://www.openspaceproject.com",
    "version": "1.0"
  },
  "panel_visibility": {
    "mission": true
  },
  "properties": [
    {
      "name": "{earth_satellites~space_stations}.Renderable.Enabled",
      "type": "setPropertyValue",
      "value": "false"
    },
    {
      "name": "Scene.MoonTrail.Renderable.Appearance.Color",
      "type": "setPropertyValueSingle",
      "value": "{0.5, 0.5, 0.5}"
    },
    {
      "name": "Scene.Earth.Renderable.Layers.ColorLayers.ESRI_NOAA20_Combo.Enabled",
      "type": "setPropertyValueSingle",
      "value": "true"
    },
    {
      "name": "Scene.Earth.Renderable.Layers.ColorLayers.ESRI_VIIRS_Combo.Enabled",
      "type": "setPropertyValueSingle",
      "value": "false"
    },
    {
      "name": "Scene.ISS.Renderable.Enabled",
      "type": "setPropertyValueSingle",
      "value": "false"
    },
    {
      "name": "Scene.ISS_trail.Renderable.Enabled",
      "type": "setPropertyValueSingle",
      "value": "false"
    },
    {
      "name": "Scene.*Trail.Renderable.Enabled",
      "type": "setPropertyValue",
      "value": "false"
    },
    {
      "name": "Scene.EarthTrail.Renderable.Enabled",
      "type": "setPropertyValueSingle",
      "value": "true"
    },
    {
      "name": "Scene.MoonTrail.Renderable.Enabled",
      "type": "setPropertyValueSingle",
      "value": "true"
    },
    {
      "name": "Scene.MoonTrail.Renderable.Appearance.EnableFade",
      "type": "setPropertyValueSingle",
      "value": "false"
    },
    {
      "name": "Scene.Artemis2EarthTrail.Renderable.Enabled",
      "type": "setPropertyValueSingle",
      "value": "true"
    },
    {
      "name": "Scene.Artemis2MoonTrail.Renderable.Enabled",
      "type": "setPropertyValueSingle",
      "value": "false"
    },
    {
      "name": "Scene.Artemis2LiveTrail.Renderable.Enabled",
      "type": "setPropertyValueSingle",
      "value": "true"
    }
  ],
  "time": {
    "is_paused": false,
    "type": "absolute",
    "value": "2026-04-04T12:00:00"
  },
  "version": {
    "major": 1,
    "minor": 5
  }
}
