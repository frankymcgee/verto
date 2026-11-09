import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../verto/public/js/gantt_view.js', import.meta.url), 'utf8');

function screen({ canWrite = true, mode = 'Day', loadFailure = false } = {}) {
    const state = { charts: [], requests: [], routes: [], writes: [], messages: [], errors: [], saved: [], styles: [] };
    let finishLoading;

    function element(html = '') {
        return {
            0: {}, html, children: [], events: {}, length: 1,
            empty() { this.children = []; return this; },
            addClass() { return this; }, removeClass() { return this; },
            append(child) { this.children.push(child); return this; },
            prepend(child) { this.children.unshift(child); return this; },
            on(event, selector, handler) { this.events[event] = handler || selector; return this; },
            off(event) { delete this.events[event]; return this; },
            data() { return this.values; },
        };
    }
    const footer = element();
    const paging = element();
    paging.find = (selector) => {
        if (selector === '.level-left') return footer;
        if (selector === '.gantt-view-mode') return { length: footer.children.length };
        return element();
    };

    const $ = (value) => typeof value === 'string' ? element(value) : value;
    $.isFunction = (value) => typeof value === 'function';
    const modes = [{ name: 'Day' }, { name: 'Week' }, { name: 'Month' }];
    class Gantt {
        constructor(container, tasks, options) {
            this.container = container;
            this.tasks = tasks;
            this.options = { view_modes: modes, ...options };
            this.config = {};
            this.change_view_mode(options.view_mode);
            state.charts.push(this);
        }
        change_view_mode(value) {
            const selected = modes.find((entry) => entry.name === value);
            assert.ok(selected, 'Frappe v16 requires a view mode name');
            this.config.view_mode = selected;
            this.options.view_mode = selected.name;
            this.options.on_view_change(selected);
        }
    }
    const frappe = {
        views: { ListView: class {} },
        provide() {},
        require(paths, callback) {
            state.requests.push(...paths);
            finishLoading = () => {
                state.view.constructor.Gantt = loadFailure ? undefined : Gantt;
                callback();
            };
        },
        set_route: (...args) => state.routes.push(args),
        db: { set_value: (...args) => state.writes.push(args) },
        msgprint: (message) => state.messages.push(message),
    };
    state.context = vm.createContext({
        frappe, $, setTimeout, __: (value) => value,
        document: {
            getElementById: id => state.styles.find(style => style.id === id),
            createElement: tag => ({ tag }),
            head: { appendChild: style => state.styles.push(style) },
        },
        moment: (value) => ({ format: () => String(value), utc() { return this; } }),
        console: { error: (...args) => state.errors.push(args) },
    });
    vm.runInContext(source, state.context);
    state.view = new frappe.views.GanttView();
    Object.assign(state.view, {
        can_write: canWrite,
        view_user_settings: { gantt_view_mode: mode },
        calendar_settings: { field_map: { start: 'exp_start_date', end: 'exp_end_date', progress: 'progress' } },
        settings: {},
        data: [{ name: 'TASK-1', subject: 'Inspect equipment' }],
        tasks: [{ id: 'TASK-1', name: 'Inspect equipment', task: 'Inspect equipment', doctype: 'Task', _start: 'Nov 9', _end: 'Nov 10' }],
        $result: element(),
        $paging_area: paging,
        save_view_user_settings(settings) {
            state.saved.push(settings);
            Object.assign(this.view_user_settings, settings);
        },
    });
    state.view.load_lib = new Promise((resolve) => frappe.require(state.view.required_libs, resolve));
    state.finishLoading = () => finishLoading();
    state.render = async () => {
        const pending = state.view.render();
        state.finishLoading();
        await pending;
    };
    state.footer = footer;
    state.paging = paging;
    return state;
}

test('the standalone script registers its real library before loading other assets', () => {
    const state = screen();
    const Chart = state.view.constructor.Gantt;
    assert.equal(typeof Chart, 'function');
    assert.equal(Chart.VIEW_MODE.DAY.name, 'Day');
    assert.equal(state.context.Gantt, undefined);
    assert.deepEqual(state.requests, []);
});

test('the standalone script includes chart styles once across view refreshes', async () => {
    const state = screen();
    await state.render();
    await state.view.render();
    assert.equal(state.styles.length, 1);
    assert.equal(state.styles[0].id, 'verto-gantt-library-style');
    assert.match(state.styles[0].textContent, /\.gantt-container/);
    assert.match(state.styles[0].textContent, /\.popup-wrapper/);
    assert.match(state.styles[0].textContent, /\.verto-gantt-layout/);
    assert.doesNotMatch(state.styles[0].textContent, /@import/);
    assert.deepEqual(state.requests, []);
});

test('an existing Gantt style element receives updated standalone layout rules', async () => {
    const state = screen();
    const style = { id: 'verto-gantt-library-style', textContent: 'old chart styles' };
    state.styles.push(style);
    await state.render();
    assert.equal(state.styles.length, 1);
    assert.match(style.textContent, /\.verto-gantt-layout/);
});

test('custom Gantt waits for Desk setup and renders without requesting dependency URLs or a global Gantt', async () => {
    const state = screen();
    assert.deepEqual(state.requests, []);
    const pending = state.view.render();
    assert.equal(state.charts.length, 0);
    assert.equal(state.view.$result.children.length, 0);
    state.finishLoading();
    await pending;
    assert.equal(state.context.Gantt, undefined);
    assert.equal(state.charts.length, 1);
    assert.equal(state.view.$result.children.length, 1);
    const layout = state.view.$result.children[0];
    assert.match(layout.html, /verto-gantt-layout/);
    const [column, chart] = layout.children;
    assert.match(column.html, /gantt-task-column/);
    assert.match(column.children[1].html, /Inspect equipment/);
    assert.match(chart.html, /gantt-chart-container/);
    assert.equal(state.charts[0].container, chart[0]);
    const options = state.charts[0].options;
    assert.equal(options.upper_header_height + options.lower_header_height + 10, 60);
    assert.equal(options.bar_height + options.padding, 53);
    assert.equal(state.messages.length, 0);
});

test('v16 mode objects produce named buttons and persist a mode name that can be reopened', async () => {
    const state = screen({ mode: 'Week' });
    await state.render();
    const buttons = state.footer.children[0];
    assert.doesNotMatch(buttons, /\[object Object\]/);
    assert.match(buttons, /btn-info[\s\S]*?data-value="Week"/);
    assert.match(buttons, /data-value="Month"/);
    const button = { data: () => ({ value: 'Month' }), addClass() {} };
    state.paging.events.click({ currentTarget: button });
    await new Promise((resolve) => setTimeout(resolve, 10));
    assert.equal(state.view.gantt.config.view_mode.name, 'Month');
    assert.equal(state.saved.at(-1).gantt_view_mode, 'Month');
    await state.view.render();
    assert.equal(state.view.gantt.config.view_mode.name, 'Month');
    assert.equal(state.footer.children.length, 1, 'refresh keeps a single mode selector');
});

test('v16 popup callback keeps custom content and navigates to the clicked task', async () => {
    const state = screen();
    await state.render();
    const task = state.view.tasks[0];
    const options = state.view.gantt.options;
    assert.equal(typeof options.popup, 'function');
    assert.match(options.popup({ task }), /Inspect equipment/);
    state.view.settings.gantt_custom_popup_html = (item, doc) => `<strong>${item.id}: ${doc.subject}</strong>`;
    const popup = options.popup({ task });
    assert.match(popup, /<strong>TASK-1: Inspect equipment<\/strong>/);
    assert.match(popup, /data-doctype="Task"/);
    const [column, container] = state.view.$result.children[0].children;
    const click = container.events['click.verto-gantt'];
    click.call({ getAttribute: (key) => ({ 'data-doctype': 'Task', 'data-id': 'TASK-2' })[key] });
    assert.deepEqual(state.routes.at(-1), ['Form', 'Task', 'TASK-2']);
    column.children[1].events.click();
    assert.deepEqual(state.routes.at(-1), ['Form', 'Task', 'TASK-1']);
});

test('read-only users cannot move dates or change progress in the updated library', async () => {
    const state = screen({ canWrite: false });
    await state.render();
    const { options } = state.view.gantt;
    assert.equal(options.readonly, true);
    options.on_date_change(state.view.tasks[0], '2026-11-09', '2026-11-10');
    options.on_progress_change(state.view.tasks[0], 50);
    assert.equal(state.writes.length, 0);
});

test('writers retain mapped date and progress updates', async () => {
    const state = screen();
    await state.render();
    const { options } = state.view.gantt;
    assert.equal(options.readonly, false);
    options.on_date_change(state.view.tasks[0], '2026-11-09', '2026-11-10');
    options.on_progress_change(state.view.tasks[0], 50);
    assert.equal(state.writes[0][2].exp_start_date, '2026-11-09');
    assert.equal(state.writes[0][2].exp_end_date, '2026-11-10');
    assert.equal(state.writes[1][2].progress, 50);
});

test('missing Gantt export reports a load failure without an unhandled rejection', async () => {
    const state = screen({ loadFailure: true });
    await state.render();
    assert.equal(state.charts.length, 0);
    assert.equal(state.messages.length, 1);
    assert.equal(state.errors.length, 1);
    assert.match(state.errors[0][1].message, /library did not load/);
});

test('a rejected asset loader reports the failure without an unhandled rejection', async () => {
    const state = screen();
    state.view.load_lib = Promise.reject(new Error('Synthetic asset failure'));
    await state.view.render();
    assert.equal(state.messages.length, 1);
    assert.equal(state.charts.length, 0);
    assert.match(state.errors[0][1].message, /Synthetic asset failure/);
});
