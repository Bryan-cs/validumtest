import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import { StatCard, C, fmt, Card } from '../components/UI';
import useAuthStore from '../hooks/useAuth';

const MESES = ['Todos','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear().toString();

export default function Dashboard() {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const [anio, setAnio] = useState(anioActual);
  const [mes,  setMes]  = useState('Todos');

  // Filtros de actividad
  const [actDia,  setActDia]  = useState('');
  const [actMes,  setActMes]  = useState('');
  const [actAnio, setActAnio] = useState('');

  const params = {};
  if (anio !== 'Todos') params.anio = anio;
  if (mes  !== 'Todos') params.mes  = mes;

  const { data: d, isLoading } = useQuery({
    queryKey: ['dashboard', anio, mes],
    queryFn: () => api.get('/dashboard', { params }).then(r => r.data),
    refetchInterval: 30_000,
  });

  const { data: act } = useQuery({
    queryKey: ['actividad', actDia, actMes, actAnio],
    queryFn: () => api.get('/actividad', { params: {
      dia: actDia, mes: actMes, anio: actAnio,
    }}).then(r => r.data),
  });

  const limpiarActividad = async () => {
    if (!window.confirm('¿Limpiar todo el historial de actividad?')) return;
    try {
      await api.delete('/actividad');
      qc.invalidateQueries({ queryKey: ['actividad'] });
      toast.success('Historial limpiado');
    } catch { toast.error('Error al limpiar historial'); }
  };

  const sel = { padding:'7px 12px', border:`1px solid ${C.border}`, borderRadius:7,
    fontSize:13, outline:'none', background:'#fff', color:C.text };

  return (
    <div>
      {/* Header + filtros */}
      <div style={{ display:'flex', alignItems:'center', marginBottom:20, gap:10 }}>
        <div>
          <h1 style={{ margin:0, fontSize:22, fontWeight:700, color:C.primary }}>Dashboard</h1>
          <p style={{ margin:0, fontSize:13, color:C.text2 }}>Resumen general del sistema</p>
        </div>
        <div style={{ marginLeft:'auto', display:'flex', gap:8, alignItems:'center' }}>
          <span style={{ fontSize:12, color:C.text2 }}>Período:</span>
          <select style={sel} value={anio} onChange={e=>setAnio(e.target.value)}>
            {['Todos', anioActual, String(+anioActual-1)].map(a=><option key={a}>{a}</option>)}
          </select>
          <select style={sel} value={mes} onChange={e=>setMes(e.target.value)}>
            {MESES.map(m=><option key={m}>{m}</option>)}
          </select>
          <button onClick={()=>{setAnio('Todos');setMes('Todos');}}
            style={{ ...sel, cursor:'pointer', background:C.surface2 }}>↺ Todo</button>
        </div>
      </div>

      {/* Métricas afiliados */}
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        <StatCard label="Activos"         value={d?.activos       ?? '—'} color={C.green} />
        <StatCard label="Retirados"       value={d?.retirados     ?? '—'} color={C.red} />
        <StatCard label="Suspendidos"     value={d?.suspendidos   ?? '—'} color={C.amber} />
        <StatCard label="Total afiliados" value={d?.total_afiliados?? '—'} color={C.primary} />
      </div>

      {/* Métricas financieras */}
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        <StatCard label="Facturas emitidas"  value={d?.facturas       ?? '—'} color={C.blue} />
        <StatCard label="Ingresos"           value={fmt(d?.ingresos)}         color={C.primary} />
        <StatCard label="Pendiente cobro"    value={fmt(d?.pendiente_cobro)}  color={C.amber} />
        <StatCard label={`Nóminas (×${d?.meses_factor??1} mes)`} value={fmt(d?.nominas)}      color={C.red} />
        <StatCard label={`Gastos fijos (×${d?.meses_factor??1} mes)`} value={fmt(d?.gastos_fijos)} color={C.red} />
        <StatCard label="Utilidad neta"      value={fmt(d?.utilidad_neta)}
          color={(d?.utilidad_neta ?? 0) >= 0 ? C.green : C.red} />
      </div>

      {/* Actividad reciente */}
      <Card>
        <div style={{ display:'flex', alignItems:'center', marginBottom:12, gap:10, flexWrap:'wrap' }}>
          <h3 style={{ margin:0, fontSize:14, fontWeight:600, color:C.primary }}>
            📋 Historial de actividad
          </h3>
          <span style={{ fontSize:12, color:C.text2, marginLeft:4 }}>
            {act?.length ?? 0} registros
          </span>
          <div style={{ marginLeft:'auto', display:'flex', gap:6, alignItems:'center', flexWrap:'wrap' }}>
            <input type="number" placeholder="Día" min={1} max={31}
              value={actDia} onChange={e=>setActDia(e.target.value)}
              style={{ ...sel, width:64 }} />
            <select style={sel} value={actMes} onChange={e=>setActMes(e.target.value)}>
              <option value="">Todos los meses</option>
              {MESES.filter(m=>m!=='Todos').map(m=><option key={m}>{m}</option>)}
            </select>
            <input type="number" placeholder="Año" min={2020} max={2099}
              value={actAnio} onChange={e=>setActAnio(e.target.value)}
              style={{ ...sel, width:80 }} />
            <button onClick={()=>{setActDia('');setActMes('');setActAnio('');}}
              style={{ ...sel, cursor:'pointer', background:C.surface2 }}>↺</button>
            {user?.rol === 'admin' && (
              <button onClick={limpiarActividad}
                style={{ ...sel, cursor:'pointer', background:C.red, color:'#fff', border:'none', fontWeight:600 }}>
                🗑️ Limpiar
              </button>
            )}
          </div>
        </div>
        <div style={{ overflowX:'auto' }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
            <thead>
              <tr style={{ background:C.surface2 }}>
                {['Fecha','Usuario','Acción','Módulo','Detalle'].map(h=>(
                  <th key={h} style={{ padding:'7px 10px', textAlign:'left', color:C.text2,
                    fontWeight:600, borderBottom:`1px solid ${C.border}`, whiteSpace:'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(act||[]).map((a,i)=>(
                <tr key={i} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ padding:'7px 10px', color:C.text2, whiteSpace:'nowrap' }}>{a.fecha}</td>
                  <td style={{ padding:'7px 10px', fontWeight:500 }}>{a.usuario}</td>
                  <td style={{ padding:'7px 10px' }}>{a.accion}</td>
                  <td style={{ padding:'7px 10px', color:C.blue }}>{a.modulo}</td>
                  <td style={{ padding:'7px 10px', color:C.text2 }}>{a.detalle}</td>
                </tr>
              ))}
              {(!act||act.length===0)&&(
                <tr><td colSpan={5} style={{ padding:'14px',textAlign:'center',color:C.text2 }}>Sin actividad</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
