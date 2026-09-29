import test from 'node:test';
import assert from 'node:assert/strict';
import { createWorkbook, normalizeWorkbook, duplicatePage, movePage, workbookKey, prepareScene } from '../verto/public/js/whiteboard/pages.js';
import { createSaveQueue } from '../verto/public/js/whiteboard/saveQueue.js';

test('legacy drawing becomes Page 1 without losing images, positions or settings', () => {
  const legacy = {type:'excalidraw', elements:[{id:'note', x:-200, y:40, width:1800, height:900, angle:0.4, version:1}], appState:{zoom:{value:1.5},scrollX:88},files:{image:{dataURL:'data:image/png;base64,test'}}};
  const result = normalizeWorkbook(JSON.stringify(legacy));
  assert.equal(result.pages.length, 1);
  assert.equal(result.pages[0].title, 'Page 1');
  assert.deepEqual(result.pages[0].scene, legacy);
  assert.ok(result.pages[0].bounds.x < -200);
  assert.ok(result.pages[0].bounds.width > 1800);
});

test('unsupported and corrupt saved data are not silently replaced by a blank board', () => {
  for (const invalid of [{type:'tldraw'}, '{broken', {type:'verto-whiteboard',version:1,pages:[]}]) {
    assert.throws(() => normalizeWorkbook(invalid));
  }
});

test('empty state creates a single independent page with a fixed frame', () => {
  const first = normalizeWorkbook(null), second = normalizeWorkbook('{}');
  assert.equal(first.pages.length, 1);
  assert.equal(first.activePageId, first.pages[0].id);
  assert.notEqual(first.pages[0].id, second.pages[0].id);
  assert.deepEqual(first.pages[0].bounds, {x:0,y:0,width:1600,height:900});
});

test('duplicating a page creates independent drawing/image state', () => {
  const page = createWorkbook().pages[0];
  page.scene.elements.push({id:'shape', version:1});
  page.scene.files.picture = {dataURL:'image'};
  const copy = duplicatePage(page);
  assert.notEqual(copy.id, page.id);
  copy.scene.elements[0].version = 9;
  copy.scene.files.picture.dataURL = 'different';
  assert.equal(page.scene.elements[0].version, 1);
  assert.equal(page.scene.files.picture.dataURL, 'image');
});

test('page reorder preserves content and rejects moves beyond either end', () => {
  const book = createWorkbook();
  const copy = duplicatePage(book.pages[0]);
  book.pages.push(copy);
  const moved = movePage(book, copy.id, -1);
  assert.equal(moved.pages[0].id, copy.id);
  assert.equal(moved.activePageId, book.activePageId);
  assert.equal(movePage(moved, copy.id, -1), moved);
  assert.equal(movePage(book, copy.id, 1), book);
});

test('saved identity includes page names, order, content and per-page viewports', () => {
  const book = createWorkbook(), key = workbookKey(book);
  const viewport = structuredClone(book);
  viewport.pages[0].scene.appState.zoom = {value:0.5};
  assert.notEqual(workbookKey(viewport), key);
  const renamed = structuredClone(book);
  renamed.pages[0].title = 'Office';
  assert.notEqual(workbookKey(renamed), key);
  const scene = prepareScene([], {zoom:{value:2}, collaborators:new Map(), selectedElementIds:{x:true},width:100,openMenu:'canvas'}, {});
  assert.deepEqual(scene.appState, {zoom:{value:2}});
});

test('failed save blocks switching and retains a retryable snapshot', async () => {
  let fail = true, saved;
  const queue = createSaveQueue(async value => {if(fail) throw Error('offline');saved=value;}, () => {});
  queue.baseline('old');
  queue.update('new', {pages:['A','B']});
  assert.equal(await queue.flush(), false);
  assert.equal(queue.isDirty(), true);
  fail = false;
  assert.equal(await queue.flush(), true);
  assert.equal(queue.isDirty(), false);
  assert.deepEqual(saved, {pages:['A','B']});
});

test('rapid edits are serialized so a slow older save cannot overwrite the next page', async () => {
  let finish;
  const pending = new Promise(resolve => {finish=resolve;});
  const saved=[];
  const queue=createSaveQueue(async value => {saved.push(value);if(saved.length===1) await pending;},()=>{});
  queue.baseline('old');queue.update('one',{page:'A'});
  const saving=queue.flush();
  queue.update('two',{page:'B'});
  assert.equal(queue.flush(), saving);
  finish();await saving;
  assert.deepEqual(saved,[{page:'A'},{page:'B'}]);
  assert.equal(queue.isDirty(),false);
});
