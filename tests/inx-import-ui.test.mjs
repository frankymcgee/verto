import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { test } from 'node:test';

const script = readFileSync(new URL('../verto/public/js/inx_incident_import.js', import.meta.url), 'utf8');

function screen() {
    const calls = [], dialogs = [], buttons = [];
    let upload;
    const preview = {
        row_count: 190, new_sources: 190, changed_sources: 0, unchanged_sources: 0,
        new_lessons: 190, enabled_lessons_returning_to_review: 0, missing_review_summaries: 190,
        file_sha256: 'synthetic-preview-hash', ignored_columns: ['Reported By Name'],
    };
    const frappe = {
        provide() {},
        utils: { escape_html: value => String(value).replaceAll('<', '&lt;') },
        ui: {
            FileUploader: class { constructor(options) { upload = options; } },
            Dialog: class {
                constructor(options) { this.options = options; dialogs.push(this); }
                show() {}
                hide() { this.hidden = true; }
                get_primary_btn() { return { prop: (key, value) => buttons.push([key, value]) }; }
                get_value(field) { return this.options.fields.find(item => item.fieldname === field)?.default; }
            },
        },
        call: async options => { calls.push(options); return { message: preview }; },
        msgprint() {},
    };
    const context = vm.createContext({ frappe, verto: { inx_incidents: {} }, __: value => value });
    vm.runInContext(script, context);
    context.verto.inx_incidents.open_import();
    return { frappe, calls, dialogs, buttons, upload, preview, context };
}

test('upload is private and a preview never imports incident rows', async () => {
    const state = screen();
    assert.equal(state.upload.make_attachments_public, false);
    assert.equal(state.upload.allow_toggle_private, false);
    assert.equal(state.upload.allow_web_link, false);
    assert.equal(state.upload.allow_multiple, false);
    await state.upload.on_success({ name: 'FILE-TEST' });
    assert.equal(state.calls.length, 1);
    assert.equal(state.calls[0].args.dry_run, true);
    assert.match(state.dialogs[0].options.fields[0].options, /investigation actions and controls are left blank/i);
    assert.match(state.dialogs[0].options.fields[0].options, /190/);
});

test('explicit import uses the preview hash and prevents a double click', async () => {
    const state = screen();
    await state.upload.on_success({ name: 'FILE-TEST' });
    await state.dialogs[0].options.primary_action();
    assert.equal(state.calls.length, 2);
    assert.equal(state.calls[1].args.dry_run, false);
    assert.equal(state.calls[1].args.expected_sha256, state.preview.file_sha256);
    assert.equal(state.calls[1].args.prepare_drafts, true);
    assert.match(state.dialogs[0].options.fields[1].description, /OpenAI account/);
    assert.deepEqual(state.buttons, [['disabled', true], ['disabled', false]]);
    assert.equal(state.dialogs[0].hidden, true);
});

test('sanitisation can be disabled on an import without skipping the import', async () => {
    const state = screen();
    await state.upload.on_success({ name: 'FILE-TEST' });
    state.dialogs[0].get_value = () => 0;
    await state.dialogs[0].options.primary_action();
    assert.equal(state.calls[1].args.prepare_drafts, false);
    assert.equal(state.calls[1].args.dry_run, false);
});

test('existing drafts can be queued with identifiers only and clear review guidance', async () => {
    const state = screen();
    state.context.verto.inx_incidents.prepare_drafts(['DRAFT-TEST']);
    const dialog = state.dialogs[0];
    assert.match(dialog.options.fields[0].options, /Detailed Observation/);
    assert.match(dialog.options.fields[0].options, /OpenAI account/);
    await dialog.options.primary_action();
    assert.equal(state.calls[0].method, 'verto.api.inx_incident_sanitisation.prepare_inx_drafts');
    assert.deepEqual(Array.from(state.calls[0].args.names), ['DRAFT-TEST']);
    assert.equal(dialog.hidden, true);
});

test('a failed import remains open and allows retry', async () => {
    const state = screen();
    await state.upload.on_success({ name: 'FILE-TEST' });
    state.frappe.call = async () => { throw new Error('Synthetic server error'); };
    await assert.rejects(state.dialogs[0].options.primary_action(), /Synthetic server error/);
    assert.equal(state.dialogs[0].hidden, undefined);
    assert.deepEqual(state.buttons.at(-1), ['disabled', false]);
});
