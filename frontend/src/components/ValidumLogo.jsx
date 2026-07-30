/* Marca Validum — "V" de dos brazos (navy + lima). Vectorial, escala sin pérdida.
   Colores oficiales de marca: navy #1D3F72 · lima #C8D72B. */

export function ValidumMark({ size = 40, navy = '#1D3F72', lime = '#C8D72B', style, className }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label="Validum"
         style={style} className={className}>
      {/* Brazo izquierdo navy: arriba-izquierda -> abajo-centro.
          Brazo derecho lima: arriba-derecha -> abajo-centro.
          Los signos de rotación estaban invertidos y los trazos se juntaban ARRIBA,
          dibujando una "Λ" en vez de la "V" de Validum (ver public/validum-logo.png). */}
      <rect x="-5.5" y="-20" width="11" height="40" rx="5.5" fill={navy}
            transform="translate(18,23.5) rotate(-17)" />
      <rect x="-5" y="-19" width="10" height="38" rx="5" fill={lime}
            transform="translate(30.5,24.5) rotate(19)" />
    </svg>
  );
}

/* Logotipo en recuadro (marca sobre fondo blanco redondeado) — para topbars/tiles. */
export function ValidumBadge({ size = 44, radius = 12, style }) {
  return (
    <span style={{
      width: size, height: size, borderRadius: radius, background: '#fff',
      display: 'grid', placeItems: 'center', flex: 'none',
      boxShadow: '0 2px 8px rgba(16,24,40,.12)', ...style,
    }}>
      <ValidumMark size={size * 0.66} />
    </span>
  );
}

export default ValidumMark;
