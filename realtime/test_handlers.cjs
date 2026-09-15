const { test } = require('node:test');
const assert = require('node:assert/strict');
const handlers = require('./handlers.js');

function client(user = 'viewer@example.test', result = true) {
  const callbacks = new Map(), joins = [], leaves = [];
  let requests = 0;
  const socket = {
    user, connected: true,
    on(event, callback) { callbacks.set(event, callback); },
    join(room) { joins.push(room); }, leave(room) { leaves.push(room); },
    frappe_request(path) {
      requests++;
      assert.equal(path, '/api/method/verto.api.planner_realtime.can_subscribe');
      return Promise.resolve({ ok: true, json: async () => ({ message: result }) });
    },
  };
  handlers(socket);
  return { socket, callbacks, joins, leaves, requests: () => requests };
}

test('only an authenticated, permitted socket joins the fixed planner room', async () => {
  for (const [user, allowed] of [['Guest', true], ['viewer', false], ['viewer', true]]) {
    const c = client(user, allowed);
    let reply;
    await c.callbacks.get('verto:planner_subscribe')((value) => { reply = value; });
    assert.equal(reply.ok, user !== 'Guest' && allowed);
    assert.deepEqual(c.joins, reply.ok ? ['verto:planner'] : []);
    if (user === 'Guest') assert.equal(c.requests(), 0);
  }
});

test('duplicate subscriptions share the permission request', async () => {
  const c = client();
  const subscribe = c.callbacks.get('verto:planner_subscribe');
  await Promise.all([subscribe(() => {}), subscribe(() => {})]);
  assert.equal(c.requests(), 1);
});

test('unsubscribe or disconnect prevents a pending permission check from rejoining', async () => {
  for (const event of ['verto:planner_unsubscribe', 'disconnect']) {
    const c = client();
    let release;
    c.socket.frappe_request = () => new Promise((resolve) => { release = resolve; });
    const subscribing = c.callbacks.get('verto:planner_subscribe')(() => {});
    c.callbacks.get(event)();
    release({ ok: true, json: async () => ({ message: true }) });
    await subscribing;
    assert.deepEqual(c.joins, []);
  }
});

test('permission service failures never grant membership', async () => {
  const c = client();
  c.socket.frappe_request = async () => { throw new Error('unavailable'); };
  let result;
  await c.callbacks.get('verto:planner_subscribe')((value) => { result = value; });
  assert.equal(result.ok, false);
  assert.deepEqual(c.joins, []);
});
