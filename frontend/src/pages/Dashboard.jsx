import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { StatCard, SkeletonCard, C, fmt } from '../components/UI';

const MESES = ['Todos','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear().toString();

export default function Dashboard() {
  const [anio, setAnio] = useState(anioActual);
  const [mes,  setMes]  = useState('Todos');

  const params = {};
  if (anio !== 'Todos') params.anio = anio;
  if (mes  !== 'Todos') params.mes  = mes;

  const { data: d, isLoading } = useQuery({
    queryKey: ['dashboard', anio, mes],
    queryFn: () => api.get('/dashboard', { params }).then(r => r.data),
    refetchInterval: 120_000,
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
          <button onClick={()=>{setAnio(anioActual);setMes('Todos');}}
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
          ? [1,2,3,4].map(i => <div key={i} style={{ flex:1, minWidth:140 }}><SkeletonCard height={88} /></div>)
          : <>
            <StatCard label="Ingresos"                  value={fmt(d?.ingresos)}              color={C.primary} icon="💰" />
            <StatCard label={`Nóminas (×${d?.meses_factor??1} mes)`}     value={fmt(d?.nominas)}      color={C.red} icon="👔" />
            <StatCard label={`Gastos fijos (×${d?.meses_factor??1} mes)`} value={fmt(d?.gastos_fijos)} color={C.red} icon="📝" />
            <StatCard label="Utilidad neta"             value={fmt(d?.utilidad_neta)}
              color={(d?.utilidad_neta ?? 0) >= 0 ? C.green : C.red}
              icon={(d?.utilidad_neta ?? 0) >= 0 ? '📈' : '📉'} />
          </>
        }
      </div>
    </div>
  );
}
