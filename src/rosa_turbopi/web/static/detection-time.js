for (const time of document.querySelectorAll('time[datetime]')) {
  time.textContent = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo', dateStyle: 'short', timeStyle: 'medium',
  }).format(new Date(time.dateTime));
}
