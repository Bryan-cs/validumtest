import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear();
const ANIOS = [anioActual-1, anioActual, anioActual+1].map(String);

const C = {
  primary:  'var(--c-primary)',  accent:   'var(--c-accent)',
  green:    'var(--c-green)',    greenBg:  'var(--c-green-bg)',
  red:      'var(--c-red)',      redBg:    'var(--c-red-bg)',
  amber:    'var(--c-amber)',    amberBg:  'var(--c-amber-bg)',
  blue:     'var(--c-blue)',     blueBg:   'var(--c-blue-bg)',
  yellow:   'var(--c-amber)',    yellowBg: 'var(--c-amber-bg)',
  border:   'var(--c-border)',
  surface:  'var(--c-surface)',  surface2: 'var(--c-surface2)',
  bg:       'var(--c-bg)',
  text:     'var(--c-text)',     text2:    'var(--c-text2)',
};

const _moneyFmt = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const money = (v) => _moneyFmt.format(v || 0);

const inp = { width:'100%', padding:'8px 10px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, boxSizing:'border-box', outline:'none', color:C.text, background:C.surface };
const lbl = { fontSize:12, fontWeight:600, color:C.text2, display:'block', marginBottom:4 };
const tdc = { padding:'10px 12px', fontSize:13, color:C.text, verticalAlign:'middle' };

function Badge({ color, bg, children }) {
  return (
    <span style={{ background:bg, color, borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600, whiteSpace:'nowrap' }}>
      {children}
    </span>
  );
}

function Btn({ children, onClick, disabled, variant='primary', size='md' }) {
  const styles = {
    primary:   { background:C.primary,   color:'#fff',  border:'none' },
    accent:    { background:C.accent,    color:'#fff',  border:'none' },
    secondary: { background:C.surface,      color:C.text,  border:`1px solid ${C.border}` },
    danger:    { background:C.red,       color:'#fff',  border:'none' },
    success:   { background:C.green,     color:'#fff',  border:'none' },
  };
  const pad = size === 'sm' ? '5px 10px' : '8px 16px';
  return (
    <button onClick={onClick} disabled={disabled} style={{
      ...styles[variant], padding:pad, borderRadius:7, fontSize:size==='sm'?12:13,
      cursor:disabled?'not-allowed':'pointer', opacity:disabled?.6:1, fontWeight:600,
    }}>
      {children}
    </button>
  );
}

// ─── MODAL RESUMEN ─────────────────────────────────────────────────────────────
function ModalResumen({ doc, onClose }) {
  const { data, isLoading } = useQuery({
    queryKey: ['portal-resumen', doc],
    queryFn: () => api.get(`/portal/afiliados/${doc}/resumen`).then(r => r.data),
    enabled: !!doc,
  });

  const descargarPDF = () => {
    if (!data?.afiliado) return;
    api.get(`/portal/afiliados/${doc}/estado-cuenta`, { responseType: 'blob' })
      .then(r => {
        const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
        const a = document.createElement('a'); a.href = url;
        a.download = `estado-cuenta-${doc}.pdf`; a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => toast.error('Error al descargar PDF'));
  };

  return (
    <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.5)',zIndex:1000,display:'flex',alignItems:'flex-start',justifyContent:'center',paddingTop:40,overflowY:'auto' }}>
      <div style={{ background:C.surface,borderRadius:14,padding:28,width:700,maxWidth:'95vw',boxShadow:'0 20px 60px rgba(0,0,0,.3)',margin:'0 auto 40px' }}>
        <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20 }}>
          <h3 style={{ margin:0,color:C.primary,fontSize:16 }}>Resumen del Afiliado</h3>
          <button onClick={onClose} style={{ background:'none',border:'none',fontSize:20,cursor:'pointer',color:C.text2 }}>×</button>
        </div>

        {isLoading ? (
          <p style={{ textAlign:'center',color:C.text2,padding:40 }}>Cargando...</p>
        ) : data ? (
          <>
            {/* Info personal */}
            <div style={{ background:C.surface,borderRadius:10,padding:16,marginBottom:16 }}>
              <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:10 }}>
                {[
                  ['Nombre', data.afiliado.nombre],
                  ['Documento', `${data.afiliado.tipo_doc} ${data.afiliado.doc}`],
                  ['Empresa', data.afiliado.empresa],
                  ['Cargo', data.afiliado.cargo],
                  ['EPS', data.afiliado.eps],
                  ['AFP', data.afiliado.afp],
                  ['CCF', data.afiliado.ccf],
                  ['ARL', data.afiliado.arl],
                  ['Teléfono', data.afiliado.tel],
                  ['Email', data.afiliado.email],
                  ['Fecha ingreso', data.afiliado.fecha_ingreso],
                  ['Fecha afiliación', data.afiliado.fecha_afiliacion],
                  ['Detalle', data.afiliado.detalle],
                ].map(([k, v]) => v ? (
                  <div key={k}>
                    <span style={{ fontSize:11,color:C.text2,fontWeight:600 }}>{k}</span>
                    <div style={{ fontSize:13,color:C.text }}>{v}</div>
                  </div>
                ) : null)}
              </div>
              <div style={{ marginTop:10,display:'flex',gap:10,alignItems:'center',flexWrap:'wrap' }}>
                <Badge color={data.afiliado.estado==='ACTIVO'?C.green:C.red} bg={data.afiliado.estado==='ACTIVO'?C.greenBg:C.redBg}>
                  {data.afiliado.estado}
                </Badge>
              </div>
            </div>

            {/* Resumen financiero */}
            <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:16 }}>
              <div style={{ background:C.greenBg,borderRadius:10,padding:14,textAlign:'center' }}>
                <div style={{ fontSize:11,color:C.green,fontWeight:600 }}>Total pagado</div>
                <div style={{ fontSize:18,color:C.green,fontWeight:700 }}>{money(data.total_pagado)}</div>
              </div>
              <div style={{ background:C.redBg,borderRadius:10,padding:14,textAlign:'center' }}>
                <div style={{ fontSize:11,color:C.red,fontWeight:600 }}>Total pendiente</div>
                <div style={{ fontSize:18,color:C.red,fontWeight:700 }}>{money(data.total_pendiente)}</div>
              </div>
            </div>

            {/* Tabla de facturas */}
            {data.facturas.length > 0 && (
              <div style={{ overflowX:'auto',borderRadius:8,border:`1px solid ${C.border}`,marginBottom:16 }}>
                <table style={{ width:'100%',borderCollapse:'collapse',fontSize:12 }}>
                  <thead><tr style={{ background:C.surface2 }}>
                    {['Período','Código','Estado','Total','Banco'].map(h=>(
                      <th key={h} style={{ padding:'8px 10px',textAlign:'left',fontWeight:600,color:C.text2,borderBottom:`1px solid ${C.border}` }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {data.facturas.map(f=>(
                      <tr key={f.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                        <td style={tdc}>{f.mes} {f.anio}</td>
                        <td style={tdc}>{f.codigo}</td>
                        <td style={tdc}>
                          <Badge color={f.estado==='pagado'?C.green:C.red} bg={f.estado==='pagado'?C.greenBg:C.redBg}>
                            {f.estado?.toUpperCase()}
                          </Badge>
                        </td>
                        <td style={tdc}>{money(f.costos)}</td>
                        <td style={tdc}>{f.banco||'—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div style={{ display:'flex',gap:10,justifyContent:'flex-end' }}>
              <Btn variant="accent" onClick={descargarPDF}>Descargar Estado de Cuenta PDF</Btn>
              <Btn variant="secondary" onClick={onClose}>Cerrar</Btn>
            </div>
          </>
        ) : (
          <p style={{ textAlign:'center',color:C.red }}>Error al cargar datos</p>
        )}
      </div>
    </div>
  );
}

// ─── MODAL NOVEDAD DE PAGO ─────────────────────────────────────────────────────
function ModalNovedadPago({ seleccionados, afiliados, onClose, onSuccess }) {
  const [mes, setMes] = useState(MESES[new Date().getMonth()]);
  const [anio, setAnio] = useState(String(anioActual));
  const [obs, setObs] = useState('');
  const [archivos, setArchivos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);

  const crear = useMutation({
    mutationFn: async () => {
      const res = await api.post('/portal/novedades-pago', {
        mes, anio, afiliados_docs: seleccionados, obs,
      });
      const novId = res.data?.id;
      if (archivos.length > 0 && novId) {
        setSubiendo(true);
        await Promise.all(archivos.map(file => {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('afiliado_doc', seleccionados[0] || '');
          fd.append('contexto', 'novedad_pago');
          fd.append('contexto_id', String(novId));
          return api.post('/documentos', fd);
        }));
        setSubiendo(false);
      }
      return res;
    },
    onSuccess: () => { toast.success('Novedad de pago reportada al administrador'); onSuccess(); onClose(); },
    onError: (e) => { setSubiendo(false); const d = e?.response?.data?.detail; toast.error(d || 'Error al reportar novedad'); },
  });

  const selAfiliados = afiliados.filter(a => seleccionados.includes(a.doc));

  return (
    <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.5)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ background:C.surface,borderRadius:14,padding:28,width:480,boxShadow:'0 20px 60px rgba(0,0,0,.3)' }}>
        <h3 style={{ margin:'0 0 16px',color:C.primary }}>Reportar Novedad de Pago SS</h3>

        <p style={{ fontSize:13,color:C.text2,marginBottom:12 }}>
          Se notificará al administrador que los siguientes afiliados pagarán seguridad social:
        </p>

        <div style={{ background:C.surface,borderRadius:8,padding:10,marginBottom:16,maxHeight:140,overflowY:'auto' }}>
          {selAfiliados.map(a => (
            <div key={a.doc} style={{ fontSize:13,padding:'3px 0',color:C.text }}>
              • {a.nombre} <span style={{ color:C.text2 }}>({a.doc})</span>
            </div>
          ))}
        </div>

        <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12 }}>
          <div>
            <label style={lbl}>Mes</label>
            <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
              {MESES.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año</label>
            <select style={inp} value={anio} onChange={e => setAnio(e.target.value)}>
              {ANIOS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>

        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Observaciones (opcional)</label>
          <textarea style={{ ...inp, resize:'vertical', minHeight:60 }} value={obs} onChange={e => setObs(e.target.value)} />
        </div>

        <div style={{ marginBottom:16 }}>
          <label style={lbl}>Adjuntar documentos (opcional)</label>
          <div style={{ border:`2px dashed ${C.border}`,borderRadius:8,padding:'12px',textAlign:'center',
            background:C.surface2,cursor:'pointer' }}
            onClick={()=>document.getElementById('portal-pago-files')?.click()}>
            <input id="portal-pago-files" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx"
              style={{ display:'none' }}
              onChange={e=>{ setArchivos(prev=>[...prev,...Array.from(e.target.files)]); e.target.value=''; }} />
            <div style={{ fontSize:12,color:C.text2 }}>📂 Click para adjuntar comprobantes</div>
          </div>
          {archivos.length > 0 && (
            <div style={{ marginTop:6,display:'flex',flexDirection:'column',gap:3 }}>
              {archivos.map((f,i)=>(
                <div key={i} style={{ display:'flex',alignItems:'center',gap:6,fontSize:11,color:C.text,
                  background:C.surface2,padding:'3px 8px',borderRadius:5 }}>
                  <span style={{ flex:1 }}>{f.name}</span>
                  <span style={{ cursor:'pointer',color:C.red,fontWeight:700 }} onClick={()=>setArchivos(prev=>prev.filter((_,j)=>j!==i))}>×</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display:'flex',gap:10,justifyContent:'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="success" onClick={() => crear.mutate()} disabled={crear.isPending||subiendo}>
            {subiendo ? 'Subiendo archivos...' : crear.isPending ? 'Enviando...' : 'Confirmar y Notificar'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

// ─── MODAL NOVEDAD DE AFILIADO ────────────────────────────────────────────────
function ModalNovedadAfiliado({ afiliado, onClose, onSuccess }) {
  const TIPOS = [
    'Incapacidad médica', 'Licencia de maternidad/paternidad',
    'Accidente laboral', 'Cambio de salario', 'Cambio de cargo',
    'Suspensión', 'Ausentismo', 'Otro',
  ];
  const [tipo, setTipo] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [archivos, setArchivos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);

  const crear = useMutation({
    mutationFn: async () => {
      if (!tipo) throw new Error('Selecciona el tipo de novedad');
      if (!descripcion.trim()) throw new Error('La descripción es obligatoria');
      const res = await api.post('/portal/solicitudes-novedad', { afiliado_doc: afiliado.doc, tipo, descripcion });
      const novId = res.data?.id;
      if (archivos.length > 0 && novId) {
        setSubiendo(true);
        await Promise.all(archivos.map(file => {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('afiliado_doc', afiliado.doc);
          fd.append('contexto', 'novedad_afil');
          fd.append('contexto_id', String(novId));
          return api.post('/documentos', fd);
        }));
        setSubiendo(false);
      }
      return res;
    },
    onSuccess: () => { toast.success('Novedad enviada al administrador'); onSuccess(); onClose(); },
    onError: (e) => { setSubiendo(false); const d = e?.message || e?.response?.data?.detail; toast.error(d || 'Error'); },
  });

  const removeFile = (idx) => setArchivos(prev => prev.filter((_,i) => i !== idx));

  return (
    <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.5)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ background:C.surface,borderRadius:14,padding:28,width:500,boxShadow:'0 20px 60px rgba(0,0,0,.3)',maxHeight:'90vh',overflowY:'auto' }}>
        <h3 style={{ margin:'0 0 16px',color:C.primary }}>Reportar Novedad del Afiliado</h3>

        <div style={{ background:C.surface2,borderRadius:8,padding:12,marginBottom:16 }}>
          <div style={{ fontWeight:600,fontSize:14,color:C.text }}>{afiliado.nombre}</div>
          <div style={{ fontSize:12,color:C.text2 }}>{afiliado.tipo_doc} {afiliado.doc} — {afiliado.empresa}</div>
        </div>

        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Tipo de novedad *</label>
          <select style={inp} value={tipo} onChange={e => setTipo(e.target.value)}>
            <option value="">— Seleccionar tipo —</option>
            {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Descripción *</label>
          <textarea style={{ ...inp, resize:'vertical', minHeight:90 }}
            placeholder="Describe la situación del afiliado..."
            value={descripcion} onChange={e => setDescripcion(e.target.value)} />
        </div>

        <div style={{ marginBottom:16 }}>
          <label style={lbl}>Adjuntar documentos (opcional)</label>
          <div style={{ border:`2px dashed ${C.border}`,borderRadius:8,padding:'14px',textAlign:'center',
            background:C.surface2,cursor:'pointer',position:'relative' }}
            onClick={()=>document.getElementById('portal-nov-files')?.click()}>
            <input id="portal-nov-files" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx"
              style={{ display:'none' }}
              onChange={e=>{ setArchivos(prev=>[...prev,...Array.from(e.target.files)]); e.target.value=''; }} />
            <div style={{ fontSize:13,color:C.text2 }}>📂 Click para seleccionar archivos</div>
          </div>
          {archivos.length > 0 && (
            <div style={{ marginTop:8,display:'flex',flexDirection:'column',gap:4 }}>
              {archivos.map((f,i)=>(
                <div key={i} style={{ display:'flex',alignItems:'center',gap:8,fontSize:12,color:C.text,
                  background:C.surface2,padding:'4px 8px',borderRadius:6 }}>
                  <span style={{ flex:1 }}>{f.name} ({(f.size/1024).toFixed(0)} KB)</span>
                  <span style={{ cursor:'pointer',color:C.red,fontWeight:700 }} onClick={()=>removeFile(i)}>×</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display:'flex',gap:10,justifyContent:'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="accent" onClick={() => crear.mutate()} disabled={crear.isPending||subiendo||!tipo||!descripcion.trim()}>
            {subiendo ? 'Subiendo archivos...' : crear.isPending ? 'Enviando...' : 'Enviar novedad'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

// ─── MODAL SOLICITAR RETIRO ────────────────────────────────────────────────────
function ModalRetiro({ afiliado, onClose, onSuccess }) {
  const [motivo, setMotivo] = useState('');
  const [obs, setObs] = useState('');

  const crear = useMutation({
    mutationFn: () => {
      if (!motivo.trim()) return Promise.reject(new Error('El motivo es obligatorio'));
      return api.post('/portal/solicitar-retiro', { afiliado_doc: afiliado.doc, motivo, obs });
    },
    onSuccess: () => { toast.success('Solicitud de retiro enviada al administrador'); onSuccess(); onClose(); },
    onError: (e) => { const d = e?.message || e?.response?.data?.detail; toast.error(d || 'Error'); },
  });

  return (
    <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.5)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ background:C.surface,borderRadius:14,padding:28,width:440,boxShadow:'0 20px 60px rgba(0,0,0,.3)' }}>
        <h3 style={{ margin:'0 0 16px',color:C.primary }}>Solicitar Retiro</h3>

        <div style={{ background:C.surface,borderRadius:8,padding:12,marginBottom:16 }}>
          <div style={{ fontWeight:600,fontSize:14,color:C.text }}>{afiliado.nombre}</div>
          <div style={{ fontSize:12,color:C.text2 }}>{afiliado.tipo_doc} {afiliado.doc} — {afiliado.empresa}</div>
        </div>

        <p style={{ fontSize:13,color:C.text2,marginBottom:12 }}>
          El retiro será gestionado por el empleado correspondiente. Solo se registra la solicitud.
        </p>

        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Motivo *</label>
          <select style={inp} value={motivo} onChange={e => setMotivo(e.target.value)}>
            <option value="">— Seleccionar motivo —</option>
            <option value="Renuncia voluntaria">Renuncia voluntaria</option>
            <option value="Terminación de contrato">Terminación de contrato</option>
            <option value="Pensión">Pensión</option>
            <option value="Fallecimiento">Fallecimiento</option>
            <option value="Otro">Otro</option>
          </select>
        </div>

        <div style={{ marginBottom:16 }}>
          <label style={lbl}>Observaciones</label>
          <textarea style={{ ...inp, resize:'vertical', minHeight:70 }} value={obs} onChange={e => setObs(e.target.value)} />
        </div>

        <div style={{ display:'flex',gap:10,justifyContent:'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="danger" onClick={() => crear.mutate()} disabled={crear.isPending||!motivo}>
            {crear.isPending ? 'Enviando...' : 'Solicitar retiro'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

// ─── ADJUNTOS POR NOVEDAD ────────────────────────────────────────────────────
function DocsNovedad({ novedadId, contexto = 'novedad_resp' }) {
  const [open, setOpen] = useState(false);
  const { data: docs=[], isLoading } = useQuery({
    queryKey: ['docs-novedad-portal', contexto, novedadId],
    queryFn: () => api.get('/documentos', { params: { contexto, contexto_id: novedadId } }).then(r => r.data),
    enabled: open,
  });
  if (!open) return (
    <button onClick={() => setOpen(true)}
      style={{ fontSize:11, color:C.blue, background:'none', border:'none', cursor:'pointer', padding:0, textDecoration:'underline', marginTop:6, display:'block' }}>
      📎 Ver adjuntos
    </button>
  );
  return (
    <div style={{ marginTop:8 }}>
      {isLoading ? <span style={{ fontSize:11, color:C.text2 }}>Cargando...</span> :
        docs.length === 0 ? <span style={{ fontSize:11, color:C.text2 }}>Sin adjuntos</span> :
        docs.map(d => (
          <div key={d.id} style={{ fontSize:12, marginBottom:3 }}>
            <span style={{ color:C.blue, cursor:'pointer', textDecoration:'underline' }}
              onClick={async () => {
                try {
                  const res = await api.get(`/documentos/${d.id}/descargar`, { responseType:'blob' });
                  const a = document.createElement('a'); a.href = URL.createObjectURL(res.data); a.download = d.nombre; a.click();
                } catch { toast.error('Error al descargar archivo'); }
              }}>
              📄 {d.nombre}
            </span>
            <span style={{ color:C.text2, fontSize:10, marginLeft:6 }}>{d.subido_por}</span>
          </div>
        ))
      }
      <button onClick={() => setOpen(false)}
        style={{ fontSize:10, color:C.text2, background:'none', border:'none', cursor:'pointer', padding:0, marginTop:4 }}>
        Ocultar
      </button>
    </div>
  );
}

// ─── HISTORIAL ─────────────────────────────────────────────────────────────────
function TabHistorial() {
  const [subtab, setSubtab] = useState('novedades');
  const [fecha, setFecha] = useState('');
  const [estado, setEstado] = useState('');

  const { data: novedades=[] } = useQuery({ queryKey:['portal-novedades'], queryFn:()=>api.get('/portal/novedades-pago').then(r=>r.data), refetchInterval:60_000 });
  const { data: retiros=[] }   = useQuery({ queryKey:['portal-retiros'],   queryFn:()=>api.get('/portal/solicitudes-retiro').then(r=>r.data), refetchInterval:60_000 });
  const { data: novAfil=[] }   = useQuery({ queryKey:['portal-novedades-afil'], queryFn:()=>api.get('/portal/solicitudes-novedad').then(r=>r.data), refetchInterval:60_000 });

  const TABS = [
    { id:'novedades', label:`💳 Novedades de Pago (${novedades.length})` },
    { id:'retiros',   label:`🚪 Retiros (${retiros.length})` },
    { id:'afiliados', label:`📝 Novedades Afiliados (${novAfil.length})` },
  ];

  const listas = { novedades, retiros, afiliados: novAfil };
  const listaActual = listas[subtab] || [];

  const estadoOpts = {
    novedades: ['pendiente','procesado'],
    retiros:   ['pendiente','ejecutado','rechazado'],
    afiliados: ['pendiente','atendido'],
  };

  const filtrada = listaActual.filter(item => {
    if (fecha  && item.creado?.slice(0,10) !== fecha) return false;
    if (estado && item.estado !== estado) return false;
    return true;
  });

  const colorEstado = (e) => {
    if (e === 'procesado' || e === 'ejecutado' || e === 'atendido') return [C.green, C.greenBg];
    if (e === 'rechazado') return [C.red, C.redBg];
    return [C.amber, C.amberBg];
  };

  const filtStyle = { padding:'6px 10px', border:`1px solid ${C.border}`, borderRadius:6, fontSize:12, outline:'none', color:C.text, background:C.surface };

  return (
    <div>
      {/* Sub-tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16, flexWrap:'wrap' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => { setSubtab(t.id); setFecha(''); setEstado(''); }} style={{
            padding:'7px 16px', borderRadius:8, border:`1px solid ${subtab===t.id ? C.primary : C.border}`,
            fontSize:12, fontWeight:600, cursor:'pointer',
            background: subtab===t.id ? C.primary : C.surface,
            color: subtab===t.id ? '#fff' : C.text2,
          }}>{t.label}</button>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} style={filtStyle} />
        <select value={estado} onChange={e => setEstado(e.target.value)} style={filtStyle}>
          <option value="">Todos los estados</option>
          {(estadoOpts[subtab]||[]).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {(fecha || estado) && (
          <button onClick={() => { setFecha(''); setEstado(''); }}
            style={{ background:'none', border:'none', cursor:'pointer', color:C.text2, fontSize:12 }}>
            ✕ Limpiar
          </button>
        )}
        <span style={{ fontSize:12, color:C.text2, marginLeft:'auto' }}>{filtrada.length} resultado(s)</span>
      </div>

      {/* Lista */}
      {filtrada.length === 0 ? (
        <div style={{ textAlign:'center', padding:40, color:C.text2 }}>
          <div style={{ fontSize:32, marginBottom:8 }}>📭</div>
          Sin registros
        </div>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(300px, 1fr))', gap:12 }}>
          {filtrada.map(item => {
            const [color, bg] = colorEstado(item.estado);
            return (
              <div key={item.id} style={{ background:C.surface, borderRadius:10, border:`1px solid ${C.border}`, padding:14 }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
                  <div style={{ fontWeight:600, fontSize:13, color:C.text }}>
                    {subtab === 'novedades' ? `${item.mes} ${item.anio}` : item.afiliado_nombre}
                  </div>
                  <Badge color={color} bg={bg}>{item.estado}</Badge>
                </div>
                {subtab === 'novedades' && (
                  <div style={{ fontSize:12, color:C.text2 }}>
                    {item.afiliados?.length} afiliado(s): {item.afiliados?.slice(0,3).join(', ')}{item.afiliados?.length>3?` +${item.afiliados.length-3}`:''}
                  </div>
                )}
                {subtab === 'retiros' && (
                  <>
                    <div style={{ fontSize:12, color:C.text2 }}>Doc: {item.afiliado_doc}</div>
                    <div style={{ fontSize:12, color:C.text2 }}>Motivo: {item.motivo}</div>
                  </>
                )}
                {subtab === 'afiliados' && (
                  <>
                    <div style={{ fontSize:12, color:C.blue, fontWeight:600 }}>{item.tipo}</div>
                    <div style={{ fontSize:12, color:C.text2, marginTop:2 }}>{item.descripcion}</div>
                  </>
                )}
                {item.obs && <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>Obs: {item.obs}</div>}
                {item.respuesta && (
                  <div style={{ fontSize:12, color:C.blue, background:C.blueBg, borderRadius:6, padding:'6px 10px', marginTop:8 }}>
                    <strong>✅ Respuesta:</strong> {item.respuesta}
                  </div>
                )}
                <DocsNovedad novedadId={item.id} contexto={subtab === 'novedades' ? 'resp_pago' : subtab === 'retiros' ? 'resp_retiro' : 'resp_afil'} />
                <div style={{ fontSize:11, color:C.text2, marginTop:6 }}>{new Date(item.creado).toLocaleString('es-CO')}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── CAMPANA DE NOTIFICACIONES ─────────────────────────────────────────────────
function CampanaNotif() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const { data: notifs=[] } = useQuery({
    queryKey: ['portal-notifs'],
    queryFn: () => api.get('/tareas/notificaciones').then(r => r.data),
    refetchInterval: 60_000,
  });

  const leer = useMutation({
    mutationFn: () => api.put('/tareas/notificaciones/leer'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-notifs'] }),
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error al marcar como leídas'),
  });
  const limpiar = useMutation({
    mutationFn: () => api.delete('/tareas/notificaciones'),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-notifs'] }); setOpen(false); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error al limpiar notificaciones'),
  });

  const noLeidas = notifs.filter(n => !n.leida).length;

  const handleOpen = () => {
    setOpen(v => !v);
    if (!open && noLeidas > 0) leer.mutate();
  };

  return (
    <div ref={ref} style={{ position:'relative' }}>
      <button onClick={handleOpen} style={{ background:'rgba(255,255,255,.15)', border:'1px solid rgba(255,255,255,.3)', borderRadius:8, padding:'6px 12px', color:'#fff', cursor:'pointer', fontSize:16, position:'relative' }}>
        🔔
        {noLeidas > 0 && (
          <span style={{ position:'absolute', top:-6, right:-6, background:C.red, color:'#fff', borderRadius:'50%', width:18, height:18, fontSize:10, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center' }}>
            {noLeidas > 9 ? '9+' : noLeidas}
          </span>
        )}
      </button>
      {open && (
        <div style={{ position:'absolute', right:0, top:'calc(100% + 8px)', width:340, maxHeight:420, overflowY:'auto', background:C.surface, borderRadius:12, boxShadow:'0 8px 32px rgba(0,0,0,.2)', zIndex:200, border:`1px solid ${C.border}` }}>
          <div style={{ padding:'12px 16px', borderBottom:`1px solid ${C.border}`, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontWeight:700, fontSize:14, color:C.text }}>Notificaciones</span>
            {notifs.length > 0 && (
              <button onClick={() => limpiar.mutate()} style={{ background:'none', border:'none', fontSize:11, color:C.text2, cursor:'pointer' }}>Limpiar</button>
            )}
          </div>
          {notifs.length === 0 ? (
            <p style={{ padding:'20px 16px', color:C.text2, fontSize:13, margin:0 }}>Sin notificaciones.</p>
          ) : (
            notifs.map(n => (
              <div key={n.id} style={{ padding:'10px 16px', borderBottom:`1px solid ${C.border}`, background:n.leida ? '#fff' : C.blueBg }}>
                <div style={{ fontSize:13, color:C.text, lineHeight:1.4 }}>{n.mensaje}</div>
                <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>{new Date(n.creado).toLocaleString('es-CO')}</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─── PORTAL PRINCIPAL ──────────────────────────────────────────────────────────
export default function PortalCliente() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const handleLogout = () => { logout(); navigate('/login'); };
  const [dark, setDark] = useState(() => localStorage.getItem('theme-portal') === 'dark');
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme-portal', dark ? 'dark' : 'light');
  }, [dark]);
  const [q, setQ] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroEmpresa, setFiltroEmpresa] = useState('');
  const [tab, setTab] = useState('afiliados');
  const [seleccionados, setSeleccionados] = useState([]);
  const [resumenDoc, setResumenDoc] = useState(null);
  const [retiroAfil, setRetiroAfil] = useState(null);
  const [novedadAfil, setNovedadAfil] = useState(null);
  const [showNovedadModal, setShowNovedadModal] = useState(false);
  const [pagina, setPagina] = useState(1);
  const POR_PAGINA = 50;

  const { data: afiliados = [], isLoading } = useQuery({
    queryKey: ['portal-afiliados'],
    queryFn: () => api.get('/portal/afiliados').then(r => r.data),
    refetchInterval: 120_000,
  });

  const empresasUnicas = useMemo(() => [...new Set(afiliados.map(a => a.empresa).filter(Boolean))].sort(), [afiliados]);
  const estadosUnicos  = useMemo(() => [...new Set(afiliados.map(a => a.estado).filter(Boolean))].sort(), [afiliados]);

  const filtrados = useMemo(() => {
    return afiliados.filter(a => {
      if (q.trim()) {
        const lower = q.toLowerCase();
        if (!a.nombre.toLowerCase().includes(lower) && !a.doc.includes(lower)) return false;
      }
      if (filtroEstado  && a.estado   !== filtroEstado)  return false;
      if (filtroEmpresa && a.empresa  !== filtroEmpresa) return false;
      return true;
    });
  }, [afiliados, q, filtroEstado, filtroEmpresa]);

  const limpiarFiltros = () => { setQ(''); setFiltroEstado(''); setFiltroEmpresa(''); setPagina(1); };

  useEffect(() => { setPagina(1); }, [q, filtroEstado, filtroEmpresa]);

  const paginados = useMemo(() => {
    const start = (pagina - 1) * POR_PAGINA;
    return filtrados.slice(start, start + POR_PAGINA);
  }, [filtrados, pagina, POR_PAGINA]);

  const totalPaginas = Math.ceil(filtrados.length / POR_PAGINA);

  const descargarExcel = useCallback(() => {
    api.get('/portal/exportar-excel', { responseType: 'blob' })
      .then(r => {
        const url = window.URL.createObjectURL(new Blob([r.data]));
        const a = document.createElement('a'); a.href = url;
        a.download = 'mis-afiliados.xlsx'; a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => toast.error('Error al exportar Excel'));
  }, []);

  const toggleSel = (doc) => setSeleccionados(prev =>
    prev.includes(doc) ? prev.filter(d => d !== doc) : [...prev, doc]
  );
  const toggleTodos = () => {
    if (seleccionados.length === filtrados.length) setSeleccionados([]);
    else setSeleccionados(filtrados.map(a => a.doc));
  };

  const estadoColor = (est) => ({
    bg: est === 'ACTIVO' ? C.greenBg : C.redBg,
    color: est === 'ACTIVO' ? C.green : C.red,
  });

  const { activos, retirados, suspendidos } = useMemo(() => {
    let act = 0, ret = 0, sus = 0;
    for (const a of afiliados) {
      if (a.estado === 'ACTIVO') act++;
      else if (a.estado === 'RETIRADO') ret++;
      else if (a.estado === 'SUSPENDIDO') sus++;
    }
    return { activos: act, retirados: ret, suspendidos: sus };
  }, [afiliados]);

  return (
    <div style={{ minHeight:'100vh', background:'var(--c-bg)', fontFamily:'Inter, system-ui, sans-serif' }}>
      {/* Header único */}
      <div style={{ background:C.primary, padding:'0 24px' }}>
        <div style={{ maxWidth:1100, margin:'0 auto' }}>
          {/* Barra top */}
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 0 10px' }}>
            <span style={{ color:'#fff', fontSize:18, fontWeight:700 }}>
              BBC <span style={{ color:C.accent }}>File</span>
              <span style={{ color:'rgba(255,255,255,.5)', fontSize:12, fontWeight:400, marginLeft:10 }}>Portal del Cliente</span>
            </span>
            <div style={{ display:'flex', alignItems:'center', gap:12 }}>
              <span style={{ color:'rgba(255,255,255,.75)', fontSize:13 }}>👤 {user?.nombre}</span>
              <CampanaNotif />
              <button onClick={() => setDark(d => !d)} title={dark ? 'Modo claro' : 'Modo oscuro'} style={{ padding:'5px 10px', background:'rgba(255,255,255,.15)', border:'1px solid rgba(255,255,255,.25)', borderRadius:6, color:'#fff', fontSize:15, cursor:'pointer' }}>
                {dark ? '☀️' : '🌙'}
              </button>
              <button onClick={handleLogout} style={{ padding:'5px 12px', background:'rgba(255,255,255,.15)', border:'1px solid rgba(255,255,255,.25)', borderRadius:6, color:'#fff', fontSize:12, cursor:'pointer' }}>
                Salir
              </button>
            </div>
          </div>
          {/* Stats en header */}
          <div style={{ display:'flex', gap:24, padding:'10px 0 16px', borderTop:'1px solid rgba(255,255,255,.15)' }}>
            {[
              ['Total', afiliados.length, C.accent],
              ['Activos', activos, '#4ade80'],
              ['Retirados', retirados, '#f87171'],
              ['Suspendidos', suspendidos, '#fcd34d'],
            ].map(([lbl, val, color]) => (
              <div key={lbl}>
                <div style={{ fontSize:11, color:'rgba(255,255,255,.55)', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.05em' }}>{lbl}</div>
                <div style={{ fontSize:22, fontWeight:700, color }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

    <div style={{ maxWidth:1100, margin:'0 auto', padding:24 }}>
      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:20, borderBottom:`2px solid ${C.border}`, paddingBottom:0 }}>
        {[['afiliados','👥 Mis Afiliados'],['historial','📋 Historial']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding:'9px 20px', borderRadius:'8px 8px 0 0', border:`1px solid ${tab===id?C.border:'transparent'}`,
            borderBottom: tab===id?`2px solid ${C.primary}`:'none',
            fontSize:13, fontWeight:600, cursor:'pointer',
            background: tab===id ? C.surface : 'transparent',
            color: tab===id ? C.primary : C.text2,
            marginBottom: tab===id ? -2 : 0,
          }}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'afiliados' && (
        <>
          {/* Filtros */}
          <div style={{ background:C.surface, borderRadius:10, border:`1px solid ${C.border}`, padding:'12px 16px', marginBottom:16 }}>
            <div style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
              <div>
                <label style={lbl}>Buscar</label>
                <input type="text" placeholder="Nombre o cédula..." value={q} onChange={e => setQ(e.target.value)}
                  style={{ ...inp, width:220 }} />
              </div>
              <div>
                <label style={lbl}>Estado</label>
                <select style={{ ...inp, width:160 }} value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}>
                  <option value="">Todos</option>
                  {estadosUnicos.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>
              <div>
                <label style={lbl}>Empresa</label>
                <select style={{ ...inp, width:200 }} value={filtroEmpresa} onChange={e => setFiltroEmpresa(e.target.value)}>
                  <option value="">Todas</option>
                  {empresasUnicas.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>
              {(q || filtroEstado || filtroEmpresa) && (
                <Btn variant="secondary" onClick={limpiarFiltros}>Limpiar filtros</Btn>
              )}
              <div style={{ flex:1 }} />
              <Btn variant="secondary" onClick={descargarExcel}>Exportar Excel</Btn>
              {seleccionados.length > 0 && (
                <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                  <span style={{ fontSize:13, color:C.text2 }}>{seleccionados.length} seleccionado(s)</span>
                  <Btn variant="success" onClick={() => setShowNovedadModal(true)}>Reportar novedad de pago</Btn>
                  <Btn variant="secondary" onClick={() => setSeleccionados([])}>Limpiar selección</Btn>
                </div>
              )}
            </div>
          </div>

          {/* Cards de afiliados */}
          {isLoading ? (
            <p style={{ textAlign:'center', color:C.text2, padding:40 }}>Cargando afiliados...</p>
          ) : filtrados.length === 0 ? (
            <div style={{ textAlign:'center', padding:40, color:C.text2 }}>
              <div style={{ fontSize:40, marginBottom:8 }}>🔍</div>
              {q ? `Sin resultados para "${q}"` : 'No hay afiliados registrados.'}
            </div>
          ) : (
            <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}`, background:C.surface }}>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
                <thead>
                  <tr style={{ background:C.surface2 }}>
                    <th style={{ padding:'10px 12px', borderBottom:`1px solid ${C.border}` }}>
                      <input type="checkbox" checked={seleccionados.length===filtrados.length&&filtrados.length>0} onChange={toggleTodos} />
                    </th>
                    {['Nombre','Documento','Empresa','EPS','AFP','Estado','Detalle','Novedades','Acciones'].map(h => (
                      <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paginados.map(a => {
                    const sel = seleccionados.includes(a.doc);
                    const ec = estadoColor(a.estado);
                    return (
                      <tr key={a.id} style={{ borderBottom:`1px solid ${C.border}`, background:sel?C.blueBg:'transparent' }}>
                        <td style={tdc}><input type="checkbox" checked={sel} onChange={() => toggleSel(a.doc)} /></td>
                        <td style={tdc}><span style={{ fontWeight:600 }}>{a.nombre}</span></td>
                        <td style={tdc}><span style={{ color:C.text2 }}>{a.tipo_doc} {a.doc}</span></td>
                        <td style={tdc}>{a.empresa}</td>
                        <td style={tdc}>{a.eps||'—'}</td>
                        <td style={tdc}>{a.afp||'—'}</td>
                        <td style={tdc}><Badge color={ec.color} bg={ec.bg}>{a.estado}</Badge></td>
                        <td style={{ ...tdc, maxWidth:200 }}>
                          {a.detalle
                            ? <span style={{ color:C.blue, fontSize:12 }}>{a.detalle}</span>
                            : <span style={{ color:C.text2, fontSize:12 }}>—</span>}
                        </td>
                        <td style={tdc}>
                          {a.novedades
                            ? <span style={{ color:C.amber, fontSize:12, fontWeight:600 }}>{a.novedades}</span>
                            : <span style={{ color:C.text2, fontSize:12 }}>—</span>}
                        </td>
                        <td style={tdc}>
                          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                            <Btn size="sm" onClick={() => setResumenDoc(a.doc)}>Ver</Btn>
                            <Btn size="sm" variant="accent" onClick={() => setNovedadAfil(a)}>Novedad</Btn>
                            <Btn size="sm" variant="danger" onClick={() => setRetiroAfil(a)}>Retiro</Btn>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {totalPaginas > 1 && (
            <div style={{ display:'flex', gap:8, justifyContent:'center', alignItems:'center', padding:'12px 0' }}>
              <Btn variant="secondary" size="sm" onClick={() => setPagina(p => Math.max(1, p-1))} disabled={pagina===1}>← Anterior</Btn>
              <span style={{ fontSize:13, color:C.text2 }}>Página {pagina} de {totalPaginas} ({filtrados.length} afiliados)</span>
              <Btn variant="secondary" size="sm" onClick={() => setPagina(p => Math.min(totalPaginas, p+1))} disabled={pagina===totalPaginas}>Siguiente →</Btn>
            </div>
          )}
        </>
      )}

      {tab === 'historial' && <TabHistorial />}

      {/* Modales */}
      {resumenDoc && <ModalResumen doc={resumenDoc} onClose={() => setResumenDoc(null)} />}

      {showNovedadModal && (
        <ModalNovedadPago
          seleccionados={seleccionados}
          afiliados={afiliados}
          onClose={() => setShowNovedadModal(false)}
          onSuccess={() => {
            setSeleccionados([]);
            qc.invalidateQueries({ queryKey: ['portal-novedades'] });
          }}
        />
      )}

      {retiroAfil && (
        <ModalRetiro
          afiliado={retiroAfil}
          onClose={() => setRetiroAfil(null)}
          onSuccess={() => qc.invalidateQueries({ queryKey: ['portal-retiros'] })}
        />
      )}

      {novedadAfil && (
        <ModalNovedadAfiliado
          afiliado={novedadAfil}
          onClose={() => setNovedadAfil(null)}
          onSuccess={() => qc.invalidateQueries({ queryKey: ['portal-novedades-afil'] })}
        />
      )}
    </div>
    </div>
  );
}
