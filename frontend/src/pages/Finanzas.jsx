import React, { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { C, fmt, SkeletonCard } from '../components/UI';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Button } from '../components/ui/button';
import {
  TrendingUp, TrendingDown, DollarSign, Clock,
  Building2, X, ChevronLeft, ChevronRight,
  Landmark, BarChart3, FileText, PlusCircle,
  HeartPulse, Briefcase, Receipt, AlertCircle, RefreshCw,
} from 'lucide-react';
import {
  PieChart, Pie, Cell, Tooltip as ReTooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';

// ── Constantes ────────────────────────────────────────────────────────────────
const MESES = ['Todos','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear().toString();
const mesActual  = MESES[new Date().getMonth() + 1];
const PIE_COLORS = ['#6366f1','#22c55e','#f59e0b','#ef4444','#3b82f6','#8b5cf6','#ec4899','#14b8a6'];

const pctOf = (val, total) => total > 0 ? (val / total) * 100 : 0;

const margenVariant = (p) => {
  if (p >= 20) return { color: C.green, bg: C.greenBg };
  if (p >= 10) return { color: C.amber, bg: C.amberBg };
  return             { color: C.red,   bg: C.redBg   };
};

// ── Barra de progreso coloreada ───────────────────────────────────────────────
function ColorBar({ value, color, className = '' }) {
  return (
    <div className={`h-1.5 rounded-full overflow-hidden ${className}`}
      style={{ background: `${color}20` }}>
      <div className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min(100, Math.max(0, value))}%`, background: color }} />
    </div>
  );
}

// ── Fila de costo con barra visual ────────────────────────────────────────────
function CostRow({ label, icon: Icon, value, pct, color }) {
  return (
    <div className="flex items-center gap-3 py-2.5">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: `${color}15` }}>
        <Icon className="h-3.5 w-3.5" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-sm font-medium text-foreground">{label}</span>
          <span className="text-sm font-bold tabular-nums" style={{ color }}>
            {value > 0 ? `(${fmt(value)})` : fmt(value)}
          </span>
        </div>
        <ColorBar value={pct} color={color} />
      </div>
      <span className="text-xs text-muted-foreground w-10 text-right tabular-nums shrink-0">
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

// ── KPI Card izquierdo ────────────────────────────────────────────────────────
function KpiCard({ label, value, icon: Icon, color, sub }) {
  return (
    <Card className="relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none rounded-lg"
        style={{ background: `linear-gradient(135deg, ${color}12 0%, transparent 60%)` }} />
      <CardContent className="p-4">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-2.5"
          style={{ background: `${color}18` }}>
          <Icon className="h-4 w-4" style={{ color }} />
        </div>
        <div className="text-xl font-bold tracking-tight leading-none" style={{ color }}>{value}</div>
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mt-1">{label}</div>
        {sub && <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>}
      </CardContent>
    </Card>
  );
}

// ── Selector de período ───────────────────────────────────────────────────────
function PeriodSelector({ anio, mes, setAnio, setMes }) {
  const idx = MESES.indexOf(mes);
  const prev = () => {
    if (mes === 'Todos') return;
    if (idx === 1) { setAnio(a => String(+a - 1)); setMes('Diciembre'); }
    else setMes(MESES[idx - 1]);
  };
  const next = () => {
    if (mes === 'Todos') return;
    if (idx === 12) { setAnio(a => String(+a + 1)); setMes('Enero'); }
    else setMes(MESES[idx + 1]);
  };
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="icon" onClick={prev} disabled={mes === 'Todos'} className="h-8 w-8">
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <select value={anio} onChange={e => setAnio(e.target.value)}
        className="h-8 rounded-md border px-2 text-sm bg-card text-foreground">
        {['Todos', anioActual, String(+anioActual - 1)].map(a => <option key={a}>{a}</option>)}
      </select>
      <select value={mes} onChange={e => setMes(e.target.value)}
        className="h-8 rounded-md border px-2 text-sm bg-card text-foreground">
        {MESES.map(m => <option key={m}>{m}</option>)}
      </select>
      <Button variant="outline" size="icon" onClick={next} disabled={mes === 'Todos'} className="h-8 w-8">
        <ChevronRight className="h-4 w-4" />
      </Button>
      <Button variant="outline" size="sm" onClick={() => { setAnio(anioActual); setMes(mesActual); }} className="h-8">
        ↺ Hoy
      </Button>
    </div>
  );
}

// ── Gráfico bancos interactivo ────────────────────────────────────────────────
function BancoChart({ data, total }) {
  const [activeIdx, setActiveIdx] = useState(null);
  const selected = activeIdx !== null ? data[activeIdx] : null;

  return (
    <div className="flex gap-5 items-center">
      {/* Donut clickeable */}
      <div className="relative shrink-0" style={{ width: 180, height: 180 }}>
        <ResponsiveContainer width={180} height={180}>
          <PieChart>
            <Pie
              data={data} dataKey="total" nameKey="banco"
              cx="50%" cy="50%" innerRadius={54} outerRadius={78}
              paddingAngle={2}
              onClick={(_, idx) => setActiveIdx(activeIdx === idx ? null : idx)}
            >
              {data.map((_, i) => (
                <Cell key={i}
                  fill={PIE_COLORS[i % PIE_COLORS.length]}
                  opacity={activeIdx === null || activeIdx === i ? 1 : 0.25}
                  stroke={activeIdx === i ? '#fff' : 'transparent'}
                  strokeWidth={activeIdx === i ? 2.5 : 0}
                  style={{ cursor: 'pointer', transition: 'opacity .2s, stroke-width .15s' }}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Centro — muestra banco seleccionado o total */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none select-none">
          {selected ? (
            <>
              <span className="text-[10px] text-muted-foreground font-medium leading-tight text-center px-2 line-clamp-1">
                {selected.banco}
              </span>
              <span className="text-sm font-extrabold leading-tight tabular-nums"
                style={{ color: PIE_COLORS[activeIdx % PIE_COLORS.length] }}>
                {fmt(selected.total)}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {pctOf(selected.total, total).toFixed(1)}%
              </span>
            </>
          ) : (
            <>
              <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wider">Total</span>
              <span className="text-sm font-extrabold tabular-nums">{fmt(total)}</span>
              <span className="text-[10px] text-muted-foreground">100%</span>
            </>
          )}
        </div>
      </div>

      {/* Lista de bancos */}
      <div className="flex-1 flex flex-col gap-0.5">
        {data.map((b, i) => {
          const pct = pctOf(b.total, total);
          const color = PIE_COLORS[i % PIE_COLORS.length];
          const isActive = activeIdx === i;
          return (
            <div key={b.banco}
              onClick={() => setActiveIdx(activeIdx === i ? null : i)}
              className="flex flex-col gap-1 cursor-pointer rounded-lg px-2.5 py-2 transition-all duration-150"
              style={{ background: isActive ? `${color}12` : 'transparent',
                       border: isActive ? `1px solid ${color}30` : '1px solid transparent' }}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-2.5 h-2.5 rounded-full shrink-0 transition-transform duration-150"
                    style={{ background: color, transform: isActive ? 'scale(1.3)' : 'scale(1)' }} />
                  <span className="text-sm font-medium truncate">{b.banco}</span>
                </div>
                <span className="text-sm font-bold tabular-nums shrink-0" style={{ color }}>
                  {fmt(b.total)}
                </span>
              </div>
              <div className="flex items-center gap-2 pl-4">
                <ColorBar value={pct} color={color} className="flex-1" />
                <span className="text-xs text-muted-foreground tabular-nums w-9 text-right shrink-0">
                  {pct.toFixed(1)}%
                </span>
              </div>
            </div>
          );
        })}
        {data.length > 0 && (
          <p className="text-[10px] text-muted-foreground text-center mt-1">
            Clic en un banco para resaltar
          </p>
        )}
      </div>
    </div>
  );
}

function BarTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 shadow-md text-sm">
      <div className="font-semibold mb-1">{label}</div>
      {payload.map(p => (
        <div key={p.name} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.fill }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium">{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Modal cliente ─────────────────────────────────────────────────────────────
function ModalCliente({ cliente, onClose }) {
  const [anio, setAnio] = useState(anioActual);
  const [mes,  setMes]  = useState(mesActual);
  const ref = useRef(null);

  useEffect(() => {
    const fn = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [onClose]);

  const params = {};
  if (anio !== 'Todos') params.anio = anio;
  if (mes  !== 'Todos') params.mes  = mes;

  const { data: d, isLoading } = useQuery({
    queryKey: ['finanzas-cliente', cliente, anio, mes],
    queryFn: () => api.get(`/dashboard/cliente/${encodeURIComponent(cliente)}`, { params }).then(r => r.data),
    enabled: !!cliente,
    staleTime: 0,
  });

  const ing  = d?.ingresos  ?? 0;
  const cos  = d?.costos    ?? 0;
  const util = d?.utilidad  ?? 0;
  const histData = (d?.historial ?? []).map(h => ({
    name: `${h.mes.slice(0, 3)} ${h.anio}`,
    Ingresos: h.ingresos,
    'Aportes SS': h.costos,
  }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,.6)' }}
      onClick={e => { if (!ref.current?.contains(e.target)) onClose(); }}>
      <div ref={ref}
        className="bg-card border rounded-2xl w-full max-w-2xl flex flex-col shadow-2xl"
        style={{ maxHeight: '90vh', minHeight: 0 }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
          <div>
            <div className="text-xs text-muted-foreground font-mono mb-1">Cliente</div>
            <h2 className="text-xl font-bold tracking-tight">{cliente}</h2>
          </div>
          <div className="flex items-center gap-2">
            <PeriodSelector anio={anio} mes={mes} setAnio={setAnio} setMes={setMes} />
            <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="p-6 flex flex-col gap-5">
            {/* KPIs */}
            {isLoading
              ? <div className="grid grid-cols-3 gap-3">{[1,2,3].map(i=><SkeletonCard key={i} height={84}/>)}</div>
              : (
                <div className="grid grid-cols-3 gap-3">
                  <KpiCard label="Ingresos"     value={fmt(ing)}  icon={DollarSign} color={C.primary} />
                  <KpiCard label="Aportes SS"   value={fmt(cos)}  icon={HeartPulse} color={C.red} />
                  <KpiCard label="Utilidad neta" value={fmt(util)}
                    icon={util >= 0 ? TrendingUp : TrendingDown}
                    color={util >= 0 ? C.green : C.red}
                    sub={`${d?.margen_pct ?? 0}% margen`} />
                </div>
              )
            }

            {/* Afiliados */}
            {!isLoading && d?.afiliados && (
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-semibold">Afiliados</span>
                    <Badge variant="secondary">{d.afiliados.total} total</Badge>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: 'Activos',         v: d.afiliados.activos,         color: C.green },
                      { label: 'Suspendidos',      v: d.afiliados.suspendidos,      color: C.amber },
                      { label: 'Doble afiliación', v: d.afiliados.doble_afiliacion, color: C.blue  },
                      { label: 'No encontrado',    v: d.afiliados.no_encontrado,    color: C.red   },
                      { label: 'En espera',        v: d.afiliados.en_espera,        color: C.amber },
                    ].filter(x => x.v > 0).map(({ label, v, color }) => (
                      <span key={label} className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold border"
                        style={{ color, borderColor: `${color}44`, background: `${color}12` }}>
                        {v} {label}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Bancos interactivo */}
            {!isLoading && (d?.ingresos_por_banco?.length ?? 0) > 0 && (
              <Card>
                <CardHeader className="pb-0 pt-4 px-4">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Landmark className="h-4 w-4 text-muted-foreground" /> Cobros por banco
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-3">
                  <BancoChart data={d.ingresos_por_banco} total={d.ingresos} />
                </CardContent>
              </Card>
            )}

            {/* Barras historial */}
            {!isLoading && histData.length > 0 && (
              <Card>
                <CardHeader className="pb-0 pt-4 px-4">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-muted-foreground" /> Historial mensual
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={histData} barSize={16} barGap={3}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: C.text2 }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={v => `$${(v/1000000).toFixed(1)}M`} tick={{ fontSize: 10, fill: C.text2 }} axisLine={false} tickLine={false} width={52} />
                      <ReTooltip content={<BarTooltip />} />
                      <Bar dataKey="Ingresos"   fill={C.primary} radius={[4,4,0,0]} />
                      <Bar dataKey="Aportes SS" fill={C.red}     radius={[4,4,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}

            {!isLoading && !d && (
              <p className="text-center text-muted-foreground text-sm py-8">Sin datos para el período seleccionado.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────
export default function Finanzas() {
  const [anio,      setAnio]      = useState(anioActual);
  const [mes,       setMes]       = useState(mesActual);
  const [clienteFiltro, setClienteFiltro] = useState('');
  const [clienteSel,    setClienteSel]    = useState(null);

  const params = {};
  if (anio !== 'Todos') params.anio = anio;
  if (mes  !== 'Todos') params.mes  = mes;

  const { data: dash, isLoading: loadDash, refetch: refetchDash } = useQuery({
    queryKey: ['dashboard', anio, mes],
    queryFn: () => api.get('/dashboard', { params }).then(r => r.data),
    refetchInterval: 300_000,
    staleTime: 0,
  });

  const { data: clientes = [], isLoading: loadClientes, refetch: refetchClientes } = useQuery({
    queryKey: ['finanzas-clientes', anio, mes],
    queryFn: () => api.get('/dashboard/clientes', { params }).then(r => r.data),
    refetchInterval: 300_000,
    staleTime: 0,
  });

  const refetchAll = () => { refetchDash(); refetchClientes(); };

  const isLoading = loadDash || loadClientes;

  const ingBruto  = dash ? (dash.ingresos - (dash.ingresos_adicionales ?? 0)) : 0;
  const ingAdic   = dash?.ingresos_adicionales ?? 0;
  const ingTotal  = dash?.ingresos             ?? 0;
  const aportesSS = clientes.reduce((s, c) => s + (c.costos ?? 0), 0);
  const nominas   = dash?.nominas              ?? 0;
  const gastos    = dash?.gastos_fijos         ?? 0;
  const mora      = dash?.total_impuestos_planillas ?? 0;
  const utilNeta  = dash?.utilidad_neta        ?? 0;
  const utilBruta = dash?.utilidad_bruta       ?? 0;
  const pendTotal = dash?.pendiente_cobro_total ?? 0;
  const mFactor   = dash?.meses_factor         ?? 1;
  const bancosData = dash?.ingresos_por_banco  ?? [];

  const listaClientes = clientes.map(c => c.cliente).sort((a, b) => a.localeCompare(b));

  const clientesFilt = clienteFiltro
    ? clientes.filter(c => c.cliente === clienteFiltro)
    : clientes;

  return (
    <div className="flex flex-col gap-0">
      {/* Header */}
      <div className="flex items-center justify-between pb-5 mb-6 border-b relative">
        <div className="absolute bottom-[-1px] left-0 w-12 h-0.5 rounded"
          style={{ background: `linear-gradient(90deg, ${C.primary}, ${C.accent})` }} />
        <div>
          <div className="text-[11px] text-muted-foreground font-mono mb-1">Panel / Reportes Financieros</div>
          <h1 className="text-2xl font-extrabold tracking-tight"
            style={{ fontFamily:"'Syne', sans-serif", letterSpacing:'-.4px' }}>
            Reportes Financieros
          </h1>
          <p className="text-sm text-muted-foreground font-light">Resultados financieros y rentabilidad por cliente</p>
        </div>
        <div className="flex items-center gap-2">
          <PeriodSelector anio={anio} mes={mes} setAnio={setAnio} setMes={setMes} />
          <Button variant="outline" size="icon" onClick={refetchAll} disabled={isLoading} className="h-8 w-8" title="Actualizar datos">
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Layout dos columnas */}
      <div className="flex gap-5 items-start">

        {/* Panel izquierdo */}
        <div className="w-52 shrink-0 flex flex-col gap-3 sticky top-4">
          {isLoading ? (
            [1,2,3].map(i => <SkeletonCard key={i} height={90} />)
          ) : (
            <>
              <KpiCard label="Ingresos totales" value={fmt(ingTotal)}
                icon={DollarSign} color={C.primary}
                sub={ingAdic > 0 ? `incl. ${fmt(ingAdic)} extra` : undefined} />
              <KpiCard label="Aportes SS" value={fmt(aportesSS)}
                icon={HeartPulse} color={C.red}
                sub={ingTotal > 0 ? `${pctOf(aportesSS, ingTotal).toFixed(1)}% de ingresos` : undefined} />
              <KpiCard label="Utilidad neta" value={fmt(utilNeta)}
                icon={utilNeta >= 0 ? TrendingUp : TrendingDown}
                color={utilNeta >= 0 ? C.green : C.red}
                sub={ingTotal > 0 ? `${pctOf(utilNeta, ingTotal).toFixed(1)}% margen` : undefined} />
              <KpiCard label="Pendiente cobrar" value={fmt(pendTotal)}
                icon={Clock} color={C.amber} sub="saldo histórico" />
            </>
          )}
        </div>

        {/* Contenido derecho */}
        <div className="flex-1 flex flex-col gap-5 min-w-0">

          {/* Bloque ingresos + costos */}
          <Card>
            <CardContent className="p-5">
              {isLoading ? <SkeletonCard height={220} /> : (
                <div className="flex flex-col gap-0">

                  {/* ── INGRESOS ── */}
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1 h-4 rounded-full" style={{ background: C.primary }} />
                    <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Ingresos</span>
                  </div>

                  <div className="rounded-xl p-4 flex flex-col gap-2 mb-4"
                    style={{ background: `${C.primary}08`, border: `1px solid ${C.primary}20` }}>
                    <div className="flex justify-between items-center text-sm">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <FileText className="h-3.5 w-3.5" /> Facturas cobradas
                      </div>
                      <span className="font-semibold tabular-nums">{fmt(ingBruto)}</span>
                    </div>
                    {ingAdic > 0 && (
                      <div className="flex justify-between items-center text-sm">
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <PlusCircle className="h-3.5 w-3.5" /> Ingresos adicionales
                        </div>
                        <span className="font-semibold tabular-nums" style={{ color: C.green }}>{fmt(ingAdic)}</span>
                      </div>
                    )}
                    <Separator className="my-1" />
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-bold">Total ingresos</span>
                      <span className="text-base font-bold tabular-nums" style={{ color: C.primary }}>{fmt(ingTotal)}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 my-2">
                    <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground px-1">Deducciones</span>
                    <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                  </div>

                  {/* ── COSTOS ── */}
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-1 h-4 rounded-full" style={{ background: C.red }} />
                    <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Costos y deducciones</span>
                    {aportesSS === 0 && ingTotal > 0 && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                        style={{ color: C.amber, background: `${C.amber}15`, border: `1px solid ${C.amber}30` }}>
                        ⚠ Sin aportes SS registrados
                      </span>
                    )}
                  </div>

                  <div className="rounded-xl overflow-hidden mb-4"
                    style={{ border: `1px solid var(--border)`, background: `${C.red}04` }}>
                    <div className="flex flex-col divide-y">
                      <CostRow label="Aportes Seguridad Social"
                        icon={HeartPulse} value={aportesSS}
                        pct={pctOf(aportesSS, ingTotal)} color={C.red} />
                      <CostRow label={`Nóminas${mFactor > 1 ? ` (×${mFactor} meses)` : ''}`}
                        icon={Briefcase} value={nominas}
                        pct={pctOf(nominas, ingTotal)} color="#f97316" />
                      <CostRow label={`Gastos fijos${mFactor > 1 ? ` (×${mFactor} meses)` : ''}`}
                        icon={Receipt} value={gastos}
                        pct={pctOf(gastos, ingTotal)} color="#a855f7" />
                      {mora > 0 && (
                        <CostRow label="Mora / 4×1000 / cargo adicional"
                          icon={AlertCircle} value={mora}
                          pct={pctOf(mora, ingTotal)} color={C.amber} />
                      )}
                    </div>
                  </div>

                  {/* ── UTILIDAD NETA ── */}
                  <div className="mt-4 rounded-xl p-4 flex items-center justify-between"
                    style={{
                      background: `${utilNeta >= 0 ? C.green : C.red}10`,
                      border: `1.5px solid ${utilNeta >= 0 ? C.green : C.red}30`,
                    }}>
                    <div className="flex items-center gap-2">
                      {utilNeta >= 0
                        ? <TrendingUp className="h-5 w-5" style={{ color: C.green }} />
                        : <TrendingDown className="h-5 w-5" style={{ color: C.red }} />}
                      <span className="font-bold text-sm">Utilidad neta</span>
                    </div>
                    <div className="text-right">
                      <div className="text-xl font-extrabold tabular-nums"
                        style={{ color: utilNeta >= 0 ? C.green : C.red }}>
                        {fmt(utilNeta)}
                      </div>
                      {ingTotal > 0 && (
                        <div className="text-xs text-muted-foreground">
                          {pctOf(utilNeta, ingTotal).toFixed(1)}% de margen
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ── UTILIDAD BRUTA ── */}
                  <div className="mt-2 rounded-xl p-4 flex items-center justify-between"
                    style={{
                      background: `${C.primary}08`,
                      border: `1px solid ${C.primary}20`,
                    }}>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4" style={{ color: C.primary }} />
                      <div>
                        <span className="font-semibold text-sm">Utilidad bruta</span>
                        <div className="text-xs" style={{ color: C.text2 }}>Sin descontar nóminas ni gastos fijos</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold tabular-nums"
                        style={{ color: C.primary }}>
                        {fmt(utilBruta)}
                      </div>
                      {ingTotal > 0 && (
                        <div className="text-xs text-muted-foreground">
                          {pctOf(utilBruta, ingTotal).toFixed(1)}% de margen
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              )}
            </CardContent>
          </Card>

          {/* Bancos interactivo */}
          {!isLoading && bancosData.length > 0 && (
            <Card>
              <CardHeader className="pb-0 pt-4 px-5">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Landmark className="h-4 w-4 text-muted-foreground" /> Cobros por banco
                </CardTitle>
              </CardHeader>
              <CardContent className="px-5 pb-5 pt-3">
                <BancoChart data={bancosData} total={ingTotal} />
              </CardContent>
            </Card>
          )}

          {/* Tabla clientes */}
          <div>
            <div className="flex items-center gap-3 mb-3">
              <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Análisis por cliente</span>
              <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
            </div>
          <Card className="overflow-hidden">
            <CardHeader className="pb-3 pt-4 px-5">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" /> Rentabilidad por cliente
                </CardTitle>
                <select
                  value={clienteFiltro}
                  onChange={e => setClienteFiltro(e.target.value)}
                  className="h-8 rounded-md border px-2 text-sm bg-card text-foreground w-44"
                >
                  <option value="">Todos los clientes</option>
                  {listaClientes.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-t border-b bg-muted/40">
                    {['Cliente','Afiliados','Ingresos','Aportes SS','Utilidad','Margen','Pendiente'].map(h => (
                      <th key={h} className={`px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap border-r last:border-r-0 ${h === 'Cliente' ? 'text-left' : 'text-right'}`}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {isLoading
                    ? [1,2,3,4].map(i => (
                      <tr key={i} className="border-b">
                        {[1,2,3,4,5,6,7].map(j => (
                          <td key={j} className="px-4 py-3">
                            <div className="h-3.5 rounded bg-muted animate-pulse" style={{ width: j === 1 ? '70%' : '50%' }} />
                          </td>
                        ))}
                      </tr>
                    ))
                    : clientesFilt.length === 0
                      ? (
                        <tr>
                          <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground text-sm">
                            {clienteFiltro ? 'Sin resultados para ese cliente.' : 'Sin datos para el período.'}
                          </td>
                        </tr>
                      )
                      : clientesFilt.map(c => {
                        const mv = margenVariant(c.margen_pct ?? 0);
                        return (
                          <tr key={c.cliente}
                            onClick={() => setClienteSel(c.cliente)}
                            className="border-b hover:bg-muted/30 cursor-pointer transition-colors">
                            <td className="px-4 py-3 font-semibold border-r last:border-r-0">{c.cliente}</td>
                            <td className="px-4 py-3 text-right text-muted-foreground border-r last:border-r-0">{c.n_afiliados}</td>
                            <td className="px-4 py-3 text-right font-semibold tabular-nums border-r last:border-r-0" style={{ color: C.primary }}>
                              {fmt(c.ingresos)}
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums border-r last:border-r-0" style={{ color: C.red }}>
                              {fmt(c.costos)}
                            </td>
                            <td className="px-4 py-3 text-right font-bold tabular-nums border-r last:border-r-0"
                              style={{ color: (c.utilidad ?? 0) >= 0 ? C.green : C.red }}>
                              {fmt(c.utilidad)}
                            </td>
                            <td className="px-4 py-3 border-r last:border-r-0">
                              <div className="flex flex-col items-end gap-1.5">
                                <span className="text-xs font-bold px-2 py-0.5 rounded-full"
                                  style={{ color: mv.color, background: mv.bg }}>
                                  {(c.margen_pct ?? 0).toFixed(1)}%
                                </span>
                                <ColorBar value={c.margen_pct ?? 0} color={mv.color} className="w-20" />
                              </div>
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums border-r last:border-r-0" style={{ color: C.amber }}>
                              {fmt(c.pendiente)}
                            </td>
                          </tr>
                        );
                      })
                  }
                </tbody>
              </table>
            </div>
          </Card>
          </div>

        </div>
      </div>

      {clienteSel && (
        <ModalCliente cliente={clienteSel} onClose={() => setClienteSel(null)} />
      )}
    </div>
  );
}
