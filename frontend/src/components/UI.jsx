// Shared UI Components for BBC File

export const C = {
  primary:  '#0D3B6E',
  accent:   '#E89B2A',
  green:    '#15803D',
  greenBg:  '#DCFCE7',
  red:      '#B91C1C',
  redBg:    '#FEE2E2',
  amber:    '#B45309',
  amberBg:  '#FEF3C7',
  blue:     '#185FA5',
  blueBg:   '#E6F1FB',
  text:     '#1E293B',
  text2:    '#64748B',
  border:   '#E2E8F0',
  surface:  '#FFFFFF',
  surface2: '#F8FAFC',
  bg:       '#F0F4F8',
};

export function Card({ children, style }) {
  return (
    <div style={{ background: C.surface, borderRadius: 12, border: `1px solid ${C.border}`,
      padding: 20, ...style }}>
      {children}
    </div>
  );
}

export function StatCard({ label, value, color = C.primary }) {
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12,
      padding: '14px 18px', flex: 1 }}>
      <div style={{ borderTop: `3px solid ${color}`, marginBottom: 10, borderRadius: 2 }} />
      <div style={{ fontSize: 11, color: C.text2, fontWeight: 600, textTransform:'uppercase',
        letterSpacing:'0.05em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

export function Badge({ label, color = C.text2, bg = C.surface2 }) {
  return (
    <span style={{ background: bg, color, borderRadius: 12, padding: '2px 10px',
      fontSize: 11, fontWeight: 600, whiteSpace:'nowrap' }}>
      {label}
    </span>
  );
}

export function Btn({ children, onClick, variant='primary', size='md', disabled, style }) {
  const base = { border:'none', borderRadius:7, fontWeight:600, cursor: disabled?'not-allowed':'pointer',
    opacity: disabled?0.6:1, transition:'opacity .15s', ...style };
  const variants = {
    primary:   { background: C.primary, color: '#fff', padding: size==='sm'?'6px 14px':'9px 20px', fontSize: size==='sm'?12:14 },
    secondary: { background: C.surface2, color: C.text, border:`1px solid ${C.border}`, padding: size==='sm'?'6px 14px':'9px 20px', fontSize: size==='sm'?12:14 },
    accent:    { background: C.accent, color: '#fff', padding: size==='sm'?'6px 14px':'9px 20px', fontSize: size==='sm'?12:14 },
    danger:    { background: C.redBg, color: C.red, border:`1px solid ${C.red}`, padding: size==='sm'?'6px 14px':'9px 20px', fontSize: size==='sm'?12:14 },
    success:   { background: C.greenBg, color: C.green, border:`1px solid ${C.green}`, padding: size==='sm'?'6px 14px':'9px 20px', fontSize: size==='sm'?12:14 },
  };
  return <button onClick={onClick} disabled={disabled} style={{ ...base, ...variants[variant] }}>{children}</button>;
}

export function Input({ label, value, onChange, placeholder, type='text', style }) {
  return (
    <div style={{ marginBottom: 12, ...style }}>
      {label && <label style={{ display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 }}>{label}</label>}
      <input type={type} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}
        style={{ width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`,
          borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text }} />
    </div>
  );
}

export function Select({ label, value, onChange, options = [], style }) {
  return (
    <div style={{ marginBottom: 12, ...style }}>
      {label && <label style={{ display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 }}>{label}</label>}
      <select value={value} onChange={e=>onChange(e.target.value)}
        style={{ width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`,
          borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box',
          color:C.text, background:'#fff' }}>
        {options.map(o => typeof o === 'string'
          ? <option key={o} value={o}>{o}</option>
          : <option key={o.value} value={o.value}>{o.label}</option>
        )}
      </select>
    </div>
  );
}

export function Table({ headers, rows, loading }) {
  const thStyle = { padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600,
    color: C.text2, background: C.surface2, borderBottom:`1px solid ${C.border}`,
    textTransform:'uppercase', letterSpacing:'0.05em', whiteSpace:'nowrap' };
  const tdStyle = { padding:'10px 12px', fontSize:13, color: C.text,
    borderBottom:`1px solid ${C.border}`, verticalAlign:'middle' };
  return (
    <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
      <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
        <thead>
          <tr>{headers.map((h,i)=><th key={i} style={thStyle}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {loading
            ? <tr><td colSpan={headers.length} style={{ ...tdStyle, textAlign:'center', color:C.text2 }}>Cargando...</td></tr>
            : rows.length === 0
            ? <tr><td colSpan={headers.length} style={{ ...tdStyle, textAlign:'center', color:C.text2 }}>Sin registros</td></tr>
            : rows}
        </tbody>
      </table>
    </div>
  );
}

export function Modal({ open, onClose, title, children, width=540 }) {
  if (!open) return null;
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.45)', zIndex:1000,
      display:'flex', alignItems:'center', justifyContent:'center', padding:20 }}>
      <div style={{ background:C.surface, borderRadius:14, width:'100%', maxWidth:width,
        maxHeight:'90vh', overflow:'auto', boxShadow:'0 25px 80px rgba(0,0,0,.3)' }}>
        <div style={{ display:'flex', alignItems:'center', padding:'18px 22px',
          borderBottom:`1px solid ${C.border}` }}>
          <h2 style={{ margin:0, fontSize:16, fontWeight:700, color:C.primary }}>{title}</h2>
          <button onClick={onClose} style={{ marginLeft:'auto', background:'none', border:'none',
            fontSize:20, cursor:'pointer', color:C.text2 }}>✕</button>
        </div>
        <div style={{ padding:22 }}>{children}</div>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div style={{ display:'flex', alignItems:'center', marginBottom:20 }}>
      <div>
        <h1 style={{ margin:0, fontSize:22, fontWeight:700, color:C.primary }}>{title}</h1>
        {subtitle && <p style={{ margin:'2px 0 0', fontSize:13, color:C.text2 }}>{subtitle}</p>}
      </div>
      {action && <div style={{ marginLeft:'auto' }}>{action}</div>}
    </div>
  );
}

export function statusBadge(estado) {
  const map = {
    'ACTIVO':   [C.green, C.greenBg],
    'RETIRADO': [C.red,   C.redBg],
    'SUSPENDIDO':[C.amber, C.amberBg],
    'HOY':      [C.green, C.greenBg],
    'VENCIDO':  [C.red,   C.redBg],
    'PROXIMO':  [C.text2, C.surface2],
    'COBRADO':  [C.blue,  C.blueBg],
    'pagado':   [C.green, C.greenBg],
    'pendiente':[C.amber, C.amberBg],
  };
  const key = Object.keys(map).find(k => (estado||'').toUpperCase().includes(k.toUpperCase())) || '';
  const [color, bg] = map[key] || [C.text2, C.surface2];
  return <Badge label={estado} color={color} bg={bg} />;
}

export const fmt = (n) => n == null ? '$ 0' : '$ ' + Math.round(n).toLocaleString('es-CO');
