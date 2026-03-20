import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import { C, Btn, Modal, PageHeader, statusBadge } from '../components/UI';
import { BarraFiltros } from '../components/FiltroCheck';

const SERVICIOS = ['EPS','AFP','CCF','ARL 1','ARL 2','ARL 3','ARL 4','ARL 5'];
const ESTADOS_SRV = ['ACTIVO','SUSPENDIDO','DOBLE AFILIACION','EN ESPERA DE ACTIVACION',
                     'RETIRADO','EN MORA','NO AFILIADO','PENDIENTE'];
const UP = (v) => (v||'').toUpperCase();

const InputUp = ({ label, value, onChange, placeholder, type='text', style, readOnly }) => (
  <div style={{ marginBottom:12, ...style }}>
    {label && <label style={lbl}>{label}</label>}
    <input type={type} value={value} readOnly={readOnly}
      onChange={e => onChange(type==='text'||type==='tel' ? UP(e.target.value) : e.target.value)}
      placeholder={placeholder}
      style={{ width:'100%',padding:'9px 12px',border:`1px solid ${C.border}`,borderRadius:7,
        fontSize:13,outline:'none',boxSizing:'border-box',color:C.text,
        textTransform:(type==='text'||type==='tel')?'uppercase':'none',
        background: readOnly ? C.surface2 : '#fff' }} />
  </div>
);

const Sel = ({ label, value, onChange, options=[], style }) => (
  <div style={{ marginBottom:12, ...style }}>
    {label && <label style={lbl}>{label}</label>}
    <select value={value} onChange={e=>onChange(e.target.value)}
      style={{ width:'100%',padding:'9px 12px',border:`1px solid ${C.border}`,borderRadius:7,
        fontSize:13,outline:'none',boxSizing:'border-box',color:C.text,background:'#fff' }}>
      {options.map(o=>typeof o==='string'
        ?<option key={o} value={o}>{o||'—'}</option>
        :<option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  </div>
);

export default function Afiliados() {
  const qc = useQueryClient();
  const [tab, setTab]           = useState('activos'); // 'activos' | 'eliminados'
  const [busqueda, setBusqueda] = useState('');
  const [filtros,  setFiltros]  = useState({ estado:[], empresa:[], cliente:[], subtipo:[] });
  const [modal,    setModal]    = useState(null);
  const [form,     setForm]     = useState({});

  const setFiltro = (key,vals) => setFiltros(f=>({...f,[key]:vals}));
  const limpiar   = () => setFiltros({ estado:[], empresa:[], cliente:[], subtipo:[] });

  const [pagina, setPagina] = useState(1);
  const POR_PAG = 50;

  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data) });
  // Sin paginación: para filtros y exportaciones
  const { data: todos=[] } = useQuery({
    queryKey:['afiliados_all'],
    queryFn:()=>api.get('/afiliados').then(r=>r.data.items||[]),
  });
  // Con paginación: para la tabla principal
  const { data: resp={total:0,items:[]}, isLoading } = useQuery({
    queryKey:['afiliados', pagina],
    queryFn:()=>api.get('/afiliados', { params:{ skip:(pagina-1)*POR_PAG, limit:POR_PAG } }).then(r=>r.data),
    keepPreviousData: true,
  });
  const data     = resp.items || [];
  const totalReg = resp.total || 0;
  const totalPags = Math.ceil(totalReg / POR_PAG);
  const { data: actividad=[] } = useQuery({ queryKey:['actividad'], queryFn:()=>api.get('/actividad').then(r=>r.data) });
  const { data: eliminados=[], isLoading: loadElim } = useQuery({
    queryKey:['eliminados'], queryFn:()=>api.get('/eliminados').then(r=>r.data),
    enabled: tab === 'eliminados',
  });

  const clientesUnicos = [...new Set(todos.map(a=>a.cliente_txt).filter(Boolean))].sort();
  const subtiposUnicos = [...new Set(todos.map(a=>a.subtipo).filter(Boolean))].sort();
  const estadosOpts    = [...new Set(todos.map(a=>a.estado_srv||a.estado).filter(Boolean))].sort();

  const dataFiltrada = data.filter(a => {
    const q = busqueda.toLowerCase();
    if (busqueda && !`${a.nombre} ${a.doc} ${a.empresa} ${a.cliente_txt}`.toLowerCase().includes(q)) return false;
    if (filtros.empresa.length && !filtros.empresa.includes(a.empresa))               return false;
    if (filtros.cliente.length && !filtros.cliente.includes(a.cliente_txt))           return false;
    if (filtros.estado.length  && !filtros.estado.includes(a.estado_srv||a.estado))   return false;
    if (filtros.subtipo.length && !filtros.subtipo.includes(a.subtipo))               return false;
    return true;
  });

  const sf = (k,v) => setForm(f=>({...f,[k]:v}));
  const openNuevo  = () => { setForm({ empresa:'', servicios:[], subtipo:'0', estado:'ACTIVO', estado_srv:'ACTIVO' }); setModal('nuevo'); };
  const openEditar = (a) => { setForm({...a}); setModal(a); };
  const toggleSrv  = (s) => { const srvs=form.servicios||[]; sf('servicios', srvs.includes(s)?srvs.filter(x=>x!==s):[...srvs,s]); };

  const guardar = useMutation({
    mutationFn: () => {
      const payload = { ...form,
        fecha_ingreso:    form.fecha_ingreso    || new Date().toISOString().slice(0,10),
        fecha_afiliacion: form.fecha_afiliacion || new Date().toISOString().slice(0,10),
      };
      return modal==='nuevo' ? api.post('/afiliados',payload) : api.put(`/afiliados/${modal.id}`,payload);
    },
    onSuccess: () => { toast.success(modal==='nuevo'?'Afiliado registrado':'Actualizado'); qc.invalidateQueries({queryKey:['afiliados']}); qc.invalidateQueries({queryKey:['afiliados_all']}); setModal(null); },
    onError: e => toast.error(e.response?.data?.detail||'Error'),
  });

  const eliminar = useMutation({
    mutationFn: id => api.delete(`/afiliados/${id}`),
    onSuccess: res => { const n=res.data?.facturas_pendientes; toast.success(n?`Eliminado. ${n} factura(s) conservadas`:'Afiliado eliminado'); qc.invalidateQueries({queryKey:['afiliados']}); qc.invalidateQueries({queryKey:['afiliados_all']}); qc.invalidateQueries({queryKey:['eliminados']}); },
    onError: e => toast.error(e.response?.data?.detail||'Error'),
  });

  const restaurar = useMutation({
    mutationFn: id => api.post(`/eliminados/${id}/restaurar`),
    onSuccess: res => { toast.success(`✅ ${res.data.nombre} restaurado como ACTIVO`); qc.invalidateQueries({queryKey:['afiliados']}); qc.invalidateQueries({queryKey:['afiliados_all']}); qc.invalidateQueries({queryKey:['eliminados']}); },
    onError: e => toast.error(e.response?.data?.detail||'Error al restaurar'),
  });

  // Historial filtrado por afiliado seleccionado
  const [afilSelHist, setAfilSelHist] = useState(null);
  const histAfil = actividad.filter(a => afilSelHist && a.detalle?.includes(afilSelHist));

  return (
    <div>
      <PageHeader title="👥 Afiliados"
        subtitle={tab==='activos' ? `${dataFiltrada.length} de ${totalReg} registros` : `${eliminados.length} eliminados`}
        action={tab==='activos' && <Btn variant="accent" onClick={openNuevo}>+ Nuevo afiliado</Btn>} />

      {/* Pestañas */}
      <div style={{ display:'flex', gap:4, marginBottom:16, borderBottom:`2px solid ${C.border}`, paddingBottom:0 }}>
        {[
          { key:'activos',    label:`👥 Activos (${totalReg})` },
          { key:'eliminados', label:`🗑️ Eliminados (${eliminados.length || '...'})` },
          { key:'historial',  label:'📋 Historial de cambios' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            padding:'9px 18px', border:'none', borderRadius:'7px 7px 0 0',
            background: tab===t.key ? C.primary : 'transparent',
            color: tab===t.key ? '#fff' : C.text2,
            fontWeight: tab===t.key ? 700 : 400, fontSize:13, cursor:'pointer',
            borderBottom: tab===t.key ? `2px solid ${C.primary}` : 'none',
            marginBottom: tab===t.key ? -2 : 0,
          }}>{t.label}</button>
        ))}
      </div>

      {/* ═══ TAB: ACTIVOS ═══ */}
      {tab === 'activos' && (
        <>
          <input placeholder="🔍 Buscar nombre, documento, empresa, cliente..."
            value={busqueda} onChange={e=>setBusqueda(e.target.value)}
            style={{ width:'100%',padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
              fontSize:13,outline:'none',marginBottom:12,boxSizing:'border-box' }} />
          <BarraFiltros
            filtros={[
              { key:'empresa', label:'Empresa', icon:'🏢', options: listas.empresas||[] },
              { key:'cliente', label:'Cliente', icon:'👤', options: clientesUnicos },
              { key:'estado',  label:'Estado',  icon:'📌', options: estadosOpts },
              { key:'subtipo', label:'Subtipo', icon:'🔢', options: subtiposUnicos },
            ]}
            valores={filtros} onChange={setFiltro} onLimpiar={limpiar}
          />
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
              <thead>
                <tr style={{ background:C.surface2 }}>
                  {['Nombre','Empresa','Documento','Cliente','Subtipo','EPS','ARL','Servicios','Estado','Novedades','Acciones'].map(h=>(
                    <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                      color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading && <tr><td colSpan={11} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
                {!isLoading && dataFiltrada.length===0 && (
                  <tr><td colSpan={11} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin registros</td></tr>
                )}
                {dataFiltrada.map(a=>(
                  <tr key={a.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                    <td style={tdc}>
                      <span style={{ fontWeight:600, cursor:'pointer', color:C.primary }}
                        onClick={() => { setAfilSelHist(a.nombre); setTab('historial'); }}>
                        {a.nombre}
                      </span>
                    </td>
                    <td style={tdc}>{a.empresa||'—'}</td>
                    <td style={{ ...tdc,fontFamily:'monospace',fontSize:12 }}>{a.doc}</td>
                    <td style={tdc}>{a.cliente_txt||'—'}</td>
                    <td style={tdc}>{a.subtipo?<Chip>{a.subtipo}</Chip>:'—'}</td>
                    <td style={tdc}><span style={{ fontSize:11,color:C.text2 }}>{a.eps||'—'}</span></td>
                    <td style={tdc}><span style={{ fontSize:11,color:C.text2 }}>{a.arl||'—'}</span></td>
                    <td style={tdc}>
                      <div style={{ display:'flex',flexWrap:'wrap',gap:3 }}>
                        {(a.servicios||[]).map(s=><SrvChip key={s}>{s}</SrvChip>)}
                      </div>
                    </td>
                    <td style={tdc}>{statusBadge(a.estado_srv||a.estado)}</td>
                    <td style={{ ...tdc,maxWidth:160 }}>
                      <span style={{ fontSize:11,color:C.text2,display:'-webkit-box',
                        WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden' }}>
                        {a.obs||'—'}
                      </span>
                    </td>
                    <td style={tdc}>
                      <div style={{ display:'flex',gap:6 }}>
                        <Btn size="sm" variant="secondary" onClick={()=>openEditar(a)}>✏️ Editar</Btn>
                        <Btn size="sm" variant="danger" onClick={()=>{ if(window.confirm(`¿Eliminar a ${a.nombre}?`)) eliminar.mutate(a.id); }}>×</Btn>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ═══ TAB: ELIMINADOS ═══ */}
      {tab === 'eliminados' && (
        <div>
          <div style={{ background:C.amberBg, border:`1px solid ${C.amber}`, borderRadius:8,
            padding:'10px 14px', marginBottom:14, fontSize:12, color:C.amber, fontWeight:500 }}>
            ⚠️ Afiliados eliminados del sistema. Puedes restaurarlos como ACTIVOS con el botón ↩ Restaurar.
          </div>
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
              <thead>
                <tr style={{ background:C.surface2 }}>
                  {['Nombre','Empresa','Documento','Mes','Fecha eliminación','Eliminado por','Acciones'].map(h=>(
                    <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                      color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loadElim && <tr><td colSpan={7} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
                {!loadElim && eliminados.length===0 && (
                  <tr><td colSpan={7} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin registros eliminados</td></tr>
                )}
                {eliminados.map(e=>(
                  <tr key={e.id} style={{ borderBottom:`1px solid ${C.border}`, background:'#FFF5F5' }}>
                    <td style={{ ...tdc,fontWeight:600,color:C.red }}>{e.nombre}</td>
                    <td style={tdc}>{e.empresa||'—'}</td>
                    <td style={{ ...tdc,fontFamily:'monospace',fontSize:12 }}>{e.doc}</td>
                    <td style={tdc}>{e.mes||'—'}</td>
                    <td style={tdc}>{e.fecha_eliminacion||'—'}</td>
                    <td style={tdc}>{e.eliminado_por||'—'}</td>
                    <td style={tdc}>
                      <Btn size="sm" variant="success"
                        onClick={() => { if(window.confirm(`¿Restaurar a ${e.nombre} como ACTIVO?`)) restaurar.mutate(e.id); }}
                        disabled={restaurar.isPending}>
                        ↩ Restaurar
                      </Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ TAB: HISTORIAL ═══ */}
      {tab === 'historial' && (
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:14, flexWrap:'wrap' }}>
            <span style={{ fontSize:13, color:C.text2 }}>Filtrar por afiliado:</span>
            <input placeholder="Escribe el nombre del afiliado..."
              value={afilSelHist||''} onChange={e=>setAfilSelHist(e.target.value)}
              style={{ padding:'8px 12px',border:`1px solid ${C.border}`,borderRadius:7,
                fontSize:13,outline:'none',width:260 }} />
            {afilSelHist && <Btn size="sm" variant="secondary" onClick={()=>setAfilSelHist(null)}>✕ Limpiar</Btn>}
            <span style={{ fontSize:11, color:C.text2, marginLeft:'auto' }}>
              💡 También puedes hacer clic en el nombre de un afiliado en la tabla para ver su historial
            </span>
          </div>
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
              <thead>
                <tr style={{ background:C.surface2 }}>
                  {['Fecha','Usuario','Acción','Módulo','Detalle'].map(h=>(
                    <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                      color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(afilSelHist ? histAfil : actividad).slice(0,100).map((a,i)=>(
                  <tr key={i} style={{ borderBottom:`1px solid ${C.border}` }}>
                    <td style={{ ...tdc,fontSize:11,color:C.text2,whiteSpace:'nowrap' }}>{a.fecha}</td>
                    <td style={{ ...tdc,fontWeight:600 }}>{a.usuario}</td>
                    <td style={tdc}>{a.accion}</td>
                    <td style={{ ...tdc,color:C.blue }}>{a.modulo}</td>
                    <td style={{ ...tdc,color:C.text2,fontSize:12 }}>{a.detalle}</td>
                  </tr>
                ))}
                {(afilSelHist ? histAfil : actividad).length===0 && (
                  <tr><td colSpan={5} style={{ padding:20,textAlign:'center',color:C.text2 }}>
                    {afilSelHist ? `Sin historial para "${afilSelHist}"` : 'Sin actividad registrada'}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── MODAL FORMULARIO ─── */}
      <Modal open={!!modal} onClose={()=>setModal(null)} width={720}
        title={modal==='nuevo'?'➕ Nuevo afiliado':`✏️ Editar — ${form.nombre||''}`}>
        <Seccion title="Datos personales" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <InputUp label="Nombre completo *" value={form.nombre||''} onChange={v=>sf('nombre',v)} />
          <InputUp label="N° Documento *"    value={form.doc||''}    onChange={v=>sf('doc',v)} />
          <InputUp label="Cargo"             value={form.cargo||''} onChange={v=>sf('cargo',v)} />
          <InputUp label="Teléfono"          value={form.tel||''} onChange={v=>sf('tel',v)} type="tel" />
          <InputUp label="Email"             value={form.email||''} onChange={v=>sf('email',v)} style={{ gridColumn:'1/-1' }} />
          <InputUp label="Dirección"         value={form.dir||''} onChange={v=>sf('dir',v)} style={{ gridColumn:'1/-1' }} />
        </div>

        <Seccion title="Empresa y contrato" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <Sel label="Razón Social" value={form.empresa||''} onChange={v=>sf('empresa',v)}
            options={['', ...(listas.empresas||[])].map(e=>({value:e,label:e||'— Seleccionar'}))} />
          <Sel label="Subtipo" value={form.subtipo||'0'} onChange={v=>sf('subtipo',v)}
            options={['0','3','4','20','22'].map(s=>({value:s,label:`Subtipo ${s}`}))} />
          <InputUp label="Cliente (empresa o persona que contrata)" value={form.cliente_txt||''}
            onChange={v=>sf('cliente_txt',v)} style={{ gridColumn:'1/-1' }} />
        </div>

        <Seccion title="Afiliaciones SS" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <Sel label="EPS"        value={form.eps||''} onChange={v=>sf('eps',v)} options={[''].concat(listas.eps||[])} />
          <Sel label="ARL"        value={form.arl||''} onChange={v=>sf('arl',v)} options={[''].concat(listas.arl||[])} />
          <Sel label="CCF (caja)" value={form.ccf||''} onChange={v=>sf('ccf',v)} options={[''].concat(listas.ccf||[])} />
          <Sel label="AFP"        value={form.afp||''} onChange={v=>sf('afp',v)} options={[''].concat(listas.afp||[])} />
        </div>

        <div style={{ marginBottom:14 }}>
          <label style={{ ...lbl, marginBottom:8, display:'block' }}>Servicios contratados</label>
          <div style={{ display:'flex',flexWrap:'wrap',gap:8,padding:'12px 14px',
            background:C.surface2,border:`1px solid ${C.border}`,borderRadius:8 }}>
            {SERVICIOS.map(s=>{
              const checked = (form.servicios||[]).includes(s);
              return (
                <label key={s} onClick={()=>toggleSrv(s)} style={{
                  display:'flex',alignItems:'center',gap:6,cursor:'pointer',padding:'6px 12px',
                  borderRadius:7,background:checked?C.blueBg:'#fff',
                  border:`1px solid ${checked?C.blue:C.border}`,
                  color:checked?C.blue:C.text,fontWeight:checked?600:400,fontSize:13,
                }}>
                  <input type="checkbox" checked={checked} onChange={()=>{}} style={{ accentColor:C.primary }} />
                  {s}
                </label>
              );
            })}
          </div>
        </div>

        <Seccion title="Estado" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:'0 16px' }}>
          <Sel label="Estado del afiliado" value={form.estado||'ACTIVO'}
            onChange={v=>{ sf('estado',v); sf('estado_srv',v); }}
            options={ESTADOS_SRV.map(e=>({value:e,label:e}))} />
          <InputUp label="Fecha ingreso"    type="date" value={form.fecha_ingreso||''}    onChange={v=>sf('fecha_ingreso',v)} />
          <InputUp label="Fecha afiliación" type="date" value={form.fecha_afiliacion||''} onChange={v=>sf('fecha_afiliacion',v)} />
        </div>

        <Seccion title="IBC y observaciones" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <div style={{ marginBottom:12 }}>
            <label style={lbl}>IBC individual ($) — vacío = usa global</label>
            <input type="number" value={form.ibc||''} onChange={e=>sf('ibc',e.target.value?+e.target.value:null)}
              placeholder={`IBC global: ${(1950905).toLocaleString('es-CO')}`}
              style={{ width:'100%',padding:'9px 12px',border:`1px solid ${C.border}`,borderRadius:7,
                fontSize:13,outline:'none',boxSizing:'border-box',color:C.text }} />
          </div>
          <div style={{ marginBottom:12 }}>
            <label style={lbl}>Observaciones / Novedades</label>
            <textarea value={form.obs||''} onChange={e=>sf('obs',UP(e.target.value))}
              placeholder="OBSERVACIONES DEL AFILIADO..." rows={2}
              style={{ width:'100%',padding:'9px 12px',border:`1px solid ${C.border}`,borderRadius:7,
                fontSize:13,outline:'none',boxSizing:'border-box',color:C.text,
                resize:'vertical',textTransform:'uppercase' }} />
          </div>
        </div>

        <div style={{ display:'flex',justifyContent:'flex-end',gap:10,marginTop:8,
          borderTop:`1px solid ${C.border}`,paddingTop:14 }}>
          <Btn variant="secondary" onClick={()=>setModal(null)}>Cancelar</Btn>
          <Btn onClick={()=>guardar.mutate()} disabled={guardar.isPending}>
            {guardar.isPending?'Guardando...':'💾 Guardar afiliado'}
          </Btn>
        </div>
      </Modal>

      {/* Paginación */}
      {totalPags > 1 && tab === 'activos' && (
        <div style={{ display:'flex', justifyContent:'center', alignItems:'center',
          gap:6, marginTop:16, flexWrap:'wrap' }}>
          <button onClick={()=>setPagina(1)} disabled={pagina===1} style={btnPag}>«</button>
          <button onClick={()=>setPagina(p=>Math.max(1,p-1))} disabled={pagina===1} style={btnPag}>‹</button>
          {[...Array(Math.min(5,totalPags))].map((_,i) => {
            const start = Math.max(1, Math.min(pagina-2, totalPags-4));
            const p = start + i;
            if(p > totalPags) return null;
            return <button key={p} onClick={()=>setPagina(p)} style={{
              ...btnPag, background:p===pagina?C.primary:'#fff',
              color:p===pagina?'#fff':C.text, fontWeight:p===pagina?700:400 }}>{p}</button>;
          })}
          <button onClick={()=>setPagina(p=>Math.min(totalPags,p+1))} disabled={pagina===totalPags} style={btnPag}>›</button>
          <button onClick={()=>setPagina(totalPags)} disabled={pagina===totalPags} style={btnPag}>»</button>
          <span style={{ fontSize:12, color:C.text2, marginLeft:4 }}>
            Pág {pagina}/{totalPags} · {totalReg} total
          </span>
        </div>
      )}
    </div>
  );
}

function Seccion({ title }) {
  return (
    <div style={{ fontSize:12,fontWeight:700,color:C.primary,borderBottom:`2px solid ${C.primary}`,
      paddingBottom:4,marginTop:16,marginBottom:10,textTransform:'uppercase',letterSpacing:'0.05em' }}>
      {title}
    </div>
  );
}
function Chip({ children }) {
  return <span style={{ background:C.surface2,border:`1px solid ${C.border}`,borderRadius:5,padding:'2px 8px',fontSize:11 }}>{children}</span>;
}
function SrvChip({ children }) {
  return <span style={{ background:C.blueBg,color:C.blue,borderRadius:5,padding:'1px 7px',fontSize:10,fontWeight:600 }}>{children}</span>;
}

const tdc = { padding:'10px 12px',fontSize:13,color:'#1E293B',verticalAlign:'middle' };
const lbl = { display:'block',fontSize:12,color:'#64748B',fontWeight:500,marginBottom:4 };
const btnPag = {
  padding:'6px 12px', border:`1px solid ${C.border}`, borderRadius:6,
  background:'#fff', cursor:'pointer', fontSize:13, color:C.text,
};
