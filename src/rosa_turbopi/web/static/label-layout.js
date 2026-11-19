// Place measured labels without overlaps, preferring positions near their own box.
function placeLabels(items, width, height, gap) {
  const placed = [];
  return items.map(item => {
    if (item.width > width || item.height > height) return null;
    const clampX = x => Math.max(0, Math.min(width - item.width, x));
    const clampY = y => Math.max(0, Math.min(height - item.height, y));
    const xs = [item.x, item.right - item.width, 0, width - item.width];
    const ys = [item.y - item.height - gap, item.bottom + gap, item.y, 0, height - item.height];
    for (const box of placed) {
      xs.push(box.x - item.width - gap, box.x + box.width + gap);
      ys.push(box.y - item.height - gap, box.y + box.height + gap);
    }
    const candidates = xs.flatMap(x => ys.map(y => ({
      x: clampX(x), y: clampY(y), width: item.width, height: item.height,
    })));
    const distance = box => (box.x - item.x) ** 2 + (box.y - (item.y - item.height - gap)) ** 2;
    candidates.sort((a, b) => distance(a) - distance(b));
    const found = candidates.find(box => placed.every(other =>
      box.x + box.width + gap <= other.x || other.x + other.width + gap <= box.x ||
      box.y + box.height + gap <= other.y || other.y + other.height + gap <= box.y));
    if (found) placed.push(found);
    return found || null;
  });
}

const detectionSvg = document.querySelector('figure svg');
if (detectionSvg) {
  function arrangeLabels() {
    const {width, height} = detectionSvg.viewBox.baseVal;
    const overflow = document.querySelector('.label-overflow');
    overflow.replaceChildren();
    detectionSvg.querySelectorAll('.label-leader').forEach(line => line.remove());
    const groups = [...detectionSvg.querySelectorAll('g')].filter(g => g.querySelector(':scope > .bbox'));
    const items = groups.map(group => {
      const box = group.querySelector('.bbox');
      const annotation = group.querySelector('.annotation');
      annotation.style.display = '';
      const text = annotation.querySelector('text');
      const rect = annotation.querySelector('rect');
      const padding = parseFloat(getComputedStyle(text).fontSize) * 0.4;
      const labelWidth = text.getComputedTextLength() + padding * 2;
      rect.setAttribute('width', labelWidth);
      return {
        x: box.x.baseVal.value, y: box.y.baseVal.value,
        right: box.x.baseVal.value + box.width.baseVal.value,
        bottom: box.y.baseVal.value + box.height.baseVal.value,
        width: labelWidth, height: rect.height.baseVal.value,
      };
    });
    const positions = placeLabels(items, width, height, width / 140);
    groups.forEach((group, index) => {
      const annotation = group.querySelector('.annotation');
      const rect = annotation.querySelector('rect');
      const position = positions[index];
      if (!position) {
        annotation.style.display = 'none';
        const entry = document.createElement('li');
        entry.textContent = group.querySelector('title').textContent;
        entry.style.color = group.style.getPropertyValue('--bbox-color');
        overflow.append(entry);
        return;
      }
      annotation.setAttribute('transform', `translate(${position.x - rect.x.baseVal.value} ${position.y - rect.y.baseVal.value})`);
      const item = items[index];
      const anchorX = Math.max(item.x, Math.min(item.right, position.x + position.width / 2));
      const anchorY = Math.max(item.y, Math.min(item.bottom, position.y + position.height / 2));
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('class', 'label-leader');
      line.setAttribute('x1', anchorX);
      line.setAttribute('y1', anchorY);
      line.setAttribute('x2', Math.max(position.x, Math.min(position.x + position.width, anchorX)));
      line.setAttribute('y2', Math.max(position.y, Math.min(position.y + position.height, anchorY)));
      group.insertBefore(line, annotation);
    });
    overflow.hidden = !overflow.children.length;
  }
  arrangeLabels();
  document.fonts.ready.then(arrangeLabels);
}
