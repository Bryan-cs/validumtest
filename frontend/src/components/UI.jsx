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

export function StatCard({ label, value, color = C.primary, icon, trend, trendUp = true }) {
  return (
    <div className="stat-card-lift" style={{
      background: C.surface, border: `1px solid ${C.border}`, borderRadius: 14,
      padding: '18px', flex: 1, position: 'relative', overflow: 'hidden', cursor: 'default',
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        background: `linear-gradient(135deg, ${color}15 0%, transparent 65%)`,
        pointerEvents: 'none',
      }} />
      {trend && (
        <div style={{
          position: 'absolute', top: 14, right: 14,
          background: trendUp ? C.greenBg : C.redBg,
          color: trendUp ? C.green : C.red,
          borderRadius: 100, padding: '2px 8px',
          fontSize: 11, fontWeight: 700,
        }}>{trend}</div>
      )}
      {icon && (
        <div style={{
          width: 34, height: 34, borderRadius: 9,
          background: `${color}18`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 15, marginBottom: 12, position: 'relative',
        }}>{icon}</div>
      )}
      <div style={{
        fontFamily: "'Syne', sans-serif",
        fontSize: 26, fontWeight: 800,
        letterSpacing: '-0.5px', lineHeight: 1,
        color, marginBottom: 4, position: 'relative',
      }}>{value}</div>
      <div style={{
        fontSize: 11, color: C.text2, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.06em',
        position: 'relative',
      }}>{label}</div>
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
  const p = size === 'sm' ? '6px 14px' : '9px 20px';
  const fs = size === 'sm' ? 12 : 14;
  const base = {
    border: 'none', borderRadius: 9, fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    fontFamily: 'inherit', display: 'inline-flex', alignItems: 'center', gap: 6,
    ...style,
  };
  const variants = {
    primary:   { background: C.primary, color: '#fff', padding: p, fontSize: fs, boxShadow: '0 1px 3px rgba(0,0,0,.12), 0 3px 8px rgba(0,0,0,.08)' },
    secondary: { background: C.surface2, color: C.text, border: `1.5px solid ${C.border}`, padding: p, fontSize: fs, boxShadow: '0 1px 2px rgba(0,0,0,.04)' },
    accent:    { background: C.accent, color: '#fff', padding: p, fontSize: fs, boxShadow: '0 1px 3px rgba(0,0,0,.12)' },
    danger:    { background: C.redBg, color: C.red, border: `1.5px solid ${C.red}44`, padding: p, fontSize: fs },
    success:   { background: C.greenBg, color: C.green, border: `1.5px solid ${C.green}44`, padding: p, fontSize: fs },
    warning:   { background: C.amberBg, color: C.amber, border: `1.5px solid ${C.amber}44`, padding: p, fontSize: fs },
  };
  return <button onClick={onClick} disabled={disabled} className="btn-lift" style={{ ...base, ...variants[variant] }}>{children}</button>;
}

export function Input({ label, value, onChange, placeholder, type='text', style }) {
  return (
    <div style={{ marginBottom: 12, ...style }}>
      {label && <label style={{ display:'block', fontSize:11, color:C.text2, fontWeight:600, marginBottom:5, textTransform:'uppercase', letterSpacing:'.7px' }}>{label}</label>}
      <input type={type} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}
        className="ui-input"
        style={{ width:'100%', padding:'11px 14px', border:`1.5px solid ${C.border}`,
          borderRadius:10, fontSize:14, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface,
          transition:'border-color .18s, box-shadow .18s' }} />
    </div>
  );
}

export function Select({ label, value, onChange, options = [], style }) {
  return (
    <div style={{ marginBottom: 12, ...style }}>
      {label && <label style={{ display:'block', fontSize:11, color:C.text2, fontWeight:600, marginBottom:5, textTransform:'uppercase', letterSpacing:'.7px' }}>{label}</label>}
      <select value={value} onChange={e=>onChange(e.target.value)}
        className="ui-input"
        style={{ width:'100%', padding:'11px 14px', border:`1.5px solid ${C.border}`,
          borderRadius:10, fontSize:14, outline:'none', boxSizing:'border-box',
          color:C.text, background:C.surface, transition:'border-color .18s, box-shadow .18s' }}>
        {options.map(o => typeof o === 'string'
          ? <option key={o} value={o}>{o}</option>
          : <option key={o.value} value={o.value}>{o.label}</option>
        )}
      </select>
    </div>
  );
}

export function Table({ headers, rows, loading }) {
  const thStyle = {
    padding:'12px 16px', textAlign:'left', fontSize:10.5, fontWeight:700,
    color: C.text2, background: C.surface, borderBottom:`2px solid ${C.border}`,
    textTransform:'uppercase', letterSpacing:'0.1em', whiteSpace:'nowrap',
  };
  const tdStyle = {
    padding:'13px 16px', fontSize:13.5, color: C.text,
    borderBottom:`1px solid ${C.border}`, verticalAlign:'middle',
    transition:'background .12s',
  };
  return (
    <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
      <table className="tbl" style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
        <thead>
          <tr>{headers.map((h,i)=><th key={i} style={{ ...thStyle, paddingLeft: i===0?20:undefined, paddingRight: i===headers.length-1?20:undefined }}>{h}</th>)}</tr>
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
      <div style={{ background:C.surface, borderRadius:16, width:'100%', maxWidth:width,
        maxHeight:'90vh', overflow:'auto', boxShadow:'0 32px 80px rgba(0,0,0,.25)', overflow:'hidden' }}>
        <div style={{ height:4, background:`linear-gradient(90deg, ${C.primary}, ${C.accent})` }} />
        <div style={{ display:'flex', alignItems:'center', padding:'18px 22px',
          borderBottom:`1px solid ${C.border}` }}>
          <h2 style={{ margin:0, fontFamily:"'Syne', sans-serif", fontSize:18, fontWeight:800, color:C.text, letterSpacing:'-.3px' }}>{title}</h2>
          <button onClick={onClose} style={{
            marginLeft:'auto', width:28, height:28, display:'flex', alignItems:'center', justifyContent:'center',
            background:C.surface2, border:`1px solid ${C.border}`, borderRadius:6,
            fontSize:14, cursor:'pointer', color:C.text2, flexShrink:0,
          }}>✕</button>
        </div>
        <div style={{ padding:22, overflowY:'auto', maxHeight:'calc(90vh - 110px)' }}>{children}</div>
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, action, crumb }) {
  return (
    <div style={{ marginBottom:24, paddingBottom:20, borderBottom:`1px solid ${C.border}`, position:'relative' }}>
      <div style={{ position:'absolute', bottom:-1, left:0, width:48, height:2, background:`linear-gradient(90deg, ${C.primary}, ${C.accent})`, borderRadius:2 }} />
      {crumb && (
        <div style={{ fontSize:11, color:C.text2, marginBottom:5, fontFamily:"'IBM Plex Mono', monospace" }}>{crumb}</div>
      )}
      <div style={{ display:'flex', alignItems:'flex-end' }}>
        <div>
          <h1 style={{ margin:0, fontFamily:"'Syne', sans-serif", fontSize:24, fontWeight:800, color:C.text, letterSpacing:'-.4px', lineHeight:1.1 }}>{title}</h1>
          {subtitle && <p style={{ margin:'3px 0 0', fontSize:13, color:C.text2, fontWeight:300 }}>{subtitle}</p>}
        </div>
        {action && <div style={{ marginLeft:'auto' }}>{action}</div>}
      </div>
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
      <div onClick={e => e.stopPropagation()} style={{ background:C.surface, borderRadius:16,
        maxWidth:400, width:'100%', boxShadow:'0 32px 80px rgba(0,0,0,.25)', overflow:'hidden' }}>
        <div style={{ height:4, background:`linear-gradient(90deg, ${C.primary}, ${C.accent})` }} />
        <div style={{ padding:'22px 24px 24px' }}>
          <h3 style={{ margin:'0 0 8px', color:C.text, fontFamily:"'Syne', sans-serif", fontSize:17, fontWeight:800, letterSpacing:'-.3px' }}>{title}</h3>
          <p style={{ margin:'0 0 22px', color:C.text2, fontSize:14, lineHeight:1.6 }}>{message}</p>
          <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
            <Btn variant="secondary" onClick={onCancel}>Cancelar</Btn>
            <Btn variant={variant} onClick={onConfirm}>{confirmLabel}</Btn>
          </div>
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
