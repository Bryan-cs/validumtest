/**
 * Audio compartido para notificaciones.
 *
 * AudioContext en navegadores modernos arranca en estado "suspended" y
 * solo se puede desbloquear durante un gesto de usuario (click / keydown).
 * Este módulo crea UN solo contexto, lo desbloquea en la primera
 * interacción del usuario, y lo reutiliza para todas las notificaciones.
 */

let _ctx = null;

function _unlock() {
  if (_ctx) return;
  try {
    _ctx = new (window.AudioContext || window.webkitAudioContext)();
    _ctx.resume();
  } catch (_) { /* navegador sin soporte */ }
  document.removeEventListener('click', _unlock, true);
  document.removeEventListener('keydown', _unlock, true);
}
document.addEventListener('click', _unlock, true);
document.addEventListener('keydown', _unlock, true);

/**
 * Reproduce un tono corto.  No lanza errores.
 * @param {number} freq      — frecuencia en Hz (default 1000)
 * @param {number} duration  — segundos (default 0.25)
 * @param {number} volume    — 0-1 (default 0.28)
 */
export function playBeep(freq = 1000, duration = 0.25, volume = 0.28) {
  try {
    if (!_ctx || _ctx.state !== 'running') return;
    const t   = _ctx.currentTime;
    const osc = _ctx.createOscillator();
    const g   = _ctx.createGain();
    osc.connect(g);
    g.connect(_ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq, t);
    g.gain.setValueAtTime(volume, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + duration);
    osc.start(t);
    osc.stop(t + duration);
  } catch (_) {}
}
