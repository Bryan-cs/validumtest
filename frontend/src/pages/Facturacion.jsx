import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import { C, Btn, Modal, PageHeader, StatCard, fmt } from '../components/UI';
import { BarraFiltros } from '../components/FiltroCheck';

const UP = v => (v||'').toUpperCase();

async function dlExcel(url, filename) {
  try {
    const res = await api.get(url, { responseType: 'blob' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(res.data);
    a.download = filename;
    a.click();
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || 'Error generando reporte';
    alert(typeof msg === 'string' ? msg : 'Error generando reporte');
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

// Cálculo de planilla idéntico al .py
function calcPlanilla(afiliado, config, dias) {
  const ceil100 = v => Math.ceil(v / 100) * 100;
  if (!afiliado || !config) return [];
  const ibc = (afiliado.ibc && afiliado.ibc > 0) ? afiliado.ibc : (config.ibc_global || 1950905);
  const pcts = config.porcentajes || {};
  const servicios = afiliado.servicios || [];
  const result = [];
  const seen = new Set();
  for (const s of servicios) {
    const su = s.toUpperCase();
    let key = null;
    if (su.includes('EPS')) key = 'EPS';
    else if (su.includes('CCF') || su.includes('CAJA')) key = 'CCF';
    else if (su.includes('AFP') || su.includes('PENSION')) key = 'AFP';
    else if (su.includes('ARL')) {
      for (const n of ['1','2','3','4','5']) { if (su.includes(n)) { key = `ARL ${n}`; break; } }
    }
    if (!key) key = s;
    if (!seen.has(key)) {
      seen.add(key);
      const pct = pcts[key] || 0;
      const val30 = ceil100(ibc * pct);
      const valor = dias > 0 ? ceil100(val30 * dias / 30) : 0;
      result.push({ servicio: key, pct, val30, valor, ibc });
    }
  }
  // ARL del campo directo
  if (afiliado.arl && afiliado.arl !== 'N/A' && afiliado.arl !== '') {
    const arlKey = `ARL ${afiliado.arl}`;
    if (!seen.has(arlKey)) {
      const pct = pcts[arlKey] || 0;
      const val30 = ceil100(ibc * pct);
      const valor = dias > 0 ? ceil100(val30 * dias / 30) : 0;
      result.push({ servicio: arlKey, pct, val30, valor, ibc });
    }
  }
  return result;
}

// ─── MODAL NUEVA FACTURA ─────────────────────────────────────────────────────
export function NuevaFacturaModal({ open, onClose, config, listas, prefill }) {
  const [cedula, setCedula] = useState('');
  const [afiliado, setAfiliado] = useState(null);
  const [errorBusq, setErrorBusq] = useState('');
  const [dias, setDias] = useState(30);
  const [mes, setMes] = useState(MESES[new Date().getMonth()]);
  const [anio, setAnio] = useState(String(new Date().getFullYear()));
  const [estado, setEstado] = useState('pendiente');
  const [banco, setBanco] = useState('');
  const [ingreso, setIngreso] = useState(0);
  const [novedades, setNovedades] = useState('');
  const [marcados, setMarcados] = useState({});
  const [conceptos, setConceptos] = useState([]);
  const qc = useQueryClient();

  useEffect(() => {
    if (!open) {
      setCedula(''); setAfiliado(null); setErrorBusq(''); setDias(30);
      setMes(MESES[new Date().getMonth()]); setEstado('pendiente');
      setBanco(''); setIngreso(0); setNovedades(''); setMarcados({}); setConceptos([]);
    }
  }, [open]);

  useEffect(() => {
    if (open && prefill && prefill.doc) {
      setCedula(prefill.doc);
      api.get('/afiliados', { params: { q: prefill.doc } }).then(r => {
        const found = (r.data.items||[]).find(a => a.doc === prefill.doc) || r.data.items?.[0];
        if (found) { setAfiliado(found); setErrorBusq(''); }
      }).catch(() => toast.error('Error buscando afiliado'));
    }
  }, [open, prefill]);

  const planilla = calcPlanilla(afiliado, config, dias);
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
    try {
      const r = await api.get('/afiliados', { params: { q: cedula.trim() } });
      const found = (r.data.items||[]).find(a => a.doc === cedula.trim()) || r.data.items?.[0];
      if (!found) { setErrorBusq(`No se encontró afiliado con cédula "${cedula}"`); setAfiliado(null); return; }
      setAfiliado(found); setErrorBusq('');
    } catch { setErrorBusq('Error buscando afiliado'); }
  };

  const costoPlanilla = planilla.reduce((s, p) => s + (marcados[p.servicio] ? p.valor : 0), 0);
  const extra = conceptos.reduce((s, c) => {
    const val = parseFloat(c.valor) || 0;
    return s + (c.tipo === 'Deduccion' ? -val : val);
  }, 0);
  const utilidad = ingreso - costoPlanilla + extra;
  const ibc = afiliado ? ((afiliado.ibc && afiliado.ibc > 0) ? afiliado.ibc : config?.ibc_global) : config?.ibc_global;

  const guardar = useMutation({
    mutationFn: () => {
      if (!afiliado) return Promise.reject(new Error('Busca el afiliado primero'));
      return api.post('/facturas', {
        nombre_afiliado: afiliado.nombre, doc: afiliado.doc,
        cliente: afiliado.cliente_txt || afiliado.empresa || '',
        anio, mes, periodo: String(dias), estado, banco,
        ingresos: ingreso, costos: costoPlanilla,
        conceptos_extra: extra, utilidad, novedades,
        servicios_detalle: planilla.map(p => ({ ...p, incluido: marcados[p.servicio] !== false })),
        conceptos_detalle: conceptos,
      });
    },
    onSuccess: () => { toast.success('Factura guardada'); qc.invalidateQueries({queryKey:['facturas']}); qc.invalidateQueries({queryKey:['cobro']}); onClose(); },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||e.message||'Error')); },
  });

  return (
    <Modal open={open} onClose={onClose} width={820} title="Nueva factura por afiliado">
      <div style={{ display:'grid', gridTemplateColumns:'2fr 1fr 1fr 1fr', gap:10, marginBottom:10 }}>
        <div>
          <label style={lbl}>Cédula del afiliado *</label>
          <div style={{ display:'flex', gap:6 }}>
            <input style={{ ...inp, flex:1 }} value={cedula} onChange={e => setCedula(e.target.value)}
              onKeyDown={e => e.key==='Enter' && buscar()} placeholder="Número de documento..." />
            <Btn onClick={buscar} size="sm">🔍 Consultar</Btn>
          </div>
        </div>
        <div><label style={lbl}>Días (0-30)</label>
          <input type="number" min={0} max={30} style={inp} value={dias}
            onChange={e => setDias(Math.min(30, Math.max(0, +e.target.value)))} /></div>
        <div><label style={lbl}>Mes</label>
          <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
            {MESES.map(m => <option key={m}>{m}</option>)}</select></div>
        <div><label style={lbl}>Estado</label>
          <select style={inp} value={estado} onChange={e => setEstado(e.target.value)}>
            <option value="pendiente">Pendiente</option><option value="pagado">Pagado</option></select></div>
      </div>

      {errorBusq && <div style={{ background:C.redBg,color:C.red,borderRadius:7,padding:'8px 12px',fontSize:12,marginBottom:10 }}>{errorBusq}</div>}
      {afiliado && (
        <div style={{ background:C.blueBg,color:C.blue,borderRadius:7,padding:'8px 12px',fontSize:12,marginBottom:10,fontWeight:500 }}>
          ✓ <strong>{afiliado.nombre}</strong> | Empresa: {afiliado.empresa} | Cliente: {afiliado.cliente_txt||'—'} |
          IBC: {fmt(ibc)}{afiliado.ibc ? ' ⚡ propio' : ' (global)'} | Días: {dias}/30 | Total planilla: <strong>{fmt(costoPlanilla)}</strong>
          {dias===0 && <span style={{ color:C.amber }}> ⚠️ Días=0: primer mes, planilla no aplica</span>}
        </div>
      )}

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:10 }}>
        <div style={{ gridColumn:'1/-1' }}><label style={lbl}>📝 Novedades / observaciones</label>
          <input style={{ ...inp, textTransform:'uppercase' }} value={novedades}
            onChange={e => setNovedades(UP(e.target.value))} placeholder="OBSERVACIONES DE ESTA FACTURA..." /></div>
        <div><label style={lbl}>Banco / Forma de pago</label>
          <select style={inp} value={banco} onChange={e => setBanco(e.target.value)}>
            <option value="">Seleccionar...</option>
            {(listas?.bancos||[]).map(b => <option key={b}>{b}</option>)}</select></div>
      </div>

      <SrvTable planilla={planilla} marcados={marcados} setMarcados={setMarcados} dias={dias}
        sinAfiliado={!afiliado} />

      <div style={{ marginBottom:10 }}>
        <label style={lbl}>Ingreso cobrado al cliente ($)</label>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <input type="number" style={{ ...inp, width:220 }} value={ingreso}
            onChange={e => setIngreso(parseFloat(e.target.value)||0)} placeholder="0" />
          <span style={{ fontSize:11,color:C.text2 }}>Planilla + administración cobrada</span>
        </div>
      </div>

      <ConceptosSection conceptos={conceptos} setConceptos={setConceptos} />
      <ResumenFinanciero ingreso={ingreso} costoPlanilla={costoPlanilla} extra={extra} utilidad={utilidad} />

      <div style={{ display:'flex', justifyContent:'flex-end', gap:10 }}>
        <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
        <Btn onClick={() => guardar.mutate()} disabled={guardar.isPending || !afiliado}>
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
  const [ingreso, setIngreso] = useState(0);
  const [novedades, setNovedades] = useState('');
  const [marcados, setMarcados] = useState({});
  const [conceptos, setConceptos] = useState([]);
  const [afiliado, setAfiliado] = useState(null);
  const qc = useQueryClient();

  useEffect(() => {
    if (open && factura) {
      setDias(parseInt(factura.periodo) || 30);
      setMes(factura.mes || MESES[new Date().getMonth()]);
      setEstado(factura.estado || 'pendiente');
      setBanco(factura.banco || '');
      setIngreso(factura.ingresos || 0);
      setNovedades(factura.novedades || '');
      setConceptos(factura.conceptos_detalle || []);
      const m = {};
      (factura.servicios_detalle || []).forEach(s => { m[s.servicio] = s.incluido !== false; });
      setMarcados(m);
      if (factura.doc) {
        api.get('/afiliados', { params: { q: factura.doc } })
          .then(r => { const f = (r.data.items||[]).find(a => a.doc === factura.doc); if (f) setAfiliado(f); })
          .catch(() => toast.error('Error buscando afiliado'));
      }
    }
  }, [open, factura?.id]);

  const planilla = calcPlanilla(afiliado, config, dias);
  const planillaFinal = planilla.length > 0 ? planilla : (factura?.servicios_detalle || []).map(s => ({
    servicio: s.servicio, pct: s.pct || 0, valor: s.valor || 0, val30: s.val30 || 0,
  }));

  const costoPlanilla = planillaFinal.reduce((s, p) => s + (marcados[p.servicio] !== false ? p.valor : 0), 0);
  const extra = conceptos.reduce((s, c) => {
    const val = parseFloat(c.valor) || 0;
    return s + (c.tipo === 'Deduccion' ? -val : val);
  }, 0);
  const utilidad = ingreso - costoPlanilla + extra;

  const guardar = useMutation({
    mutationFn: () => api.put(`/facturas/${factura.id}`, {
      mes, periodo: String(dias), estado, banco,
      ingresos: ingreso, costos: costoPlanilla,
      conceptos_extra: extra, utilidad, novedades,
      servicios_detalle: planillaFinal.map(p => ({ ...p, incluido: marcados[p.servicio] !== false })),
      conceptos_detalle: conceptos,
    }),
    onSuccess: () => { toast.success('Factura actualizada'); qc.invalidateQueries({queryKey:['facturas']}); onClose(); },
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
      <SrvTable planilla={planillaFinal} marcados={marcados} setMarcados={setMarcados} dias={dias} />
      <div style={{ marginBottom:10 }}><label style={lbl}>Ingreso cobrado al cliente ($)</label>
        <input type="number" style={{ ...inp,width:220 }} value={ingreso}
          onChange={e => setIngreso(parseFloat(e.target.value)||0)} /></div>
      <ConceptosSection conceptos={conceptos} setConceptos={setConceptos} />
      <ResumenFinanciero ingreso={ingreso} costoPlanilla={costoPlanilla} extra={extra} utilidad={utilidad} />
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
function SrvTable({ planilla, marcados, setMarcados, dias, sinAfiliado }) {
  return (
    <div style={{ marginBottom:10 }}>
      <div style={{ fontSize:13,fontWeight:700,color:C.primary,borderBottom:`2px solid ${C.primary}`,paddingBottom:4,marginBottom:6 }}>
        Servicios contratados del afiliado
        <span style={{ fontSize:11,fontWeight:400,color:C.text2,marginLeft:8 }}>Desmarca los que no aplican (ej: primer mes)</span>
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
                  borderBottom:`1px solid ${C.border}`,background: inc?'#fff':C.surface2 }}>
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
                    color:inc?C.red:C.text2,textDecoration:inc?'none':'line-through' }}>
                    {dias===0 ? <span style={{ color:C.text2 }}>— (ref: {fmt(p.val30)})</span>
                      : `${fmt(p.valor)}${dias<30?` (${dias}d)`:''}`}
                  </div>
                </div>
              );
            })}
          </div>
        )
      }
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
        onClick={() => setConceptos(cs => [...cs, {tipo:'Bono',desc:'',valor:0}])}>
        + Agregar concepto
      </Btn>
    </div>
  );
}

function ResumenFinanciero({ ingreso, costoPlanilla, extra, utilidad }) {
  return (
    <div style={{ background:C.surface2,border:`1px solid ${C.border}`,borderRadius:8,padding:'12px 16px',marginBottom:14 }}>
      <div style={{ fontSize:13,fontWeight:700,color:C.primary,marginBottom:8 }}>Resumen financiero</div>
      {[
        ['Ingreso cobrado al cliente:', fmt(ingreso), C.text],
        ['Costo planilla gobierno (marcados):', fmt(costoPlanilla), C.red],
        ['Conceptos adicionales:', fmt(extra), C.amber],
        ['Utilidad neta = Ingreso − Planilla + Conceptos:', fmt(utilidad), utilidad>=0?C.green:C.red],
      ].map(([label,value,color]) => (
        <div key={label} style={{ display:'flex',justifyContent:'space-between',marginBottom:4 }}>
          <span style={{ fontSize:12,color:C.text2 }}>{label}</span>
          <span style={{ fontSize:14,fontWeight:700,color }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

// ─── PÁGINA PRINCIPAL ────────────────────────────────────────────────────────
export default function Facturacion({ prefillAfiliado, onFacturaCreada }) {
  const qc = useQueryClient();
  const [busqueda, setBusqueda] = useState('');
  const [filtros,  setFiltros]  = useState({ anio:[String(new Date().getFullYear())], mes:[], cliente:[], estado:[] });
  const setFiltro = (key, vals) => setFiltros(f=>({...f,[key]:vals}));
  const limpiar   = () => setFiltros({ anio:[String(new Date().getFullYear())], mes:[], cliente:[], estado:[] });
  const [modalNueva,  setModalNueva]  = useState(false);
  const [modalEditar, setModalEditar] = useState(null);
  const [prefill, setPrefill] = useState(null);

  useEffect(() => {
    if (prefillAfiliado) { setPrefill(prefillAfiliado); setModalNueva(true); }
  }, [prefillAfiliado]);

  const [paginaF, setPaginaF] = useState(1);
  const POR_PAG_F = 50;

  // Mapear filtros al formato del backend
  const anioB    = filtros.anio.length    === 1 ? filtros.anio[0]    : '';
  const mesB     = filtros.mes.length     === 1 ? filtros.mes[0]     : '';
  const clienteB = filtros.cliente.length === 1 ? filtros.cliente[0] : '';
  const estadoB  = filtros.estado.length  === 1
    ? (filtros.estado[0] === 'Pagada' ? 'pagado' : 'pendiente') : '';
  const hayFiltros = anioB || mesB || clienteB || estadoB || busqueda ||
    filtros.anio.length > 1 || filtros.mes.length > 1 ||
    filtros.cliente.length > 1 || filtros.estado.length > 1;

  // Si hay filtros activos, traer todos y filtrar localmente; si no, paginar
  const { data: respF={total:0,items:[]}, isLoading } = useQuery({
    queryKey: ['facturas', paginaF, anioB, mesB, clienteB, estadoB, hayFiltros],
    queryFn: () => api.get('/facturas', { params: hayFiltros
      ? { anio: anioB, mes: mesB, cliente: clienteB, estado: estadoB, limit: 0 }
      : { skip: (paginaF-1)*POR_PAG_F, limit: POR_PAG_F }
    }).then(r=>r.data),
    keepPreviousData: true,
  });

  // Resetear página cuando cambien los filtros
  useEffect(() => { setPaginaF(1); }, [anioB, mesB, clienteB, estadoB, busqueda]);

  const rows      = respF.items || [];
  const totalFact = respF.total || 0;
  const totalPagsF = Math.ceil(totalFact / POR_PAG_F);
  const { data: config={} } = useQuery({ queryKey:['config'], queryFn:()=>api.get('/config').then(r=>r.data) });
  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data) });

  const clientesUnicos = [...new Set(rows.map(r=>r.cliente).filter(Boolean))].sort();
  const aniosUnicos    = [...new Set(rows.map(r=>r.anio).filter(Boolean))].sort();
  const mesesUnicos    = [...new Set(rows.map(r=>r.mes).filter(Boolean))];
  const MESES_ORDER    = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  const mesesOrd       = MESES_ORDER.filter(m=>mesesUnicos.includes(m));

  // Filtrado local
  const rowsFiltradas = rows.filter(f => {
    const q = busqueda.toLowerCase();
    if (busqueda && !`${f.nombre_afiliado} ${f.doc} ${f.cliente} ${f.codigo}`.toLowerCase().includes(q)) return false;
    if (filtros.anio.length    && !filtros.anio.includes(f.anio))                    return false;
    if (filtros.mes.length     && !filtros.mes.includes(f.mes))                      return false;
    if (filtros.cliente.length && !filtros.cliente.includes(f.cliente))              return false;
    if (filtros.estado.length  && !filtros.estado.includes(f.estado==='pagado'?'Pagada':'Pendiente')) return false;
    return true;
  });

  const pagar = useMutation({
    mutationFn: id => api.patch(`/facturas/${id}/pagar`),
    onSuccess: () => { toast.success('Factura marcada como pagada'); qc.invalidateQueries({queryKey:['facturas']}); },
  });
  const eliminar = useMutation({
    mutationFn: id => api.delete(`/facturas/${id}`),
    onSuccess: () => { toast.success('Factura eliminada'); qc.invalidateQueries({queryKey:['facturas']}); },
  });

  const totIng  = rowsFiltradas.reduce((s,f)=>s+(f.ingresos||0),0);
  const totUtil = rowsFiltradas.reduce((s,f)=>s+(f.utilidad||0),0);
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

      <input placeholder="🔍 Buscar código, afiliado, documento, cliente..."
        value={busqueda} onChange={e=>setBusqueda(e.target.value)}
        style={{ width:'100%',padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
          fontSize:13,outline:'none',marginBottom:12,boxSizing:'border-box' }} />
      <BarraFiltros
        filtros={[
          { key:'anio',    label:'Año',     icon:'📅', options: aniosUnicos },
          { key:'mes',     label:'Mes',     icon:'🗓️', options: mesesOrd },
          { key:'cliente', label:'Cliente', icon:'👤', options: clientesUnicos },
          { key:'estado',  label:'Estado',  icon:'📌', options: ['Pendiente','Pagada'] },
        ]}
        valores={filtros}
        onChange={setFiltro}
        onLimpiar={limpiar}
      />

      <div style={{ overflowX:'auto',borderRadius:10,border:`1px solid ${C.border}` }}>
        <table style={{ width:'100%',borderCollapse:'collapse',background:'#fff' }}>
          <thead>
            <tr style={{ background:C.surface2 }}>
              {['Código','Afiliado','Cliente','Período','Ingreso','Planilla','Utilidad','Banco','Estado','Novedades','Acciones'].map(h=>(
                <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                  color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={10} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
            {rowsFiltradas.map(f => {
              const isHuerfana = f.afiliado_eliminado && f.estado==='pendiente';
              return (
                <tr key={f.id} style={{ borderBottom:`1px solid ${C.border}`,background:isHuerfana?C.redBg:'#fff' }}>
                  <td style={tdc}><span style={{ fontFamily:'monospace',fontSize:12 }}>{f.codigo}</span></td>
                  <td style={{ ...tdc,color:isHuerfana?C.red:C.text }}>
                    {f.nombre_afiliado}
                    {isHuerfana && <span style={{ fontSize:10,marginLeft:4 }}>⚠️ eliminado</span>}
                  </td>
                  <td style={tdc}>{f.cliente||'—'}</td>
                  <td style={tdc}>{f.mes} {f.anio}{f.periodo&&f.periodo!=='30'?` (${f.periodo}d)`:''}</td>
                  <td style={{ ...tdc,textAlign:'right',fontWeight:600 }}>{fmt(f.ingresos)}</td>
                  <td style={{ ...tdc,textAlign:'right',color:C.red }}>{fmt(f.costos)}</td>
                  <td style={{ ...tdc,textAlign:'right',fontWeight:700,color:(f.utilidad>=0)?C.green:C.red }}>{fmt(f.utilidad)}</td>
                  <td style={tdc}>{f.banco||'—'}</td>
                  <td style={tdc}>
                    <span style={{ background:f.estado==='pagado'?C.greenBg:C.amberBg,
                      color:f.estado==='pagado'?C.green:C.amber,
                      borderRadius:10,padding:'2px 10px',fontSize:11,fontWeight:600 }}>
                      {f.estado==='pagado'?'Pagada':'Pendiente'}
                    </span>
                  </td>
                  <td style={{ ...tdc,fontSize:11,color:C.text2,maxWidth:200,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis' }}>
                    {f.novedades||'—'}
                  </td>
                  <td style={tdc}>
                    <div style={{ display:'flex',gap:5,flexWrap:'wrap' }}>
                      <Btn size="sm" variant="secondary" onClick={()=>setModalEditar(f)}>✏️ Editar</Btn>
                      {f.estado==='pendiente' && <Btn size="sm" variant="success" onClick={()=>pagar.mutate(f.id)}>✓ Pagada</Btn>}
                      <Btn size="sm" variant="secondary" onClick={()=>{
                        const tel = (f.tel||'').replace(/\D/g,'');
                        if (!tel) { alert('El afiliado no tiene teléfono registrado'); return; }
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
                          .replace('{{total}}', Number(f.costos||0).toLocaleString('es-CO'))
                          .replace('{{servicios}}', serviciosTexto ? `Servicios contratados:\n${serviciosTexto}` : '');
                        const msg = encodeURIComponent(texto);
                        window.open(`https://wa.me/${phone}?text=${msg}`, '_blank');
                      }}>💬 WhatsApp</Btn>
                      <Btn size="sm" variant="secondary"
                        onClick={()=>dlExcel(`/facturas/${f.id}/pdf`, `factura_${f.codigo}.pdf`)}>📄 PDF</Btn>
                      <Btn size="sm" variant="danger"
                        onClick={()=>{ if(window.confirm('¿Eliminar factura?')) eliminar.mutate(f.id); }}>×</Btn>
                    </div>
                  </td>
                </tr>
              );
            })}
            {!isLoading && rowsFiltradas.length===0 && (
              <tr><td colSpan={11} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin facturas</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <NuevaFacturaModal open={modalNueva} onClose={()=>{setModalNueva(false);setPrefill(null);}}
        config={config} listas={listas} prefill={prefill} />
      <EditarFacturaModal open={!!modalEditar} onClose={()=>setModalEditar(null)}
        factura={modalEditar} config={config} listas={listas} />
    </div>
  );
}

const tdc = { padding:'10px 12px',fontSize:13,color:'#1E293B',verticalAlign:'middle' };
const sel = { padding:'8px 12px',border:'1px solid #E2E8F0',borderRadius:7,fontSize:13,outline:'none',background:'#fff',color:'#1E293B' };
const lbl = { display:'block',fontSize:12,color:'#64748B',fontWeight:500,marginBottom:4 };
const inp = { width:'100%',padding:'9px 12px',border:'1px solid #E2E8F0',borderRadius:7,fontSize:13,outline:'none',boxSizing:'border-box',color:'#1E293B' };
