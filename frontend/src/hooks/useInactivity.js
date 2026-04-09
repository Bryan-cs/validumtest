import { useEffect, useRef, useState, useCallback } from 'react';

const INACTIVITY_MS  = 15 * 60 * 1000;  // 15 minutos
const WARNING_MS     = 13 * 60 * 1000;  // aviso a los 13 min (2 min antes)
const EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click'];

/**
 * Cierra sesión automáticamente tras INACTIVITY_MS de inactividad.
 * Muestra aviso a los 13 min para que el usuario pueda extender la sesión.
 *
 * @param {Function} onLogout — función que ejecuta el logout real
 * @returns {{ showWarning, extender }} — estado del aviso y función para extender
 */
export default function useInactivity(onLogout) {
  const [showWarning, setShowWarning] = useState(false);
  const timerLogout  = useRef(null);
  const timerWarning = useRef(null);

  const reset = useCallback(() => {
    setShowWarning(false);
    clearTimeout(timerLogout.current);
    clearTimeout(timerWarning.current);

    timerWarning.current = setTimeout(() => {
      setShowWarning(true);
    }, WARNING_MS);

    timerLogout.current = setTimeout(() => {
      setShowWarning(false);
      onLogout();
    }, INACTIVITY_MS);
  }, [onLogout]);

  useEffect(() => {
    reset();
    EVENTS.forEach(e => window.addEventListener(e, reset, { passive: true }));
    return () => {
      clearTimeout(timerLogout.current);
      clearTimeout(timerWarning.current);
      EVENTS.forEach(e => window.removeEventListener(e, reset));
    };
  }, [reset]);

  const extender = useCallback(() => {
    reset();
  }, [reset]);

  return { showWarning, extender };
}
