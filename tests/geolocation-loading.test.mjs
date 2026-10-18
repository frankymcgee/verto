import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../verto/public/js/geolocation.js', import.meta.url), 'utf8');
const defaults = readFileSync(new URL('../verto/public/js/map_defaults.js', import.meta.url), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
const point = name => JSON.stringify({
    type: 'FeatureCollection',
    features: [{ type: 'Feature', properties: { name }, geometry: { type: 'Point', coordinates: [115, -32] } }],
});

function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}

function leaflet(state) {
    class LayerGroup {
        constructor() { this.layers = []; }
        addLayer(layer) { this.layers.push(layer); return this; }
        removeLayer(layer) { this.layers = this.layers.filter(item => item !== layer); }
        eachLayer(callback) { [...this.layers].forEach(callback); }
        addTo() { return this; }
        getBounds() { return {}; }
    }
    class Circle {
        static include(methods) { Object.assign(this.prototype, methods); }
        toGeoJSON() { return { properties: {} }; }
    }
    class CircleMarker extends Circle {}
    class TileLayer {
        constructor(url, options) { this._url = url; this.options = options; }
        addTo() { return this; }
    }
    class Control {
        addTo() { return this; }
        remove() {}
    }
    return {
        LayerGroup, FeatureGroup: LayerGroup, Circle, CircleMarker, TileLayer,
        Icon: { Default: {} },
        map(id) {
            const map = {
                id, events: {},
                setView(center, zoom) { this.center = center; this.zoom = zoom; return this; },
                on(event, handler) { this.events[event] = handler; },
                invalidateSize() {}, fitBounds() {},
            };
            state.maps.push(map);
            return map;
        },
        tileLayer: (url, options) => new TileLayer(url, options),
        Control: { Draw: Control },
        control: {
            layers(base, overlays) { state.layers.push({ base, overlays }); return new Control(); },
            locate: () => new Control(),
        },
        geoJson(data) {
            state.geojson.push(data);
            const group = new LayerGroup();
            data.features.forEach(feature => group.addLayer({ feature }));
            return group;
        },
    };
}

function screen({ doctype = 'Project', dialog = false, warm = false } = {}) {
    const state = { maps: [], layers: [], geojson: [], requests: [], events: [], errors: [] };
    state.js = deferred();
    state.css = deferred();
    const document = { querySelector: () => null };
    const wrapper = {
        addClass() { return this; }, removeClass() { return this; },
        html() { return this; }, css() { return this; },
        on(event, handler) { state.events.push({ event, handler }); return this; },
    };
    const frappe = {
        utils: {}, boot: {}, dom: { get_unique_id: () => `map-${doctype}` },
        ui: { form: { ControlData: class {} }, color: { get: name => name } },
        provide() {},
        require(bundle) {
            state.requests.push(bundle);
            if (bundle.endsWith('.js')) {
                return state.js.promise.then(() => { state.context.L = leaflet(state); });
            }
            return state.css.promise;
        },
    };
    frappe.provide = path => path.split('.').slice(1).reduce((parent, key) => parent[key] ||= {}, frappe);
    state.context = vm.createContext({
        frappe, document, $: () => wrapper,
        console: { error: (...args) => state.errors.push(args) },
    });
    if (warm) state.context.L = leaflet(state);
    vm.runInContext(defaults, state.context);
    vm.runInContext(source, state.context);
    state.control = new frappe.ui.form.ControlGeolocation();
    Object.assign(state.control, { disp_area: {}, disp_status: 'Write', frm: dialog ? null : { doctype } });
    state.showDialog = () => state.events.forEach(({ handler }) => handler());
    return state;
}

for (const doctype of ['Project', 'Task']) {
    test(`${doctype} form and child tables finish rendering before cold map assets load`, async () => {
        const state = screen({ doctype });
        const grid = {};
        assert.doesNotThrow(() => {
            state.control.set_disp_area(point(doctype));
            // Frappe creates grid pagination when the subsequent table renders.
            grid.grid_pagination = { go_to_page(page) { this.page = page; } };
        });
        grid.grid_pagination.go_to_page(1);
        assert.equal(grid.grid_pagination.page, 1);
        assert.equal(state.maps.length, 0);
        assert.deepEqual(state.requests, ['leaflet.bundle.js', 'leaflet.bundle.css']);

        state.js.resolve();
        await flush();
        assert.equal(state.maps.length, 0, 'wait for the stylesheet as well as the map plugins');
        state.css.resolve();
        await flush();
        assert.equal(state.maps.length, 1);
        assert.equal(state.geojson.at(-1).features[0].properties.name, doctype);
        assert.equal(state.control.editableLayers.layers.length, 1);
        assert.ok(state.control.draw_control);
        assert.ok(state.control.locate_control);
        assert.match(state.layers[0].overlays.Rail._url, /openrailwaymap/);
        assert.deepEqual(Array.from(state.maps[0].center), [-32.5279, 115.7189]);
    });
}

test('an existing Leaflet global still waits for the Frappe draw and locate bundle', async () => {
    const state = screen({ warm: true });
    delete state.context.L.Control.Draw;
    delete state.context.L.control.locate;
    assert.doesNotThrow(() => state.control.set_disp_area(point('Cached')));
    assert.equal(state.maps.length, 0);
    state.js.resolve(); state.css.resolve();
    await flush();
    assert.ok(state.control.draw_control);
    assert.ok(state.control.locate_control);
});

test('document changes during asset loading render the latest location and clear blank locations', async () => {
    const state = screen();
    state.control.set_disp_area(point('Previous'));
    state.control.set_disp_area(point('Current'));
    state.js.resolve(); state.css.resolve();
    await flush();
    assert.equal(state.maps.length, 1);
    assert.ok(state.geojson.every(data => data.features[0].properties.name === 'Current'));
    state.control.set_disp_area('');
    await flush();
    assert.equal(state.control.editableLayers.layers.length, 0);
});

test('dialog refreshes keep one map handler and use the latest field value', async () => {
    const state = screen({ dialog: true });
    state.control.set_disp_area(point('Previous'));
    state.control.set_disp_area(point('Current'));
    assert.equal(state.maps.length, 0);
    assert.equal(state.events.length, 1);
    state.showDialog();
    assert.equal(state.maps.length, 0, 'opening the dialog waits for the assets');
    state.js.resolve(); state.css.resolve();
    await flush();
    assert.equal(state.maps.length, 1);
    assert.equal(state.geojson.at(-1).features[0].properties.name, 'Current');
});

test('failed map assets are reported without rejecting the form refresh and can be retried', async () => {
    const state = screen();
    state.control.set_disp_area(point('Retry'));
    state.js.reject(new Error('Synthetic map bundle failure'));
    state.css.resolve();
    await flush();
    assert.equal(state.maps.length, 0);
    assert.equal(state.errors.length, 1);
    assert.match(state.errors[0][1].message, /Synthetic map bundle failure/);
    state.js = deferred();
    state.control.set_disp_area(point('Retry'));
    state.js.resolve();
    await flush();
    assert.equal(state.maps.length, 1);
});
