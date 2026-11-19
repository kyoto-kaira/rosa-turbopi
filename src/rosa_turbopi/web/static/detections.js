// Preserve expanded tool details across timeline updates.
{
  const openDetails = new Set();
  document.addEventListener('toggle', event => {
    const details = event.target;
    if (!details.matches?.('.tool details')) return;
    const id = details.closest('.tool').dataset.callId;
    if (details.open) openDetails.add(id);
    else if (details.isConnected) openDetails.delete(id);
  }, true);
  document.addEventListener('htmx:afterSwap', () => {
    for (const details of document.querySelectorAll('.tool details')) {
      if (openDetails.has(details.closest('.tool').dataset.callId)) details.open = true;
    }
  });
  document.addEventListener('conversationReset', () => {
    openDetails.clear();
  });
}
