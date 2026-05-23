export function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) & 0xFFFFFFFF;
  return Math.abs(h);
}

export const EMPRESA_COLOR = {
  'carsecoop':  { bg: '#F3E8FF', color: '#7C3AED' },
  'protsecoop': { bg: '#FEF9C3', color: '#A16207' },
  'technova':   { bg: '#FEF3C7', color: '#D97706' },
  'techplanet': { bg: '#DCFCE7', color: '#16A34A' },
};

export const EMPRESA_PALETTE = [
  { bg: '#DBEAFE', color: '#1D4ED8' },
  { bg: '#FCE7F3', color: '#9D174D' },
  { bg: '#D1FAE5', color: '#065F46' },
  { bg: '#FEE2E2', color: '#991B1B' },
  { bg: '#EDE9FE', color: '#5B21B6' },
  { bg: '#FFF7ED', color: '#9A3412' },
  { bg: '#ECFEFF', color: '#155E75' },
  { bg: '#F0FDF4', color: '#166534' },
];

export const BANCO_COLOR = {
  'davivienda':  { bar: '#FF6B6B', badge: '#FEE2E2', text: '#991B1B' },
  'bancolombia': { bar: '#FBBF24', badge: '#FEF9C3', text: '#92400E' },
  'bogota':      { bar: '#60A5FA', badge: '#DBEAFE', text: '#1D4ED8' },
  'nequi':       { bar: '#A78BFA', badge: '#EDE9FE', text: '#5B21B6' },
  'daviplata':   { bar: '#F472B6', badge: '#FCE7F3', text: '#9D174D' },
  'bbva':        { bar: '#34D399', badge: '#D1FAE5', text: '#065F46' },
  'occidente':   { bar: '#FB923C', badge: '#FFF7ED', text: '#9A3412' },
  'popular':     { bar: '#22D3EE', badge: '#ECFEFF', text: '#155E75' },
};

export const BANCO_PALETTE = [
  { bar: '#60A5FA', badge: '#DBEAFE', text: '#1D4ED8' },
  { bar: '#34D399', badge: '#D1FAE5', text: '#065F46' },
  { bar: '#F472B6', badge: '#FCE7F3', text: '#9D174D' },
  { bar: '#FBBF24', badge: '#FEF9C3', text: '#92400E' },
  { bar: '#A78BFA', badge: '#EDE9FE', text: '#5B21B6' },
  { bar: '#FB923C', badge: '#FFF7ED', text: '#9A3412' },
  { bar: '#22D3EE', badge: '#ECFEFF', text: '#155E75' },
  { bar: '#FF6B6B', badge: '#FEE2E2', text: '#991B1B' },
];

export function empresaStyle(nombre = '') {
  if (!nombre) return null;
  const key = Object.keys(EMPRESA_COLOR).find(k => nombre.toLowerCase().includes(k));
  if (key) return EMPRESA_COLOR[key];
  return EMPRESA_PALETTE[hashStr(nombre.toLowerCase()) % EMPRESA_PALETTE.length];
}
