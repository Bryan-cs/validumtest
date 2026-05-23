import React, { useState, useMemo, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../utils/api';
import { C, Btn, PageHeader, StatCard, fmt, ErrorMsg } from '../components/UI';
import { BarraFiltros } from '../components/FiltroCheck';
import { NuevaFacturaModal } from './Facturacion';

async function dlExcel(url, filename) {
  try {
    const res = await api.get(url, { responseType: 'blob' });
    const objUrl = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = objUrl;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(objUrl);
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || 'Error generando reporte';
    const { toast: _toast } = await import('sonner');
    _toast.error(typeof msg === 'string' ? msg : 'Error generando reporte');
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

const ANIOS = [String(new Date().getFullYear()), String(new Date().getFullYear() - 1)];
const POR_PAG = 50;

function loadFiltrosCobro() {
  try { return JSON.parse(localStorage.getItem('bbc_cobro_filtros')) ?? {}; }
  catch { return {}; }
}

export default function Cobro() {
  const saved = loadFiltrosCobro();
  const [filtros,    setFiltros]    = useState(saved.filtros    ?? { empresa:[], cliente:[], estado:[], subtipo:[] });
  const [expanded,   setExp]        = useState(null);
  const [novedadModal, setNovedadModal] = useState(null);
  const [facturaAfil, setFacturaAfil] = useState(null);
  const [mesFiltro,  setMesFiltro]  = useState(saved.mesFiltro  ?? '');
  const [anioFiltro, setAnioFiltro] = useState(saved.anioFiltro ?? '');
  const [docBuscar,  setDocBuscar]  = useState(saved.docBuscar  ?? '');
  const [docFiltro,  setDocFiltro]  = useState(saved.docFiltro  ?? '');
  const [pagina, setPagina] = useState(1);

  useEffect(() => { try { localStorage.setItem('bbc_cobro_filtros', JSON.stringify({ filtros, mesFiltro, anioFiltro, docBuscar, docFiltro })); } catch {} }, [filtros, mesFiltro, anioFiltro, docBuscar, docFiltro]);

  const setFiltro = (key, vals) => { setFiltros(f => ({ ...f, [key]: vals })); setPagina(1); };
  const limpiar   = () => { setFiltros({ empresa:[], cliente:[], estado:[], subtipo:[] }); setDocBuscar(''); setDocFiltro(''); setPagina(1); };

  const { data: listas = {} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });
  const { data: config = {} } = useQuery({ queryKey:['config'], queryFn:()=>api.get('/config').then(r=>r.data) });
  const qc = useQueryClient();
  const { data: rows = [], isLoading, isError: isErrorCobro, refetch: refetchCobro } = useQuery({
    queryKey: ['cobro', mesFiltro, anioFiltro, docFiltro],
    queryFn: () => api.get('/cobro', { params:{ empresa:'', cliente:'', tipo:'', mes: mesFiltro, anio: anioFiltro, doc: docFiltro } }).then(r=>r.data),
    refetchInterval: 60_000,
    placeholderData: (prev) => prev,
  });

  const clientesUnicos = useMemo(() => [...new Set(rows.map(r=>r.cliente).filter(Boolean))].sort(), [rows]);
  const subtiposUnicos = useMemo(() => [...new Set(rows.map(r=>r.subtipo).filter(Boolean))].sort(), [rows]);
  const estadosOpts    = ['COBRAR HOY','VENCIDO','PRÓXIMO','COBRADO'];

  const hoy = new Date();
  const mesActualNombre = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][hoy.getMonth()];
  const anioActualStr = String(hoy.getFullYear());

  const rowsFiltrados = useMemo(() => rows.filter(r => {
    const labelEstado = ESTADO_CONFIG[r.estado]?.label || r.estado;
    // Ocultar COBRADO de meses anteriores a menos que el usuario filtre explícitamente por COBRADO
    if (r.estado === 'COBRADO') {
      const filtrandoPorCobrado = filtros.estado.includes('COBRADO');
      if (!filtrandoPorCobrado) return false; // ocultar todos los cobrados por defecto
      // si filtra por COBRADO: solo mostrar mes actual
      const esMesActual = r.mes === mesActualNombre && r.anio === anioActualStr;
      if (!esMesActual) return false;
    }
    if (filtros.empresa.length  && !filtros.empresa.includes(r.empresa))    return false;
    if (filtros.cliente.length  && !filtros.cliente.includes(r.cliente))    return false;
    if (filtros.estado.length   && !filtros.estado.includes(labelEstado))   return false;
    if (filtros.subtipo.length  && !filtros.subtipo.includes(r.subtipo))    return false;
    return true;
  }), [rows, filtros, mesActualNombre, anioActualStr]);

  const totalPags   = Math.max(1, Math.ceil(rowsFiltrados.length / POR_PAG));
  const rowsPagina  = rowsFiltrados.slice((pagina - 1) * POR_PAG, pagina * POR_PAG);

  const { nHoy, nVenc, nCobr, planPend } = useMemo(() => {
    let nHoy=0, nVenc=0, nCobr=0, planPend=0;
    for (const r of rowsFiltrados) {
      if (r.estado==='HOY') { nHoy++; planPend+=r.planilla; }
      else if (r.estado==='VENCIDO') { nVenc++; planPend+=r.planilla; }
      else if (r.estado==='COBRADO') nCobr++;
    }
    return { nHoy, nVenc, nCobr, planPend };
  }, [rowsFiltrados]);


  return (
    <div>
      <PageHeader title="💰 Módulo de cobro"
        subtitle={`${rowsFiltrados.length} afiliados — ${new Date().toLocaleDateString('es-CO',{weekday:'long',day:'numeric',month:'long'})}`}
        action={<Btn variant="secondary" onClick={()=>dlExcel('/reportes/cobro','cobro_afiliacion.xlsx')}>⬇ Excel</Btn>} />

      {isErrorCobro && <ErrorMsg message="Error al cargar datos de cobro" onRetry={refetchCobro} />}
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        <StatCard label="Cobrar hoy"       value={nHoy}          color={C.green} />
        <StatCard label="Vencidos"         value={nVenc}         color={C.red} />
        <StatCard label="Planilla pend."   value={fmt(planPend)} color={C.amber} />
        <StatCard label="Cobrados mes"     value={nCobr}         color={C.blue} />
        <StatCard label="Total mostrados"  value={rowsFiltrados.length} color={C.primary} />
      </div>

      {/* Búsqueda por documento */}
      <div style={{ display:'flex', gap:10, alignItems:'center', marginBottom:12, flexWrap:'wrap' }}>
        <div style={{ position:'relative', flex:'0 0 auto' }}>
          <input
            type="text"
            value={docBuscar}
            onChange={e => setDocBuscar(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { setDocFiltro(docBuscar.trim()); setPagina(1); } }}
            placeholder="🔍 Buscar por N° documento..."
            style={{ padding:'7px 12px', paddingRight:70, borderRadius:7, border:`1px solid ${C.border}`,
              fontSize:13, color:C.text, background:C.surface, width:260 }}
          />
          <button
            onClick={() => { setDocFiltro(docBuscar.trim()); setPagina(1); }}
            style={{ position:'absolute', right:4, top:'50%', transform:'translateY(-50%)',
              padding:'4px 12px', borderRadius:5, border:'none', background:C.primary,
              color:'#fff', fontSize:12, fontWeight:600, cursor:'pointer' }}>
            Buscar
          </button>
        </div>
        {docFiltro && (
          <div style={{ display:'flex', alignItems:'center', gap:6, background:C.blueBg,
            border:`1px solid ${C.blue}`, borderRadius:7, padding:'5px 12px' }}>
            <span style={{ fontSize:12, color:C.blue, fontWeight:600 }}>
              Doc: {docFiltro}
            </span>
            <button onClick={() => { setDocBuscar(''); setDocFiltro(''); setPagina(1); }}
              style={{ background:'none', border:'none', cursor:'pointer', fontSize:14, color:C.blue, padding:0 }}>✕</button>
          </div>
        )}

        {/* Filtro mes / año */}
        <select value={mesFiltro} onChange={e=>{ setMesFiltro(e.target.value); setPagina(1); }}
          style={{ padding:'7px 12px', borderRadius:7, border:`1px solid ${C.border}`, fontSize:13, color:C.text, background:C.surface }}>
          <option value="">Todos los meses</option>
          {MESES.map(m=><option key={m} value={m}>{m}</option>)}
        </select>
        <select value={anioFiltro} onChange={e=>{ setAnioFiltro(e.target.value); setPagina(1); }}
          style={{ padding:'7px 12px', borderRadius:7, border:`1px solid ${C.border}`, fontSize:13, color:C.text, background:C.surface }}>
          <option value="">Todos los años</option>
          {ANIOS.map(a=><option key={a} value={a}>{a}</option>)}
        </select>
        {(mesFiltro||anioFiltro||docFiltro) && (
          <button onClick={()=>{ setMesFiltro(''); setAnioFiltro(''); setDocBuscar(''); setDocFiltro(''); setPagina(1); }}
            style={{ padding:'7px 14px', borderRadius:7, border:`1px solid ${C.border}`, background:C.surface2, fontSize:12, cursor:'pointer', color:C.text2 }}>
            ✕ Limpiar filtros
          </button>
        )}
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
        <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
          <thead>
            <tr style={{ background:C.surface2 }}>
              {['','Afiliado','Doc.','Subtipo','Cliente','Período','Día cobro','Servicios','Planilla ($)','Estado','Novedades',''].map(h=>(
                <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                  color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={12} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
            {!isLoading && rowsFiltrados.length===0 && (
              <tr><td colSpan={12} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin resultados.</td></tr>
            )}
            {rowsPagina.map(r => {
              const cfg   = ESTADO_CONFIG[r.estado]||ESTADO_CONFIG.PROXIMO;
              const isExp = expanded===r.id;
              const rowBg = r.estado==='VENCIDO' ? C.redBg : r.estado==='HOY' ? C.greenBg : C.surface;
              return (
                <React.Fragment key={r.id}>
                  <tr
                    style={{ borderBottom:`1px solid ${C.border}`, background:rowBg, cursor:'pointer', transition:'background .1s' }}
                    onClick={()=>setExp(isExp?null:r.id)}
                    onMouseEnter={e=>{
                      if(r.estado!=='VENCIDO'&&r.estado!=='HOY') e.currentTarget.style.background=C.surface2;
                      qc.prefetchQuery({
                        queryKey: ['facturas_cobro', r.doc],
                        queryFn: () => api.get('/facturas', { params:{ doc: r.doc, limit:0 } }).then(res => res.data.items || []),
                        staleTime: 30_000,
                      });
                    }}
                    onMouseLeave={e=>{ e.currentTarget.style.background=rowBg; }}>
                    <td style={{ padding:'8px 10px', width:32 }}>
                      <span style={{ fontSize:12, color:C.text2 }}>{isExp?'▼':'▶'}</span>
                    </td>
                    <td style={tdc}>
                      <div style={{ fontWeight:700, color:C.text, fontSize:14 }}>{r.nombre}</div>
                      <div style={{ fontSize:11, color:C.text2, marginTop:1 }}>{r.empresa}</div>
                    </td>
                    <td style={{ ...tdc, fontFamily:'monospace', fontSize:13, color:C.text, fontWeight:600 }}>{r.doc}</td>
                    <td style={tdc}>
                      {r.subtipo
                        ? <span style={{ background:C.surface2,border:`1px solid ${C.border}`,borderRadius:5,padding:'2px 8px',fontSize:11,fontWeight:600 }}>{r.subtipo}</span>
                        : <span style={{ color:C.text2 }}>—</span>}
                    </td>
                    <td style={{ ...tdc, color:C.text, fontSize:13, fontWeight:600 }}>{r.cliente||'—'}</td>
                    <td style={{ ...tdc, fontWeight:700, color:C.primary, whiteSpace:'nowrap' }}>{r.mes} {r.anio}</td>
                    <td style={{ ...tdc, whiteSpace:'nowrap' }}>
                      <span style={{ background:C.blueBg, color:C.blue, borderRadius:6, padding:'2px 9px', fontSize:11, fontWeight:700 }}>
                        Día {r.dia_cobro}
                      </span>
                    </td>
                    <td style={tdc}>
                      <div style={{ display:'flex',flexWrap:'wrap',gap:3 }}>
                        {(r.servicios||[]).map(s=>(
                          <span key={s} style={{ background:C.blueBg,color:C.blue,borderRadius:5,padding:'1px 7px',fontSize:10,fontWeight:600 }}>{s}</span>
                        ))}
                      </div>
                    </td>
                    <td style={{ ...tdc, textAlign:'right', fontWeight:700, color:C.red, fontSize:14 }}>{fmt(r.planilla)}</td>
                    <td style={tdc}>
                      <span style={{ background:cfg.bg,color:cfg.fg,borderRadius:10,padding:'3px 12px',fontSize:11,fontWeight:700,whiteSpace:'nowrap' }}>
                        {cfg.label}
                      </span>
                    </td>
                    <td style={{ ...tdc, maxWidth:180 }} title={r.novedades||undefined}>
                      {r.novedades ? (
                        <span onClick={e=>{e.stopPropagation();setNovedadModal({nombre:r.nombre,texto:r.novedades});}}
                          style={{ fontSize:11,color:C.amber,fontWeight:600,cursor:'pointer',
                            display:'block',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis' }}>
                          📝 {r.novedades}
                        </span>
                      ) : <span style={{ fontSize:11,color:C.text2 }}>—</span>}
                    </td>
                    <td style={{ ...tdc, width:110 }} onClick={e=>e.stopPropagation()}>
                      <button
                        title="Generar factura"
                        onClick={e=>{ e.stopPropagation(); setFacturaAfil({ doc: r.doc }); }}
                        style={{ padding:'6px 12px', borderRadius:7, border:'none',
                          background:C.primary, color:'#fff', cursor:'pointer', fontSize:12,
                          fontWeight:700, whiteSpace:'nowrap', display:'flex', alignItems:'center', gap:5 }}>
                        🧾 Facturar
                      </button>
                    </td>
                  </tr>
                  {isExp && (
                    <tr style={{ background:C.surface2, borderBottom:`1px solid ${C.border}` }}>
                      <td colSpan={12} style={{ padding:'12px 20px' }}>
                        <PlanillaDetalle afiliado={r} cobroRow={r} config={config} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Paginación */}
      {totalPags > 1 && (
        <div style={{ display:'flex', justifyContent:'center', alignItems:'center', gap:6, marginTop:14, flexWrap:'wrap' }}>
          <button onClick={()=>setPagina(1)} disabled={pagina===1} style={btnPag}>«</button>
          <button onClick={()=>setPagina(p=>Math.max(1,p-1))} disabled={pagina===1} style={btnPag}>‹</button>
          {[...Array(Math.min(5, totalPags))].map((_,i) => {
            const p = pagina <= 3 ? i+1 : pagina - 2 + i;
            if (p < 1 || p > totalPags) return null;
            return <button key={p} onClick={()=>setPagina(p)} style={{ ...btnPag, fontWeight: p===pagina?700:400, background: p===pagina ? C.primary : C.surface2, color: p===pagina ? '#fff' : C.text }}>{p}</button>;
          })}
          <button onClick={()=>setPagina(p=>Math.min(totalPags,p+1))} disabled={pagina===totalPags} style={btnPag}>›</button>
          <button onClick={()=>setPagina(totalPags)} disabled={pagina===totalPags} style={btnPag}>»</button>
          <span style={{ fontSize:12, color:C.text2, marginLeft:4 }}>Pág {pagina}/{totalPags} · {rowsFiltrados.length} total</span>
        </div>
      )}

      <NuevaFacturaModal
        open={!!facturaAfil}
        onClose={() => setFacturaAfil(null)}
        config={config}
        listas={listas}
        prefill={facturaAfil}
      />

      {/* Modal novedades completas */}
      {novedadModal && (
        <div onClick={() => setNovedadModal(null)}
          style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.45)', zIndex:1000,
            display:'flex', alignItems:'center', justifyContent:'center' }}>
          <div onClick={e => e.stopPropagation()}
            style={{ background:C.surface, borderRadius:12, padding:28, maxWidth:520, width:'90%',
              boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
              <span style={{ fontWeight:700, fontSize:14, color:C.primary }}>
                📝 Novedades — {novedadModal.nombre}
              </span>
              <button onClick={() => setNovedadModal(null)}
                style={{ background:'none', border:'none', cursor:'pointer', fontSize:18, color:C.text2 }}>✕</button>
            </div>
            <p style={{ margin:0, fontSize:14, color:C.text, lineHeight:1.6, whiteSpace:'pre-wrap' }}>
              {novedadModal.texto}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanillaDetalle({ afiliado, cobroRow, config }) {
  const { data: facturas=[] } = useQuery({
    queryKey: ['facturas_cobro', afiliado?.doc],
    queryFn: () => api.get('/facturas', { params:{ doc: afiliado.doc, limit:0 } }).then(r=>r.data.items||[]),
    enabled: !!afiliado?.doc,
    staleTime: 30_000,
  });

  if (!afiliado||!config) return <div style={{ color:C.text2,fontSize:12 }}>Sin datos</div>;
  const ceil100 = v=>Math.ceil(v/100)*100;
  const ibc  = (afiliado.ibc&&afiliado.ibc>0)?afiliado.ibc:(config.ibc_global||1750905);
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
          <div key={d.servicio} style={{ background:C.surface,border:`1px solid ${C.border}`,borderRadius:8,padding:'8px 14px',minWidth:130 }}>
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
        {afiliado.novedades && (
          <span style={{ color:C.amber,fontWeight:600 }}>📝 Novedades: <strong>{afiliado.novedades}</strong></span>
        )}
      </div>

      {/* Historial de pagos */}
      {facturas.length > 0 && (
        <div style={{ marginTop:12 }}>
          <div style={{ fontSize:11,fontWeight:700,color:C.primary,marginBottom:6 }}>💳 Historial de pagos</div>
          <div style={{ display:'flex',flexWrap:'wrap',gap:4 }}>
            {facturas.slice(0,12).map(f=>(
              <div key={f.id} style={{
                background: f.estado==='pagado'?C.greenBg:C.amberBg,
                border:`1px solid ${f.estado==='pagado'?C.green:C.amber}`,
                borderRadius:7, padding:'4px 10px', fontSize:10,
              }}>
                <span style={{ fontWeight:700,color:f.estado==='pagado'?C.green:C.amber }}>
                  {f.mes} {f.anio}
                </span>
                <span style={{ color:C.text2,marginLeft:4 }}>{f.estado==='pagado'?'✓ Pagado':'⏳ Pend.'}</span>
                {f.ingresos>0 && <span style={{ color:C.text2,marginLeft:4 }}>${Number(f.ingresos).toLocaleString('es-CO')}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const tdc   = { padding:'10px 12px',fontSize:13,color:C.text,verticalAlign:'middle' };
const btnPag = { padding:'5px 10px', borderRadius:6, border:`1px solid ${C.border}`, background:C.surface2, cursor:'pointer', fontSize:13, color:C.text };
