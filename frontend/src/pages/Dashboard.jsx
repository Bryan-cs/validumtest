import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { StatCard, C, fmt } from '../components/UI';

const MESES = ['Todos','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear().toString();

const MESES_ABREV = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];

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

  const mesParaMeses = anio !== 'Todos' ? anio : anioActual;
  const { data: mesesData = [] } = useQuery({
    queryKey: ['dashboard_meses', mesParaMeses],
    queryFn: () => api.get('/dashboard/meses', { params: { anio: mesParaMeses } }).then(r => r.data),
    refetchInterval: 120_000,
    enabled: mes === 'Todos',
  });

  const sel = { padding:'7px 12px', border:`1px solid ${C.border}`, borderRadius:7,
    fontSize:13, outline:'none', background:C.surface, color:C.text };

  const mesActualAbrev = MESES_ABREV[new Date().getMonth()];
  const mesActualIdx   = new Date().getMonth(); // 0-indexed

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
          <button onClick={()=>{setAnio(anioActual);setMes('Todos');}}
            style={{ ...sel, cursor:'pointer', background:C.surface2 }}>↺ Hoy</button>
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
      <div style={{ display:'flex', gap:10, marginBottom:8, flexWrap:'wrap' }}>
        <StatCard label="Facturas emitidas"  value={d?.facturas       ?? '—'} color={C.blue} />
        <StatCard label="Ingresos"           value={fmt(d?.ingresos)}         color={C.primary} />
        <StatCard label={`Pendiente período`} value={fmt(d?.pendiente_cobro)}  color={C.amber} />
        <StatCard label="⚠ Pendiente total" value={fmt(d?.pendiente_cobro_total)} color={C.red} />
        <StatCard label={`Nóminas (×${d?.meses_factor??1} mes)`} value={fmt(d?.nominas)} color={C.red} />
        <StatCard label={`Gastos fijos (×${d?.meses_factor??1} mes)`} value={fmt(d?.gastos_fijos)} color={C.red} />
        <StatCard label="Utilidad neta" value={fmt(d?.utilidad_neta)}
          color={(d?.utilidad_neta ?? 0) >= 0 ? C.green : C.red} />
      </div>

      {/* Resumen mensual — solo cuando no hay filtro de mes específico */}
      {mes === 'Todos' && mesesData.length > 0 && (
        <div style={{ marginTop:20 }}>
          <div style={{ fontSize:13, fontWeight:700, color:C.text2, marginBottom:10 }}>
            Resumen mensual — {mesParaMeses}
          </div>
          <div style={{ overflowX:'auto' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface,
              borderRadius:10, overflow:'hidden', border:`1px solid ${C.border}` }}>
              <thead>
                <tr style={{ background:C.surface2 }}>
                  {['Mes','Facturas','Ingresos','Pendiente'].map(h=>(
                    <th key={h} style={{ padding:'9px 14px', textAlign: h==='Mes'?'left':'right',
                      fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}`,
                      whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {mesesData.map((row, i) => {
                  const esMesActual = row.mes === mesActualAbrev && parseInt(mesParaMeses) === new Date().getFullYear();
                  return (
                    <tr key={row.mes}
                      style={{
                        borderBottom: i < mesesData.length-1 ? `1px solid ${C.border}` : 'none',
                        background: esMesActual ? C.blueBg : 'transparent',
                        cursor: 'pointer',
                      }}
                      onClick={() => { setMes(MESES[i+1]); setAnio(mesParaMeses); }}
                    >
                      <td style={{ padding:'9px 14px', fontSize:13, color: esMesActual ? C.blue : C.text,
                        fontWeight: esMesActual ? 700 : 400 }}>
                        {esMesActual ? `${row.mes} ◀` : row.mes}
                      </td>
                      <td style={{ padding:'9px 14px', fontSize:13, color:C.text, textAlign:'right' }}>
                        {row.facturas > 0 ? row.facturas : <span style={{color:C.text2}}>—</span>}
                      </td>
                      <td style={{ padding:'9px 14px', fontSize:13, fontWeight: row.ingresos>0?600:400,
                        color: row.ingresos>0 ? C.green : C.text2, textAlign:'right' }}>
                        {row.ingresos > 0 ? fmt(row.ingresos) : '—'}
                      </td>
                      <td style={{ padding:'9px 14px', fontSize:13,
                        color: row.pendiente>0 ? C.amber : C.text2, textAlign:'right',
                        fontWeight: row.pendiente>0 ? 600 : 400 }}>
                        {row.pendiente > 0 ? fmt(row.pendiente) : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize:11, color:C.text2, marginTop:6 }}>
            Clic en una fila para ver el detalle del mes.
          </p>
        </div>
      )}
    </div>
  );
}
