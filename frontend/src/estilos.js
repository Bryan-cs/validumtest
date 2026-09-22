/** Medidas compartidas de los formularios. El color sigue viniendo de `C`. */

export function campo(C) {
  return {
    padding: '9px 12px',
    borderRadius: 8,
    border: `1px solid ${C.border}`,
    background: C.surface,
    fontSize: 13,
    color: C.text,
    outline: 'none',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
  };
}

export function celda(C) {
  return {
    padding: '8px 10px',
    fontSize: 13,
    color: C.text,
    verticalAlign: 'middle',
    borderBottom: `1px solid ${C.border}`,
    borderRight: `1px solid ${C.border}`,
    whiteSpace: 'nowrap',
  };
}
