const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function setup() {
  const handlers = {}, requests = [];
  const doc = latest => ({
    querySelector: selector => selector === '.timeline-history' ? {dataset: {latestRunId: latest}} : null,
    querySelectorAll: () => [],
  });
  const document = {...doc('run-2'), addEventListener: (name, fn) => {handlers[name] = fn;},
    getElementById: () => ({addEventListener() {}, value: ''})};
  const context = {document, Intl, Date, Map, JSON, URL, location: {href: 'http://localhost/'},
    DOMParser: class {parseFromString(data) {return doc(data);}},
    htmx: {ajax: (...args) => requests.push(args)}};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('src/rosa_turbopi/web/static/app.js', 'utf8'), context);
  const click = id => handlers.click({target: {closest: () => ({dataset: {runId: id}})}});
  const update = latest => {
    const event = {detail: {data: latest}, prevented: false, preventDefault() {this.prevented = true;}};
    handlers['htmx:sseBeforeMessage'](event);
    return event;
  };
  return {handlers, requests, click, update};
}
test('older history stays selected until a new execution arrives', () => {
  const {click, update, requests} = setup();
  click('run-1');
  assert.equal(update('run-2').prevented, true);
  assert.equal(requests[0][1], '/runs/run-1');
  assert.equal(update('run-3').prevented, false);
  assert.equal(update('run-3').prevented, false);
  assert.equal(requests.length, 1);
});
test('returning to latest and resetting resume following updates', () => {
  const {click, update, handlers, requests} = setup();
  click('run-1');
  click('run-2');
  assert.equal(update('run-2').prevented, false);
  handlers.conversationReset();
  assert.equal(update('').prevented, false);
  assert.equal(update('new-run').prevented, false);
  assert.equal(requests.length, 0);
});
test('late history response cannot replace the new execution', () => {
  const {click, update, handlers} = setup();
  click('run-1');
  update('run-3');
  const event = {detail: {shouldSwap: true, xhr: {responseURL: 'http://localhost/runs/run-1', responseText: 'run-2'}}};
  handlers['htmx:beforeSwap'](event);
  assert.equal(event.detail.shouldSwap, false);
});
