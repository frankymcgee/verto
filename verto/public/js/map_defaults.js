frappe.provide("frappe.utils");

const map_settings = frappe.provide("frappe.utils.map_defaults");
const configured_map = frappe.boot?.verto_map_settings || {};

const has_value = (value) => value !== undefined && value !== null && value !== "";
const setting_or = (value, fallback) => (has_value(value) ? value : fallback);
const number_or = (value, fallback) => {
	const parsed = Number(value);
	return has_value(value) && Number.isFinite(parsed) ? parsed : fallback;
};

const existing_center = Array.isArray(map_settings.center)
	? map_settings.center
	: [-32.5279, 115.7189];

map_settings.center = [
	number_or(configured_map.center_latitude, existing_center[0]),
	number_or(configured_map.center_longitude, existing_center[1]),
];
map_settings.zoom = number_or(configured_map.default_zoom, map_settings.zoom ?? 6);
map_settings.minZoom = number_or(configured_map.min_zoom, map_settings.minZoom ?? 0);
map_settings.maxZoom = number_or(configured_map.max_zoom, map_settings.maxZoom ?? 19);
map_settings.image_path =
	map_settings.image_path || "/assets/frappe/images/leaflet/";

const existing_tiles =
	map_settings.tiles && typeof map_settings.tiles === "object"
		? map_settings.tiles
		: {};

const existing_default = existing_tiles.default_tile || {};
const existing_satellite = existing_tiles.satellite_tile || {};
const existing_labels = existing_tiles.labels_tail || {};
const existing_terrain = existing_tiles.terrain_lines_tail || {};

map_settings.tiles = {
	...existing_tiles,

	default_tile: {
		url: setting_or(
			configured_map.default_tile_url,
			existing_default.url ||
				"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
		),
		options: {
			...(existing_default.options || {}),
			minZoom: map_settings.minZoom,
			maxZoom: map_settings.maxZoom,
			attribution: setting_or(
				configured_map.default_attribution,
				existing_default.options?.attribution ||
					'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
			),
		},
	},

	satellite_tile: {
		url: setting_or(
			configured_map.satellite_tile_url,
			existing_satellite.url ||
				"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
		),
		options: {
			...(existing_satellite.options || {}),
			minZoom: map_settings.minZoom,
			maxZoom: map_settings.maxZoom,
			attribution: setting_or(
				configured_map.satellite_attribution,
				existing_satellite.options?.attribution ||
					"Tiles &copy; Esri and the GIS User Community"
			),
		},
	},

	labels_tail: {
		url: setting_or(
			configured_map.labels_tile_url,
			existing_labels.url ||
				"https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
		),
		options: {
			...(existing_labels.options || {}),
			minZoom: map_settings.minZoom,
			maxZoom: map_settings.maxZoom,
			attribution: setting_or(
				configured_map.labels_attribution,
				existing_labels.options?.attribution || "Labels &copy; Esri"
			),
		},
	},

	terrain_lines_tail: {
		url: setting_or(
			configured_map.terrain_tile_url,
			existing_terrain.url ||
				"https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}"
		),
		options: {
			...(existing_terrain.options || {}),
			minZoom: map_settings.minZoom,
			maxZoom: number_or(
				configured_map.terrain_max_zoom,
				existing_terrain.options?.maxZoom ?? 13
			),
			opacity: Math.min(
				1,
				Math.max(
					0,
					number_or(
						configured_map.terrain_opacity,
						existing_terrain.options?.opacity ?? 0.45
					)
				)
			),
			attribution: setting_or(
				configured_map.terrain_attribution,
				existing_terrain.options?.attribution || "Terrain &copy; Esri"
			),
		},
	},
};
