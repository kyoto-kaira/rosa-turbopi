// Parse multipart frames incrementally; both headers and boundaries may span chunks.
function byteIndex(data, needle, start = 0) {
  outer: for (let i = start; i <= data.length - needle.length; i++) {
    for (let j = 0; j < needle.length; j++) {
      if (data[i + j] !== needle[j]) continue outer;
    }
    return i;
  }
  return -1;
}
async function consumeMjpeg(body, boundary, onFrame) {
  const delimiter = new TextEncoder().encode('--' + boundary);
  const headerEnd = new Uint8Array([13, 10, 13, 10]);
  const reader = body.getReader();
  let buffer = new Uint8Array();
  try {
    while (true) {
      const {done, value} = await reader.read();
      if (done) throw new Error('Camera stream ended');
      if (buffer.length + value.length > 8 * 1024 * 1024) throw new Error('Camera frame too large');
      const joined = new Uint8Array(buffer.length + value.length);
      joined.set(buffer);
      joined.set(value, buffer.length);
      buffer = joined;
      let start = byteIndex(buffer, delimiter);
      while (start !== -1) {
        const next = byteIndex(buffer, delimiter, start + delimiter.length);
        if (next === -1) {
          buffer = buffer.slice(start);
          break;
        }
        const headers = byteIndex(buffer, headerEnd, start + delimiter.length);
        if (headers !== -1 && headers < next) {
          const type = new TextDecoder().decode(buffer.slice(start + delimiter.length, headers));
          if (!/content-type:\s*image\/jpeg/i.test(type)) throw new Error('Invalid camera frame');
          const end = buffer[next - 2] === 13 && buffer[next - 1] === 10 ? next - 2 : next;
          onFrame(buffer.slice(headers + headerEnd.length, end));
        }
        buffer = buffer.slice(next);
        start = 0;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

// Camera stays outside the SSE workspace so chat updates never restart its connection.
const cameraImage = document.getElementById('camera-stream');
if (cameraImage) {
  const message = document.getElementById('camera-message');
  const status = document.getElementById('camera-status');
  let controller;
  let retryTimer;
  let imageUrl;
  function disconnectCamera() {
    clearTimeout(retryTimer);
    controller?.abort();
    controller = null;
    cameraImage.removeAttribute('src');
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = null;
    cameraImage.hidden = true;
    message.hidden = false;
  }
  async function connectCamera() {
    disconnectCamera();
    if (document.hidden) return;
    const connection = new AbortController();
    controller = connection;
    message.textContent = status.textContent = '接続中';
    try {
      const response = await fetch('/camera/stream', {signal: connection.signal, cache: 'no-store'});
      const boundary = response.headers.get('content-type')?.match(/boundary\s*=\s*(?:"([^"]+)"|([^;\s]+))/i);
      if (!response.ok || !response.body || !boundary) throw new Error('Camera unavailable');
      await consumeMjpeg(response.body, boundary[1] || boundary[2], frame => {
        if (controller !== connection) return;
        const previous = imageUrl;
        imageUrl = URL.createObjectURL(new Blob([frame], {type: 'image/jpeg'}));
        cameraImage.src = imageUrl;
        if (previous) URL.revokeObjectURL(previous);
      });
    } catch (error) {
      if (controller !== connection || connection.signal.aborted) return;
      disconnectCamera();
      message.textContent = '映像未接続';
      status.textContent = '再接続待ち';
      retryTimer = setTimeout(connectCamera, 3000);
    }
  }
  cameraImage.addEventListener('load', () => {
    cameraImage.hidden = false;
    message.hidden = true;
    status.textContent = '配信中';
  });
  cameraImage.addEventListener('error', () => {
    disconnectCamera();
    message.textContent = '映像未接続';
    status.textContent = '再接続待ち';
    retryTimer = setTimeout(connectCamera, 3000);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) disconnectCamera();
    else connectCamera();
  });
  window.addEventListener('pagehide', disconnectCamera);
  window.addEventListener('pageshow', connectCamera);
  connectCamera();
}
