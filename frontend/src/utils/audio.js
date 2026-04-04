// Contexto de audio compartido — se desbloquea con el primer gesto del usuario
let _ctx = null;

function _unlock() {
  if (_ctx) return;
  _ctx = new (window.AudioContext || window.webkitAudioContext)();
  _ctx.resume();
  document.removeEventListener('click', _unlock, true);
  document.removeEventListener('keydown', _unlock, true);
}
document.addEventListener('click', _unlock, true);
document.addEventListener('keydown', _unlock, true);

export function playBeep(freq = 1000, duration = 0.25, volume = 0.28) {
  if (!_ctx || _ctx.state !== 'running') return;
  try {
    const osc = _ctx.createOscillator();
    const gain = _ctx.createGain();
    osc.connect(gain);
    gain.connect(_ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq, _ctx.currentTime);
    gain.gain.setValueAtTime(volume, _ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, _ctx.currentTime + duration);
    osc.start(_ctx.currentTime);
    osc.stop(_ctx.currentTime + duration);
  } catch (_) {}
}
