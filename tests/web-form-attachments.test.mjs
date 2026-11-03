import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../verto/public/js/field_interaction_attachments.js', import.meta.url), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

class Element {
    constructor(tag) { this.tagName = tag; this.children = []; this.events = {}; this.style = {}; this.attributes = {}; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(event, handler) { this.events[event] = handler; }
    click() { return this.events.click?.(); }
}

function screen({ doctype = 'Field Interaction', isNew = true, doc = {}, options = {} } = {}) {
    const state = { requests: [], saves: [], messages: [], events: {}, ready: [], timers: [], reads: [], dirty: 0 };
    const parent = new Element('div');
    const form = {
        doc_type: doctype, is_new: isNew, doc, name: 'public-field-interaction',
        web_form_request_key: 'request-key',
        make_form_dirty() { state.dirty++; },
        events: { on(event, handler) { state.events[event] = handler; } },
        save(...args) {
            if (state.invalid) return false;
            state.saves.push({ doc: JSON.parse(JSON.stringify(this.doc)), args, context: this });
            return false;
        },
    };
    const frappe = {
        web_form: form,
        ready(callback) { state.ready.push(callback); },
        call(request) {
            state.requests.push(request);
            return Promise.resolve({ message: {
                max_files: 3, max_file_bytes: 16, max_total_bytes: 20,
                allowed_extensions: ['jpg', 'png', 'txt'], ...options,
            } });
        },
        msgprint(message) { state.messages.push(message); },
    };
    class Reader {
        readAsDataURL(file) {
            const complete = () => {
                if (file.fail) { this.onerror(); return; }
                this.result = `data:${file.type || 'text/plain'};base64,${file.content || 'YQ=='}`;
                this.onload();
            };
            if (file.deferred) state.reads.push(complete);
            else complete();
        }
    }
    const context = vm.createContext({ frappe, document: {
        createElement: tag => new Element(tag), querySelector: () => parent,
    }, FileReader: Reader, window: {}, setTimeout: fn => state.timers.push(fn) });
    vm.runInContext(source, context);
    state.ready.forEach(fn => fn());
    state.timers.splice(0).forEach(fn => fn());
    state.form = form;
    state.parent = parent;
    state.picker = form._vertoAttachments;
    state.reloadScript = () => {
        const readyCount = state.ready.length;
        vm.runInContext(source, context);
        state.ready.slice(readyCount).forEach(fn => fn());
        state.timers.splice(0).forEach(fn => fn());
    };
    return state;
}

const file = (name, size = 4, extra = {}) => ({ name, size, type: 'text/plain', ...extra });

test('only new Field Interaction responses get the picker, including existing custom form scripts', async () => {
    for (const config of [{ doctype: 'User' }, { isNew: false }, { doc: { name: 'FI-EXISTING' } }]) {
        const state = screen(config);
        assert.equal(state.picker, undefined);
        assert.equal(state.requests.length, 0);
    }
    const state = screen();
    await flush();
    assert.equal(state.requests.length, 1);
    assert.equal(state.requests[0].args.web_form_request_key, 'request-key');
    assert.equal(state.picker.input.multiple, true);
    state.reloadScript();
    assert.equal(state.parent.children.length, 1);
    assert.equal(state.requests.length, 1);
});

test('selecting files keeps them local and normal save sends every file in one request', async () => {
    const state = screen();
    await flush();
    await state.picker.addFiles([file('one.txt'), file('two.png', 5, { type: 'image/png' })]);
    assert.equal(state.requests.length, 1, 'only the options request, with no uploads before submit');
    assert.equal(state.saves.length, 0);
    state.form.save('normal-save-argument');
    const saved = state.saves[0];
    assert.equal(saved.context, state.form);
    assert.deepEqual(saved.args, ['normal-save-argument']);
    assert.deepEqual(saved.doc._verto_attachments, [
        { file_name: 'one.txt', content: 'YQ==' }, { file_name: 'two.png', content: 'YQ==' },
    ]);
    assert.equal(state.picker.files.length, 2, 'retain the selection until success is confirmed');
});

test('removing a selected file excludes it from the eventual payload without server deletion', async () => {
    const state = screen();
    await flush();
    await state.picker.addFiles([file('one.txt'), file('two.txt')]);
    state.picker.list.children[0].children.at(-1).click();
    state.form.save();
    assert.deepEqual(state.saves[0].doc._verto_attachments.map(item => item.file_name), ['two.txt']);
    assert.equal(state.requests.length, 1);
});

test('failed form validation retains selections and successful save clears the payload', async () => {
    const state = screen();
    await flush();
    await state.picker.addFiles([file('one.txt')]);
    state.invalid = true;
    state.form.save();
    assert.equal(state.saves.length, 0);
    assert.equal(state.picker.files.length, 1);
    state.invalid = false;
    state.form.save();
    assert.equal(state.saves.length, 1);
    state.events.after_save();
    assert.equal(state.picker.files.length, 0);
    assert.equal(state.form.doc._verto_attachments, undefined);
});

test('saving waits for file reads and a read error preserves previous selections', async () => {
    const state = screen();
    await flush();
    await state.picker.addFiles([file('kept.txt')]);
    const pending = state.picker.addFiles([file('waiting.txt', 4, { deferred: true })]);
    state.form.save();
    assert.equal(state.saves.length, 0);
    assert.match(state.messages.at(-1), /wait/);
    state.reads[0]();
    await pending;
    await state.picker.addFiles([file('broken.txt', 4, { fail: true })]);
    assert.deepEqual(Array.from(state.picker.files, item => item.file_name), ['kept.txt', 'waiting.txt']);
    assert.equal(state.picker.pending, false);
});

test('count, file type, per-file and total size boundaries reject the new selection', async () => {
    for (const files of [[file('a.txt'), file('b.txt'), file('c.txt'), file('d.txt')],
        [file('payload.html')], [file('txt')], [file('empty.txt', 0)],
        [file('big.txt', 17)], [file('a.txt', 11), file('b.txt', 11)]]) {
        const state = screen();
        await flush();
        await state.picker.addFiles(files);
        assert.equal(state.picker.files.length, 0);
        assert.equal(state.messages.length, 1);
    }
});

test('filenames render as text and image previews do not enter the submission payload', async () => {
    const state = screen();
    await flush();
    await state.picker.addFiles([file('<img onerror=alert(1)>.png', 4, { type: 'image/png' })]);
    const row = state.picker.list.children[0];
    assert.equal(row.children[0].tagName, 'img');
    assert.match(row.children[1].textContent, /^<img onerror=alert\(1\)>\.png/);
    assert.equal(row.children[1].innerHTML, undefined);
    state.form.save();
    assert.deepEqual(Object.keys(state.saves[0].doc._verto_attachments[0]).sort(), ['content', 'file_name']);
});

test('a site allowing none of the supported extensions disables the picker and still permits form submission', async () => {
    const state = screen({ options: { allowed_extensions: [] } });
    await flush();
    assert.equal(state.picker.button.disabled, true);
    assert.match(state.picker.help.textContent, /unavailable/);
    state.form.save();
    assert.equal(state.saves.length, 1);
    assert.equal(state.saves[0].doc._verto_attachments, undefined);
});
