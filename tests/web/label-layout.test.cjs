const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = {document: {querySelector: () => null}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('src/rosa_turbopi/web/static/label-layout.js', 'utf8'), context);
test('clustered labels stay within the image without overlapping', () => {
  const items = Array.from({length: 8}, () => ({x: 20, y: 20, right: 80, bottom: 80, width: 70, height: 20}));
  const boxes = context.placeLabels(items, 280, 210, 2);
  assert.equal(boxes.filter(Boolean).length, 8);
  boxes.forEach((box, i) => {
    assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= 280 && box.y + box.height <= 210);
    boxes.slice(0, i).forEach(other => assert.ok(
      box.x + box.width <= other.x || other.x + other.width <= box.x ||
      box.y + box.height <= other.y || other.y + other.height <= box.y));
  });
});
test('oversized and crowded labels fall back to the list', () => {
  assert.equal(context.placeLabels([{x:0, y:0, right:10, bottom:10, width:300, height:20}], 280, 210, 2)[0], null);
  const items = Array.from({length: 3}, () => ({x:0, y:0, right:10, bottom:10, width:100, height:100}));
  const boxes = context.placeLabels(items, 100, 100, 2);
  assert.equal(boxes.filter(Boolean).length, 1);
});
