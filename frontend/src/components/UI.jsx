// Componentes de interfaz compartidos — Validum
import React, { useEffect, useState, Component } from 'react';
import { Button } from './ui/button';
import { Card as ShadCard } from './ui/card';
import { cn } from '../lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

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

export function StatCard({ label, value, color, icon, trend, trendUp = true, clickHint, style }) {
  const accentColor = color || 'var(--c-primary)';
  return (
    <div
      className="bbc-stat-card relative overflow-hidden rounded-xl border bg-card p-[18px] flex-1 min-w-[130px]"
      style={{ '--stat-accent': accentColor, ...style }}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ background: `linear-gradient(135deg, ${accentColor}15 0%, transparent 65%)` }}
      />
      {clickHint && <div className="bbc-stat-hint">{clickHint}</div>}
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
          className="bbc-stat-icon w-8 h-8 rounded-lg flex items-center justify-center text-sm mb-3 relative"
          style={{ background: `${accentColor}18` }}
        >
          {icon}
        </div>
      )}
      <div
        className="bbc-stat-value text-2xl font-bold tracking-tight leading-none mb-1 relative"
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

export function Btn({ type = 'button', children, onClick, variant = 'primary', size = 'md', disabled, style, title }) {
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
      type={type}
      onClick={onClick}
      disabled={disabled}
      variant={variantMap[variant] || 'default'}
      size={sizeMap[size] || 'default'}
      style={style}
      title={title}
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

export function Modal({ open, onClose, title, children, width = 540 }) {
  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent style={{ maxWidth: width }} className="overflow-y-auto max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="font-bold tracking-tight">{title}</DialogTitle>
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  );
}

export function PageHeader({ title, subtitle, action, crumb }) {
  return (
    <div className="mb-6 pb-5 border-b border-border relative">
      <div className="absolute bottom-[-1px] left-0 w-12 h-0.5 bg-gradient-to-r from-[var(--c-primary)] to-[var(--c-accent)] rounded" />
      {crumb && (
        <div className="text-xs text-muted-foreground font-mono mb-1">{crumb}</div>
      )}
      <div className="flex items-end flex-wrap gap-2">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold tracking-tight text-foreground leading-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
        </div>
        {action && <div className="ml-auto shrink-0">{action}</div>}
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

export const fmt = (n) => {
  if (n == null) return '$ 0';
  const abs = Math.round(Math.abs(n)).toLocaleString('es-CO');
  return (n < 0 ? '-' : '') + '$ ' + abs;
};

export function ConfirmModal({ open, title, message, confirmLabel = 'Eliminar', variant = 'danger', onConfirm, onCancel }) {
  return (
    <Dialog open={open} onOpenChange={v => !v && onCancel()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
        <div className="flex justify-end gap-2 mt-2">
          <Btn variant="secondary" onClick={onCancel}>Cancelar</Btn>
          <Btn variant={variant} onClick={onConfirm}>{confirmLabel}</Btn>
        </div>
      </DialogContent>
    </Dialog>
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
  componentDidCatch(error) {
    import('@sentry/react').then(({ captureException }) => captureException(error)).catch(() => {});
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

export function ErrorMsg({ message = 'Error al cargar datos', onRetry }) {
  return (
    <div style={{ padding: 40, textAlign: 'center' }}>
      <p style={{ color: C.red, fontSize: 14, margin: '0 0 12px' }}>{message}</p>
      {onRetry && <Btn variant="secondary" size="sm" onClick={onRetry}>Reintentar</Btn>}
    </div>
  );
}

export function SkeletonRow({ cols = 5, height = 14 }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} style={{ padding: '10px 12px' }}>
          <div className="bbc-skeleton" style={{ height, width: i === 0 ? '60%' : i === cols - 1 ? '40%' : '80%' }} />
        </td>
      ))}
    </tr>
  );
}

export function SkeletonCard({ height = 80 }) {
  return <div className="bbc-skeleton" style={{ height, borderRadius: 10, width: '100%' }} />;
}
