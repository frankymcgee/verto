frappe.provide("frappe.utils");

const map_settings = frappe.provide("frappe.utils.map_defaults");

// Keep existing Frappe defaults where available.
map_settings.center = map_settings.center || [-32.5279, 115.7189];
map_settings.zoom = map_settings.zoom ?? 6;
map_settings.minZoom = map_settings.minZoom ?? 0;
map_settings.maxZoom = map_settings.maxZoom ?? 19;

map_settings.image_path =
	map_settings.image_path || "/assets/frappe/images/leaflet/";

const existing_tiles =
	map_settings.tiles && typeof map_settings.tiles === "object"
		? map_settings.tiles
		: {};

map_settings.tiles = {
	...existing_tiles,

	// Default street map
	default_tile: existing_tiles.default_tile || {
		url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
		options: {
			minZoom: map_settings.minZoom,
			maxZoom: map_settings.maxZoom,
			attribution:
				'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
		},
	},

	// Esri satellite imagery
	satellite_tile: existing_tiles.satellite_tile || {
		url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
		options: {
			minZoom: map_settings.minZoom,
			maxZoom: 19,
			attribution:
				"Tiles &copy; Esri and the GIS User Community",
		},
	},

	// Place-name and boundary overlay for satellite mode
	labels_tail: existing_tiles.labels_tail || {
		url: "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
		options: {
			minZoom: map_settings.minZoom,
			maxZoom: 19,
			attribution: "Labels &copy; Esri",
		},
	},

	// Terrain overlay
	terrain_lines_tail: existing_tiles.terrain_lines_tail || {
		url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
		options: {
			minZoom: map_settings.minZoom,
			maxZoom: 13,
			opacity: 0.45,
			attribution: "Terrain &copy; Esri",
		},
	},
};
