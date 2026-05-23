import React, { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, Modal, PageHeader, StatCard, fmt, SkeletonRow, ErrorMsg, ConfirmModal } from '../components/UI';
import { BarraFiltros } from '../components/FiltroCheck';
import usePlanilla from '../hooks/usePlanilla';

const UP = v => (v||'').toUpperCase();

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
const TIPOS_CONCEPTO = ['Bono','Comision','Ajuste','Descuento','Otro ingreso','Deduccion'];

function calcularFechaVencimiento(fecha_afiliacion, mes, anio) {
  if (!fecha_afiliacion || !mes || !anio) return null;
  const partes = fecha_afiliacion.split('-');
  if (partes.length !== 3) return null;
  const dia = parseInt(partes[2], 10);
  if (isNaN(dia) || dia < 1 || dia > 31) return null;
  if (dia >= 26 || dia <= 4)        return `05 de ${mes} de ${anio}`;
  if (dia >= 5  && dia <= 9)        return `10 de ${mes} de ${anio}`;
  if (dia >= 10 && dia <= 14)       return `15 de ${mes} de ${anio}`;
  if (dia >= 15 && dia <= 19)       return `20 de ${mes} de ${anio}`;
  if (dia >= 20 && dia <= 25)       return `25 de ${mes} de ${anio}`;
  return null;
}

// ─── MODAL NUEVA FACTURA ─────────────────────────────────────────────────────
export function NuevaFacturaModal({ open, onClose, config, listas, prefill }) {
  const [cedula, setCedula] = useState('');
  const [afiliado, setAfiliado] = useState(null);
  const [errorBusq, setErrorBusq] = useState('');
  const [dias, setDias] = useState(30);
  const searchIdRef = React.useRef(0);
  const [mes, setMes] = useState(() => MESES[new Date().getMonth()]);
  const [anio, setAnio] = useState(() => String(new Date().getFullYear()));
  const [estado, setEstado] = useState('pendiente');
  const [ingreso, setIngreso] = useState('');
  const [novedades, setNovedades] = useState('');
  const [marcados, setMarcados] = useState({});
  const [conceptos, setConceptos] = useState([]);
  const [cargoAdicional, setCargoAdicional] = useState(config?.cargo_adicional ?? 2200);
  const qc = useQueryClient();

  useEffect(() => {
    if (!open) {
      setCedula(''); setAfiliado(null); setErrorBusq(''); setDias(30);
      const hoy = new Date();
      setMes(MESES[hoy.getMonth()]); setAnio(String(hoy.getFullYear())); setEstado('pendiente');
      setIngreso(''); setNovedades(''); setMarcados({}); setConceptos([]);
      setCargoAdicional(config?.cargo_adicional ?? 2200);
    }
  }, [open, config]);

  useEffect(() => {
    if (open && prefill && prefill.doc) {
      setCedula(prefill.doc);
      api.get('/afiliados', { params: { q: prefill.doc } }).then(r => {
        const found = (r.data.items||[]).find(a => a.doc === prefill.doc) || r.data.items?.[0];
        if (found) { setAfiliado(found); setErrorBusq(''); }
      }).catch(() => toast.error('Error buscando afiliado'));
    }
  }, [open, prefill]);

  const { data: planilla = [] } = usePlanilla(afiliado, dias);
  const planillaKey = planilla.map(p => p.servicio + ':' + p.valor).join(',');

  useEffect(() => {
    if (planilla.length > 0) {
      const m = {};
      planilla.forEach(p => { m[p.servicio] = true; });
      setMarcados(m);
    }
  }, [planillaKey]);

  const buscar = async () => {
    if (!cedula.trim()) return;
    const reqId = ++searchIdRef.current;
    try {
      const r = await api.get('/afiliados', { params: { q: cedula.trim() } });
      if (reqId !== searchIdRef.current) return; // respuesta obsoleta — ignorar
      const found = (r.data.items||[]).find(a => a.doc === cedula.trim()) || r.data.items?.[0];
      if (!found) { setErrorBusq(`No se encontró afiliado con cédula "${cedula}"`); setAfiliado(null); return; }
      setAfiliado(found); setErrorBusq('');
    } catch {
      if (reqId !== searchIdRef.current) return;
      setErrorBusq('Error buscando afiliado');
    }
  };

  const planillaSS = planilla.reduce((s, p) => s + (marcados[p.servicio] ? p.valor : 0), 0);
  const cargoAdm = +cargoAdicional || 0;
  const costoPlanilla = planillaSS + cargoAdm; // total para mostrar
  const extra = conceptos.reduce((s, c) => {
    const val = parseFloat(c.valor) || 0;
    return s + (c.tipo === 'Deduccion' ? -val : val);
  }, 0);
  const ingresoNum = parseFloat(ingreso) || 0;
  const utilidad = ingresoNum - costoPlanilla + extra;
  const ibc = afiliado ? ((afiliado.ibc && afiliado.ibc > 0) ? afiliado.ibc : config?.ibc_global) : config?.ibc_global;

  const guardar = useMutation({
    mutationFn: () => {
      if (!afiliado) return Promise.reject(new Error('Busca el afiliado primero'));
      return api.post('/facturas', {
        nombre_afiliado: afiliado.nombre, doc: afiliado.doc,
        cliente: afiliado.cliente_txt || '',
        anio, mes, periodo: String(dias), estado,
        ingresos: ingresoNum, costos: planillaSS, costo_adm: cargoAdm,
        conceptos_extra: extra, utilidad, novedades,
        servicios_detalle: planilla.map(p => ({ ...p, incluido: marcados[p.servicio] !== false })),
        conceptos_detalle: conceptos,
      });
    },
    onSuccess: () => { toast.success('Factura guardada'); qc.invalidateQueries({queryKey:['facturas']}); qc.invalidateQueries({queryKey:['cobro']}); qc.invalidateQueries({queryKey:['dashboard']}); qc.invalidateQueries({queryKey:['finanzas-clientes']}); qc.invalidateQueries({queryKey:['finanzas-cliente']}); onClose(); },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||e.message||'Error')); },
  });

  const inicialAvatar = afiliado ? afiliado.nombre.trim()[0].toUpperCase() : null;

  return (
    <Modal open={open} onClose={onClose} width={860} title="🧾 Nueva factura por afiliado">

      {/* ── Fila 1: Búsqueda + período ── */}
      <div style={{ display:'grid', gridTemplateColumns:'2fr 80px 1fr 1fr', gap:10, marginBottom:14 }}>
        <div>
          <label style={mlbl}>Cédula del afiliado *</label>
          <div style={{ display:'flex', gap:6 }}>
            <input style={{ ...inp, flex:1 }} value={cedula}
              onChange={e => setCedula(e.target.value.replace(/\D/g, ''))}
              onKeyDown={e => e.key==='Enter' && buscar()} placeholder="Número de documento..." />
            <Btn onClick={buscar} size="sm">🔍</Btn>
          </div>
        </div>
        <div><label style={mlbl}>Días</label>
          <input type="number" min={0} max={30} style={inp} value={dias}
            onChange={e => setDias(Math.min(30, Math.max(0, +e.target.value)))} /></div>
        <div><label style={mlbl}>Mes</label>
          <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
            {MESES.map(m => <option key={m}>{m}</option>)}</select></div>
        <div><label style={mlbl}>Año</label>
          <select style={inp} value={anio} onChange={e => setAnio(e.target.value)}>
            {Array.from({ length: 6 }, (_, i) => String(new Date().getFullYear() - 2 + i)).map(a => (
              <option key={a}>{a}</option>
            ))}
          </select></div>
      </div>

      {/* ── Error búsqueda ── */}
      {errorBusq && (
        <div style={{ background:C.redBg, color:C.red, borderRadius:8, padding:'10px 14px',
          fontSize:12, marginBottom:12, fontWeight:600, display:'flex', alignItems:'center', gap:8 }}>
          ⚠️ {errorBusq}
        </div>
      )}

      {/* ── Tarjeta afiliado ── */}
      {afiliado && (
        <div style={{ background:`linear-gradient(135deg, ${C.primary}12 0%, ${C.blueBg} 100%)`,
          border:`1.5px solid ${C.primary}30`, borderRadius:12, padding:'14px 18px',
          marginBottom:14, display:'flex', alignItems:'center', gap:14 }}>
          <div style={{ width:44, height:44, borderRadius:12, background:C.primary,
            display:'flex', alignItems:'center', justifyContent:'center',
            fontSize:20, fontWeight:800, color:'#fff', flexShrink:0 }}>
            {inicialAvatar}
          </div>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ fontWeight:800, fontSize:15, color:C.text, marginBottom:4 }}>{afiliado.nombre}</div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
              {afiliado.empresa && (
                <span style={{ background:C.surface2, border:`1px solid ${C.border}`, borderRadius:6,
                  padding:'2px 10px', fontSize:11, fontWeight:600, color:C.text2 }}>
                  🏢 {afiliado.empresa}
                </span>
              )}
              {afiliado.cliente_txt && (
                <span style={{ background:C.primary, borderRadius:6,
                  padding:'2px 10px', fontSize:11, fontWeight:700, color:'#fff' }}>
                  👤 {afiliado.cliente_txt}
                </span>
              )}
              <span style={{ background:C.surface2, border:`1px solid ${C.border}`, borderRadius:6,
                padding:'3px 12px', fontSize:13, fontWeight:700, color:C.text2 }}>
                IBC {fmt(ibc)}{afiliado.ibc ? ' ⚡' : ''}
              </span>
              {afiliado.fecha_afiliacion && (
                <span style={{ background:C.primary, borderRadius:6,
                  padding:'2px 10px', fontSize:11, fontWeight:700, color:'#fff' }}>
                  📅 Fecha de afiliación: {afiliado.fecha_afiliacion}
                </span>
              )}
              {dias===0 && (
                <span style={{ background:C.amberBg, border:`1px solid ${C.amber}40`, borderRadius:6,
                  padding:'2px 10px', fontSize:11, fontWeight:700, color:C.amber }}>
                  ⚠️ Días=0 · primer mes
                </span>
              )}
            </div>
          </div>
          <div style={{ textAlign:'right', flexShrink:0 }}>
            <div style={{ fontSize:11, color:C.text2, fontWeight:700 }}>Total planilla</div>
            <div style={{ fontSize:22, fontWeight:800, color:C.primary }}>{fmt(costoPlanilla)}</div>
          </div>
        </div>
      )}

      {/* ── Alerta detalle afiliado ── */}
      {afiliado?.detalle && (
        <div style={{ background:C.amberBg, border:`1px solid ${C.amber}`,borderRadius:8,
          padding:'10px 14px', marginBottom:12, fontSize:12, color:C.text,
          display:'flex', gap:8, alignItems:'flex-start' }}>
          <span style={{ fontSize:16 }}>⚠️</span>
          <span><strong style={{ color:C.amber }}>Detalle:</strong> {afiliado.detalle}</span>
        </div>
      )}

      {/* ── Servicios ── */}
      <SrvTable planilla={planilla} marcados={marcados} setMarcados={setMarcados} dias={dias}
        sinAfiliado={!afiliado} cargoAdicional={cargoAdicional} setCargoAdicional={setCargoAdicional}
        fechaAfiliacion={afiliado?.fecha_afiliacion} />

      {/* ── Ingreso + Novedades en fila ── */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 2fr', gap:12, marginBottom:12 }}>
        <div>
          <label style={mlbl}>💵 Ingreso cobrado al cliente ($)</label>
          <input type="number" style={{ ...inp, fontSize:16, fontWeight:700 }} value={ingreso}
            onChange={e => setIngreso(e.target.value)} placeholder="0" />
        </div>
        <div>
          <label style={mlbl}>📝 Novedades / observaciones</label>
          <input style={{ ...inp, textTransform:'uppercase' }} value={novedades}
            onChange={e => setNovedades(UP(e.target.value))} placeholder="OBSERVACIONES DE ESTA FACTURA..." />
        </div>
      </div>

      <ConceptosSection conceptos={conceptos} setConceptos={setConceptos} />
      <ResumenFinanciero ingreso={ingresoNum} costoPlanilla={costoPlanilla} extra={extra} utilidad={utilidad} />

      <div style={{ display:'flex', justifyContent:'flex-end', gap:10 }}>
        <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={() => guardar.mutate()} disabled={guardar.isPending || !afiliado || !afiliado.cliente_txt}
          title={afiliado && !afiliado.cliente_txt ? 'El afiliado no tiene cliente asignado — edítalo primero' : ''}>
          {guardar.isPending ? 'Guardando...' : '💾 Guardar factura'}
        </Btn>
      </div>
    </Modal>
  );
}

// ─── MODAL EDITAR FACTURA ────────────────────────────────────────────────────
function EditarFacturaModal({ open, onClose, factura, config, listas }) {
  const [dias, setDias] = useState(30);
  const [mes, setMes] = useState('');
  const [estado, setEstado] = useState('pendiente');
  const [banco, setBanco] = useState('');
  const [ingreso, setIngreso] = useState('');
  const [novedades, setNovedades] = useState('');
  const [marcados, setMarcados] = useState({});
  const [conceptos, setConceptos] = useState([]);
  const [afiliado, setAfiliado] = useState(null);
  const [cargoAdicional, setCargoAdicional] = useState(config?.cargo_adicional ?? 2200);
  const qc = useQueryClient();

  useEffect(() => {
    if (open && factura) {
      setDias(parseInt(factura.periodo) || 30);
      setMes(factura.mes || MESES[new Date().getMonth()]);
      setEstado(factura.estado || 'pendiente');
      setBanco(factura.banco || '');
      setIngreso(factura.ingresos ?? '');
      setNovedades(factura.novedades || '');
      setConceptos(factura.conceptos_detalle || []);
      setCargoAdicional(config?.cargo_adicional ?? 2200);
      const m = {};
      (factura.servicios_detalle || []).forEach(s => { m[s.servicio] = s.incluido !== false; });
      setMarcados(m);
      if (factura.doc) {
        api.get('/afiliados', { params: { q: factura.doc } })
          .then(r => { const f = (r.data.items||[]).find(a => a.doc === factura.doc); if (f) setAfiliado(f); })
          .catch(() => toast.error('Error buscando afiliado'));
      }
    }
  }, [open, factura?.id, config]);

  const { data: planilla = [] } = usePlanilla(afiliado, dias);
  const planillaFinal = planilla.length > 0 ? planilla : (factura?.servicios_detalle || []).map(s => ({
    servicio: s.servicio, pct: s.pct || 0, valor: s.valor || 0, val30: s.val30 || 0,
  }));

  const planillaSS = planillaFinal.reduce((s, p) => s + (marcados[p.servicio] !== false ? p.valor : 0), 0);
  const cargoAdm = +cargoAdicional || 0;
  const costoPlanilla = planillaSS + cargoAdm; // total para mostrar
  const extra = conceptos.reduce((s, c) => {
    const val = parseFloat(c.valor) || 0;
    return s + (c.tipo === 'Deduccion' ? -val : val);
  }, 0);
  const ingresoNum = parseFloat(ingreso) || 0;
  const utilidad = ingresoNum - costoPlanilla + extra;

  const guardar = useMutation({
    mutationFn: () => api.put(`/facturas/${factura.id}`, {
      mes, periodo: String(dias), estado, banco,
      ingresos: ingresoNum, costos: planillaSS, costo_adm: cargoAdm,
      conceptos_extra: extra, utilidad, novedades,
      servicios_detalle: planillaFinal.map(p => ({ ...p, incluido: marcados[p.servicio] !== false })),
      conceptos_detalle: conceptos,
    }),
    onSuccess: () => { toast.success('Factura actualizada'); qc.invalidateQueries({ queryKey: ['facturas'] }); qc.invalidateQueries({ queryKey: ['finanzas-clientes'] }); qc.invalidateQueries({ queryKey: ['finanzas-cliente'] }); qc.invalidateQueries({ queryKey: ['dashboard'] }); qc.invalidateQueries({ queryKey: ['cobro'] }); onClose(); },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); },
  });

  if (!factura) return null;
  return (
    <Modal open={open} onClose={onClose} width={820} title={`✏️ Editar — ${factura.codigo}`}>
      <div style={{ background:C.surface2,borderRadius:7,padding:'8px 12px',fontSize:12,marginBottom:12,color:C.text2 }}>
        <strong style={{ color:C.text }}>{factura.nombre_afiliado}</strong> | Cliente: {factura.cliente||'—'} | Doc: {factura.doc||'—'}
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:10, marginBottom:10 }}>
        <div><label style={lbl}>Días (0-30)</label>
          <input type="number" min={0} max={30} style={inp} value={dias}
            onChange={e => setDias(Math.min(30,Math.max(0,+e.target.value)))} /></div>
        <div><label style={lbl}>Mes</label>
          <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
            {MESES.map(m => <option key={m}>{m}</option>)}</select></div>
        <div><label style={lbl}>Estado</label>
          <select style={inp} value={estado} onChange={e => setEstado(e.target.value)}>
            <option value="pendiente">Pendiente</option><option value="pagado">Pagado</option></select></div>
        <div><label style={lbl}>Banco / Pago</label>
          <select style={inp} value={banco} onChange={e => setBanco(e.target.value)}>
            <option value="">Seleccionar...</option>
            {(listas?.bancos||[]).map(b => <option key={b}>{b}</option>)}</select></div>
      </div>
      <div style={{ marginBottom:10 }}><label style={lbl}>Novedades</label>
        <input style={inp} value={novedades} onChange={e => setNovedades(e.target.value.toUpperCase())} /></div>
      <SrvTable planilla={planillaFinal} marcados={marcados} setMarcados={setMarcados} dias={dias}
        cargoAdicional={cargoAdicional} setCargoAdicional={setCargoAdicional} />
      <div style={{ marginBottom:10 }}><label style={lbl}>Ingreso cobrado al cliente ($)</label>
        <input type="number" style={{ ...inp,width:220 }} value={ingreso}
          onChange={e => setIngreso(e.target.value)} placeholder="0" /></div>
      <ConceptosSection conceptos={conceptos} setConceptos={setConceptos} />
      <ResumenFinanciero ingreso={ingresoNum} costoPlanilla={costoPlanilla} extra={extra} utilidad={utilidad} />
      <div style={{ display:'flex', justifyContent:'flex-end', gap:10 }}>
        <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={() => guardar.mutate()} disabled={guardar.isPending}>
          {guardar.isPending ? 'Guardando...' : '💾 Guardar cambios'}
        </Btn>
      </div>
    </Modal>
  );
}

// ─── COMPONENTES COMPARTIDOS ─────────────────────────────────────────────────
function SrvTable({ planilla, marcados, setMarcados, dias, sinAfiliado, cargoAdicional, setCargoAdicional, fechaAfiliacion }) {
  return (
    <div style={{ marginBottom:10 }}>
      <div style={{ fontSize:13,fontWeight:700,color:C.primary,borderBottom:`2px solid ${C.primary}`,paddingBottom:4,marginBottom:6,display:'flex',alignItems:'center',gap:10 }}>
        <span>Servicios contratados del afiliado</span>
        <span style={{ fontSize:11,fontWeight:700,color:C.amber,background:C.amberBg,
          border:`1px solid ${C.amber}40`,borderRadius:5,padding:'2px 9px' }}>
          ⚠️ Desmarca los que no aplican (ej: primer mes)
        </span>
      </div>
      {planilla.length === 0
        ? <div style={{ color:C.text2,fontSize:12,padding:'8px 0' }}>{sinAfiliado ? 'Busca el afiliado por cédula para cargar servicios.' : 'Sin servicios registrados.'}</div>
        : (
          <div style={{ border:`1px solid ${C.border}`,borderRadius:7,overflow:'hidden' }}>
            <div style={{ display:'grid',gridTemplateColumns:'40px 140px 80px 1fr',background:C.surface2,borderBottom:`1px solid ${C.border}` }}>
              {['✓','Servicio','%','Valor planilla ($)'].map(h => (
                <div key={h} style={{ padding:'6px 10px',fontSize:11,fontWeight:600,color:C.text2 }}>{h}</div>
              ))}
            </div>
            {planilla.map(p => {
              const inc = marcados[p.servicio] !== false;
              return (
                <div key={p.servicio} style={{ display:'grid',gridTemplateColumns:'40px 140px 80px 1fr',
                  borderBottom:`1px solid ${C.border}`,background: inc?C.surface:C.surface2 }}>
                  <div style={{ padding:'8px 10px',display:'flex',alignItems:'center' }}>
                    <input type="checkbox" checked={inc}
                      onChange={() => {
                        const esArl = p.servicio.startsWith('ARL');
                        setMarcados(m => {
                          const next = { ...m, [p.servicio]: !inc };
                          if (esArl && !inc) {
                            planilla.forEach(s => {
                              if (s.servicio !== p.servicio && s.servicio.startsWith('ARL')) next[s.servicio] = false;
                            });
                          }
                          return next;
                        });
                      }} /></div>
                  <div style={{ padding:'8px 10px',fontSize:13,color:inc?C.text:C.text2,
                    textDecoration:inc?'none':'line-through' }}>{p.servicio}</div>
                  <div style={{ padding:'8px 10px',fontSize:12,color:C.text2 }}>
                    {((p.pct||0)*100).toFixed(4).replace(/\.?0+$/,'')}%</div>
                  <div style={{ padding:'8px 10px',fontSize:13,fontWeight:600,
                    color:inc?C.primary:C.text2,textDecoration:inc?'none':'line-through' }}>
                    {dias===0 ? <span style={{ color:C.text2 }}>— (ref: {fmt(p.val30)})</span>
                      : `${fmt(p.valor)}${dias<30?` (${dias}d)`:''}`}
                  </div>
                </div>
              );
            })}
          </div>
        )
      }
      {cargoAdicional !== undefined && (
        <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:6,
          background:C.surface2, border:`1px solid ${C.border}`, borderRadius:7, padding:'6px 12px' }}>
          <span style={{ fontSize:12, color:C.text2, fontWeight:700 }}>⚙️ Mora / 4x1000 / cargo adicional:</span>
          <input type="number" value={cargoAdicional} onChange={e => setCargoAdicional(e.target.value)}
            style={{ width:110, padding:'4px 8px', border:`1px solid ${C.border}`, borderRadius:6,
              fontSize:13, fontWeight:700, color:C.text, background:C.surface, outline:'none' }} />
          <span style={{ fontSize:11, color:C.text2, fontWeight:700 }}>Se suma al costo de la planilla</span>
        </div>
      )}
    </div>
  );
}

function ConceptosSection({ conceptos, setConceptos }) {
  return (
    <div style={{ marginBottom:10 }}>
      <div style={{ fontSize:13,fontWeight:700,color:C.primary,borderBottom:`2px solid ${C.primary}`,paddingBottom:4,marginBottom:6 }}>
        Conceptos adicionales <span style={{ fontSize:11,fontWeight:400,color:C.text2 }}>(suman/restan a la utilidad)</span>
      </div>
      {conceptos.map((c,i) => (
        <div key={i} style={{ display:'flex',gap:6,marginBottom:4 }}>
          <select style={{ ...inp,width:160 }} value={c.tipo}
            onChange={e => setConceptos(cs => cs.map((x,j) => j===i?{...x,tipo:e.target.value}:x))}>
            {TIPOS_CONCEPTO.map(t => <option key={t}>{t}</option>)}</select>
          <input style={{ ...inp,flex:1 }} placeholder="DESCRIPCIÓN..." value={c.desc}
            onChange={e => setConceptos(cs => cs.map((x,j) => j===i?{...x,desc:e.target.value}:x))} />
          <input type="number" style={{ ...inp,width:140 }} placeholder="Valor $" value={c.valor}
            onChange={e => setConceptos(cs => cs.map((x,j) => j===i?{...x,valor:e.target.value}:x))} />
          <Btn size="sm" variant="danger" onClick={() => setConceptos(cs => cs.filter((_,j) => j!==i))}>×</Btn>
        </div>
      ))}
      <Btn size="sm" variant="secondary"
        onClick={() => setConceptos(cs => [...cs, {tipo:'Bono',desc:'',valor:''}])}>
        + Agregar concepto
      </Btn>
    </div>
  );
}

function ResumenFinanciero({ ingreso, costoPlanilla, extra, utilidad }) {
  const cards = [
    { label:'Ingreso cliente',   value:fmt(ingreso),       icon:'💵', ingreso:true },
    { label:'Costo planilla SS', value:fmt(costoPlanilla), icon:'📋' },
    { label:'Conceptos extra',   value:fmt(extra),         icon:'➕' },
    { label:'Utilidad neta',     value:fmt(utilidad),      icon: utilidad>=0?'📈':'📉', utilidad:true },
  ];
  return (
    <div style={{ marginBottom:14 }}>
      <div style={{ fontSize:12, fontWeight:700, color:C.text2, textTransform:'uppercase',
        letterSpacing:'.06em', marginBottom:8 }}>Resumen financiero</div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:8 }}>
        {cards.map(c => (
          <div key={c.label} style={{ background:C.surface2, border:`1px solid ${C.border}`,
            borderRadius:10, padding:'12px 14px' }}>
            <div style={{ fontSize:18, marginBottom:4 }}>{c.icon}</div>
            <div style={{ fontSize:12, color:C.text, fontWeight:700, marginBottom:2 }}>{c.label}</div>
            <div style={{ fontSize:18, fontWeight:800,
              color: c.utilidad ? (utilidad>=0 ? C.primary : C.red) : c.ingreso ? C.green : C.text }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── FORM EDITAR INGRESO ADICIONAL ───────────────────────────────────────────
const TIPOS_IA = ['Comisión', 'Planilla verificable', 'Otro'];
function EditIngAdForm({ inicial, MESES_NUM, onGuardar, onCancel, isPending }) {
  const [form, setForm] = useState({
    concepto: inicial.concepto || 'Comisión',
    descripcion: inicial.descripcion || '',
    valor: inicial.valor || '',
    mes: inicial.mes,
    anio: inicial.anio,
  });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
      <div>
        <label style={lbl}>Concepto</label>
        <select style={sel} value={form.concepto} onChange={e=>set('concepto',e.target.value)}>
          {TIPOS_IA.map(t=><option key={t}>{t}</option>)}
        </select>
      </div>
      <div>
        <label style={lbl}>Descripción</label>
        <input style={sel} value={form.descripcion} onChange={e=>set('descripcion',e.target.value)} />
      </div>
      <div>
        <label style={lbl}>Valor *</label>
        <input type="number" style={sel} min="0" value={form.valor} onChange={e=>set('valor',e.target.value)} />
      </div>
      <div style={{ display:'flex', gap:10 }}>
        <div style={{ flex:1 }}>
          <label style={lbl}>Mes *</label>
          <select style={sel} value={form.mes} onChange={e=>set('mes',parseInt(e.target.value))}>
            {MESES_NUM.map((m,i)=><option key={m} value={i+1}>{m}</option>)}
          </select>
        </div>
        <div style={{ flex:1 }}>
          <label style={lbl}>Año *</label>
          <input type="number" style={sel} value={form.anio} min="2020" max="2099"
            onChange={e=>set('anio',parseInt(e.target.value))} />
        </div>
      </div>
      <div style={{ display:'flex', gap:10, justifyContent:'flex-end', marginTop:4 }}>
        <Btn variant="secondary" onClick={onCancel}>Cancelar</Btn>
        <Btn disabled={!form.valor || parseFloat(form.valor) <= 0 || isPending}
          onClick={()=>onGuardar({ concepto:form.concepto, descripcion:form.descripcion,
            valor:parseFloat(form.valor), mes:form.mes, anio:form.anio })}>
          {isPending ? 'Guardando...' : '💾 Guardar'}
        </Btn>
      </div>
    </div>
  );
}

// ─── PÁGINA PRINCIPAL ────────────────────────────────────────────────────────
export default function Facturacion({ prefillAfiliado, onFacturaCreada }) {
  const qc = useQueryClient();
  const [busqueda, setBusqueda] = useState('');
  const [filtros,  setFiltros]  = useState({ anio:[String(new Date().getFullYear())], mes:[MESES[new Date().getMonth()]], cliente:[], estado:[] });
  const setFiltro = (key, vals) => setFiltros(f=>({...f,[key]:vals}));
  const limpiar   = () => setFiltros({ anio:[String(new Date().getFullYear())], mes:[MESES[new Date().getMonth()]], cliente:[], estado:[] });
  const [modalNueva,  setModalNueva]  = useState(false);
  const [modalEditar, setModalEditar] = useState(null);
  const [prefill, setPrefill] = useState(null);
  const [expandedRow, setExpandedRow] = useState(null);
  const [seleccionadas, setSeleccionadas] = useState(new Set());
  const [modalBulkPagar, setModalBulkPagar] = useState(false);
  const [bancoBulk, setBancoBulk] = useState('');
  const [confirmState, setConfirmState] = useState({ open: false, title: '', message: '', onConfirm: null });
  useEffect(() => {
    if (prefillAfiliado) { setPrefill(prefillAfiliado); setModalNueva(true); }
  }, [prefillAfiliado]);

  const [tabActivo, setTabActivo] = useState('facturas');
  const [paginaF, setPaginaF] = useState(1);
  const POR_PAG_F = 50;

  // Mapear filtros al formato del backend
  const anioB    = filtros.anio.length    === 1 ? filtros.anio[0]    : '';
  const mesB     = filtros.mes.length     === 1 ? filtros.mes[0]     : '';
  const clienteB = filtros.cliente.length === 1 ? filtros.cliente[0] : '';
  const estadoB  = filtros.estado.length  === 1
    ? (filtros.estado[0] === 'Pagada' ? 'pagado' : filtros.estado[0] === 'Planilla Pagada' ? 'planilla_pagada' : 'pendiente') : '';
  const hayFiltros = anioB || mesB || clienteB || estadoB || busqueda ||
    filtros.anio.length > 1 || filtros.mes.length > 1 ||
    filtros.cliente.length > 1 || filtros.estado.length > 1;

  // Con mes seleccionado O búsqueda activa: traer todos y filtrar localmente
  // Sin mes ni búsqueda: paginar en servidor
  const hayMes = !!mesB;
  const { data: respF={total:0,items:[]}, isLoading, isError: isErrorFacturas, refetch: refetchFacturas } = useQuery({
    queryKey: ['facturas', paginaF, anioB, mesB, clienteB, estadoB, busqueda, hayFiltros],
    queryFn: () => api.get('/facturas', { params: hayFiltros && (hayMes || busqueda)
      ? { anio: anioB, mes: mesB, cliente: clienteB, estado: estadoB, limit: 0, exclude_planilla: true }
      : { anio: anioB, mes: mesB, cliente: clienteB, estado: estadoB, skip: (paginaF-1)*POR_PAG_F, limit: POR_PAG_F, exclude_planilla: true }
    }).then(r=>r.data),
    placeholderData: (prev) => prev,
  });

  // Resetear página cuando cambien los filtros
  useEffect(() => { setPaginaF(1); }, [anioB, mesB, clienteB, estadoB, busqueda]);
  useEffect(() => { setPaginaIA(1); }, [anioB, mesB]);

  const rows      = respF.items || [];
  const totalFact = respF.total || 0;
  const totalPagsF = Math.ceil(totalFact / POR_PAG_F);
  const { data: config={} } = useQuery({ queryKey:['config'], queryFn:()=>api.get('/config').then(r=>r.data), staleTime: 300_000 });
  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });
  const { data: todosClientes=[] } = useQuery({ queryKey:['clientes'], queryFn:()=>api.get('/clientes').then(r=>r.data), staleTime: 300_000 });

  const clientesUnicos = todosClientes.filter(Boolean);
  const MESES_ORDER    = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  const anioActual     = new Date().getFullYear();
  const aniosUnicos    = Array.from({length: 4}, (_, i) => String(anioActual - i));
  const mesesOrd       = MESES_ORDER;

  // Filtrado local (memoizado — evita recalcular en cada render)
  const rowsFiltradas = useMemo(() => rows.filter(f => {
    const q = busqueda.toLowerCase();
    if (busqueda && !`${f.nombre_afiliado} ${f.doc} ${f.cliente} ${f.codigo}`.toLowerCase().includes(q)) return false;
    if (filtros.anio.length    && !filtros.anio.includes(f.anio))                    return false;
    if (filtros.mes.length     && !filtros.mes.includes(f.mes))                      return false;
    if (filtros.cliente.length && !filtros.cliente.includes(f.cliente))              return false;
    if (filtros.estado.length  && !filtros.estado.includes(
      f.estado==='pagado' ? 'Pagada' : f.estado==='planilla_pagada' ? 'Planilla Pagada' : 'Pendiente'
    )) return false;
    return true;
  }), [rows, busqueda, filtros]);

  const rowsPaginaF = rowsFiltradas.slice((paginaF-1)*POR_PAG_F, paginaF*POR_PAG_F);
  const totalPagsF2 = Math.max(1, Math.ceil(rowsFiltradas.length / POR_PAG_F));

  const [modalPagar, setModalPagar] = useState(null);
  const [bancoPago, setBancoPago] = useState('');


  // Ingresos adicionales
  const MESES_NUM = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  const hoyMes  = new Date().getMonth() + 1;
  const hoyAnio = new Date().getFullYear();
  const [modalIngAd, setModalIngAd]       = useState(false);
  const [editIngAd,  setEditIngAd]        = useState(null); // objeto a editar
  const [formIngAd, setFormIngAd]         = useState({ concepto:'Comisión', descripcion:'', valor:'', mes: hoyMes, anio: hoyAnio });
  const [paginaIA, setPaginaIA]           = useState(1);
  const POR_PAG_IA = 20;

  // Sin filtros explícitos: mostrar solo el mes actual (no acumular meses anteriores)
  const iaParams = {};
  if (anioB) iaParams.anio = parseInt(anioB);
  if (mesB)  iaParams.mes  = MESES_NUM.indexOf(mesB) + 1;
  if (!anioB && !mesB) { iaParams.mes = hoyMes; iaParams.anio = hoyAnio; }

  const { data: ingAdList = [] } = useQuery({
    queryKey: ['ingresos-adicionales', iaParams.mes, iaParams.anio],
    queryFn: () => api.get('/ingresos-adicionales', { params: iaParams }).then(r => r.data),
  });

  const totIngAd = ingAdList.reduce((s, i) => s + (i.valor || 0), 0);
  const totalPagsIA = Math.ceil(ingAdList.length / POR_PAG_IA);
  const ingAdPaginado = ingAdList.slice((paginaIA - 1) * POR_PAG_IA, paginaIA * POR_PAG_IA);

  const crearIngAd = useMutation({
    mutationFn: data => api.post('/ingresos-adicionales', data),
    onSuccess: () => {
      toast.success('Ingreso adicional agregado');
      qc.invalidateQueries({ queryKey: ['ingresos-adicionales'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      setModalIngAd(false);
      setFormIngAd({ concepto:'Comisión', descripcion:'', valor:'', mes: hoyMes, anio: hoyAnio });
    },
    onError: e => toast.error(e.response?.data?.detail || 'Error'),
  });

  const editarIngAd = useMutation({
    mutationFn: ({ id, data }) => api.put(`/ingresos-adicionales/${id}`, data),
    onSuccess: () => {
      toast.success('Ingreso actualizado');
      qc.invalidateQueries({ queryKey: ['ingresos-adicionales'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      setEditIngAd(null);
    },
    onError: e => toast.error(e.response?.data?.detail || 'Error'),
  });

  const elimIngAd = useMutation({
    mutationFn: id => api.delete(`/ingresos-adicionales/${id}`),
    onSuccess: () => {
      toast.success('Ingreso adicional eliminado');
      qc.invalidateQueries({ queryKey: ['ingresos-adicionales'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: e => toast.error(e.response?.data?.detail || 'Error'),
  });

  const pagar = useMutation({
    mutationFn: ({ id, banco, monto }) => api.patch(`/facturas/${id}/pagar`, null, { params: { banco, ...(monto != null ? { monto } : {}) } }),
    onSuccess: (res) => {
      const estado = res.data?.estado;
      toast.success(estado === 'pagado' ? 'Factura marcada como pagada' : 'Abono registrado — factura sigue pendiente hasta pago total');
      qc.invalidateQueries({ queryKey: ['facturas'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['finanzas-clientes'] });
      qc.invalidateQueries({ queryKey: ['finanzas-cliente'] });
      setModalPagar(null); setBancoPago('');
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al registrar pago'),
  });
  const eliminar = useMutation({
    mutationFn: id => api.delete(`/facturas/${id}`),
    onSuccess: () => { toast.success('Factura eliminada'); qc.invalidateQueries({ queryKey: ['facturas'] }); qc.invalidateQueries({ queryKey: ['dashboard'] }); qc.invalidateQueries({ queryKey: ['finanzas-clientes'] }); qc.invalidateQueries({ queryKey: ['finanzas-cliente'] }); },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al eliminar factura'),
  });

  const planillaPagada = useMutation({
    mutationFn: id => api.patch(`/facturas/${id}/planilla-pagada`),
    onSuccess: () => {
      toast.success('Planilla marcada como pagada');
      qc.invalidateQueries({ queryKey: ['facturas'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['finanzas-clientes'] });
      qc.invalidateQueries({ queryKey: ['finanzas-cliente'] });
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al marcar planilla'),
  });

  const pagarBulk = useMutation({
    mutationFn: async ({ ids, banco }) => {
      const results = await Promise.allSettled(ids.map(id => api.patch(`/facturas/${id}/pagar`, null, { params: { banco } })));
      const ok = results.filter(r => r.status === 'fulfilled').length;
      const err = results.filter(r => r.status === 'rejected').length;
      return { ok, err };
    },
    onSuccess: ({ ok, err }) => {
      if (ok) toast.success(`${ok} factura(s) marcada(s) como pagada`);
      if (err) toast.error(`${err} factura(s) no se pudieron pagar`);
      qc.invalidateQueries({ queryKey: ['facturas'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['finanzas-clientes'] });
      qc.invalidateQueries({ queryKey: ['finanzas-cliente'] });
      setSeleccionadas(new Set()); setModalBulkPagar(false); setBancoBulk('');
    },
    onError: () => {
      setModalBulkPagar(false);
      toast.error('Error al procesar pagos en lote');
    },
  });

  const planillaBulk = useMutation({
    mutationFn: async (ids) => {
      const results = await Promise.allSettled(ids.map(id => api.patch(`/facturas/${id}/planilla-pagada`)));
      const ok = results.filter(r => r.status === 'fulfilled').length;
      const err = results.filter(r => r.status === 'rejected').length;
      return { ok, err };
    },
    onSuccess: ({ ok, err }) => {
      if (ok) toast.success(`${ok} factura(s) marcada(s) como planilla pagada`);
      if (err) toast.error(`${err} factura(s) no se pudieron actualizar`);
      qc.invalidateQueries({ queryKey: ['facturas'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['finanzas-clientes'] });
      qc.invalidateQueries({ queryKey: ['finanzas-cliente'] });
      setSeleccionadas(new Set());
    },
  });

  const toggleSel = (id) => setSeleccionadas(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  const toggleTodos = () => {
    const pendientes = rowsFiltradas.filter(f => f.estado === 'pendiente').map(f => f.id);
    const todosSel = pendientes.every(id => seleccionadas.has(id));
    setSeleccionadas(todosSel ? new Set() : new Set(pendientes));
  };
  const selPendientes = rowsFiltradas.filter(f => f.estado === 'pendiente' && seleccionadas.has(f.id));
  const selPagadas    = rowsFiltradas.filter(f => f.estado === 'pagado'    && seleccionadas.has(f.id));

  const esPagada = f => f.estado === 'pagado' || f.estado === 'planilla_pagada';
  // Si hay filtro de estado activo, las stats suman sobre todo rowsFiltradas (el usuario eligió qué ver)
  // Sin filtro de estado → solo facturas pagadas (comportamiento original)
  const hayFiltroEstado = !!estadoB;
  const baseIng  = hayFiltroEstado ? rowsFiltradas : rowsFiltradas.filter(esPagada);
  const totIng  = baseIng.reduce((s,f)=>s+(f.ingresos||0),0) + totIngAd;
  const totUtil = baseIng.reduce((s,f)=>s+(f.utilidad||0),0) + totIngAd;
  const totPend = rowsFiltradas.filter(f=>f.estado==='pendiente').reduce((s,f)=>s+(f.ingresos||0),0);

  return (
    <div>
      <PageHeader title="🧾 Facturación" subtitle={`${rowsFiltradas.length} de ${totalFact} facturas`}
        action={
          <div style={{ display:'flex', gap:8 }}>
            <Btn variant="secondary" onClick={()=>{
              const p = new URLSearchParams();
              if (anioB) p.set('anio', anioB);
              if (mesB)  p.set('mes',  mesB);
              if (clienteB) p.set('cliente', clienteB);
              if (estadoB)  p.set('estado',  estadoB);
              dlExcel(`/reportes/financiero?${p}`, `facturas${anioB?'_'+anioB:''}${mesB?'_'+mesB:''}.xlsx`);
            }}>📊 Exportar Excel</Btn>
            <Btn variant="accent" onClick={()=>{setPrefill(null);setModalNueva(true);}}>+ Nueva factura</Btn>
          </div>
        } />

      <div style={{ display:'flex',gap:10,marginBottom:14,flexWrap:'wrap' }}>
        <StatCard label="Total ingresos"      value={fmt(totIng)}  color={C.primary} />
        <StatCard label="Utilidad bruta"      value={fmt(totUtil)} color={C.green} />
        <StatCard label="Pendiente cobro"     value={fmt(totPend)} color={C.amber} />
        <StatCard label="Facturas pendientes" value={rowsFiltradas.filter(f=>f.estado==='pendiente').length} color={C.red} />
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16, background:C.surface2, borderRadius:10, padding:4, border:`1px solid ${C.border}` }}>
        {[
          { key:'facturas',  label:`🧾 Facturas (${rowsFiltradas.length})` },
          { key:'ingresos',  label:`➕ Ingresos adicionales${ingAdList.length > 0 ? ` (${ingAdList.length})` : ''}` },
        ].map(t => (
          <button key={t.key} onClick={()=>setTabActivo(t.key)} style={{
            flex:1, padding:'8px 4px', border:'none', borderRadius:7, cursor:'pointer', fontSize:13,
            fontWeight: tabActivo===t.key ? 700 : 400,
            background: tabActivo===t.key ? C.primary : 'transparent',
            color: tabActivo===t.key ? '#fff' : C.text2,
            transition:'all .15s',
          }}>{t.label}</button>
        ))}
      </div>

      {tabActivo === 'ingresos' && (
        <div>
          <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:12 }}>
            <Btn variant="accent" onClick={()=>setModalIngAd(true)}>➕ Agregar ingreso</Btn>
          </div>
          {ingAdList.length === 0 ? (
            <div style={{ background:C.surface, borderRadius:10, padding:32, textAlign:'center', border:`1px solid ${C.border}` }}>
              <p style={{ color:C.text2, fontSize:14, margin:0 }}>Sin ingresos adicionales{anioB||mesB ? ` para ${mesB||''} ${anioB||''}`.trim() : ''}</p>
            </div>
          ) : (
            <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
              <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
                <thead>
                  <tr style={{ background:C.surface2 }}>
                    {['Concepto','Descripción','Valor','Mes','Año','Registrado por','Fecha',''].map(h => (
                      <th key={h} style={{ padding:'10px 12px', fontSize:13, fontWeight:700, color:C.text, textAlign:'left', borderBottom:`1px solid ${C.border}`, whiteSpace:'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ingAdPaginado.map(i => (
                    <tr key={i.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                      <td style={tdc}>
                        <span style={{ fontWeight:600, color:C.primary }}>{i.concepto}</span>
                      </td>
                      <td style={{ ...tdc, fontWeight:700, color:C.text }}>{i.descripcion || '—'}</td>
                      <td style={{ ...tdc, fontWeight:700, color:C.green }}>{fmt(i.valor)}</td>
                      <td style={tdc}>{MESES_NUM[i.mes-1]}</td>
                      <td style={tdc}>{i.anio}</td>
                      <td style={{ ...tdc, color:C.text2 }}>{i.creado_por || '—'}</td>
                      <td style={{ ...tdc, color:C.text2, fontSize:12 }}>{i.creado ? new Date(i.creado).toLocaleDateString('es-CO') : '—'}</td>
                      <td style={tdc}>
                        <div style={{ display:'flex', gap:4 }}>
                          <Btn size="sm" variant="secondary"
                            onClick={()=>setEditIngAd(i)}>✏️</Btn>
                          <Btn size="sm" variant="danger" disabled={elimIngAd.isPending}
                            onClick={()=>setConfirmState({ open:true, title:'Eliminar ingreso', message:'¿Eliminar este ingreso adicional?', onConfirm:()=>{ elimIngAd.mutate(i.id); setConfirmState(s=>({...s,open:false})); } })}>
                            🗑️
                          </Btn>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ background:C.surface2, borderTop:`2px solid ${C.border}` }}>
                    <td colSpan={2} style={{ ...tdc, fontWeight:700, color:C.text }}>Total</td>
                    <td style={{ ...tdc, fontWeight:700, color:C.green }}>{fmt(totIngAd)}</td>
                    <td colSpan={5} />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
          {/* Paginación ingresos adicionales */}
          {totalPagsIA > 1 && (
            <div style={{ display:'flex', justifyContent:'center', alignItems:'center', gap:8, marginTop:12 }}>
              <button onClick={()=>setPaginaIA(p=>Math.max(1,p-1))} disabled={paginaIA===1}
                style={{ padding:'5px 12px', border:`1px solid ${C.border}`, borderRadius:7, background:C.surface2,
                  cursor:paginaIA===1?'not-allowed':'pointer', opacity:paginaIA===1?0.5:1, fontSize:12 }}>‹ Anterior</button>
              <span style={{ fontSize:12, color:C.text2 }}>Pág. {paginaIA} de {totalPagsIA} · {ingAdList.length} registros</span>
              <button onClick={()=>setPaginaIA(p=>Math.min(totalPagsIA,p+1))} disabled={paginaIA===totalPagsIA}
                style={{ padding:'5px 12px', border:`1px solid ${C.border}`, borderRadius:7, background:C.surface2,
                  cursor:paginaIA===totalPagsIA?'not-allowed':'pointer', opacity:paginaIA===totalPagsIA?0.5:1, fontSize:12 }}>Siguiente ›</button>
            </div>
          )}
        </div>
      )}

      {tabActivo === 'facturas' && (<div>
      <input placeholder="🔍 Buscar código, afiliado, documento, cliente..."
        value={busqueda} onChange={e=>setBusqueda(e.target.value)}
        style={{ width:'100%',padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
          fontSize:14,outline:'none',marginBottom:12,boxSizing:'border-box',background:C.surface,color:C.text }} />
      <BarraFiltros
        filtros={[
          { key:'anio',    label:'Año',     icon:'📅', options: aniosUnicos },
          { key:'mes',     label:'Mes',     icon:'🗓️', options: mesesOrd },
          { key:'cliente', label:'Cliente', icon:'👤', options: clientesUnicos },
          { key:'estado',  label:'Estado',  icon:'📌', options: ['Pendiente','Pagada','Planilla Pagada'] },
        ]}
        valores={filtros}
        onChange={setFiltro}
        onLimpiar={limpiar}
      />

      {seleccionadas.size > 0 && (
        <div style={{ display:'flex',gap:8,alignItems:'center',background:C.blueBg,border:`1px solid ${C.blue}`,
          borderRadius:8,padding:'8px 14px',marginBottom:10,flexWrap:'wrap' }}>
          <span style={{ fontSize:13,fontWeight:600,color:C.blue }}>{seleccionadas.size} seleccionada(s)</span>
          {selPendientes.length > 0 && (
            <Btn size="sm" variant="success" onClick={()=>{ setBancoBulk(''); setModalBulkPagar(true); }}>
              ✓ Marcar {selPendientes.length} como Pagada
            </Btn>
          )}
          {selPagadas.length > 0 && (
            <Btn size="sm" variant="secondary" disabled={planillaBulk.isPending}
              onClick={()=>planillaBulk.mutate(selPagadas.map(f=>f.id))}>
              📋 Marcar {selPagadas.length} como Planilla Pagada
            </Btn>
          )}
          <Btn size="sm" variant="secondary" onClick={()=>setSeleccionadas(new Set())}>Limpiar selección</Btn>
        </div>
      )}

      <div style={{ overflowX:'auto',borderRadius:10,border:`1px solid ${C.border}` }}>
        <table style={{ width:'100%',borderCollapse:'collapse',background:C.surface }}>
          <thead>
            <tr style={{ background:C.surface2 }}>
              <th style={{ padding:'10px 12px',borderBottom:`1px solid ${C.border}` }}>
                <input type="checkbox"
                  checked={rowsFiltradas.filter(f=>f.estado==='pendiente').length > 0 && rowsFiltradas.filter(f=>f.estado==='pendiente').every(f=>seleccionadas.has(f.id))}
                  onChange={toggleTodos} title="Seleccionar todas las pendientes" />
              </th>
              {['Código','Afiliado','Cliente','Período','Ingreso','Planilla','Utilidad','Banco','Estado','Novedades','Acciones'].map(h=>(
                <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:13,fontWeight:700,
                  color:C.text,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isErrorFacturas && <tr><td colSpan={12}><ErrorMsg message="Error al cargar facturas" onRetry={refetchFacturas} /></td></tr>}
            {isLoading && [1,2,3,4,5].map(i => <SkeletonRow key={i} cols={11} />)}
            {rowsPaginaF.map(f => {
              const isHuerfana = f.afiliado_eliminado && f.estado==='pendiente';
              const isExpanded = expandedRow === f.id;
              const ai = f.afil_info || {};
              const isSel = seleccionadas.has(f.id);
              return (<React.Fragment key={f.id}>
                <tr style={{ borderBottom: isExpanded ? 'none' : `1px solid ${C.border}`,background:isSel?C.blueBg:isHuerfana?C.redBg:C.surface,cursor:'pointer',transition:'background .1s' }}
                  onClick={()=>setExpandedRow(isExpanded ? null : f.id)}
                  onMouseEnter={e=>{ if(!isHuerfana&&!isSel) e.currentTarget.style.background=C.surface2; }}
                  onMouseLeave={e=>{ e.currentTarget.style.background=isSel?C.blueBg:isHuerfana?C.redBg:C.surface; }}>
                  <td style={tdc} onClick={e=>e.stopPropagation()}>
                    <input type="checkbox" checked={isSel} onChange={()=>toggleSel(f.id)} />
                  </td>
                  <td style={tdc}><span style={{ fontFamily:'monospace',fontSize:12 }}>{f.codigo}</span></td>
                  <td style={{ ...tdc,color:isHuerfana?C.red:C.blue }}>
                    <span style={{ textDecoration:'underline',cursor:'pointer' }}>{f.nombre_afiliado}</span>
                    {isHuerfana && <span style={{ fontSize:10,marginLeft:4 }}>⚠️ eliminado</span>}
                  </td>
                  <td style={tdc}>{f.cliente||'—'}</td>
                  <td style={tdc}>{f.mes} {f.anio}{f.periodo&&f.periodo!=='30'?` (${f.periodo}d)`:''}</td>
                  <td style={{ ...tdc,textAlign:'right',fontWeight:600 }}>{fmt(f.ingresos)}</td>
                  <td style={{ ...tdc,textAlign:'right',color:C.red }}>{fmt(f.costos)}</td>
                  <td style={{ ...tdc,textAlign:'right',fontWeight:700,color:(f.utilidad>=0)?C.green:C.red }}>{fmt(f.utilidad)}</td>
                  <td style={tdc}>{f.banco||'—'}</td>
                  <td style={tdc}>
                    <span style={{
                      background: f.estado==='planilla_pagada' ? '#DCFCE7' : f.estado==='pagado' ? C.greenBg : C.amberBg,
                      color: f.estado==='planilla_pagada' ? '#166534' : f.estado==='pagado' ? C.green : C.amber,
                      borderRadius:10,padding:'2px 10px',fontSize:11,fontWeight:600 }}>
                      {f.estado==='planilla_pagada' ? '📋 Planilla Pagada' : f.estado==='pagado' ? 'Pagada' :
                        'Pendiente'}
                    </span>
                  </td>
                  <td style={{ ...tdc, maxWidth:200 }}>
                    {f.novedades
                      ? <span title={f.novedades} style={{ display:'inline-block', background:C.blueBg, color:C.blue,
                          borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600,
                          maxWidth:190, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', cursor:'default' }}>
                          {f.novedades}
                        </span>
                      : <span style={{ fontSize:11, color:C.text2 }}>—</span>}
                  </td>
                  <td style={tdc}>
                    <div style={{ display:'flex',gap:5,flexWrap:'wrap' }}>
                      <Btn size="sm" variant="secondary" onClick={(e)=>{e.stopPropagation();setModalEditar(f);}}>✏️ Editar</Btn>
                      {f.estado==='pendiente' && <Btn size="sm" variant="success" onClick={(e)=>{e.stopPropagation();setBancoPago('');setModalPagar(f);}}>✓ Pagada</Btn>}
                      {f.estado==='pagado' && <Btn size="sm" variant="secondary" disabled={planillaPagada.isPending} onClick={(e)=>{e.stopPropagation();planillaPagada.mutate(f.id);}}>📋 Planilla Pagada</Btn>}
                      <Btn size="sm" variant="secondary" onClick={(e)=>{
                        e.stopPropagation();
                        const tel = (f.tel||'').replace(/\D/g,'');
                        if (!tel) { toast.error('El afiliado no tiene teléfono registrado'); return; }
                        const phone = tel.startsWith('57') ? tel : `57${tel}`;
                        const horaActual = new Date().getHours();
                        const saludo = horaActual < 12 ? 'Buenos días' : horaActual < 18 ? 'Buenas tardes' : 'Buenas noches';
                        const fechaEmision = new Date().toLocaleDateString('es-CO',{day:'2-digit',month:'short',year:'numeric'});
                        const fechaVenc = calcularFechaVencimiento(f.fecha_afiliacion, f.mes, f.anio);
                        const serviciosTexto = (f.servicios_detalle||[]).filter(s=>s.incluido!==false).map(s=>`-${s.servicio}`).join('\n');
                        const plantilla = config.plantilla_whatsapp || '';
                        const texto = plantilla
                          .replace('{{saludo}}', saludo)
                          .replace('{{nombre}}', f.nombre_afiliado||'')
                          .replace('{{mes}}', f.mes||'')
                          .replace('{{anio}}', f.anio||'')
                          .replace('{{fecha_emision}}', fechaEmision)
                          .replace('{{vencimiento}}', fechaVenc ? `Fecha de Vencimiento: ${fechaVenc}` : '')
                          .replace('{{total}}', Number(f.ingresos||0).toLocaleString('es-CO'))
                          .replace('{{servicios}}', serviciosTexto ? `Servicios contratados:\n${serviciosTexto}` : '');
                        const msg = encodeURIComponent(texto);
                        window.open(`https://wa.me/${phone}?text=${msg}`, '_blank');
                      }}>💬 WhatsApp</Btn>
                      <Btn size="sm" variant="secondary"
                        onClick={(e)=>{e.stopPropagation();dlExcel(`/facturas/${f.id}/pdf`, `factura_${f.nombre_afiliado?.replace(/ /g,'_')}_${f.codigo}.pdf`);}}>📄 PDF</Btn>
                      <Btn size="sm" variant="danger"
                        onClick={(e)=>{ e.stopPropagation(); setConfirmState({ open:true, title:'Eliminar factura', message:'¿Eliminar esta factura? Esta acción no se puede deshacer.', onConfirm:()=>{ eliminar.mutate(f.id); setConfirmState(s=>({...s,open:false})); } }); }}>×</Btn>
                    </div>
                  </td>
                </tr>
                {isExpanded && Object.keys(ai).length > 0 && (
                  <tr style={{ borderBottom:`1px solid ${C.border}`,background:C.blueBg }}>
                    <td colSpan={12} style={{ padding:'10px 16px' }}>
                      <div style={{ display:'flex',gap:24,flexWrap:'wrap',fontSize:12,color:C.text }}>
                        <div><strong style={{ color:C.blue }}>Doc:</strong> {f.doc}</div>
                        <div><strong style={{ color:C.blue }}>Tel:</strong> {ai.tel||'—'}</div>
                        <div><strong style={{ color:C.blue }}>Email:</strong> {ai.email||'—'}</div>
                        <div><strong style={{ color:C.blue }}>Ciudad:</strong> {ai.ciudad||'—'}</div>
                        <div><strong style={{ color:C.blue }}>Dirección:</strong> {ai.dir||'—'}</div>
                        <div><strong style={{ color:C.blue }}>Empresa:</strong> {ai.empresa||'—'}</div>
                        <div><strong style={{ color:C.blue }}>EPS:</strong> {ai.eps||'—'}</div>
                        <div><strong style={{ color:C.blue }}>AFP:</strong> {ai.afp||'—'}</div>
                        <div><strong style={{ color:C.blue }}>ARL:</strong> {ai.arl||'—'}</div>
                        <div><strong style={{ color:C.blue }}>CCF:</strong> {ai.ccf||'—'}</div>
                        <div><strong style={{ color:C.blue }}>IBC:</strong> {fmt(ai.ibc)}</div>
                        <div><strong style={{ color:C.blue }}>Estado:</strong> {ai.estado_afil||'—'}</div>
                        {ai.detalle && <div><strong style={{ color:C.blue }}>Detalle:</strong> {ai.detalle}</div>}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>);
            })}
            {!isLoading && rowsFiltradas.length===0 && (
              <tr><td colSpan={12} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin facturas</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPagsF2 > 1 && (
        <div style={{ display:'flex', justifyContent:'center', alignItems:'center', gap:6, marginTop:14, flexWrap:'wrap' }}>
          <button onClick={()=>setPaginaF(1)} disabled={paginaF===1}
            style={{ padding:'5px 10px', borderRadius:6, border:`1px solid ${C.border}`, background:C.surface2, cursor:'pointer', fontSize:13, color:C.text }}>«</button>
          <button onClick={()=>setPaginaF(p=>Math.max(1,p-1))} disabled={paginaF===1}
            style={{ padding:'5px 10px', borderRadius:6, border:`1px solid ${C.border}`, background:C.surface2, cursor:'pointer', fontSize:13, color:C.text }}>‹</button>
          {[...Array(Math.min(5, totalPagsF2))].map((_,i) => {
            const p = paginaF <= 3 ? i+1 : paginaF - 2 + i;
            if (p < 1 || p > totalPagsF2) return null;
            return <button key={p} onClick={()=>setPaginaF(p)}
              style={{ padding:'5px 10px', borderRadius:6, border:`1px solid ${C.border}`,
                fontWeight: p===paginaF?700:400, background: p===paginaF ? C.primary : C.surface2,
                color: p===paginaF ? '#fff' : C.text, cursor:'pointer', fontSize:13 }}>{p}</button>;
          })}
          <button onClick={()=>setPaginaF(p=>Math.min(totalPagsF2,p+1))} disabled={paginaF===totalPagsF2}
            style={{ padding:'5px 10px', borderRadius:6, border:`1px solid ${C.border}`, background:C.surface2, cursor:'pointer', fontSize:13, color:C.text }}>›</button>
          <button onClick={()=>setPaginaF(totalPagsF2)} disabled={paginaF===totalPagsF2}
            style={{ padding:'5px 10px', borderRadius:6, border:`1px solid ${C.border}`, background:C.surface2, cursor:'pointer', fontSize:13, color:C.text }}>»</button>
          <span style={{ fontSize:12, color:C.text2, marginLeft:4 }}>Pág {paginaF}/{totalPagsF2} · {rowsFiltradas.length} total</span>
        </div>
      )}
      </div>)}

      <NuevaFacturaModal open={modalNueva} onClose={()=>{setModalNueva(false);setPrefill(null);}}
        config={config} listas={listas} prefill={prefill} />
      <EditarFacturaModal open={!!modalEditar} onClose={()=>setModalEditar(null)}
        factura={modalEditar} config={config} listas={listas} />

      {/* Modal editar ingreso adicional */}
      {editIngAd && (
        <Modal open={!!editIngAd} onClose={()=>setEditIngAd(null)} width={440} title="✏️ Editar ingreso adicional">
          <EditIngAdForm
            inicial={editIngAd} MESES_NUM={MESES_NUM}
            onGuardar={(data) => editarIngAd.mutate({ id: editIngAd.id, data })}
            onCancel={() => setEditIngAd(null)}
            isPending={editarIngAd.isPending}
          />
        </Modal>
      )}

      {/* Modal ingreso adicional */}
      <Modal open={modalIngAd} onClose={()=>setModalIngAd(false)} width={440} title="➕ Ingreso adicional">
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          <div>
            <label style={lbl}>Concepto *</label>
            <select style={sel} value={formIngAd.concepto} onChange={e=>setFormIngAd(f=>({...f,concepto:e.target.value}))}>
              <option>Comisión</option>
              <option>Planilla verificable</option>
              <option>Otro</option>
            </select>
          </div>
          <div>
            <label style={lbl}>Descripción</label>
            <input style={sel} placeholder="Detalle opcional..." value={formIngAd.descripcion}
              onChange={e=>setFormIngAd(f=>({...f,descripcion:e.target.value}))} />
          </div>
          <div>
            <label style={lbl}>Valor *</label>
            <input type="number" style={sel} placeholder="0" min="0" value={formIngAd.valor}
              onChange={e=>setFormIngAd(f=>({...f,valor:e.target.value}))} />
          </div>
          <div style={{ display:'flex', gap:10 }}>
            <div style={{ flex:1 }}>
              <label style={lbl}>Mes *</label>
              <select style={sel} value={formIngAd.mes} onChange={e=>setFormIngAd(f=>({...f,mes:parseInt(e.target.value)}))}>
                {MESES_NUM.map((m,i)=><option key={m} value={i+1}>{m}</option>)}
              </select>
            </div>
            <div style={{ flex:1 }}>
              <label style={lbl}>Año *</label>
              <input type="number" style={sel} value={formIngAd.anio} min="2020" max="2099"
                onChange={e=>setFormIngAd(f=>({...f,anio:parseInt(e.target.value)}))} />
            </div>
          </div>
          <div style={{ display:'flex', gap:10, justifyContent:'flex-end', marginTop:4 }}>
            <Btn variant="secondary" onClick={()=>setModalIngAd(false)}>Cancelar</Btn>
            <Btn variant="accent"
              disabled={!formIngAd.valor || parseFloat(formIngAd.valor) <= 0 || crearIngAd.isPending}
              onClick={()=>crearIngAd.mutate({ concepto:formIngAd.concepto, descripcion:formIngAd.descripcion,
                valor:parseFloat(formIngAd.valor), mes:formIngAd.mes, anio:formIngAd.anio })}>
              {crearIngAd.isPending ? 'Guardando...' : 'Agregar'}
            </Btn>
          </div>
        </div>
      </Modal>

      {/* Modal pago masivo */}
      <Modal open={modalBulkPagar} onClose={()=>setModalBulkPagar(false)} width={420} title={`✓ Marcar ${selPendientes.length} factura(s) como pagada`}>
        <div>
          <p style={{ margin:'0 0 14px',fontSize:13,color:C.text2 }}>
            Se marcarán como pagadas <strong style={{ color:C.text }}>{selPendientes.length} factura(s)</strong> pendientes seleccionadas.
          </p>
          <label style={lbl}>Banco / Forma de pago</label>
          <select style={{ ...inp, marginBottom:20 }} value={bancoBulk} onChange={e=>setBancoBulk(e.target.value)}>
            <option value="">Seleccionar banco...</option>
            {(listas?.bancos||[]).map(b=><option key={b}>{b}</option>)}
          </select>
          <div style={{ display:'flex',justifyContent:'flex-end',gap:10 }}>
            <Btn variant="secondary" onClick={()=>setModalBulkPagar(false)}>Cancelar</Btn>
            <Btn variant="success" disabled={pagarBulk.isPending || !bancoBulk}
              onClick={()=>pagarBulk.mutate({ ids: selPendientes.map(f=>f.id), banco: bancoBulk })}>
              {pagarBulk.isPending ? 'Guardando...' : `✓ Confirmar ${selPendientes.length} pago(s)`}
            </Btn>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState(s => ({ ...s, open: false }))}
      />

      {/* Mini modal: registrar pago */}
      <Modal open={!!modalPagar} onClose={()=>{ setModalPagar(null); setBancoPago(''); }} width={420} title="✓ Registrar pago">
        {modalPagar && (
          <div>
            <p style={{ margin:'0 0 14px', fontSize:13, color:C.text2 }}>
              <strong style={{ color:C.text }}>{modalPagar.nombre_afiliado}</strong> — {modalPagar.codigo}
            </p>
            <label style={lbl}>Banco / Forma de pago</label>
            <select style={{ ...inp, marginBottom:20 }} value={bancoPago} onChange={e=>setBancoPago(e.target.value)}>
              <option value="">Seleccionar banco...</option>
              {(listas?.bancos||[]).map(b=><option key={b}>{b}</option>)}
            </select>
            <div style={{ display:'flex', justifyContent:'flex-end', gap:10 }}>
              <Btn variant="secondary" onClick={()=>{ setModalPagar(null); setBancoPago(''); }}>Cancelar</Btn>
              <Btn variant="success" onClick={()=>pagar.mutate({ id:modalPagar.id, banco:bancoPago })}
                disabled={pagar.isPending || !bancoPago}>
                {pagar.isPending ? 'Guardando...' : '✓ Confirmar pago'}
              </Btn>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

const tdc = { padding:'10px 12px',fontSize:13,color:C.text,verticalAlign:'middle' };
const sel = { padding:'8px 12px',border:`1px solid ${C.border}`,borderRadius:7,fontSize:13,outline:'none',background:C.surface,color:C.text };
const lbl  = { display:'block',fontSize:12,color:C.text2,fontWeight:500,marginBottom:4 };
const mlbl = { display:'block',fontSize:11,color:C.text,fontWeight:700,marginBottom:5,textTransform:'uppercase',letterSpacing:'.05em' };
const inp = { width:'100%',padding:'9px 12px',border:`1px solid ${C.border}`,borderRadius:7,fontSize:13,outline:'none',boxSizing:'border-box',color:C.text,background:C.surface };

