import React, { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../utils/api';
import { StatCard, SkeletonCard, ErrorMsg, Card, PageHeader } from '../components/UI';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

const ESTADOS = ['nuevo', 'interesado', 'caliente', 'cerrado'];

function estadoPill(e) {
  const map = {
    nuevo:      'bg-slate-50 text-slate-600 border-slate-200',
    interesado: 'bg-green-50 text-green-700 border-green-200',
    caliente:   'bg-orange-50 text-orange-700 border-orange-200',
    cerrado:    'bg-purple-50 text-purple-700 border-purple-200',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-semibold border capitalize ${map[e] || 'bg-gray-50 text-gray-500 border-gray-200'}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />{e || '—'}
    </span>
  );
}

const sel = "h-9 rounded-lg border bg-card px-2.5 text-sm text-foreground";

export default function Leads() {
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [fEstado, setFEstado] = useState('');
  const [fPagina, setFPagina] = useState('');
  const [fCanal, setFCanal] = useState('');
  const [fServicio, setFServicio] = useState('');
  const [fDesde, setFDesde] = useState('');
  const [fHasta, setFHasta] = useState('');
  const [page, setPage] = useState(1);
  const PER = 15;

  const { data: stats, isLoading: ls, isError: es, refetch: rs } = useQuery({
    queryKey: ['leads-stats'],
    queryFn: () => api.get('/leads/stats').then(r => r.data),
    refetchInterval: 60_000,
  });
  const { data: list, isError: el, refetch: rl } = useQuery({
    queryKey: ['leads-list'],
    queryFn: () => api.get('/leads/list', { params: { limit: 100 } }).then(r => r.data),
    refetchInterval: 60_000,
  });

  const mut = useMutation({
    mutationFn: ({ id, estado }) => api.post('/leads/estado', null, { params: { id, estado } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['leads-list'] }); qc.invalidateQueries({ queryKey: ['leads-stats'] }); },
  });

  const leads = list?.leads || [];
  const paginas = list?.paginas || {};
  const pageName = (x) => (x.page_id && paginas[x.page_id]) || (x.fuente === 'whatsapp' ? 'WhatsApp' : '—');

  const filtered = useMemo(() => leads.filter(x => {
    if (fEstado && x.estado !== fEstado) return false;
    if (fPagina && x.page_id !== fPagina) return false;
    if (fCanal && x.fuente !== fCanal) return false;
    if (fServicio && x.servicio_interes !== fServicio) return false;
    if (fDesde && new Date(x.created_at) < new Date(fDesde + 'T00:00:00')) return false;
    if (fHasta && new Date(x.created_at) > new Date(fHasta + 'T23:59:59')) return false;
    if (q && ![x.nombre, x.ciudad, x.servicio_interes, x.fuente].join(' ').toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [leads, fEstado, fPagina, fCanal, fServicio, fDesde, fHasta, q]);

  // Reinicia a la página 1 cuando cambian filtros o búsqueda.
  useEffect(() => { setPage(1); }, [fEstado, fPagina, fCanal, fServicio, fDesde, fHasta, q]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PER));
  const curPage = Math.min(page, totalPages);
  const paged = filtered.slice((curPage - 1) * PER, curPage * PER);

  const uniq = (key) => {
    const m = {};
    leads.forEach(x => { if (x[key]) m[x[key]] = key === 'page_id' ? pageName(x) : x[key]; });
    return Object.entries(m);
  };

  if (es) return <ErrorMsg message="No se pudo cargar Laura. ¿LAURA_API_URL / LAURA_ADMIN_KEY configurados?" onRetry={rs} />;

  const e = stats?.por_estado || {};
  const total = stats?.total_leads || 0;
  const conv = total ? Math.round(((e.cerrado || 0) / total) * 100) : 0;
  const serie = (stats?.serie_14d || []).map(r => ({ dia: (r.dia || '').slice(5), n: r.n }));

  return (
    <div>
      <PageHeader title="Leads — Laura" subtitle="Prospectos captados por el agente de ventas en Messenger"
        action={<button onClick={() => { rs(); rl(); }} className="h-9 px-3 rounded-lg border bg-card text-sm">↻ Actualizar</button>} />

      {/* KPIs (arriba del todo) */}
      {ls ? (
        <div className="flex gap-3 flex-wrap mb-4">{Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}</div>
      ) : (
        <div className="flex gap-3 flex-wrap mb-4">
          <StatCard label="Total prospectos" value={total} color="#4F46E5" icon="◈" />
          <StatCard label="Hoy" value={stats?.hoy || 0} color="#0891B2" icon="☀" />
          <StatCard label="Nuevos" value={e.nuevo || 0} color="#64748B" icon="◎" />
          <StatCard label="Interesados" value={e.interesado || 0} color="#059669" icon="✓" />
          <StatCard label="Calientes" value={e.caliente || 0} color="#F97316" icon="🔥" />
          <StatCard label="Cerrados" value={e.cerrado || 0} color="#7C3AED" icon="★" />
          <StatCard label="Tasa de cierre" value={`${conv}%`} color="#4F46E5" icon="%" />
          <StatCard label="Sin alertar" value={stats?.calientes_sin_alertar || 0} color="#EF4444" icon="!" />
        </div>
      )}

      {/* Tabla */}
      <Card>
        <div className="flex flex-wrap gap-2 items-center mb-3">
          <div className="text-sm font-semibold mr-auto">Prospectos recientes</div>
          <input value={q} onChange={ev => setQ(ev.target.value)} placeholder="Buscar…" className={`${sel} w-44`} />
          <input type="date" value={fDesde} onChange={ev => setFDesde(ev.target.value)} className={sel} title="Desde" />
          <input type="date" value={fHasta} onChange={ev => setFHasta(ev.target.value)} className={sel} title="Hasta" />
          <select value={fEstado} onChange={ev => setFEstado(ev.target.value)} className={sel}>
            <option value="">Estado: todos</option>{ESTADOS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={fPagina} onChange={ev => setFPagina(ev.target.value)} className={sel}>
            <option value="">Página: todas</option>{uniq('page_id').map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={fCanal} onChange={ev => setFCanal(ev.target.value)} className={sel}>
            <option value="">Canal: todos</option>{uniq('fuente').map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={fServicio} onChange={ev => setFServicio(ev.target.value)} className={sel}>
            <option value="">Servicio: todos</option>{uniq('servicio_interes').map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        {el ? <ErrorMsg message="Error cargando prospectos" onRetry={rl} /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] uppercase text-muted-foreground">
                <th className="py-2 px-3">Prospecto</th><th className="py-2 px-3">Ciudad</th><th className="py-2 px-3">Servicio</th>
                <th className="py-2 px-3">Estado</th><th className="py-2 px-3">Página</th><th className="py-2 px-3">Canal</th>
                <th className="py-2 px-3">Ingreso</th><th className="py-2 px-3">Cambiar</th>
              </tr></thead>
              <tbody>
                {paged.length ? paged.map(x => (
                  <tr key={x.id} className="border-t hover:bg-muted/40">
                    <td className="py-2.5 px-3">
                      <div className="font-medium">{x.nombre || '—'}</div>
                      <div className="text-[11px] text-muted-foreground">{x.telefono || 'sin teléfono'}</div>
                    </td>
                    <td className="py-2.5 px-3">{x.ciudad || '—'}</td>
                    <td className="py-2.5 px-3">{x.servicio_interes || '—'}</td>
                    <td className="py-2.5 px-3">{estadoPill(x.estado)}</td>
                    <td className="py-2.5 px-3">{pageName(x)}</td>
                    <td className="py-2.5 px-3">{x.fuente || '—'}</td>
                    <td className="py-2.5 px-3 whitespace-nowrap">{new Date(x.created_at).toLocaleString('es-CO', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
                    <td className="py-2.5 px-3">
                      <select className={sel} value={x.estado || ''} disabled={mut.isPending}
                        onChange={ev => mut.mutate({ id: x.id, estado: ev.target.value })}>
                        {ESTADOS.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                  </tr>
                )) : <tr><td colSpan={8} className="py-8 text-center text-muted-foreground">Sin prospectos.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
        {!el && filtered.length > 0 && (
          <div className="flex items-center justify-between mt-3 text-sm text-muted-foreground">
            <span>{filtered.length} prospecto{filtered.length !== 1 ? 's' : ''} · mostrando {(curPage - 1) * PER + 1}–{Math.min(curPage * PER, filtered.length)}</span>
            <div className="flex items-center gap-2">
              <button disabled={curPage <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}
                className="h-8 px-3 rounded-lg border bg-card disabled:opacity-40">←</button>
              <span>{curPage} / {totalPages}</span>
              <button disabled={curPage >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                className="h-8 px-3 rounded-lg border bg-card disabled:opacity-40">→</button>
            </div>
          </div>
        )}
      </Card>

      {/* Evolución (medio) */}
      <Card style={{ marginTop: 16, marginBottom: 16 }}>
        <div className="text-sm font-semibold mb-3">Evolución (14 días)</div>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={serie}>
            <defs><linearGradient id="gl" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4F46E5" stopOpacity={0.35} /><stop offset="100%" stopColor="#4F46E5" stopOpacity={0} />
            </linearGradient></defs>
            <XAxis dataKey="dia" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip /><Area type="monotone" dataKey="n" stroke="#4F46E5" strokeWidth={2} fill="url(#gl)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

    </div>
  );
}
