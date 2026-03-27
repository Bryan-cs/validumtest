// Shared UI Components for BBC File
import React, { useEffect, useState, Component } from 'react';

export const C = {
  primary:  'var(--c-primary)',
  accent:   'var(--c-accent)',
  green:    'var(--c-green)',
  greenBg:  'var(--c-green-bg)',
  red:      'var(--c-red)',
  redBg:    'var(--c-red-bg)',
  amber:    'var(--c-amber)',
  amberBg:  'var(--c-amber-bg)',
  blue:     'var(--c-blue)',
  blueBg:   'var(--c-blue-bg)',
  text:     'var(--c-text)',
  text2:    'var(--c-text2)',
  border:   'var(--c-border)',
  surface:  'var(--c-surface)',
  surface2: 'var(--c-surface2)',
  bg:       'var(--c-bg)',
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
          borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface }} />
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
          color:C.text, background:C.surface }}>
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
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);
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

export function ConfirmModal({ open, title, message, confirmLabel = 'Eliminar', variant = 'danger', onConfirm, onCancel }) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onCancel]);
  if (!open) return null;
  return (
    <div onClick={onCancel} style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.45)',
      zIndex:2000, display:'flex', alignItems:'center', justifyContent:'center', padding:20 }}>
      <div onClick={e => e.stopPropagation()} style={{ background:C.surface, borderRadius:14,
        maxWidth:400, width:'100%', padding:28, boxShadow:'0 25px 80px rgba(0,0,0,.3)' }}>
        <h3 style={{ margin:'0 0 8px', color:C.text, fontSize:16, fontWeight:700 }}>{title}</h3>
        <p style={{ margin:'0 0 22px', color:C.text2, fontSize:14, lineHeight:1.5 }}>{message}</p>
        <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
          <Btn variant="secondary" onClick={onCancel}>Cancelar</Btn>
          <Btn variant={variant} onClick={onConfirm}>{confirmLabel}</Btn>
        </div>
      </div>
    </div>
  );
}

// ─── ERROR BOUNDARY ──────────────────────────────────────────────────────────
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>⚠</div>
        <h2 style={{ color: C.text, fontSize: 18, fontWeight: 700, margin: '0 0 8px' }}>
          Algo salió mal
        </h2>
        <p style={{ color: C.text2, fontSize: 14, margin: '0 0 20px' }}>
          Ocurrió un error inesperado en esta sección.
        </p>
        <Btn onClick={() => this.setState({ hasError: false, error: null })}>
          Reintentar
        </Btn>
      </div>
    );
  }
}

// ─── BANNER OFFLINE ──────────────────────────────────────────────────────────
export function OfflineBanner() {
  const [offline, setOffline] = useState(!navigator.onLine);
  useEffect(() => {
    const goOff = () => setOffline(true);
    const goOn  = () => setOffline(false);
    window.addEventListener('offline', goOff);
    window.addEventListener('online', goOn);
    return () => {
      window.removeEventListener('offline', goOff);
      window.removeEventListener('online', goOn);
    };
  }, []);
  if (!offline) return null;
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
      background: C.red, color: '#fff', textAlign: 'center',
      padding: '8px 16px', fontSize: 13, fontWeight: 600,
    }}>
      Sin conexión a internet — Los cambios no se guardarán hasta que vuelvas a conectarte
    </div>
  );
}

// ─── LOADING SPINNER ─────────────────────────────────────────────────────────
export function Loading({ text = 'Cargando...' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 40, color: C.text2, fontSize: 14 }}>
      <div style={{
        width: 20, height: 20, border: `2px solid ${C.border}`,
        borderTopColor: C.primary, borderRadius: '50%',
        animation: 'spin .6s linear infinite', marginRight: 10,
      }} />
      {text}
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

export function ErrorMsg({ message = 'Error al cargar datos', onRetry }) {
  return (
    <div style={{ padding: 40, textAlign: 'center' }}>
      <p style={{ color: C.red, fontSize: 14, margin: '0 0 12px' }}>{message}</p>
      {onRetry && <Btn variant="secondary" size="sm" onClick={onRetry}>Reintentar</Btn>}
    </div>
  );
}
