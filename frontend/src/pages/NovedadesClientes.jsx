import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, PageHeader, ErrorMsg, ConfirmModal } from '../components/UI';

const tdc = { padding:'10px 12px', fontSize:13, color:C.text, verticalAlign:'middle' };

function AdjuntosCliente({ novedadId, contexto }) {
  const [open, setOpen] = useState(false);
  const { data: docs = [], isLoading, isError } = useQuery({
    queryKey: ['adj-cliente', contexto, novedadId],
    queryFn: () => api.get('/documentos', { params: { contexto, contexto_id: novedadId } }).then(r => r.data),
    enabled: open,
    retry: 1,
  });

  if (!open) return (
    <button onClick={() => setOpen(true)}
      style={{ fontSize: 11, color: C.blue, background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', whiteSpace: 'nowrap' }}>
      📎 Ver adjuntos
    </button>
  );

  if (isLoading) return <span style={{ fontSize: 11, color: C.text2 }}>Cargando...</span>;
  if (isError) return <span style={{ fontSize: 11, color: C.red }}>Error al cargar adjuntos</span>;
  if (docs.length === 0) return <span style={{ fontSize: 11, color: C.text2 }}>Sin adjuntos</span>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {docs.map(d => (
        <span key={d.id} style={{ fontSize: 11, color: C.blue, cursor: 'pointer', textDecoration: 'underline' }}
          onClick={async () => {
            const res = await api.get(`/documentos/${d.id}/descargar`, { responseType: 'blob' });
            const u = URL.createObjectURL(res.data);
            const a = document.createElement('a'); a.href = u; a.download = d.nombre; a.click(); URL.revokeObjectURL(u);
          }}>
          📄 {d.nombre}
        </span>
      ))}
    </div>
  );
}
const lbl = { display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 };
const inp = { width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface };
const sel = { padding:'8px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', background:C.surface, color:C.text };

export default function NovedadesClientes() {
  const qc = useQueryClient();
  const [tabNov, setTabNov] = useState('novedades');
  const [confirmState, setConfirmState] = useState({ open: false, title: '', message: '', onConfirm: null });
  const [filtroCliente, setFiltroCliente] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_nov_filtros'))?.filtroCliente ?? ''; } catch { return ''; } });
  const [filtroEstado, setFiltroEstado] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_nov_filtros'))?.filtroEstado ?? ''; } catch { return ''; } });
  const [filtroFecha, setFiltroFecha] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_nov_filtros'))?.filtroFecha ?? ''; } catch { return ''; } });

  useEffect(() => { try { localStorage.setItem('bbc_nov_filtros', JSON.stringify({ filtroCliente, filtroEstado, filtroFecha })); } catch {} }, [filtroCliente, filtroEstado, filtroFecha]);

  // ── Avisos (admin → cliente) ──
  const [avisoForm, setAvisoForm] = useState({ cliente_ref:'', titulo:'', mensaje:'' });
  const [avisoFiles, setAvisoFiles] = useState([]);
  const { data: avisos=[], isLoading: loadAvisos } = useQuery({
    queryKey:['admin-avisos'],
    queryFn:()=>api.get('/portal/avisos').then(r=>r.data),
    enabled: tabNov==='avisos',
    refetchInterval:60_000,
  });
  const { data: usuariosCliente=[] } = useQuery({
    queryKey:['usuarios-portal-clientes'],
    queryFn:()=>api.get('/usuarios').then(r=>r.data.filter(u=>u.rol==='cliente'&&u.activo!==false)),
  });
  const crearAviso = useMutation({
    mutationFn: async (body) => {
      const { data } = await api.post('/portal/avisos', body);
      if (avisoFiles.length > 0) {
        for (const file of avisoFiles) {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('afiliado_doc', '');
          fd.append('contexto', 'aviso');
          fd.append('contexto_id', String(data.id));
          await api.post('/documentos', fd);
        }
      }
      return data;
    },
    onSuccess: ()=>{ toast.success('Aviso enviado'); setAvisoForm({ cliente_ref:'', titulo:'', mensaje:'' }); setAvisoFiles([]); qc.invalidateQueries(['admin-avisos']); },
    onError: ()=>toast.error('Error al enviar aviso'),
  });
  const delAviso = useMutation({
    mutationFn:(id)=>api.delete(`/portal/avisos/${id}`),
    onSuccess:(_, id)=>{ toast.success('Aviso eliminado'); qc.setQueryData(['admin-avisos'], prev=>prev?.filter(a=>a.id!==id)); },
    onError:()=>toast.error('Error al eliminar'),
  });

  // Modal para responder al resolver
  const [modalResp, setModalResp] = useState(null);
  const [respTexto, setRespTexto] = useState('');
  const [respFiles, setRespFiles] = useState([]);

  const _ctxCliente = modalResp?.tipo === 'novedad' ? 'novedad_pago' : modalResp?.tipo === 'novedad-afil' ? 'novedad_afil' : 'novedad_retiro';
  const { data: docsNovedad=[] } = useQuery({
    queryKey: ['docs-novedad', modalResp?.id, modalResp?.tipo],
    queryFn: () => api.get('/documentos', { params: { contexto: _ctxCliente, contexto_id: modalResp.id } }).then(r => r.data),
    enabled: !!modalResp,
  });

  const { data: novedades=[], isLoading: loadNov, isError: isErrorNov, refetch: refetchNov } = useQuery({
    queryKey:['admin-novedades-pago'],
    queryFn:()=>api.get('/portal/novedades-pago').then(r=>r.data),
    refetchInterval:60_000,
  });
  const { data: solicitudes=[], isLoading: loadSol } = useQuery({
    queryKey:['admin-solicitudes-retiro'],
    queryFn:()=>api.get('/portal/solicitudes-retiro').then(r=>r.data),
    refetchInterval:60_000,
  });
  const { data: novedadesAfil=[], isLoading: loadNovAfil } = useQuery({
    queryKey:['admin-novedades-afil'],
    queryFn:()=>api.get('/portal/solicitudes-novedad').then(r=>r.data),
    refetchInterval:60_000,
  });

  const cerrarModalResp = () => { setModalResp(null); setRespTexto(''); setRespFiles([]); };

  const updNovedad = useMutation({
    mutationFn:({id,estado,respuesta})=>api.patch(`/portal/novedades-pago/${id}/estado`,{estado,respuesta}),
    onSuccess:(_, { id, estado, respuesta })=>{ toast.success('Estado actualizado'); qc.setQueryData(['admin-novedades-pago'], prev => prev?.map(n => n.id === id ? { ...n, estado, respuesta: respuesta ?? n.respuesta } : n)); cerrarModalResp(); },
    onError:()=>toast.error('Error al actualizar'),
  });
  const updSolicitud = useMutation({
    mutationFn:({id,estado,respuesta})=>api.patch(`/portal/solicitudes-retiro/${id}/estado`,{estado,respuesta}),
    onSuccess:(_, { id, estado, respuesta })=>{ toast.success('Estado actualizado'); qc.setQueryData(['admin-solicitudes-retiro'], prev => prev?.map(s => s.id === id ? { ...s, estado, respuesta: respuesta ?? s.respuesta } : s)); cerrarModalResp(); },
    onError:()=>toast.error('Error al actualizar'),
  });
  const updNovedadAfil = useMutation({
    mutationFn:({id,estado,respuesta})=>api.patch(`/portal/solicitudes-novedad/${id}/estado`,{estado,respuesta}),
    onSuccess:(_, { id, estado, respuesta })=>{ toast.success('Estado actualizado'); qc.setQueryData(['admin-novedades-afil'], prev => prev?.map(s => s.id === id ? { ...s, estado, respuesta: respuesta ?? s.respuesta } : s)); cerrarModalResp(); },
    onError:()=>toast.error('Error al actualizar'),
  });

  const delNovedad = useMutation({
    mutationFn:(id)=>api.delete(`/portal/novedades-pago/${id}`),
    onSuccess:(_, id)=>{ toast.success('Novedad eliminada'); qc.setQueryData(['admin-novedades-pago'], prev => prev?.filter(n => n.id !== id)); },
    onError:()=>toast.error('Error al eliminar'),
  });
  const delSolicitud = useMutation({
    mutationFn:(id)=>api.delete(`/portal/solicitudes-retiro/${id}`),
    onSuccess:(_, id)=>{ toast.success('Solicitud eliminada'); qc.setQueryData(['admin-solicitudes-retiro'], prev => prev?.filter(s => s.id !== id)); },
    onError:()=>toast.error('Error al eliminar'),
  });
  const delNovedadAfil = useMutation({
    mutationFn:(id)=>api.delete(`/portal/solicitudes-novedad/${id}`),
    onSuccess:(_, id)=>{ toast.success('Solicitud eliminada'); qc.setQueryData(['admin-novedades-afil'], prev => prev?.filter(s => s.id !== id)); },
    onError:()=>toast.error('Error al eliminar'),
  });

  const confirmarRespuesta = async () => {
    if(!modalResp) return;
    const payload = { id: modalResp.id, estado: modalResp.estado, respuesta: respTexto };
    if (respFiles.length > 0) {
      for (const file of respFiles) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('afiliado_doc', '');
        const _ctxResp = modalResp.tipo === 'novedad' ? 'resp_pago' : modalResp.tipo === 'novedad-afil' ? 'resp_afil' : 'resp_retiro';
        fd.append('contexto', _ctxResp);
        fd.append('contexto_id', String(modalResp.id));
        try {
          await api.post('/documentos', fd);
        } catch(err) {
          const det = err?.response?.data?.detail;
          const msg = typeof det === 'string' ? det : JSON.stringify(det);
          console.error('[confirmarRespuesta] upload error', err?.response?.status, err?.response?.data);
          toast.error('Error al subir archivo: ' + (msg || err.message || 'desconocido'));
          return;
        }
      }
    }
    if(modalResp.tipo==='novedad') updNovedad.mutate(payload);
    else if(modalResp.tipo==='retiro') updSolicitud.mutate(payload);
    else updNovedadAfil.mutate(payload);
  };

  const clientesNov = [...new Set(novedades.map(n=>n.username_cliente))].sort();
  const clientesSol = [...new Set(solicitudes.map(s=>s.username_cliente||s.cliente_ref))].sort();

  const aplicarFiltros = (lista, getCli) => lista.filter(r => {
    if(filtroCliente && getCli(r) !== filtroCliente) return false;
    if(filtroEstado  && r.estado !== filtroEstado) return false;
    if(filtroFecha   && r.creado?.slice(0,10) !== filtroFecha) return false;
    return true;
  });

  const novFiltradas     = aplicarFiltros(novedades,     n => n.username_cliente);
  const solFiltradas     = aplicarFiltros(solicitudes,   s => s.username_cliente||s.cliente_ref);
  const novAfilFiltradas = aplicarFiltros(novedadesAfil, n => n.username_cliente||n.cliente_ref);

  const badgeEstado = (est) => {
    const map = {
      pendiente:  { bg:'#FEF3C7', color:'#92400E' },
      procesado:  { bg:C.greenBg, color:C.green },
      ejecutado:  { bg:C.greenBg, color:C.green },
      rechazado:  { bg:C.redBg,   color:C.red },
    };
    const s = map[est] || { bg:C.surface2, color:C.text2 };
    return <span style={{ background:s.bg, color:s.color, borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>{est}</span>;
  };

  const limpiar = () => { setFiltroCliente(''); setFiltroEstado(''); setFiltroFecha(''); };

  return (
    <div>
      <PageHeader title="📬 Novedades de Clientes" />

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16, flexWrap:'wrap' }}>
        {[
          ['novedades', 'Novedades de Pago', novedades.filter(n=>n.estado==='pendiente').length],
          ['solicitudes', 'Solicitudes de Retiro', solicitudes.filter(s=>s.estado==='pendiente').length],
          ['novedades-afil', 'Novedades Afiliados', novedadesAfil.filter(n=>n.estado==='pendiente').length],
          ['avisos', '📩 Novedades a Clientes', 0],
        ].map(([id, label, pendientes])=>(
          <button key={id} onClick={()=>{ setTabNov(id); limpiar(); }}
            style={{ padding:'8px 18px', borderRadius:8, border:'none', fontSize:13, fontWeight:600,
              cursor:'pointer', background:tabNov===id?C.primary:'#fff',
              color:tabNov===id?'#fff':C.text2, boxShadow:tabNov===id?'none':'0 1px 3px rgba(0,0,0,.1)',
              display:'flex', alignItems:'center', gap:8, position:'relative' }}>
            {label}
            {pendientes > 0 && (
              <span style={{
                background: tabNov===id ? 'rgba(255,255,255,0.3)' : '#EF4444',
                color: '#fff',
                borderRadius: 12,
                padding: '1px 7px',
                fontSize: 11,
                fontWeight: 700,
                lineHeight: '18px',
                minWidth: 20,
                textAlign: 'center',
                boxShadow: tabNov===id ? 'none' : '0 0 0 2px #FCA5A5',
              }}>
                {pendientes}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ background:C.surface, borderRadius:10, border:`1px solid ${C.border}`, padding:'12px 16px', marginBottom:16 }}>
        <div style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
          <div>
            <label style={lbl}>Cliente</label>
            <select style={sel} value={filtroCliente} onChange={e=>setFiltroCliente(e.target.value)}>
              <option value="">Todos</option>
              {(tabNov==='novedades'?clientesNov:clientesSol).map(c=><option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Estado</label>
            <select style={sel} value={filtroEstado} onChange={e=>setFiltroEstado(e.target.value)}>
              <option value="">Todos</option>
              {tabNov==='novedades'
                ? [['pendiente','Pendiente'],['procesado','Procesado']].map(([v,l])=><option key={v} value={v}>{l}</option>)
                : [['pendiente','Pendiente'],['ejecutado','Ejecutado'],['rechazado','Rechazado']].map(([v,l])=><option key={v} value={v}>{l}</option>)
              }
            </select>
          </div>
          <div>
            <label style={lbl}>Fecha</label>
            <input type="date" style={sel} value={filtroFecha} onChange={e=>setFiltroFecha(e.target.value)} />
          </div>
          {(filtroCliente||filtroEstado||filtroFecha) && <Btn variant="secondary" onClick={limpiar}>Limpiar</Btn>}
        </div>
      </div>

      {/* Tabla Novedades de Pago */}
      {tabNov==='novedades'&&(
        isErrorNov ? <ErrorMsg message="Error al cargar novedades de pago" onRetry={refetchNov} /> :
        loadNov ? <p style={{ color:C.text2 }}>Cargando...</p> :
        novFiltradas.length===0 ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin novedades{(filtroCliente||filtroEstado||filtroFecha)?' con estos filtros':''}.</p> :
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
            <thead><tr style={{ background:C.surface2 }}>
              {['Cliente','Período','Afiliados','Observaciones','Adjuntos','Estado','Respuesta admin','Registrado','Acción'].map(h=>(
                <th key={h} style={{ padding:'11px 12px', textAlign:'left', fontSize:11, fontWeight:700, color:C.text, background:C.surface2, borderBottom:`2px solid ${C.border}`, whiteSpace:'nowrap', letterSpacing:'0.03em', textTransform:'uppercase' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {novFiltradas.map(n=>(
                <tr key={n.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}><strong>{n.username_cliente}</strong>{n.cliente_ref&&<div style={{ fontSize:11,color:C.text2 }}>{n.cliente_ref}</div>}</td>
                  <td style={tdc}>{n.mes} {n.anio}</td>
                  <td style={tdc}>
                    <div style={{ fontSize:12 }}>{n.afiliados.length} persona(s)</div>
                    <div style={{ fontSize:11, color:C.text2, maxWidth:220 }}>
                      {n.afiliados.slice(0,2).join(', ')}{n.afiliados.length>2?` +${n.afiliados.length-2} más`:''}
                    </div>
                    {n.afiliados.length > 2 && (
                      <button
                        onClick={() => {
                          api.get(`/portal/novedades-pago/${n.id}/exportar-excel`, { responseType:'blob' })
                            .then(r => {
                              const url = window.URL.createObjectURL(new Blob([r.data]));
                              const a = document.createElement('a'); a.href = url;
                              a.download = `novedad-pago-${n.mes}-${n.anio}-${n.id}.xlsx`; a.click();
                              window.URL.revokeObjectURL(url);
                            })
                            .catch(() => toast.error('Error al exportar'));
                        }}
                        style={{ marginTop:4, fontSize:11, color:C.primary, background:'none', border:`1px solid ${C.border}`, borderRadius:5, padding:'2px 8px', cursor:'pointer', fontWeight:600 }}
                      >
                        Descargar lista
                      </button>
                    )}
                  </td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{n.obs||'—'}</span></td>
                  <td style={tdc}><AdjuntosCliente novedadId={n.id} contexto="novedad_pago" /></td>
                  <td style={tdc}>{badgeEstado(n.estado)}</td>
                  <td style={tdc}><span style={{ fontSize:11,color:n.respuesta?C.blue:C.text2 }}>{n.respuesta||'—'}</span></td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text, fontVariantNumeric:'tabular-nums' }}>{new Date(n.creado).toLocaleString('es-CO')}</span></td>
                  <td style={tdc}>
                    {n.estado==='pendiente'
                      ? <Btn size="sm" variant="success" onClick={()=>{ setModalResp({tipo:'novedad',id:n.id,estado:'procesado',label:`Novedad de pago ${n.mes} ${n.anio}`}); setRespTexto(n.respuesta||''); }}>Marcar procesado</Btn>
                      : <Btn size="sm" variant="secondary" onClick={()=>updNovedad.mutate({id:n.id,estado:'pendiente',respuesta:n.respuesta})} disabled={updNovedad.isPending}>Reabrir</Btn>
                    }
                    <Btn size="sm" variant="danger" style={{marginLeft:4}} onClick={()=>setConfirmState({ open:true, title:'Eliminar novedad', message:'¿Eliminar esta novedad y sus adjuntos?', onConfirm:()=>{ delNovedad.mutate(n.id); setConfirmState(s=>({...s,open:false})); } })} disabled={delNovedad.isPending}>×</Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tabla Solicitudes de Retiro */}
      {tabNov==='solicitudes'&&(
        loadSol ? <p style={{ color:C.text2 }}>Cargando...</p> :
        solFiltradas.length===0 ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin solicitudes{(filtroCliente||filtroEstado||filtroFecha)?' con estos filtros':''}.</p> :
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
            <thead><tr style={{ background:C.surface2 }}>
              {['Cliente','Afiliado','Documento','Motivo','Observaciones','Estado','Respuesta admin','Registrado','Acción'].map(h=>(
                <th key={h} style={{ padding:'11px 12px', textAlign:'left', fontSize:11, fontWeight:700, color:C.text, background:C.surface2, borderBottom:`2px solid ${C.border}`, whiteSpace:'nowrap', letterSpacing:'0.03em', textTransform:'uppercase' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {solFiltradas.map(s=>(
                <tr key={s.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}><strong>{s.username_cliente||s.cliente_ref}</strong></td>
                  <td style={tdc}>{s.afiliado_nombre}</td>
                  <td style={tdc}><span style={{ color:C.text2, fontSize:12 }}>{s.afiliado_doc}</span></td>
                  <td style={tdc}>{s.motivo}</td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{s.obs||'—'}</span></td>
                  <td style={tdc}>{badgeEstado(s.estado)}</td>
                  <td style={tdc}><span style={{ fontSize:11,color:s.respuesta?C.blue:C.text2 }}>{s.respuesta||'—'}</span></td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text, fontVariantNumeric:'tabular-nums' }}>{new Date(s.creado).toLocaleString('es-CO')}</span></td>
                  <td style={tdc}>
                    {s.estado==='pendiente'&&(
                      <div style={{ display:'flex', gap:6 }}>
                        <Btn size="sm" variant="success" onClick={()=>{ setModalResp({tipo:'retiro',id:s.id,estado:'ejecutado',label:`Retiro de ${s.afiliado_nombre}`}); setRespTexto(s.respuesta||''); }}>Ejecutado</Btn>
                        <Btn size="sm" variant="danger"  onClick={()=>{ setModalResp({tipo:'retiro',id:s.id,estado:'rechazado',label:`Retiro de ${s.afiliado_nombre}`}); setRespTexto(s.respuesta||''); }}>Rechazar</Btn>
                      </div>
                    )}
                    {s.estado!=='pendiente'&&<Btn size="sm" variant="secondary" onClick={()=>updSolicitud.mutate({id:s.id,estado:'pendiente',respuesta:s.respuesta})} disabled={updSolicitud.isPending}>Reabrir</Btn>}
                    <Btn size="sm" variant="danger" style={{marginLeft:4}} onClick={()=>setConfirmState({ open:true, title:'Eliminar solicitud', message:'¿Eliminar esta solicitud y sus adjuntos?', onConfirm:()=>{ delSolicitud.mutate(s.id); setConfirmState(cs=>({...cs,open:false})); } })} disabled={delSolicitud.isPending}>×</Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tabla Novedades de Afiliados */}
      {tabNov==='novedades-afil'&&(
        loadNovAfil ? <p style={{ color:C.text2 }}>Cargando...</p> :
        novAfilFiltradas.length===0
          ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin novedades{(filtroCliente||filtroEstado||filtroFecha)?' con estos filtros':''}.</p> :
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
            <thead><tr style={{ background:C.surface2 }}>
              {['Cliente','Afiliado','Documento','Tipo','Descripción','Adjuntos','Estado','Respuesta admin','Registrado','Acción'].map(h=>(
                <th key={h} style={{ padding:'11px 12px', textAlign:'left', fontSize:11, fontWeight:700, color:C.text, background:C.surface2, borderBottom:`2px solid ${C.border}`, whiteSpace:'nowrap', letterSpacing:'0.03em', textTransform:'uppercase' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {novAfilFiltradas.map(n=>(
                <tr key={n.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}><strong>{n.username_cliente||n.cliente_ref}</strong></td>
                  <td style={tdc}>{n.afiliado_nombre}</td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{n.afiliado_doc}</span></td>
                  <td style={tdc}><span style={{ fontWeight:600, color:C.blue, fontSize:12 }}>{n.tipo}</span></td>
                  <td style={{ ...tdc, maxWidth:220 }}><span style={{ fontSize:12, color:C.text2 }}>{n.descripcion}</span></td>
                  <td style={tdc}><AdjuntosCliente novedadId={n.id} contexto="novedad_afil" /></td>
                  <td style={tdc}>{badgeEstado(n.estado)}</td>
                  <td style={tdc}><span style={{ fontSize:11,color:n.respuesta?C.blue:C.text2 }}>{n.respuesta||'—'}</span></td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text, fontVariantNumeric:'tabular-nums' }}>{new Date(n.creado).toLocaleString('es-CO')}</span></td>
                  <td style={tdc}>
                    {n.estado==='pendiente'
                      ? <Btn size="sm" variant="success" onClick={()=>{ setModalResp({tipo:'novedad-afil',id:n.id,estado:'atendido',label:`Novedad ${n.tipo} — ${n.afiliado_nombre}`}); setRespTexto(n.respuesta||''); }}>Marcar atendido</Btn>
                      : <Btn size="sm" variant="secondary" onClick={()=>updNovedadAfil.mutate({id:n.id,estado:'pendiente',respuesta:n.respuesta})} disabled={updNovedadAfil.isPending}>Reabrir</Btn>
                    }
                    <Btn size="sm" variant="danger" style={{marginLeft:4}} onClick={()=>setConfirmState({ open:true, title:'Eliminar novedad', message:'¿Eliminar esta novedad y sus adjuntos?', onConfirm:()=>{ delNovedadAfil.mutate(n.id); setConfirmState(cs=>({...cs,open:false})); } })} disabled={delNovedadAfil.isPending}>×</Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Avisos a Clientes ── */}
      {tabNov==='avisos'&&(
        <div>
          <div style={{ background:C.surface, borderRadius:10, border:`1px solid ${C.border}`, padding:'16px 20px', marginBottom:20 }}>
            <h4 style={{ margin:'0 0 12px', fontSize:14, fontWeight:700, color:C.text }}>Nueva Novedad al Cliente</h4>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:12 }}>
              <div>
                <label style={lbl}>Cliente destinatario</label>
                <select style={inp} value={avisoForm.cliente_ref} onChange={e=>setAvisoForm(p=>({...p,cliente_ref:e.target.value}))}>
                  <option value="">Seleccionar cliente...</option>
                  {usuariosCliente.filter(u=>u.cliente_ref).map(u=>(
                    <option key={u.id} value={u.cliente_ref}>{u.nombre} — {u.cliente_ref}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={lbl}>Título</label>
                <input style={inp} placeholder="Ej: Actualización de tarifas" value={avisoForm.titulo} onChange={e=>setAvisoForm(p=>({...p,titulo:e.target.value}))} maxLength={200} />
              </div>
            </div>
            <div style={{ marginBottom:12 }}>
              <label style={lbl}>Mensaje</label>
              <textarea style={{...inp,height:80,resize:'vertical'}} placeholder="Contenido de la novedad para el cliente..." value={avisoForm.mensaje} onChange={e=>setAvisoForm(p=>({...p,mensaje:e.target.value}))} />
            </div>
            <div style={{ marginBottom:12 }}>
              <label style={{ display:'block', padding:'7px 12px', border:`2px dashed ${C.border}`, borderRadius:7,
                textAlign:'center', cursor:'pointer', color:C.text2, fontSize:12, background:C.surface2 }}>
                📎 {avisoFiles.length > 0 ? `${avisoFiles.length} archivo(s) adjunto(s)` : 'Adjuntar documentos (opcional)'}
                <input type="file" multiple style={{ display:'none' }} accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                  onChange={e => setAvisoFiles(p => [...p, ...Array.from(e.target.files)])} />
              </label>
              {avisoFiles.length > 0 && (
                <div style={{ marginTop:6, display:'flex', flexWrap:'wrap', gap:4 }}>
                  {avisoFiles.map((f, i) => (
                    <div key={i} style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 8px',
                      background:C.blueBg, border:`1px solid ${C.blue}`, borderRadius:5, fontSize:11 }}>
                      <span style={{ color:C.blue }}>{f.name}</span>
                      <span style={{ cursor:'pointer', color:C.red, fontWeight:700 }} onClick={() => setAvisoFiles(p => p.filter((_,j) => j !== i))}>×</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <Btn variant="primary"
              onClick={()=>{ if(!avisoForm.cliente_ref||!avisoForm.titulo.trim()||!avisoForm.mensaje.trim()){ toast.error('Completa todos los campos'); return; } crearAviso.mutate(avisoForm); }}
              disabled={crearAviso.isPending}>
              {crearAviso.isPending ? 'Enviando...' : '📩 Enviar Novedad'}
            </Btn>
          </div>

          {loadAvisos ? <p style={{ color:C.text2 }}>Cargando...</p> :
           avisos.length===0 ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin novedades enviadas aún.</p> :
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
              <thead><tr style={{ background:C.surface2 }}>
                {['Cliente','Título','Mensaje','Adjuntos','Estado','Enviado por','Fecha','Acción'].map(h=>(
                  <th key={h} style={{ padding:'11px 12px', textAlign:'left', fontSize:11, fontWeight:700, color:C.text, background:C.surface2, borderBottom:`2px solid ${C.border}`, whiteSpace:'nowrap', letterSpacing:'0.03em', textTransform:'uppercase' }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {avisos.map(a=>(
                  <tr key={a.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                    <td style={tdc}><strong>{a.cliente_ref}</strong></td>
                    <td style={tdc}><span style={{ fontWeight:600, fontSize:13 }}>{a.titulo}</span></td>
                    <td style={{ ...tdc, maxWidth:220 }}><span style={{ fontSize:12, color:C.text2, whiteSpace:'pre-wrap' }}>{a.mensaje}</span></td>
                    <td style={tdc}>
                      {(a.documentos||[]).length === 0
                        ? <span style={{ color:C.text2, fontSize:11 }}>—</span>
                        : (a.documentos||[]).map(d=>(
                          <div key={d.id} style={{ fontSize:11, color:C.blue, cursor:'pointer', textDecoration:'underline', marginBottom:2 }}
                            onClick={async()=>{
                              const res = await api.get(`/documentos/${d.id}/descargar`, { responseType:'blob' }).catch(()=>null);
                              if(!res) return toast.error('Error al descargar');
                              if(res.data?.url) { window.open(res.data.url,'_blank'); return; }
                              const u=URL.createObjectURL(res.data); const a2=document.createElement('a'); a2.href=u; a2.download=d.nombre; a2.click(); URL.revokeObjectURL(u);
                            }}>
                            📄 {d.nombre}
                          </div>
                        ))
                      }
                    </td>
                    <td style={tdc}>
                      {a.leido
                        ? <span style={{ background:C.greenBg, color:C.green, borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>Leído</span>
                        : <span style={{ background:'#FEF3C7', color:'#92400E', borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>No leído</span>
                      }
                    </td>
                    <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{a.creado_por}</span></td>
                    <td style={tdc}><span style={{ fontSize:12, color:C.text, fontVariantNumeric:'tabular-nums' }}>{new Date(a.creado).toLocaleString('es-CO')}</span></td>
                    <td style={tdc}>
                      <Btn size="sm" variant="danger" onClick={()=>setConfirmState({ open:true, title:'Eliminar aviso', message:'¿Eliminar este aviso y sus adjuntos?', onConfirm:()=>{ delAviso.mutate(a.id); setConfirmState(cs=>({...cs,open:false})); } })} disabled={delAviso.isPending}>×</Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
        </div>
      )}

      {/* ── Modal respuesta al resolver ── */}
      {modalResp&&(
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center'}}>
          <div style={{background:C.surface,borderRadius:14,padding:28,width:500,maxWidth:'95vw',boxShadow:'0 20px 60px rgba(0,0,0,.3)',maxHeight:'90vh',overflowY:'auto'}}>
            <h3 style={{margin:'0 0 6px',fontSize:15,fontWeight:700}}>Resolver solicitud</h3>
            <p style={{margin:'0 0 16px',fontSize:13,color:C.text2}}>{modalResp.label}</p>

            {docsNovedad.length > 0 && (
              <div style={{marginBottom:16,background:C.surface2,borderRadius:8,padding:'10px 12px'}}>
                <p style={{margin:'0 0 8px',fontSize:12,fontWeight:600,color:C.text2}}>📎 Adjuntos del cliente ({docsNovedad.length}):</p>
                {docsNovedad.map(d=>(
                  <div key={d.id} style={{display:'flex',alignItems:'center',gap:8,fontSize:12,marginBottom:4}}>
                    <span style={{flex:1,color:C.blue,cursor:'pointer',textDecoration:'underline'}}
                      onClick={async()=>{
                        const res = await api.get(`/documentos/${d.id}/descargar`,{responseType:'blob'});
                        const u=URL.createObjectURL(res.data); const a=document.createElement('a'); a.href=u; a.download=d.nombre; a.click(); URL.revokeObjectURL(u);
                      }}>
                      📄 {d.nombre}
                    </span>
                    <span style={{color:C.text2,fontSize:11}}>{d.subido_por}</span>
                  </div>
                ))}
              </div>
            )}

            <div style={{marginBottom:12}}>
              <label style={lbl}>Nota / respuesta para el cliente <span style={{fontWeight:400,color:C.text2}}>(opcional)</span></label>
              <textarea style={{...inp,height:80,resize:'vertical'}} placeholder="Ej: Se procesó el pago, se ejecutó el retiro el día..." value={respTexto} onChange={e=>setRespTexto(e.target.value)} autoFocus />
            </div>

            <div style={{marginBottom:16}}>
              <label style={{display:'block',padding:'7px 12px',border:`2px dashed ${C.border}`,borderRadius:7,
                textAlign:'center',cursor:'pointer',color:C.text2,fontSize:12,background:C.surface2}}>
                📎 {respFiles.length > 0 ? `${respFiles.length} archivo(s) de respuesta` : 'Adjuntar documento de respuesta (opcional)'}
                <input type="file" multiple style={{display:'none'}} accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                  onChange={e=>setRespFiles(p=>[...p,...Array.from(e.target.files)])} />
              </label>
              {respFiles.length > 0 && (
                <div style={{marginTop:6,display:'flex',flexWrap:'wrap',gap:4}}>
                  {respFiles.map((f,i)=>(
                    <div key={i} style={{display:'flex',alignItems:'center',gap:4,padding:'3px 8px',
                      background:C.blueBg,border:`1px solid ${C.blue}`,borderRadius:5,fontSize:11}}>
                      <span style={{color:C.blue}}>{f.name}</span>
                      <span style={{cursor:'pointer',color:C.red,fontWeight:700}} onClick={()=>setRespFiles(p=>p.filter((_,j)=>j!==i))}>×</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{display:'flex',gap:8,justifyContent:'flex-end'}}>
              <Btn variant="secondary" onClick={cerrarModalResp}>Cancelar</Btn>
              <Btn variant="success" onClick={confirmarRespuesta} disabled={updNovedad.isPending||updSolicitud.isPending||updNovedadAfil.isPending}>
                Confirmar y notificar cliente
              </Btn>
            </div>
          </div>
        </div>
      )}
      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState(s => ({ ...s, open: false }))}
      />
    </div>
  );
}
