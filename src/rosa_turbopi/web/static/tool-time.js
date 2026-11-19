// Only running calls carry a start timestamp. Completed durations remain server values.
function updateToolTimes() {
  const now = Date.now();
  for (const element of document.querySelectorAll('.tool-elapsed[data-started-at]')) {
    const started = Date.parse(element.dataset.startedAt);
    if (Number.isFinite(started)) {
      element.textContent = (Math.max(0, now - started) / 1000).toFixed(1) + 's';
    }
  }
}
updateToolTimes();
setInterval(updateToolTimes, 100);
document.addEventListener('htmx:afterSwap', updateToolTimes);
document.addEventListener('visibilitychange', updateToolTimes);
