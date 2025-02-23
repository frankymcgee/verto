frappe.provide("frappe.utils");
frappe.provide("frappe.views");

frappe.views.MapView = class MapView extends frappe.views.ListView {
	get view_name() {
		return "Map"		
	}
	
	setup_defaults() {
		super.setup_defaults();
		this.page_title = __("{0} Map", [this.page_title]);
	}

	setup_view() {}

	on_filter_change() {
		this.get_coords();
	}

	render() {
		this.get_coords().then(() => {
			this.render_map_view();
		});
		this.$paging_area.find(".level-left").append("<div></div>");
	}

	render_map_view() {
		var railway_tile = 'https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png';
		var terrainlabel_tile = 'https://tiles.stadiamaps.com/tiles/stamen_terrain_labels/{z}/{x}/{y}{r}.png';
		var terrianline_tile = 'https://tiles.stadiamaps.com/tiles/stamen_terrain_lines/{z}/{x}/{y}{r}.png';
		this.map_id = frappe.dom.get_unique_id();

		this.$result.html(`<div id="${this.map_id}" class="map-view-container"></div>`);

		L.Icon.Default.imagePath = frappe.utils.map_defaults.image_path;
		this.map = L.map(this.map_id).setView(
			frappe.utils.map_defaults.center,
			frappe.utils.map_defaults.zoom
		);
		L.tileLayer(frappe.utils.map_defaults.tiles,{maxNativeZoom :17}).addTo(this.map);
		L.tileLayer(railway_tile).addTo(this.map);		
		L.tileLayer(terrianline_tile).addTo(this.map);		
		L.tileLayer(terrainlabel_tile).addTo(this.map);		

		L.control.scale().addTo(this.map);
		if (this.coords.features && this.coords.features.length) {
			this.coords.features.forEach((coords) =>
				L.geoJSON(coords).bindPopup('<b>'+ coords.properties.project_scope_name + '</b></br><i>' + coords.properties.parent_task_name + ' - ' + coords.properties.subject + '</i>' + '</br>Contractor: ' + coords.properties.responsible_contractor + '</br><a href="/app/task/' + coords.properties.name.toString() + '">Open Task</a>').addTo(this.map)
			);
			let lastCoords = this.coords.features[0].geometry.coordinates.reverse();
			this.map.setView(lastCoords, 16);			
		}
	}

	get_coords() {
		let get_coords_method =
			(this.settings && this.settings.get_coords_method) || "verto.geo.utils.verto_get_coords";

		if (
			cur_list.meta.fields.find(
				(i) => i.fieldname === "location" && i.fieldtype === "Geolocation"
			)
		) {
			this.type = "location_field";
		} else if (
			cur_list.meta.fields.find((i) => i.fieldname === "latitude") &&
			cur_list.meta.fields.find((i) => i.fieldname === "longitude")
		) {
			this.type = "coordinates";
		}
		return frappe
			.call({
				method: get_coords_method,
				args: {
					doctype: this.doctype,
					filters: cur_list.filter_area.get(),
					type: this.type,
				},
			})
			.then((r) => {
				this.coords = r.message;
			});
	}

	get required_libs() {
		return [
			"assets/frappe/js/lib/leaflet/leaflet.css",
			"assets/frappe/js/lib/leaflet/leaflet.js",
		];
	}
};
