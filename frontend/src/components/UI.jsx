// Shared UI Components for BBC File
import React, { useEffect, useState, Component } from 'react';
import { Button } from './ui/button';
import { Badge as ShadBadge } from './ui/badge';
import { Card as ShadCard } from './ui/card';
import { cn } from '../lib/utils';

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
    <ShadCard className="p-5" style={style}>
      {children}
    </ShadCard>
  );
}

export function StatCard({ label, value, color, icon, trend, trendUp = true }) {
  const accentColor = color || 'var(--c-primary)';
  return (
    <div className="relative overflow-hidden rounded-xl border bg-card p-[18px] flex-1">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ background: `linear-gradient(135deg, ${accentColor}15 0%, transparent 65%)` }}
      />
      {trend && (
        <div className={cn(
          'absolute top-3.5 right-3.5 rounded-full px-2 py-0.5 text-[11px] font-bold',
          trendUp ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        )}>
          {trend}
        </div>
      )}
      {icon && (
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sm mb-3 relative"
          style={{ background: `${accentColor}18` }}
        >
          {icon}
        </div>
      )}
      <div
        className="text-2xl font-bold tracking-tight leading-none mb-1 relative"
        style={{ color: accentColor }}
      >
        {value}
      </div>
      <div className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wide relative">
        {label}
      </div>
    </div>
  );
}

export function Badge({ label, color, bg }) {
  return (
    <ShadBadge
      variant="outline"
      style={{
        color,
        backgroundColor: bg,
        borderColor: color ? `${color}44` : undefined,
      }}
    >
      {label}
    </ShadBadge>
  );
}

export function Btn({ children, onClick, variant = 'primary', size = 'md', disabled, style }) {
  const variantMap = {
    primary:   'default',
    secondary: 'outline',
    accent:    'default',
    danger:    'destructive',
    success:   'outline',
    warning:   'outline',
  };
  const sizeMap = { sm: 'sm', md: 'default' };
  return (
    <Button
      onClick={onClick}
      disabled={disabled}
      variant={variantMap[variant] || 'default'}
      size={sizeMap[size] || 'default'}
      style={style}
      className={cn(
        variant === 'accent' && 'bg-[var(--c-accent)] hover:bg-[var(--c-accent)]/90 text-white',
        variant === 'success' && 'text-[var(--c-green)] border-[var(--c-green)] hover:bg-[var(--c-green-bg)]',
        variant === 'warning' && 'text-[var(--c-amber)] border-[var(--c-amber)] hover:bg-[var(--c-amber-bg)]',
      )}
    >
      {children}
    </Button>
  );
}

export function Input({ label, value, onChange, placeholder, type='text', style }) {
  const uid = label ? `ui-input-${label.replace(/\s+/g,'-').toLowerCase()}` : undefined;
  return (
    <div style={{ marginBottom: 12, ...style }}>
      {label && <label htmlFor={uid} style={{ display:'block', fontSize:11, color:C.text2, fontWeight:600, marginBottom:5, textTransform:'uppercase', letterSpacing:'.7px' }}>{label}</label>}
      <input id={uid} type={type} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}
        className="ui-input"
        style={{ width:'100%', padding:'11px 14px', border:`1.5px solid ${C.border}`,
          borderRadius:10, fontSize:14, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface,
          transition:'border-color .18s, box-shadow .18s' }} />
    </div>
  );
}

export function Select({ label, value, onChange, options = [], style }) {
  const uid = label ? `ui-select-${label.replace(/\s+/g,'-').toLowerCase()}` : undefined;
  return (
    <div style={{ marginBottom: 12, ...style }}>
      {label && <label htmlFor={uid} style={{ display:'block', fontSize:11, color:C.text2, fontWeight:600, marginBottom:5, textTransform:'uppercase', letterSpacing:'.7px' }}>{label}</label>}
      <select id={uid} value={value} onChange={e=>onChange(e.target.value)}
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
  const configs = {
    'ACTIVO':            { cls: 'bg-green-50 text-green-700 border-green-200',   dot: true },
    'RETIRADO':          { cls: 'bg-red-50 text-red-700 border-red-200' },
    'SUSPENDIDO':        { cls: 'bg-amber-50 text-amber-700 border-amber-200' },
    'HOY':               { cls: 'bg-green-50 text-green-700 border-green-200' },
    'VENCIDO':           { cls: 'bg-red-50 text-red-700 border-red-200' },
    'PROXIMO':           { cls: 'bg-gray-50 text-gray-500 border-gray-200' },
    'COBRADO':           { cls: 'bg-blue-50 text-blue-700 border-blue-200' },
    'pagado':            { cls: 'bg-green-50 text-green-700 border-green-200' },
    'pendiente':         { cls: 'bg-amber-50 text-amber-700 border-amber-200' },
    'DOBLE_AFILIACION':  { cls: 'bg-purple-50 text-purple-700 border-purple-200' },
    'NO_ENCONTRADO':     { cls: 'bg-gray-50 text-gray-500 border-gray-200' },
    'EN_ESPERA':         { cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  };
  const key = Object.keys(configs).find(k =>
    (estado || '').toUpperCase().includes(k.toUpperCase())
  ) || '';
  const { cls = 'bg-gray-50 text-gray-500 border-gray-200', dot } = configs[key] || {};
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-medium border',
      cls
    )}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {estado}
    </span>
  );
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
