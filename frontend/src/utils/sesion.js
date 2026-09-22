/** Lee el access token guardado por Zustand, sin tocar la red. */

export function tokenDeSesion(raw) {
  if (!raw) return '';
  try {
    const token = JSON.parse(raw)?.state?.token;
    return typeof token === 'string' ? token : '';
  } catch {
    return '';
  }
}
