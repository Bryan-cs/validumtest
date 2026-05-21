import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, PageHeader } from '../components/UI';

const UP = v => (v || '').toUpperCase();

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

const etiq = { fontSize:11, color:C.text2, fontWeight:500, marginBottom:3 };
const val  = { fontSize:14, fontWeight:600, color:C.text };
const lbl  = { display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 };
const inp  = { width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface };

export default function Retiros() {
  const qc = useQueryClient();
  const [buscarH,  setBuscarH] = useState('');
  const [docConsulta, setDocConsulta] = useState('');
  const [modal, setModal] = useState(false);
  const [doc,   setDoc]  = useState('');
  const [fecha, setFecha]= useState(new Date().toISOString().slice(0,10));
  const [motivo,setMotivo]=useState('Renuncia');
  const [obs,   setObs]  = useState('');
  const [modalDocBuscar, setModalDocBuscar] = useState('');
  const [modalDocQuery,  setModalDocQuery]  = useState('');
  const [afiliadoRetiro, setAfiliadoRetiro] = useState(null);

  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });

  const { data: _buscadorData, isFetching: loadBuscandoAfil } = useQuery({
    queryKey: ['afiliado_retiro_buscar', modalDocQuery],
    queryFn: () => api.get('/afiliados', { params: { q: modalDocQuery, limit: 20 } }).then(r => r.data),
    enabled: !!modalDocQuery,
    staleTime: 0,
    gcTime: 0,
  });

  useEffect(() => {
    if (!modalDocQuery || !_buscadorData) return;
    const exact = (_buscadorData.items || []).find(a => a.doc === modalDocQuery);
    setAfiliadoRetiro(exact || false);
    if (exact) setDoc(exact.doc);
  }, [_buscadorData, modalDocQuery]);

  const aplicar = useMutation({
    mutationFn: ()=>api.post('/retiros',{doc,fecha,motivo,obs}),
    onSuccess: (res)=>{
      const n = res.data?.facturas_pendientes;
      toast.success(n ? `Retiro aplicado. ${n} factura(s) pendiente(s) del mes` : 'Retiro aplicado');
      qc.invalidateQueries({queryKey:['retiros']});
      qc.invalidateQueries({queryKey:['afiliados']});
      setModal(false); setDoc(''); setObs(''); setAfiliadoRetiro(null); setModalDocBuscar(''); setModalDocQuery('');
    },
    onError:(e)=>{ const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Afiliado no encontrado')); },
  });

  const { data: resultadoConsulta=[], isLoading: loadConsulta, isFetched: consultaHecha } = useQuery({
    queryKey: ['retiro_consulta', docConsulta],
    queryFn: () => api.get('/retiros', { params: { doc: docConsulta } }).then(r => r.data.items||[]),
    enabled: !!docConsulta,
  });

  const cerrarModal = () => {
    setModal(false); setDoc(''); setObs('');
    setAfiliadoRetiro(null); setModalDocBuscar(''); setModalDocQuery('');
  };

  return (
    <div>
      <PageHeader title="📋 Historial de retirados"
        action={
          <div style={{ display:'flex', gap:8 }}>
            <Btn variant="secondary" onClick={()=>dlExcel(`/reportes/retiros`,`retiros.xlsx`)}>📊 Exportar Excel</Btn>
            <Btn variant="accent" onClick={()=>setModal(true)}>+ Aplicar retiro</Btn>
          </div>
        } />

      <>
        <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:20 }}>
          <div style={{ position:'relative' }}>
            <input
              type="text"
              value={buscarH}
              onChange={e => setBuscarH(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') setDocConsulta(buscarH.trim()); }}
              placeholder="N° documento..."
              style={{ padding:'8px 14px', paddingRight:90, borderRadius:7,
                border:`1px solid ${C.border}`, fontSize:13, color:C.text,
                background:C.surface, width:260, outline:'none' }}
            />
            <button
              onClick={() => setDocConsulta(buscarH.trim())}
              style={{ position:'absolute', right:4, top:'50%', transform:'translateY(-50%)',
                padding:'4px 12px', borderRadius:5, border:'none', background:C.primary,
                color:'#fff', fontSize:12, fontWeight:600, cursor:'pointer' }}>
              Consultar
            </button>
          </div>
          {docConsulta && (
            <button onClick={() => { setBuscarH(''); setDocConsulta(''); }}
              style={{ padding:'7px 12px', borderRadius:7, border:`1px solid ${C.border}`,
                background:C.surface2, fontSize:12, cursor:'pointer', color:C.text2 }}>
              ✕ Limpiar
            </button>
          )}
        </div>

        {!docConsulta && (
          <div style={{ textAlign:'center', padding:'48px 0', color:C.text2, fontSize:14 }}>
            Ingresa el número de documento para consultar si la persona fue retirada.
          </div>
        )}

        {docConsulta && loadConsulta && (
          <div style={{ textAlign:'center', padding:'32px 0', color:C.text2 }}>Consultando...</div>
        )}

        {docConsulta && !loadConsulta && consultaHecha && (
          resultadoConsulta.length === 0 ? (
            <div style={{ textAlign:'center', padding:'32px 0', borderRadius:10,
              border:`1px solid ${C.border}`, background:C.surface }}>
              <div style={{ fontSize:32, marginBottom:8 }}>✅</div>
              <div style={{ fontSize:14, color:C.text2 }}>
                No hay registro de retiro para el documento <strong style={{color:C.text}}>{docConsulta}</strong>
              </div>
            </div>
          ) : resultadoConsulta.map(r => (
            <div key={r.id} style={{ borderRadius:10, border:`1px solid ${C.red}`,
              background:C.redBg, padding:'20px 24px' }}>
              <div style={{ fontSize:13, fontWeight:700, color:C.red, marginBottom:14 }}>
                ↪️ Registro de retiro encontrado
              </div>
              <div style={{ display:'flex', flexWrap:'wrap', gap:20 }}>
                <div><div style={etiq}>Nombre</div><div style={val}>{r.nombre}</div></div>
                <div><div style={etiq}>Documento</div><div style={{ ...val, fontFamily:'monospace' }}>{r.doc}</div></div>
                <div><div style={etiq}>Empresa</div><div style={val}>{r.empresa || '—'}</div></div>
                <div><div style={etiq}>Fecha retiro</div><div style={val}>{r.fecha}</div></div>
                <div><div style={etiq}>Motivo</div>
                  <span style={{ background:C.red, color:'#fff', borderRadius:6,
                    padding:'2px 10px', fontSize:12, fontWeight:700 }}>{r.motivo || '—'}</span>
                </div>
                <div><div style={etiq}>Registrado por</div><div style={val}>{r.registrado_por || '—'}</div></div>
              </div>
              {r.obs && (
                <div style={{ marginTop:14, padding:'10px 14px', borderRadius:7,
                  background:'rgba(0,0,0,.06)', fontSize:13, color:C.text }}>
                  <span style={{ fontWeight:600, color:C.red }}>Observaciones: </span>{r.obs}
                </div>
              )}
            </div>
          ))
        )}
      </>
      {modal && (
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
          <div style={{ background:C.surface,borderRadius:14,padding:28,width:460,boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
            <h3 style={{ margin:'0 0 18px',color:C.primary }}>Aplicar retiro</h3>

            <label style={lbl}>Cédula del afiliado *</label>
            <div style={{ display:'flex', gap:8, marginBottom:14 }}>
              <input style={{ ...inp, flex:1, margin:0 }} value={modalDocBuscar}
                onChange={e=>{ setModalDocBuscar(e.target.value); setAfiliadoRetiro(null); setModalDocQuery(''); }}
                onKeyDown={e=>{ if(e.key==='Enter' && modalDocBuscar.trim()) setModalDocQuery(modalDocBuscar.trim()); }}
                placeholder="Número de documento" />
              <Btn onClick={()=>{ if(modalDocBuscar.trim()) setModalDocQuery(modalDocBuscar.trim()); }}
                disabled={!modalDocBuscar.trim() || loadBuscandoAfil}>
                {loadBuscandoAfil ? '...' : 'Buscar'}
              </Btn>
            </div>

            {modalDocQuery && afiliadoRetiro === false && (
              <div style={{ padding:'10px 14px', borderRadius:8, background:C.redBg,
                border:`1px solid ${C.red}`, marginBottom:14, fontSize:13, color:C.red, fontWeight:500 }}>
                ❌ Afiliado no encontrado en el sistema (doc: {modalDocQuery})
              </div>
            )}

            {afiliadoRetiro && (
              <div style={{ padding:'12px 14px', borderRadius:8, background:C.greenBg,
                border:`1px solid ${C.green}`, marginBottom:14 }}>
                <div style={{ fontSize:12, fontWeight:700, color:C.green, marginBottom:6 }}>✅ Afiliado encontrado</div>
                <div style={{ fontSize:14, fontWeight:700, color:C.text }}>{afiliadoRetiro.nombre}</div>
                <div style={{ fontSize:12, color:C.text2, marginTop:2 }}>
                  {afiliadoRetiro.empresa || '—'} · Doc: {afiliadoRetiro.doc}
                  {afiliadoRetiro.eps ? ` · EPS: ${afiliadoRetiro.eps}` : ''}
                </div>
              </div>
            )}

            {afiliadoRetiro && (
              <>
                <label style={lbl}>Fecha de retiro</label>
                <input type="date" style={inp} value={fecha} onChange={e=>setFecha(e.target.value)} />
                <label style={lbl}>Motivo</label>
                <select style={inp} value={motivo} onChange={e=>setMotivo(e.target.value)}>
                  {(listas.motivos_retiro||['Renuncia','Despido','Pension','Otro']).map(m=><option key={m}>{m}</option>)}
                </select>
                <label style={lbl}>Observaciones</label>
                <textarea style={{ ...inp, height:70, textTransform:'uppercase' }} value={obs} onChange={e=>setObs(UP(e.target.value))} />
              </>
            )}

            <div style={{ display:'flex', gap:10, marginTop:14, justifyContent:'flex-end' }}>
              <Btn variant="secondary" onClick={cerrarModal}>Cancelar</Btn>
              {afiliadoRetiro && (
                <Btn onClick={()=>aplicar.mutate()} disabled={aplicar.isPending}>
                  {aplicar.isPending?'Procesando...':'Aplicar retiro'}
                </Btn>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
