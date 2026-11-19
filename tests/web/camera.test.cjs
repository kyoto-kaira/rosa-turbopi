const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/rosa_turbopi/web/static/camera.js', 'utf8');
function setup() {
  const context = {Uint8Array, TextEncoder, TextDecoder, document: {getElementById: () => null}};
  vm.createContext(context);
  vm.runInContext(source, context);
  return context;
}
test('mock page does not request camera or install reconnect handlers', () => {
  setup(); // No fetch/window supplied: any network attempt would fail.
});
test('multipart parser handles split headers/boundaries and closes reader', async () => {
  const context = setup();
  const bytes = new TextEncoder().encode(
    '--frame\r\nContent-Type: image/jpeg\r\n\r\nfirst\r\n' +
    '--frame\r\nContent-Type: image/jpeg\r\n\r\nsecond\r\n--frame--\r\n');
  for (const size of [1, 7, bytes.length]) {
    let offset = 0, cancelled = false, released = false;
    const frames = [];
    const body = {getReader: () => ({
      async read() {
        if (offset >= bytes.length) return {done: true};
        const value = bytes.slice(offset, offset + size);
        offset += size;
        return {done: false, value};
      },
      async cancel() { cancelled = true; },
      releaseLock() { released = true; },
    })};
    await assert.rejects(context.consumeMjpeg(body, 'frame', frame => {
      frames.push(new TextDecoder().decode(frame));
    }), /Camera stream ended/);
    assert.deepEqual(frames, ['first', 'second']);
    assert.ok(cancelled && released);
  }
});
test('failed stream shows unavailable, retries, and stops in hidden tabs', async () => {
  const elements = {};
  for (const id of ['camera-stream', 'camera-message', 'camera-status']) {
    elements[id] = {hidden: false, addEventListener() {}, removeAttribute() {}};
  }
  const handlers = {};
  const timers = new Map();
  let requests = 0, timerId = 0;
  const context = {
    Uint8Array, TextEncoder, TextDecoder, AbortController,
    document: {
      hidden: false,
      getElementById: id => elements[id],
      addEventListener: (name, fn) => { handlers[name] = fn; },
    },
    window: {addEventListener() {}},
    URL: {revokeObjectURL() {}},
    async fetch() { requests++; throw new Error('offline'); },
    setTimeout(fn, delay) { assert.equal(delay, 3000); timers.set(++timerId, fn); return timerId; },
    clearTimeout(id) { timers.delete(id); },
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests, 1);
  assert.equal(elements['camera-message'].textContent, '映像未接続');
  assert.equal(elements['camera-status'].textContent, '再接続待ち');
  assert.equal(timers.size, 1);
  context.document.hidden = true;
  handlers.visibilitychange();
  assert.equal(timers.size, 0);
  assert.equal(requests, 1);
  context.document.hidden = false;
  handlers.visibilitychange();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests, 2);
});
