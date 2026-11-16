const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync('src/rosa_turbopi_voice/static/voice.js', 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return {promise, resolve};
}
function setup({permission, secure = true} = {}) {
  class Element {
    constructor() { this.listeners = {}; this.value = ''; this.dataset = {}; }
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
    dispatchEvent(event) { for (const fn of this.listeners[event.type] || []) fn(event); }
    setAttribute(name, value) { this[name] = value; }
    focus() {}
    append(element) { elements[element.id] = element; }
    insertBefore(element) { this.append(element); }
    querySelector() { return row; }
  }
  const elements = {};
  const row = new Element();
  for (const id of ['chat-form', 'query', 'send', 'execution-state']) elements[id] = new Element();
  const document = new Element();
  document.getElementById = id => elements[id];
  document.createElement = () => new Element();
  const window = new Element();
  window.isSecureContext = secure;
  const timers = new Map();
  let nextTimer = 1;
  const stream = {stopped: false, getTracks() { return [{stop: () => { stream.stopped = true; }}]; }};
  const requests = [];
  class Recorder {
    static isTypeSupported(type) { return type === 'audio/webm;codecs=opus'; }
    constructor(stream, {mimeType}) { this.mimeType = mimeType; }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      queueMicrotask(() => {
        this.ondataavailable({data: new Blob(['audio'])});
        this.onstop();
      });
    }
  }
  vm.runInNewContext(source, {
    document, window, navigator: {mediaDevices: {getUserMedia: () => permission?.promise || Promise.resolve(stream)}},
    MediaRecorder: Recorder, Blob, Event, AbortController,
    setTimeout: (fn, delay) => { const id = nextTimer++; timers.set(id, {fn, delay}); return id; },
    clearTimeout: id => timers.delete(id), clearInterval() {},
    fetch: (url, options) => {
      const pending = deferred();
      requests.push({url, options, ...pending});
      return pending.promise;
    },
  });
  return {
    elements, stream, requests, timers, document,
    click: async () => { elements['voice-record'].dispatchEvent({type: 'click'}); await tick(); },
    edit(value) { elements.query.value = value; elements.query.dispatchEvent({type: 'input'}); },
    reply: async (text = '1秒前進') => {
      requests.at(-1).resolve({ok: true, json: async () => ({text})}); await tick();
    },
  };
}

test('record -> transcription -> input, without submitting the form', async () => {
  const ui = setup();
  let submitted = false;
  ui.elements['chat-form'].addEventListener('submit', () => { submitted = true; });
  await ui.click();
  assert.equal(ui.elements['voice-record']['aria-pressed'], 'true');
  await ui.click();
  assert.equal(ui.stream.stopped, true);
  assert.equal(ui.requests[0].url, '/voice/transcribe');
  assert.equal(ui.requests[0].options.headers['Content-Type'], 'audio/webm;codecs=opus');
  await ui.reply();
  assert.equal(ui.elements.query.value, '1秒前進');
  assert.equal(submitted, false);
  assert.equal(ui.timers.size, 0);
});

test('late recognition preserves edits even after edit-and-undo', async () => {
  const ui = setup();
  await ui.click(); await ui.click();
  ui.edit('typed'); ui.edit('');
  await ui.reply();
  assert.equal(ui.elements.query.value, '');
  assert.match(ui.elements['voice-status'].textContent, /破棄/);
});

test('cancelled permission request releases a subsequently granted microphone', async () => {
  const permission = deferred();
  const ui = setup({permission});
  await ui.click(); await ui.click();
  permission.resolve(ui.stream); await tick();
  assert.equal(ui.stream.stopped, true);
  assert.equal(ui.requests.length, 0);
});

for (const event of ['submit', 'conversationReset', 'busy']) {
  test(`${event} discards late transcription`, async () => {
    const ui = setup();
    await ui.click(); await ui.click();
    if (event === 'submit') ui.elements['chat-form'].dispatchEvent({type: 'submit'});
    else if (event === 'busy') {
      ui.elements['execution-state'].dataset.busy = 'true';
      ui.document.dispatchEvent({type: 'htmx:afterSwap'});
    } else ui.document.dispatchEvent({type: event});
    assert.equal(ui.requests[0].options.signal.aborted, true);
    await ui.reply();
    assert.equal(ui.elements.query.value, '');
  });
}

test('30 second limit finishes recording and browser timeout cancels request', async () => {
  const ui = setup();
  await ui.click();
  [...ui.timers.values()].find(t => t.delay === 30000).fn(); await tick();
  assert.equal(ui.stream.stopped, true);
  [...ui.timers.values()].find(t => t.delay === 50000).fn();
  assert.equal(ui.requests[0].options.signal.aborted, true);
  assert.match(ui.elements['voice-status'].textContent, /タイムアウト/);
  await ui.reply();
  assert.equal(ui.elements.query.value, '');
});

test('insecure origin disables recording', () => {
  const ui = setup({secure: false});
  assert.equal(ui.elements['voice-record'].disabled, true);
});
