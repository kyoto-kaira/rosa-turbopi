const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
test('running duration advances, survives swaps, and leaves completed duration unchanged', () => {
  let now = Date.parse('2026-11-16T00:00:05Z');
  const startedAt = '2026-11-16T00:00:00Z';
  let running = {dataset: {startedAt}, textContent: '0s'};
  const completed = {textContent: '1.23s'};
  let tick;
  const handlers = {};
  const context = {
    Date: {now: () => now, parse: Date.parse},
    document: {
      querySelectorAll(selector) {
        assert.equal(selector, '.tool-elapsed[data-started-at]');
        return running ? [running] : [];
      },
      addEventListener: (name, fn) => { handlers[name] = fn; },
    },
    setInterval(fn, delay) { tick = fn; assert.equal(delay, 100); },
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('src/rosa_turbopi/web/static/tool-time.js', 'utf8'), context);
  assert.equal(running.textContent, '5.0s');
  now += 1500;
  tick();
  assert.equal(running.textContent, '6.5s');
  running = {dataset: {startedAt}, textContent: '0s'};
  handlers['htmx:afterSwap']();
  assert.equal(running.textContent, '6.5s');
  running = null;
  now += 5000;
  tick();
  assert.equal(completed.textContent, '1.23s');
});
