(() => {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('query');
  const row = form?.querySelector('.input-row');
  if (!form || !input || !row) return;

  const button = document.createElement('button');
  button.type = 'button';
  button.id = 'voice-record';
  const microphoneIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>';
  const cancelIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
  button.innerHTML = microphoneIcon;
  button.setAttribute('aria-label', '音声入力を開始');
  button.title = '音声入力を開始';
  button.setAttribute('aria-pressed', 'false');
  const status = document.createElement('p');
  status.id = 'voice-status';
  status.setAttribute('role', 'status');
  button.setAttribute('aria-describedby', status.id);
  row.insertBefore(button, document.getElementById('send'));
  form.append(status);

  const formats = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm'];
  const mime = typeof MediaRecorder !== 'undefined'
    ? formats.find(type => MediaRecorder.isTypeSupported(type)) : null;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !mime) {
    button.disabled = true;
    status.textContent = '音声入力には、マイク対応ブラウザとHTTPSまたはlocalhost接続が必要です。';
    return;
  }

  let session = null;
  let revision = 0;
  input.addEventListener('input', () => revision++);
  const busy = () => document.getElementById('execution-state')?.dataset.busy === 'true';
  function refresh() {
    button.disabled = !session && busy();
    button.setAttribute('aria-pressed', String(session?.phase === 'recording'));
    const recording = session?.phase === 'recording';
    const label = recording ? '録音を終了' : session ? '音声入力をキャンセル' : '音声入力を開始';
    button.innerHTML = !session || recording ? microphoneIcon : cancelIcon;
    button.setAttribute('aria-label', label);
    button.title = label;
  }
  function release(s) {
    clearTimeout(s.timer);
    clearInterval(s.meter);
    s.stream?.getTracks().forEach(track => track.stop());
    if (s.context) void s.context.close().catch(() => {});
  }
  function cancel(message = '') {
    const s = session;
    session = null;
    if (s) {
      s.abort.abort();
      if (s.recorder?.state === 'recording') s.recorder.stop();
      release(s);
    }
    status.textContent = message;
    refresh();
  }
  function finish(s) {
    if (session !== s || s.phase !== 'recording') return;
    s.phase = 'transcribing';
    s.recorder.stop();
    release(s);
    status.textContent = '文字起こし中…';
    refresh();
  }
  async function upload(s) {
    if (session !== s) return;
    try {
      if (s.meter && !s.heard) throw new Error('音声を検出できませんでした。もう一度録音してください。');
      const blob = new Blob(s.chunks, {type: s.recorder.mimeType});
      s.chunks = [];
      if (!blob.size) throw new Error('録音データが空です。もう一度お試しください。');
      if (blob.size > 4 * 1024 * 1024) throw new Error('録音データが大きすぎます。短く録音してください。');
      s.timer = setTimeout(() => cancel('文字起こしがタイムアウトしました。再度お試しください。'), 50000);
      const response = await fetch('/voice/transcribe', {
        method: 'POST', headers: {'Content-Type': blob.type}, body: blob, signal: s.abort.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '文字起こしに失敗しました。');
      if (session !== s) return;
      if (revision !== s.revision || input.value !== s.original || busy()) {
        cancel('入力や実行状態が変わったため、認識結果を破棄しました。');
        return;
      }
      if (typeof data.text !== 'string' || !data.text.trim() || data.text.length > 4000) {
        throw new Error('有効な認識結果がありません。もう一度録音してください。');
      }
      input.value = data.text;
      input.dispatchEvent(new Event('input', {bubbles: true}));
      cancel('文字起こしが完了しました。内容を確認して送信してください。');
      input.focus();
    } catch (error) {
      if (session === s) cancel(error.name === 'AbortError' ? 'キャンセルしました。'
        : error.message === 'Failed to fetch' ? '通信に失敗しました。再度お試しください。' : error.message);
    }
  }
  button.addEventListener('click', async () => {
    if (session) {
      if (session.phase === 'recording') finish(session);
      else cancel('キャンセルしました。');
      return;
    }
    if (busy()) return;
    const s = {phase: 'requesting', abort: new AbortController(), chunks: [],
      revision, original: input.value};
    session = s;
    status.textContent = 'マイクの使用を許可してください。';
    refresh();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      if (session !== s) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      s.stream = stream;
      s.recorder = new MediaRecorder(stream, {mimeType: mime});
      // Local level check prevents obvious silent recordings from reaching the API.
      const Context = window.AudioContext || window.webkitAudioContext;
      if (Context) {
        s.context = new Context();
        const analyser = s.context.createAnalyser();
        s.context.createMediaStreamSource(stream).connect(analyser);
        const samples = new Float32Array(analyser.fftSize);
        s.meter = setInterval(() => {
          analyser.getFloatTimeDomainData(samples);
          if (Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length) > 0.008) s.heard = true;
        }, 100);
        void s.context.resume().catch(() => {});
      }
      let bytes = 0;
      s.recorder.ondataavailable = event => {
        if (session !== s) return;
        bytes += event.data.size;
        if (bytes > 4 * 1024 * 1024) {
          cancel('録音データが大きすぎます。短く録音してください。');
          return;
        }
        s.chunks.push(event.data);
      };
      s.recorder.onstop = () => void upload(s);
      s.recorder.onerror = () => { if (session === s) cancel('録音に失敗しました。再度お試しください。'); };
      s.recorder.start(250);
      s.phase = 'recording';
      s.timer = setTimeout(() => finish(s), 30000);
      status.textContent = '録音中… もう一度押すと終了します（最大30秒）。';
      refresh();
    } catch (error) {
      if (session === s) cancel(error.name === 'NotAllowedError'
        ? 'マイクの使用が許可されていません。ブラウザの設定を確認してください。'
        : 'マイクを開始できませんでした。接続とブラウザの設定を確認してください。');
    }
  });
  form.addEventListener('submit', () => cancel(), true);
  document.addEventListener('conversationReset', () => { revision++; cancel(); });
  document.addEventListener('htmx:afterSwap', () => {
    if (busy() && session) cancel('実行が開始されたため、音声入力を取り消しました。');
    refresh();
  });
  window.addEventListener('pagehide', () => cancel());
  refresh();
})();
