import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { StatCard, C, fmt, Card } from '../components/UI';

async function dlExcel(url, filename) {
  try {
    const res = await api.get(url, { responseType: 'blob' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(res.data);
    a.download = filename;
    a.click();
  } catch (e) {
    alert('Error generando reporte');
  }
}

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
    refetchInterval: 30_000,
  });

  const { data: act } = useQuery({
    queryKey: ['actividad'],
    queryFn: () => api.get('/actividad').then(r => r.data),
  });

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
          <button onClick={()=>dlExcel(`/reportes/consolidado`,'reporte_consolidado.xlsx')}
            style={{ ...sel, cursor:'pointer', background:'#16A34A', color:'#fff', fontWeight:600, border:'none' }}>
            📊 Consolidado
          </button>
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
        <StatCard label="Nóminas empleados"  value={fmt(d?.nominas)}          color={C.red} />
        <StatCard label="Gastos fijos"       value={fmt(d?.gastos_fijos)}     color={C.red} />
        <StatCard label="Utilidad neta"      value={fmt(d?.utilidad_neta)}
          color={(d?.utilidad_neta ?? 0) >= 0 ? C.green : C.red} />
      </div>

      {/* Actividad reciente */}
      <Card>
        <h3 style={{ margin:'0 0 14px', fontSize:14, fontWeight:600, color:C.primary }}>
          📋 Actividad reciente
        </h3>
        <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
          <thead>
            <tr style={{ background:C.surface2 }}>
              {['Fecha','Usuario','Acción','Módulo','Detalle'].map(h=>(
                <th key={h} style={{ padding:'7px 10px', textAlign:'left', color:C.text2,
                  fontWeight:600, borderBottom:`1px solid ${C.border}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(act||[]).slice(0,15).map((a,i)=>(
              <tr key={i} style={{ borderBottom:`1px solid ${C.border}` }}>
                <td style={{ padding:'7px 10px', color:C.text2 }}>{a.fecha}</td>
                <td style={{ padding:'7px 10px', fontWeight:500 }}>{a.usuario}</td>
                <td style={{ padding:'7px 10px' }}>{a.accion}</td>
                <td style={{ padding:'7px 10px', color:C.blue }}>{a.modulo}</td>
                <td style={{ padding:'7px 10px', color:C.text2 }}>{a.detalle}</td>
              </tr>
            ))}
            {(!act||act.length===0)&&(
              <tr><td colSpan={5} style={{ padding:'14px',textAlign:'center',color:C.text2 }}>Sin actividad reciente</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
