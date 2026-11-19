// Fit the camera column to the rendered image; give remaining space to the timeline.
{
  const panel = document.querySelector('.camera');
  const upper = document.querySelector('.upper');
  const image = document.getElementById('camera-stream');
  if (panel && upper) {
    const heading = panel.querySelector('h2');
    const footer = panel.querySelector('footer');
    function fitCamera() {
      const ratio = image?.naturalWidth && image.naturalHeight
        ? image.naturalWidth / image.naturalHeight : 4 / 3;
      const height = Math.max(0, panel.clientHeight - heading.offsetHeight - footer.offsetHeight);
      const width = Math.ceil(height * ratio + panel.offsetWidth - panel.clientWidth);
      const value = width + 'px';
      if (upper.style.getPropertyValue('--camera-width') !== value) {
        upper.style.setProperty('--camera-width', value);
      }
    }
    const observer = new ResizeObserver(fitCamera);
    for (const element of [panel, heading, footer]) observer.observe(element);
    image?.addEventListener('load', fitCamera);
    fitCamera();
  }
}
