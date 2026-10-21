let selectedRun = null;
let historyScroll = null;
document.addEventListener('click', event => {
  const button = event.target.closest('[data-run-id]');
  if (button) selectedRun = button.dataset.runId;
});
document.addEventListener('htmx:sseBeforeMessage', event => {
  if (selectedRun) {
    const doc = new DOMParser().parseFromString(event.detail.data, 'text/html');
    // A selected historical run stays visible; explicit actions still refresh it.
    if (selectedRun !== doc.querySelector('.query.selected')?.dataset.runId) {
      event.preventDefault();
      htmx.ajax('GET', '/runs/' + selectedRun, {target: '#workspace', swap: 'innerHTML'});
    }
  }
});
document.addEventListener('htmx:beforeSwap', () => {
  const history = document.getElementById('chat-history');
  if (history) historyScroll = history.scrollHeight - history.scrollTop - history.clientHeight < 40 ? null : history.scrollTop;
});
document.addEventListener('htmx:afterSwap', () => {
  const state = document.getElementById('execution-state');
  document.getElementById('send').disabled = state?.dataset.busy === 'true';
  const history = document.getElementById('chat-history');
  if (history) history.scrollTop = historyScroll ?? history.scrollHeight;
});
document.addEventListener('htmx:afterRequest', event => {
  if (event.detail.elt.id === 'chat-form' && event.detail.successful) {
    selectedRun = null;
    document.getElementById('query').value = '';
  }
});
