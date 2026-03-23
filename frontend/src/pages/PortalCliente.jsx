import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear();
const ANIOS = [anioActual-1, anioActual, anioActual+1].map(String);

const C = {
  primary: '#0D3B6E', accent: '#E89B2A',
  green: '#16A34A', greenBg: '#DCFCE7',
  red: '#DC2626', redBg: '#FEE2E2',
  blue: '#1D4ED8', blueBg: '#DBEAFE',
  yellow: '#92400E', yellowBg: '#FEF3C7',
  border: '#E2E8F0', surface: '#F8FAFC', surface2: '#F1F5F9',
  text: '#1E293B', text2: '#64748B',
};

const money = (v) => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(v || 0);

const inp = { width:'100%', padding:'8px 10px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, boxSizing:'border-box', outline:'none' };
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
    secondary: { background:'#fff',      color:C.text,  border:`1px solid ${C.border}` },
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
    api.get(`/afiliados/${data.afiliado.id}/estado-cuenta`, { responseType: 'blob' })
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
      <div style={{ background:'#fff',borderRadius:14,padding:28,width:700,maxWidth:'95vw',boxShadow:'0 20px 60px rgba(0,0,0,.3)',margin:'0 auto 40px' }}>
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
                <Badge color={C.blue} bg={C.blueBg}>{data.afiliado.estado_srv}</Badge>
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

  const crear = useMutation({
    mutationFn: () => api.post('/portal/novedades-pago', {
      mes, anio, afiliados_docs: seleccionados, obs,
    }),
    onSuccess: () => { toast.success('Novedad de pago reportada al administrador'); onSuccess(); onClose(); },
    onError: (e) => { const d = e?.response?.data?.detail; toast.error(d || 'Error al reportar novedad'); },
  });

  const selAfiliados = afiliados.filter(a => seleccionados.includes(a.doc));

  return (
    <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.5)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ background:'#fff',borderRadius:14,padding:28,width:480,boxShadow:'0 20px 60px rgba(0,0,0,.3)' }}>
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

        <div style={{ marginBottom:16 }}>
          <label style={lbl}>Observaciones (opcional)</label>
          <textarea style={{ ...inp, resize:'vertical', minHeight:60 }} value={obs} onChange={e => setObs(e.target.value)} />
        </div>

        <div style={{ display:'flex',gap:10,justifyContent:'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="success" onClick={() => crear.mutate()} disabled={crear.isPending}>
            {crear.isPending ? 'Enviando...' : 'Confirmar y Notificar'}
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

  const crear = useMutation({
    mutationFn: () => {
      if (!tipo) return Promise.reject(new Error('Selecciona el tipo de novedad'));
      if (!descripcion.trim()) return Promise.reject(new Error('La descripción es obligatoria'));
      return api.post('/portal/solicitudes-novedad', { afiliado_doc: afiliado.doc, tipo, descripcion });
    },
    onSuccess: () => { toast.success('Novedad enviada al administrador'); onSuccess(); onClose(); },
    onError: (e) => { const d = e?.message || e?.response?.data?.detail; toast.error(d || 'Error'); },
  });

  return (
    <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.5)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
      <div style={{ background:'#fff',borderRadius:14,padding:28,width:460,boxShadow:'0 20px 60px rgba(0,0,0,.3)' }}>
        <h3 style={{ margin:'0 0 16px',color:C.primary }}>Reportar Novedad del Afiliado</h3>

        <div style={{ background:C.surface,borderRadius:8,padding:12,marginBottom:16 }}>
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

        <div style={{ marginBottom:16 }}>
          <label style={lbl}>Descripción *</label>
          <textarea style={{ ...inp, resize:'vertical', minHeight:90 }}
            placeholder="Describe la situación del afiliado..."
            value={descripcion} onChange={e => setDescripcion(e.target.value)} />
        </div>

        <div style={{ display:'flex',gap:10,justifyContent:'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="accent" onClick={() => crear.mutate()} disabled={crear.isPending||!tipo||!descripcion.trim()}>
            {crear.isPending ? 'Enviando...' : 'Enviar novedad'}
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
      <div style={{ background:'#fff',borderRadius:14,padding:28,width:440,boxShadow:'0 20px 60px rgba(0,0,0,.3)' }}>
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

// ─── HISTORIAL ─────────────────────────────────────────────────────────────────
function TabHistorial() {
  const hoy = new Date().toISOString().slice(0, 10);
  const [fechaNov, setFechaNov] = useState(hoy);
  const [fechaRet, setFechaRet] = useState(hoy);
  const [fechaNovAfil, setFechaNovAfil] = useState(hoy);

  const { data: novedades=[] } = useQuery({
    queryKey: ['portal-novedades'],
    queryFn: () => api.get('/portal/novedades-pago').then(r => r.data),
    refetchInterval: 60_000,
  });
  const { data: retiros=[] } = useQuery({
    queryKey: ['portal-retiros'],
    queryFn: () => api.get('/portal/solicitudes-retiro').then(r => r.data),
    refetchInterval: 60_000,
  });
  const { data: novedadesAfil=[] } = useQuery({
    queryKey: ['portal-novedades-afil'],
    queryFn: () => api.get('/portal/solicitudes-novedad').then(r => r.data),
    refetchInterval: 60_000,
  });

  const filtraPorDia = (lista, fecha) => {
    if (!fecha) return lista;
    return lista.filter(item => item.creado?.slice(0, 10) === fecha);
  };

  const novFiltradas     = filtraPorDia(novedades, fechaNov);
  const retFiltrados     = filtraPorDia(retiros, fechaRet);
  const novAfilFiltradas = filtraPorDia(novedadesAfil, fechaNovAfil);

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:20 }}>
      {/* Novedades de pago */}
      <div>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
          <h4 style={{ color:C.primary, margin:0, fontSize:14 }}>Novedades de Pago</h4>
          <input type="date" value={fechaNov} onChange={e => setFechaNov(e.target.value)}
            style={{ padding:'4px 8px', border:`1px solid ${C.border}`, borderRadius:6, fontSize:12, outline:'none' }} />
          {fechaNov !== hoy && (
            <button onClick={() => setFechaNov(hoy)}
              style={{ background:'none', border:'none', cursor:'pointer', color:C.text2, fontSize:11 }}>
              Hoy
            </button>
          )}
        </div>
        {novFiltradas.length === 0 ? (
          <p style={{ color:C.text2, fontSize:13 }}>Sin novedades para esta fecha.</p>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {novFiltradas.map(n => (
              <div key={n.id} style={{ background:'#fff', borderRadius:8, border:`1px solid ${C.border}`, padding:12 }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:4 }}>
                  <span style={{ fontWeight:600, fontSize:13, color:C.text }}>{n.mes} {n.anio}</span>
                  <Badge color={n.estado==='procesado'?C.green:C.yellow} bg={n.estado==='procesado'?C.greenBg:C.yellowBg}>
                    {n.estado}
                  </Badge>
                </div>
                <div style={{ fontSize:12, color:C.text2 }}>{n.afiliados.length} afiliado(s): {n.afiliados.slice(0,3).join(', ')}{n.afiliados.length>3?` y ${n.afiliados.length-3} más`:''}</div>
                {n.obs && <div style={{ fontSize:11, color:C.text2, marginTop:2 }}>Obs: {n.obs}</div>}
                {n.respuesta && (
                  <div style={{ fontSize:12, color:C.blue, background:C.blueBg, borderRadius:6, padding:'4px 8px', marginTop:6 }}>
                    <strong>Respuesta admin:</strong> {n.respuesta}
                  </div>
                )}
                <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>{new Date(n.creado).toLocaleString('es-CO')}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Solicitudes de retiro */}
      <div>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
          <h4 style={{ color:C.primary, margin:0, fontSize:14 }}>Solicitudes de Retiro</h4>
          <input type="date" value={fechaRet} onChange={e => setFechaRet(e.target.value)}
            style={{ padding:'4px 8px', border:`1px solid ${C.border}`, borderRadius:6, fontSize:12, outline:'none' }} />
          {fechaRet !== hoy && (
            <button onClick={() => setFechaRet(hoy)}
              style={{ background:'none', border:'none', cursor:'pointer', color:C.text2, fontSize:11 }}>
              Hoy
            </button>
          )}
        </div>
        {retFiltrados.length === 0 ? (
          <p style={{ color:C.text2, fontSize:13 }}>Sin solicitudes para esta fecha.</p>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {retFiltrados.map(r => (
              <div key={r.id} style={{ background:'#fff', borderRadius:8, border:`1px solid ${C.border}`, padding:12 }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:4 }}>
                  <span style={{ fontWeight:600, fontSize:13, color:C.text }}>{r.afiliado_nombre}</span>
                  <Badge color={r.estado==='ejecutado'?C.green:r.estado==='rechazado'?C.red:C.yellow}
                         bg={r.estado==='ejecutado'?C.greenBg:r.estado==='rechazado'?C.redBg:C.yellowBg}>
                    {r.estado}
                  </Badge>
                </div>
                <div style={{ fontSize:12, color:C.text2 }}>Doc: {r.afiliado_doc}</div>
                <div style={{ fontSize:12, color:C.text2 }}>Motivo: {r.motivo}</div>
                {r.obs && <div style={{ fontSize:11, color:C.text2, marginTop:2 }}>Obs: {r.obs}</div>}
                {r.respuesta && (
                  <div style={{ fontSize:12, color:C.blue, background:C.blueBg, borderRadius:6, padding:'4px 8px', marginTop:6 }}>
                    <strong>Respuesta admin:</strong> {r.respuesta}
                  </div>
                )}
                <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>{new Date(r.creado).toLocaleString('es-CO')}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Novedades de afiliados */}
      <div>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
          <h4 style={{ color:C.primary, margin:0, fontSize:14 }}>Novedades Afiliados</h4>
          <input type="date" value={fechaNovAfil} onChange={e => setFechaNovAfil(e.target.value)}
            style={{ padding:'4px 8px', border:`1px solid ${C.border}`, borderRadius:6, fontSize:12, outline:'none' }} />
          {fechaNovAfil !== hoy && (
            <button onClick={() => setFechaNovAfil(hoy)}
              style={{ background:'none', border:'none', cursor:'pointer', color:C.text2, fontSize:11 }}>
              Hoy
            </button>
          )}
        </div>
        {novAfilFiltradas.length === 0 ? (
          <p style={{ color:C.text2, fontSize:13 }}>Sin novedades para esta fecha.</p>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {novAfilFiltradas.map(n => (
              <div key={n.id} style={{ background:'#fff', borderRadius:8, border:`1px solid ${C.border}`, padding:12 }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:4 }}>
                  <span style={{ fontWeight:600, fontSize:13, color:C.text }}>{n.afiliado_nombre}</span>
                  <Badge color={n.estado==='atendido'?C.green:C.yellow} bg={n.estado==='atendido'?C.greenBg:C.yellowBg}>
                    {n.estado}
                  </Badge>
                </div>
                <div style={{ fontSize:12, color:C.blue, fontWeight:600 }}>{n.tipo}</div>
                <div style={{ fontSize:12, color:C.text2, marginTop:2 }}>{n.descripcion}</div>
                {n.respuesta && (
                  <div style={{ fontSize:12, color:C.blue, background:C.blueBg, borderRadius:6, padding:'4px 8px', marginTop:6 }}>
                    <strong>Respuesta admin:</strong> {n.respuesta}
                  </div>
                )}
                <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>{new Date(n.creado).toLocaleString('es-CO')}</div>
              </div>
            ))}
          </div>
        )}
      </div>
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
    refetchInterval: 30_000,
  });

  const leer = useMutation({
    mutationFn: () => api.put('/tareas/notificaciones/leer'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-notifs'] }),
  });
  const limpiar = useMutation({
    mutationFn: () => api.delete('/tareas/notificaciones'),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-notifs'] }); setOpen(false); },
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
        <div style={{ position:'absolute', right:0, top:'calc(100% + 8px)', width:340, maxHeight:420, overflowY:'auto', background:'#fff', borderRadius:12, boxShadow:'0 8px 32px rgba(0,0,0,.2)', zIndex:200, border:`1px solid ${C.border}` }}>
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
  const [q, setQ] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroEmpresa, setFiltroEmpresa] = useState('');
  const [tab, setTab] = useState('afiliados');
  const [seleccionados, setSeleccionados] = useState([]);
  const [resumenDoc, setResumenDoc] = useState(null);
  const [retiroAfil, setRetiroAfil] = useState(null);
  const [novedadAfil, setNovedadAfil] = useState(null);
  const [showNovedadModal, setShowNovedadModal] = useState(false);
  const [expandedNov, setExpandedNov] = useState(null);

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

  const limpiarFiltros = () => { setQ(''); setFiltroEstado(''); setFiltroEmpresa(''); };

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

  return (
    <div style={{ minHeight:'100vh', background:'#F0F4F8', fontFamily:'Inter, system-ui, sans-serif' }}>
      {/* Top nav */}
      <div style={{ background:C.primary, padding:'12px 24px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <span style={{ color:'#fff', fontSize:18, fontWeight:700 }}>
          BBC <span style={{ color:C.accent }}>File</span>
          <span style={{ color:'rgba(255,255,255,.6)', fontSize:13, fontWeight:400, marginLeft:12 }}>Portal del Cliente</span>
        </span>
        <div style={{ display:'flex', alignItems:'center', gap:16 }}>
          <span style={{ color:'rgba(255,255,255,.8)', fontSize:13 }}>{user?.nombre}</span>
          <CampanaNotif />
          <button onClick={handleLogout} style={{ padding:'6px 14px', background:'rgba(255,255,255,.15)', border:'1px solid rgba(255,255,255,.3)', borderRadius:6, color:'#fff', fontSize:12, cursor:'pointer' }}>
            Cerrar sesión
          </button>
        </div>
      </div>

    <div style={{ maxWidth:1100, margin:'0 auto', padding:24 }}>
      {/* Header */}
      <div style={{ background:C.primary, borderRadius:12, padding:'18px 24px', marginBottom:20, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div>
          <h2 style={{ color:'#fff', margin:0, fontSize:18 }}>Mis Afiliados</h2>
          <div style={{ color:'rgba(255,255,255,.7)', fontSize:13, marginTop:2 }}>
            Bienvenido, <strong style={{ color:'#fff' }}>{user?.nombre}</strong>
          </div>
        </div>
        <div style={{ textAlign:'right' }}>
          <div style={{ color:'rgba(255,255,255,.6)', fontSize:11 }}>Total afiliados</div>
          <div style={{ color:C.accent, fontSize:24, fontWeight:700 }}>{afiliados.length}</div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:20 }}>
        {[['afiliados','👥 Mis Afiliados'],['historial','📋 Historial']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding:'8px 18px', borderRadius:8, border:'none', fontSize:13, fontWeight:600,
            cursor:'pointer', background:tab===id?C.primary:'#fff',
            color:tab===id?'#fff':C.text2, boxShadow:tab===id?'none':'0 1px 3px rgba(0,0,0,.1)',
          }}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'afiliados' && (
        <>
          {/* Filtros */}
          <div style={{ background:'#fff', borderRadius:10, border:`1px solid ${C.border}`, padding:'12px 16px', marginBottom:16 }}>
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
              {seleccionados.length > 0 && (
                <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                  <span style={{ fontSize:13, color:C.text2 }}>{seleccionados.length} seleccionado(s)</span>
                  <Btn variant="success" onClick={() => setShowNovedadModal(true)}>Reportar novedad de pago</Btn>
                  <Btn variant="secondary" onClick={() => setSeleccionados([])}>Limpiar selección</Btn>
                </div>
              )}
            </div>
          </div>

          {/* Tabla */}
          {isLoading ? (
            <p style={{ textAlign:'center', color:C.text2, padding:40 }}>Cargando afiliados...</p>
          ) : filtrados.length === 0 ? (
            <p style={{ textAlign:'center', color:C.text2, padding:40 }}>
              {q ? `Sin resultados para "${q}"` : 'No hay afiliados registrados.'}
            </p>
          ) : (
            <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}`, background:'#fff' }}>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
                <thead>
                  <tr style={{ background:C.surface2 }}>
                    <th style={{ padding:'10px 12px', borderBottom:`1px solid ${C.border}` }}>
                      <input type="checkbox" checked={seleccionados.length===filtrados.length&&filtrados.length>0}
                        onChange={toggleTodos} />
                    </th>
                    {['Nombre','Documento','Empresa','EPS','AFP','Estado','Novedades','Acciones'].map(h => (
                      <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map(a => {
                    const sel = seleccionados.includes(a.doc);
                    const ec = estadoColor(a.estado);
                    const novExpanded = expandedNov === a.doc;
                    return (
                      <React.Fragment key={a.id}>
                        <tr style={{ borderBottom: novExpanded ? 'none' : `1px solid ${C.border}`, background:sel?'#EFF6FF':'transparent' }}>
                          <td style={tdc}>
                            <input type="checkbox" checked={sel} onChange={() => toggleSel(a.doc)} />
                          </td>
                          <td style={tdc}><span style={{ fontWeight:600 }}>{a.nombre}</span></td>
                          <td style={tdc}><span style={{ color:C.text2 }}>{a.tipo_doc} {a.doc}</span></td>
                          <td style={tdc}>{a.empresa}</td>
                          <td style={tdc}>{a.eps||'—'}</td>
                          <td style={tdc}>{a.afp||'—'}</td>
                          <td style={tdc}><Badge color={ec.color} bg={ec.bg}>{a.estado}</Badge></td>
                          <td style={tdc}>
                            {a.novedades ? (
                              <button onClick={() => setExpandedNov(novExpanded ? null : a.doc)}
                                style={{ background:'none', border:'none', cursor:'pointer', color:C.accent, fontSize:12, fontWeight:600, padding:0 }}>
                                {novExpanded ? '▲ Ocultar' : '▼ Ver novedad'}
                              </button>
                            ) : <span style={{ color:C.text2, fontSize:12 }}>—</span>}
                          </td>
                          <td style={tdc}>
                            <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                              <Btn size="sm" onClick={() => setResumenDoc(a.doc)}>Ver</Btn>
                              <Btn size="sm" variant="accent" onClick={() => setNovedadAfil(a)}>Novedad</Btn>
                              <Btn size="sm" variant="danger" onClick={() => setRetiroAfil(a)}>Retiro</Btn>
                            </div>
                          </td>
                        </tr>
                        {novExpanded && (
                          <tr style={{ borderBottom:`1px solid ${C.border}` }}>
                            <td colSpan={9} style={{ padding:'8px 16px 12px 36px', background:'#FFFBEB' }}>
                              <span style={{ fontSize:11, fontWeight:600, color:C.yellow }}>NOVEDAD: </span>
                              <span style={{ fontSize:12, color:C.text }}>{a.novedades}</span>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
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
