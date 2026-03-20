import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import { C, Btn, PageHeader, StatCard, fmt } from '../components/UI';
import { BarraFiltros } from '../components/FiltroCheck';

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

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

const ESTADO_CONFIG = {
  VENCIDO: { bg:C.redBg,    fg:C.red,   label:'VENCIDO',    orden:0 },
  HOY:     { bg:C.greenBg,  fg:C.green, label:'COBRAR HOY', orden:1 },
  PROXIMO: { bg:C.surface2, fg:C.text2, label:'PRÓXIMO',    orden:2 },
  COBRADO: { bg:C.blueBg,   fg:C.blue,  label:'COBRADO',    orden:3 },
};

export default function Cobro() {
  const qc = useQueryClient();
  const [filtros, setFiltros] = useState({ empresa:[], cliente:[], estado:[], subtipo:[] });
  const [expanded, setExp] = useState(null);

  const setFiltro = (key, vals) => setFiltros(f => ({ ...f, [key]: vals }));
  const limpiar   = () => setFiltros({ empresa:[], cliente:[], estado:[], subtipo:[] });

  const { data: listas = {} }    = useQuery({ queryKey:['listas'],    queryFn:()=>api.get('/listas').then(r=>r.data) });
  const { data: config = {} }    = useQuery({ queryKey:['config'],    queryFn:()=>api.get('/config').then(r=>r.data) });
  const { data: todosAfil = [] } = useQuery({ queryKey:['afiliados_all'], queryFn:()=>api.get('/afiliados').then(r=>r.data.items||[]) });
  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['cobro'],
    queryFn: () => api.get('/cobro', { params:{ empresa:'', cliente:'', tipo:'' } }).then(r=>r.data),
    refetchInterval: 60_000,
  });

  // Opciones dinámicas
  const clientesUnicos  = [...new Set(todosAfil.map(a=>a.cliente_txt).filter(Boolean))].sort();
  const subtiposUnicos  = [...new Set(todosAfil.map(a=>a.subtipo).filter(Boolean))].sort();
  const estadosOpts     = ['COBRAR HOY','VENCIDO','PRÓXIMO','COBRADO'];

  // Filtrado local con multiselección
  const rowsFiltrados = rows.filter(r => {
    const afil = todosAfil.find(a => a.doc === r.doc);
    const labelEstado = ESTADO_CONFIG[r.estado]?.label || r.estado;
    if (filtros.empresa.length  && !filtros.empresa.includes(r.empresa))       return false;
    if (filtros.cliente.length  && !filtros.cliente.includes(r.cliente))       return false;
    if (filtros.estado.length   && !filtros.estado.includes(labelEstado))      return false;
    if (filtros.subtipo.length  && !filtros.subtipo.includes(afil?.subtipo))   return false;
    return true;
  });

  const nHoy     = rowsFiltrados.filter(r=>r.estado==='HOY').length;
  const nVenc    = rowsFiltrados.filter(r=>r.estado==='VENCIDO').length;
  const nCobr    = rowsFiltrados.filter(r=>r.estado==='COBRADO').length;
  const planPend = rowsFiltrados.filter(r=>r.estado==='HOY'||r.estado==='VENCIDO').reduce((s,r)=>s+r.planilla,0);

  const crearFactura = useMutation({
    mutationFn: (row) => api.post('/facturas', {
      nombre_afiliado: row.nombre, doc: row.doc, cliente: row.cliente||'',
      anio: String(new Date().getFullYear()), mes: MESES[new Date().getMonth()],
      periodo:'30', estado:'pendiente', ingresos:0, costos:row.planilla, utilidad:-row.planilla,
      servicios_detalle: (row.servicios||[]).map(s=>({ servicio:s, incluido:true, valor:0 })),
    }),
    onSuccess: () => { toast.success('Factura creada'); qc.invalidateQueries({queryKey:['cobro']}); qc.invalidateQueries({queryKey:['facturas']}); },
    onError: e => toast.error(e.response?.data?.detail||'Error'),
  });

  return (
    <div>
      <PageHeader title="💰 Módulo de cobro"
        subtitle={`${rowsFiltrados.length} afiliados — ${new Date().toLocaleDateString('es-CO',{weekday:'long',day:'numeric',month:'long'})}`}
        action={<Btn variant="secondary" onClick={()=>dlExcel('/reportes/cobro','cobro_afiliacion.xlsx')}>⬇ Excel</Btn>} />

      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        <StatCard label="Cobrar hoy"       value={nHoy}          color={C.green} />
        <StatCard label="Vencidos"         value={nVenc}         color={C.red} />
        <StatCard label="Planilla pend."   value={fmt(planPend)} color={C.amber} />
        <StatCard label="Cobrados mes"     value={nCobr}         color={C.blue} />
        <StatCard label="Total mostrados"  value={rowsFiltrados.length} color={C.primary} />
      </div>

      <BarraFiltros
        filtros={[
          { key:'empresa', label:'Empresa', icon:'🏢', options: listas.empresas||[] },
          { key:'cliente', label:'Cliente', icon:'👤', options: clientesUnicos },
          { key:'estado',  label:'Estado',  icon:'📌', options: estadosOpts },
          { key:'subtipo', label:'Subtipo', icon:'🔢', options: subtiposUnicos },
        ]}
        valores={filtros}
        onChange={setFiltro}
        onLimpiar={limpiar}
      />

      <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
        <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
          <thead>
            <tr style={{ background:C.surface2 }}>
              {['','Nombre','Empresa','Doc.','Subtipo','Cliente','Día cobro','Servicios','Planilla ($)','Estado','Acción'].map(h=>(
                <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                  color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={11} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
            {!isLoading && rowsFiltrados.length===0 && (
              <tr><td colSpan={11} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin resultados.</td></tr>
            )}
            {rowsFiltrados.map(r => {
              const cfg  = ESTADO_CONFIG[r.estado]||ESTADO_CONFIG.PROXIMO;
              const afil = todosAfil.find(a=>a.doc===r.doc);
              const isExp= expanded===r.id;
              return (
                <React.Fragment key={r.id}>
                  <tr style={{ borderBottom:`1px solid ${C.border}`, background:r.estado==='VENCIDO'?'#FFF5F5':'#fff' }}>
                    <td style={{ padding:'8px 10px', width:32 }}>
                      <button onClick={()=>setExp(isExp?null:r.id)}
                        style={{ background:'none',border:'none',cursor:'pointer',fontSize:14,color:C.text2,padding:0 }}>
                        {isExp?'▼':'▶'}
                      </button>
                    </td>
                    <td style={tdc}><span style={{ fontWeight:500 }}>{r.nombre}</span></td>
                    <td style={tdc}>{r.empresa}</td>
                    <td style={{ ...tdc,fontFamily:'monospace',fontSize:12 }}>{r.doc}</td>
                    <td style={tdc}>{afil?.subtipo?<span style={{ background:C.surface2,border:`1px solid ${C.border}`,borderRadius:5,padding:'2px 8px',fontSize:11 }}>{afil.subtipo}</span>:'—'}</td>
                    <td style={tdc}>{r.cliente||'—'}</td>
                    <td style={{ ...tdc,fontWeight:600,color:C.primary }}>Día {r.dia_cobro}</td>
                    <td style={tdc}>
                      <div style={{ display:'flex',flexWrap:'wrap',gap:3 }}>
                        {(r.servicios||[]).map(s=>(
                          <span key={s} style={{ background:C.blueBg,color:C.blue,borderRadius:5,padding:'1px 7px',fontSize:10,fontWeight:600 }}>{s}</span>
                        ))}
                      </div>
                    </td>
                    <td style={{ ...tdc,textAlign:'right',fontWeight:700,color:C.red }}>{fmt(r.planilla)}</td>
                    <td style={tdc}>
                      <span style={{ background:cfg.bg,color:cfg.fg,borderRadius:10,padding:'3px 10px',fontSize:11,fontWeight:700,whiteSpace:'nowrap' }}>
                        {cfg.label}
                      </span>
                    </td>
                    <td style={tdc}>
                      {r.estado!=='COBRADO'
                        ? <Btn size="sm" variant="primary" onClick={()=>crearFactura.mutate(r)} disabled={crearFactura.isPending}>🧾 Facturar</Btn>
                        : <span style={{ fontSize:11,color:C.blue }}>✓ Facturado</span>
                      }
                    </td>
                  </tr>
                  {isExp && (
                    <tr style={{ background:C.surface2,borderBottom:`1px solid ${C.border}` }}>
                      <td colSpan={11} style={{ padding:'12px 20px' }}>
                        <PlanillaDetalle afiliado={afil} config={config} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PlanillaDetalle({ afiliado, config }) {
  if (!afiliado||!config) return <div style={{ color:C.text2,fontSize:12 }}>Sin datos</div>;
  const ceil100 = v=>Math.ceil(v/100)*100;
  const ibc  = (afiliado.ibc&&afiliado.ibc>0)?afiliado.ibc:(config.ibc_global||1950905);
  const pcts = config.porcentajes||{};
  const seen = new Set(); const detalle=[];
  for (const s of (afiliado.servicios||[])) {
    const su=s.toUpperCase(); let key=null;
    if(su.includes('EPS')) key='EPS';
    else if(su.includes('CCF')||su.includes('CAJA')) key='CCF';
    else if(su.includes('AFP')||su.includes('PENSION')) key='AFP';
    else if(su.includes('ARL')) { for(const n of['1','2','3','4','5']){if(su.includes(n)){key=`ARL ${n}`;break;}} }
    if(!key) key=s;
    if(!seen.has(key)){seen.add(key);const pct=pcts[key]||0;detalle.push({servicio:key,pct,val30:ceil100(ibc*pct),val15:ceil100(ibc*pct/2)});}
  }
  if(afiliado.arl&&afiliado.arl!=='N/A'){const k=`ARL ${afiliado.arl}`;if(!seen.has(k)){const pct=pcts[k]||0;detalle.push({servicio:k,pct,val30:ceil100(ibc*pct),val15:ceil100(ibc*pct/2)});}}
  const total30=detalle.reduce((s,d)=>s+d.val30,0);
  return (
    <div>
      <div style={{ fontSize:12,fontWeight:600,color:C.primary,marginBottom:8 }}>
        📋 Planilla detallada — IBC: {fmt(ibc)}{afiliado.ibc?' ⚡ propio':' (global)'}
      </div>
      <div style={{ display:'flex',gap:6,flexWrap:'wrap',alignItems:'center' }}>
        {detalle.map(d=>(
          <div key={d.servicio} style={{ background:'#fff',border:`1px solid ${C.border}`,borderRadius:8,padding:'8px 14px',minWidth:130 }}>
            <div style={{ fontSize:11,fontWeight:700,color:C.primary,marginBottom:2 }}>{d.servicio}</div>
            <div style={{ fontSize:10,color:C.text2 }}>{(d.pct*100).toFixed(4).replace(/\.?0+$/,'')}%</div>
            <div style={{ fontSize:14,fontWeight:700,color:C.red,marginTop:2 }}>{fmt(d.val30)}</div>
            <div style={{ fontSize:10,color:C.text2 }}>15d: {fmt(d.val15)}</div>
          </div>
        ))}
        {detalle.length>0&&(
          <div style={{ background:C.primary,borderRadius:8,padding:'8px 14px',minWidth:130 }}>
            <div style={{ fontSize:11,fontWeight:700,color:'rgba(255,255,255,.7)',marginBottom:2 }}>TOTAL 30d</div>
            <div style={{ fontSize:16,fontWeight:700,color:'#fff' }}>{fmt(total30)}</div>
          </div>
        )}
      </div>
      <div style={{ marginTop:8,fontSize:11,color:C.text2,display:'flex',gap:16,flexWrap:'wrap' }}>
        <span>📅 Afiliación: <strong>{afiliado.fecha_afiliacion||'—'}</strong></span>
        <span>🏢 Empresa: <strong>{afiliado.empresa||'—'}</strong></span>
        <span>🔢 Subtipo: <strong>{afiliado.subtipo||'—'}</strong></span>
        <span>📞 Tel: <strong>{afiliado.tel||'—'}</strong></span>
      </div>
    </div>
  );
}

const tdc = { padding:'10px 12px',fontSize:13,color:'#1E293B',verticalAlign:'middle' };
