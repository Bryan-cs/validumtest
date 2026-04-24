import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { StatCard, SkeletonCard, C, fmt } from '../components/UI';
import { bancoColor } from '../utils/colors';

const MESES = ['Todos','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual  = new Date().getFullYear().toString();
const mesActual   = MESES[new Date().getMonth() + 1]; // mes actual como nombre


export default function Dashboard() {
  const [anio, setAnio] = useState(anioActual);
  const [mes,  setMes]  = useState(mesActual);

  const params = {};
  if (anio !== 'Todos') params.anio = anio;
  if (mes  !== 'Todos') params.mes  = mes;

  const { data: d, isLoading } = useQuery({
    queryKey: ['dashboard', anio, mes],
    queryFn: () => api.get('/dashboard', { params }).then(r => r.data),
    refetchInterval: 120_000,
  });

  const { data: recientes = [] } = useQuery({
    queryKey: ['afiliados-recientes'],
    queryFn: () => api.get('/afiliados/recientes').then(r => r.data),
    refetchInterval: 30_000,
  });

  const sel = { padding:'7px 12px', border:`1px solid ${C.border}`, borderRadius:7,
    fontSize:13, outline:'none', background:C.surface, color:C.text };

  return (
    <div>
      {/* Header + filtros */}
      <div style={{ display:'flex', alignItems:'center', marginBottom:24, gap:10, paddingBottom:20, borderBottom:`1px solid ${C.border}`, position:'relative' }}>
        <div style={{ position:'absolute', bottom:-1, left:0, width:48, height:2, background:`linear-gradient(90deg, ${C.primary}, ${C.accent})`, borderRadius:2 }} />
        <div>
          <div style={{ fontSize:11, color:C.text2, marginBottom:4, fontFamily:"'IBM Plex Mono', monospace" }}>Panel / Dashboard</div>
          <h1 style={{ margin:0, fontFamily:"'Syne', sans-serif", fontSize:24, fontWeight:800, color:C.text, letterSpacing:'-.4px' }}>Resumen general</h1>
          <p style={{ margin:0, fontSize:13, color:C.text2, fontWeight:300 }}>Resumen general del sistema</p>
        </div>
        <div style={{ marginLeft:'auto', display:'flex', gap:8, alignItems:'center' }}>
          <span style={{ fontSize:12, color:C.text2 }}>Período:</span>
          <select style={sel} value={anio} onChange={e=>setAnio(e.target.value)}>
            {['Todos', anioActual, String(+anioActual-1)].map(a=><option key={a}>{a}</option>)}
          </select>
          <select style={sel} value={mes} onChange={e=>setMes(e.target.value)}>
            {MESES.map(m=><option key={m}>{m}</option>)}
          </select>
          <button onClick={()=>{setAnio(anioActual);setMes(mesActual);}}
            style={{ ...sel, cursor:'pointer', background:C.surface2 }}>↺ Hoy</button>
        </div>
      </div>

      {/* Métricas afiliados */}
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        {isLoading
          ? [1,2,3,4,5,6].map(i => <div key={i} style={{ flex:1, minWidth:120 }}><SkeletonCard height={88} /></div>)
          : <>
            <StatCard label="Activos"             value={d?.activos          ?? '—'} color={C.green}   icon="👥" />
            <StatCard label="Suspendidos"         value={d?.suspendidos      ?? '—'} color={C.amber}   icon="⏸️" />
            <StatCard label="Doble afiliación"    value={d?.doble_afiliacion ?? '—'} color={C.blue}    icon="🔄" />
            <StatCard label="No se encuentra"     value={d?.no_encontrado    ?? '—'} color={C.red}     icon="🔍" />
            <StatCard label="En espera activac."  value={d?.en_espera        ?? '—'} color={C.amber}   icon="⏳" />
            <StatCard label="Total afiliados"     value={d?.total_afiliados  ?? '—'} color={C.primary} icon="📊" />
          </>
        }
      </div>

      {/* Métricas financieras */}
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        {isLoading
          ? [1,2,3,4,5].map(i => <div key={i} style={{ flex:1, minWidth:140 }}><SkeletonCard height={88} /></div>)
          : <>
            <StatCard label="Ingresos"                  value={fmt(d?.ingresos)}              color={C.primary} icon="💰" />
            <StatCard label={`Nóminas (×${d?.meses_factor??1} mes)`}     value={fmt(d?.nominas)}      color={C.red} icon="👔" />
            <StatCard label={`Gastos fijos (×${d?.meses_factor??1} mes)`} value={fmt(d?.gastos_fijos)} color={C.red} icon="📝" />
            <StatCard label="Impuestos planillas SS"    value={fmt(d?.total_impuestos_planillas ?? 0)} color={C.amber} icon="📋" />
            <StatCard label="Utilidad neta"             value={fmt(d?.utilidad_neta)}
              color={(d?.utilidad_neta ?? 0) >= 0 ? C.green : C.red}
              icon={(d?.utilidad_neta ?? 0) >= 0 ? '📈' : '📉'} />
          </>
        }
      </div>

      {/* Ingresos por banco */}
      {d?.ingresos_por_banco?.length > 0 && (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 20px', marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.text2, letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: 14 }}>
            🏦 Ingresos por banco
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {d.ingresos_por_banco.map(b => {
              const pct = d.ingresos > 0 ? Math.round((b.total / d.ingresos) * 100) : 0;
              const bc = bancoColor(b.banco);
              return (
                <div key={b.banco} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, borderRadius: 6, padding: '2px 10px',
                    background: bc.badge, color: bc.text, minWidth: 160, whiteSpace: 'nowrap',
                    overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block' }}>
                    {b.banco}
                  </span>
                  <div style={{ flex: 1, background: C.surface2, borderRadius: 4, height: 8, overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: bc.bar, borderRadius: 4,
                      transition: 'width .4s ease' }} />
                  </div>
                  <div style={{ fontSize: 13, color: bc.text, fontWeight: 700, minWidth: 110, textAlign: 'right' }}>
                    {fmt(b.total)}
                  </div>
                  <div style={{ fontSize: 11, color: C.text2, minWidth: 36, textAlign: 'right' }}>
                    {pct}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Últimos afiliados */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 20px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: C.text2, letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: 14 }}>
          👥 Últimos afiliados
        </div>
        {recientes.length === 0 ? (
          <p style={{ color: C.text2, fontSize: 13, margin: 0 }}>Sin datos</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {recientes.map(a => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 34, height: 34, borderRadius: '50%',
                  background: C.surface2, border: `1px solid ${C.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: C.primary, flexShrink: 0,
                }}>
                  {a.nombre?.charAt(0)?.toUpperCase() ?? '?'}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {a.nombre}
                  </div>
                  <div style={{ fontSize: 11, color: C.text2 }}>
                    {a.doc}{a.empresa ? ` · ${a.empresa}` : ''}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: C.text2, flexShrink: 0 }}>
                  {a.creado ? new Date(a.creado).toLocaleDateString('es-CO', { day:'2-digit', month:'short' }) : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
