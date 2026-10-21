let selectedRun = null;
const scrollPositions = new Map();
function panelKey(panel) {
  return panel.id === 'chat-history' ? 'chat' : `timeline:${panel.dataset.executionId}`;
}
function contentSnapshot() {
  return {
    chat: JSON.stringify([...document.querySelectorAll('#chat-history .message')].map(message =>
      [message.dataset.messageId, ...[...message.querySelectorAll('.message-body')].map(body => body.textContent)])),
    timeline: [...document.querySelectorAll('.timeline .tool')].map(tool => tool.textContent).join('\n'),
    run: document.querySelector('.timeline .scroll')?.dataset.executionId,
  };
}
let previousContent = contentSnapshot();
document.addEventListener('scroll', event => {
  if (event.target.matches?.('#chat-history, .timeline .scroll')) {
    scrollPositions.set(panelKey(event.target), event.target.scrollTop);
  }
}, true);
function formatRunTimes() {
  const formatter = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  });
  for (const time of document.querySelectorAll('.run-started-at')) {
    const date = new Date(time.dateTime);
    if (!Number.isNaN(date.getTime())) time.textContent = formatter.format(date);
  }
}
formatRunTimes();
document.addEventListener('click', event => {
  const button = event.target.closest('[data-run-id]');
  if (button) selectedRun = button.dataset.runId;
});
document.addEventListener('htmx:sseBeforeMessage', event => {
  if (selectedRun) {
    const doc = new DOMParser().parseFromString(event.detail.data, 'text/html');
    if (!doc.querySelector('[data-run-id]')) {
      selectedRun = null;
      return;
    }
    // A selected historical run stays visible; explicit actions still refresh it.
    if (selectedRun !== doc.querySelector('.history-link.selected')?.dataset.runId) {
      event.preventDefault();
      htmx.ajax('GET', '/runs/' + selectedRun, {target: '#workspace', swap: 'innerHTML'});
    }
  }
});
document.addEventListener('conversationReset', () => {
  selectedRun = null;
  document.getElementById('query').value = '';
});
document.addEventListener('htmx:afterSwap', event => {
  if (event.detail.target?.id === 'tools-content') {
    const dialog = document.getElementById('tools-dialog');
    if (!dialog.open) dialog.showModal();
    return;
  }
  const state = document.getElementById('execution-state');
  const busy = state?.dataset.busy === 'true';
  const connectionStatus = document.getElementById('connection-status');
  const connected = state?.dataset.connected === 'true';
  connectionStatus.textContent = connected ? '接続済み' : '未接続';
  connectionStatus.classList.toggle('connected', connected);
  document.getElementById('send').disabled = busy;
  document.getElementById('interrupt').disabled = !busy;
  document.getElementById('reset-conversation').disabled =
    busy || !document.querySelector('#chat-history .message');
  formatRunTimes();
  const current = contentSnapshot();
  const old = previousContent;
  previousContent = current;
  requestAnimationFrame(() => {
    const history = document.getElementById('chat-history');
    if (history) history.scrollTop = current.chat !== old.chat
      ? history.scrollHeight : (scrollPositions.get('chat') ?? 0);
    const timeline = document.querySelector('.timeline .scroll');
    if (timeline) {
      const key = panelKey(timeline);
      const choosingHistory = current.run !== old.run && selectedRun === current.run;
      const updated = current.run !== old.run || current.timeline !== old.timeline;
      timeline.scrollTop = updated && !choosingHistory
        ? timeline.scrollHeight : (scrollPositions.get(key) ?? 0);
    }
  });
});
document.addEventListener('htmx:afterRequest', event => {
  if (event.detail.elt.id === 'chat-form' && event.detail.successful) {
    selectedRun = null;
    document.getElementById('query').value = '';
  }
});

const toolsDialog = document.getElementById('tools-dialog');
document.getElementById('close-tools').addEventListener('click', () => toolsDialog.close());
toolsDialog.addEventListener('click', event => {
  if (event.target === toolsDialog) {
    const bounds = toolsDialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom) toolsDialog.close();
  }
});
toolsDialog.addEventListener('close', () => document.querySelector('.tools-toggle')?.focus());
