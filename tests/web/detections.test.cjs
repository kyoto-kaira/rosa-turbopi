const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/rosa_turbopi/web/static/detections.js', 'utf8');
function setup() {
  const handlers = {}, modes = [];
  const details = {
    open: false, isConnected: true,
    matches: () => true,
    closest: () => ({dataset: {callId: 'call-1'}}),
  };
  const context = {
    document: {
      querySelectorAll: () => [details],
      addEventListener(name, fn) { handlers[name] = fn; },
      dispatchEvent(event) { modes.push(event.detail.mode); },
    },
    CustomEvent: class { constructor(name, options) { this.detail = options.detail; } },
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  return {handlers, modes, details};
}
test('timeline updates preserve open details without preview controls', () => {
  const {handlers: h, modes, details} = setup();
  assert.equal(h.click, undefined);
  details.open = true;
  h.toggle({target: details});
  details.open = false;
  h['htmx:afterSwap']();
  assert.equal(details.open, true);
  h.conversationReset();
  details.open = false;
  h['htmx:afterSwap']();
  assert.equal(details.open, false);
  assert.deepEqual(modes, []);
});
