import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Btn, Modal, ConfirmModal, ErrorMsg, SkeletonCard } from '../components/UI';
import { campo, celda } from '../estilos';

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

const ESTADO_STYLE = {
  generada: { bg: '#EFF6FF', color: '#2563EB' },
  enviada:  { bg: '#FFFBEB', color: '#D97706' },
  numerada: { bg: '#F5F3FF', color: '#7C3AED' },
  pagada:   { bg: '#ECFDF5', color: '#059669' },
  anulada:  { bg: '#FEF2F2', color: '#DC2626' },
};

const pesos = (n) => '$' + (Number(n) || 0).toLocaleString('es-CO');

// Tipos de documento que acepta el campo 3 del registro tipo 2. Se puede bajar
// el mismo plano con otro documento cuando el operador tiene a la persona
// registrada con uno distinto al que está en el sistema.
const TIPOS_DOC = ['CC', 'CE', 'TI', 'PA', 'CD', 'SC', 'PE', 'PT', 'PC'];

const inp = campo(C);
const POR_PAGINA = 25;

const td = celda(C);
const thBase = {
  ...td, fontSize: 11, fontWeight: 800, letterSpacing: '0.05em',
  textTransform: 'uppercase', background: '#F8FAFC', textAlign: 'left',
  position: 'sticky', top: 0,
};

const COLUMNAS = [
  ['Afiliado', C.text],
  ['Documento', '#0369A1'],
  ['Empresa', '#6D28D9'],
  ['Cliente', '#7C3AED'],
  ['Subtipo', '#C2410C'],
  ['Servicios', '#0F766E'],
  ['Factura', '#047857'],
  ['Total', '#1D4ED8'],
  ['Estado', C.text],
  ['Acciones', C.text],
];

const lbl = {
  fontSize: 11, fontWeight: 800, letterSpacing: '0.06em',
  textTransform: 'uppercase', marginBottom: 4, display: 'block',
};

function Servicios({ lista }) {
  const tono = {
    EPS: { background: '#DBEAFE', color: '#1D4ED8' },
    AFP: { background: '#EDE9FE', color: '#6D28D9' },
    CCF: { background: '#D1FAE5', color: '#047857' },
    ARL: { background: '#FEF3C7', color: '#B45309' },
  };
  if (!lista?.length) return <span style={{ color: C.text2 }}>—</span>;
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {lista.map(s => {
        const t = tono[s.startsWith('ARL') ? 'ARL' : s] || { background: C.surface2, color: C.text2 };
        return (
          <span key={s} style={{
            fontSize: 11, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
            letterSpacing: '0.02em', ...t,
          }}>{s}</span>
        );
      })}
    </div>
  );
}

function Etiqueta({ children, color }) {
  return <label style={{ ...lbl, color }}>{children}</label>;
}

function EstadoBadge({ estado }) {
  const s = ESTADO_STYLE[estado] || { bg: '#F3F4F6', color: '#6B7280' };
  return (
    <span style={{
      fontSize: 10, fontWeight: 800, padding: '3px 8px', borderRadius: 4,
      background: s.bg, color: s.color, textTransform: 'uppercase',
    }}>
      {estado}
    </span>
  );
}

function Resumen({ etiqueta, valor, detalle }) {
  return (
    <div style={{
      flex: '1 1 140px', padding: '12px 14px', borderRadius: 12,
      background: C.surface, border: `1px solid ${C.border}`,
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.04em',
                    textTransform: 'uppercase', color: C.text2 }}>{etiqueta}</div>
      <div style={{ fontSize: 20, fontWeight: 700, marginTop: 2, color: C.text,
                    fontVariantNumeric: 'tabular-nums' }}>{valor}</div>
      {detalle && <div style={{ fontSize: 12, color: C.text2, marginTop: 2 }}>{detalle}</div>}
    </div>
  );
}
function Total({ etiqueta, valor, destacado }) {
  if (!destacado && !valor) return null;
  return (
    <div style={{
      padding: '8px 12px', borderRadius: 8,
      background: destacado ? '#EFF6FF' : C.surface,
      border: `1px solid ${destacado ? '#BFDBFE' : C.border}`, minWidth: 110,
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: C.text2,
                    textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {etiqueta}
      </div>
      <div style={{ fontSize: destacado ? 17 : 14, fontWeight: 700,
                    color: destacado ? '#1D4ED8' : C.text, marginTop: 2,
                    fontVariantNumeric: 'tabular-nums' }}>
        {pesos(valor)}
      </div>
    </div>
  );
}

export default function Liquidacion() {
  const qc = useQueryClient();
  const hoy = new Date();

  const [anio, setAnio] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() + 1);
  const [busqueda, setBusqueda] = useState('');
  const [subtipo, setSubtipo] = useState('');   // el del formulario: 0, 3, 4, 20, 22
  const [tipoDocFiltro, setTipoDocFiltro] = useState('');
  const [empresa, setEmpresa] = useState('');
  const [clienteFiltro, setClienteFiltro] = useState('');
  const [elegidas, setElegidas] = useState(() => new Set());  // planilla_id
  const [soloPendientes, setSoloPendientes] = useState(false);
  const [estadoFactura, setEstadoFactura] = useState('pagado');
  const [previa, setPrevia] = useState(null);      // { afiliado, resumen }
  const [porAnular, setPorAnular] = useState(null);
  const [docDescarga, setDocDescarga] = useState({});   // planilla_id → tipo de documento
  const [respuesta, setRespuesta] = useState(null);     // lo que contestó el operador
  const [pagina, setPagina] = useState(1);

  const periodo = `${anio}-${String(mes).padStart(2, '0')}`;

  const { data: operador } = useQuery({
    queryKey: ['operador-estado'],
    queryFn: async () => (await api.get('/liquidacion/operador/estado')).data,
    staleTime: 5 * 60 * 1000,
  });

  const { data: personas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['liquidacion-pendientes', anio, mes, estadoFactura],
    queryFn: async () =>
      (await api.get(`/liquidacion/pendientes?anio=${anio}&mes=${mes}&estado_factura=${estadoFactura}`)).data,
  });

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return personas.filter(p => {
      if (soloPendientes && p.planilla_id) return false;
      if (subtipo && String(p.subtipo ?? '') !== subtipo) return false;
      if (tipoDocFiltro && (p.tipo_doc || '') !== tipoDocFiltro) return false;
      if (empresa && (p.empresa || '') !== empresa) return false;
      if (clienteFiltro && (p.cliente || '') !== clienteFiltro) return false;
      if (!q) return true;
      return [p.nombre, p.doc, p.cliente, p.empresa].some(v => (v || '').toLowerCase().includes(q));
    });
  }, [personas, busqueda, soloPendientes, subtipo, tipoDocFiltro, empresa, clienteFiltro]);

  const totalPaginas = Math.max(1, Math.ceil(visibles.length / POR_PAGINA));
  const paginaActual = Math.min(pagina, totalPaginas);
  const enPagina = visibles.slice(
    (paginaActual - 1) * POR_PAGINA, paginaActual * POR_PAGINA);
  const irAPagina = (n) => setPagina(Math.min(Math.max(1, n), totalPaginas));

  const EMPRESAS = useMemo(
    () => [...new Set(personas.map(p => p.empresa).filter(Boolean))].sort(),
    [personas]);
  const CLIENTES = useMemo(
    () => [...new Set(personas.map(p => p.cliente).filter(Boolean))].sort(),
    [personas]);

  // Un archivo plano lleva un solo aportante en el encabezado, asi que solo se
  // pueden juntar personas de la misma empresa. Se sigue la primera elegida.
  const empresaDeLaSeleccion = useMemo(() => {
    const primera = visibles.find(p => elegidas.has(p.planilla_id));
    return primera?.empresa ?? null;
  }, [visibles, elegidas]);

  const seleccionadas = useMemo(
    () => visibles.filter(p => elegidas.has(p.planilla_id)),
    [visibles, elegidas]);

  const alternar = (p) => setElegidas(previas => {
    const s = new Set(previas);
    s.has(p.planilla_id) ? s.delete(p.planilla_id) : s.add(p.planilla_id);
    return s;
  });

  // Los subtipos que de verdad hay en pantalla, con su significado.
  const SUBTIPOS = {
    '0':  'Cotiza pension',
    '3':  'Exonerada por edad',
    '4':  'Requisitos cumplidos',
    '20': 'Obligada a pension',
    '22': 'Extranjera',
  };

  const pendientes = personas.filter(p => !p.planilla_id).length;

  const previsualizar = useMutation({
    mutationFn: async (persona) => ({
      persona,
      datos: (await api.post('/liquidacion/previsualizar', {
        afiliado_id: persona.id, anio: Number(anio), mes: Number(mes),
      })).data,
    }),
    onSuccess: ({ persona, datos }) => {
      setPrevia({ persona, datos });
      if (datos.avisos?.length) datos.avisos.forEach(a => toast.warning(a));
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'No se pudo calcular'),
  });

  const liquidar = useMutation({
    mutationFn: async (persona) => (await api.post('/liquidacion', {
      afiliado_id: persona.id, anio: Number(anio), mes: Number(mes),
    })).data,
    onSuccess: (d) => {
      toast.success(`Planilla de ${d.afiliado.nombre}: ${pesos(d.totales.general)}`);
      setPrevia(null);
      qc.invalidateQueries({ queryKey: ['liquidacion-pendientes'] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'No se pudo liquidar'),
  });

  // Hay errores que el operador marca como corregibles por el. El codigo de
  // actividad economica es el caso: sale del anexo del Decreto 768, que no
  // esta en ninguna documentacion legible, y su validador si lo tiene.
  const corregir = useMutation({
    mutationFn: async (planillaId) =>
      (await api.post(`/liquidacion/${planillaId}/corregir`)).data,
    onSuccess: (d) => {
      const quedan = d.inconsistencias?.errores?.length ?? 0;
      toast.success(quedan
        ? `El operador corrigió lo que pudo; quedan ${quedan} sin corregir.`
        : 'El operador corrigió la planilla y no quedaron errores.');
      setRespuesta(null);
      qc.invalidateQueries({ queryKey: ['liquidacion-pendientes'] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'No se pudo corregir'),
  });

  const enviar = useMutation({
    // El envio sale con el mismo documento que se eligio para descargar: si la
    // persona esta en las bases del operador como CE, mandar CC la deja fuera.
    mutationFn: async (persona) => {
      const tipo = docDescarga[persona.planilla_id] || persona.tipo_doc_sugerido
                   || persona.tipo_doc || 'CC';
      const qs = tipo && tipo !== persona.tipo_doc ? `?tipo_doc=${tipo}` : '';
      return (await api.post(`/liquidacion/${persona.planilla_id}/enviar${qs}`)).data;
    },
    onSuccess: (d, persona) => {
      setRespuesta({ ...d, planilla_id: persona.planilla_id });
      if (d.simulado) {
        toast.info('Simulación: no se envió nada al operador. ' +
                   'Cambia SUAPORTE_MODO a "real" para enviar de verdad.');
      } else if (d.numero_planilla) {
        toast.success(`Planilla numerada: ${d.numero_planilla}`);
      } else if (d.errores?.length) {
        toast.warning(`El operador recibió la planilla ${d.codigo_planilla} con ` +
                      `${d.errores.length} error(es) por corregir`);
      } else {
        toast.success('Planilla enviada al operador');
      }
      qc.invalidateQueries({ queryKey: ['liquidacion-pendientes'] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'No se pudo enviar'),
  });

  const anular = useMutation({
    mutationFn: async (id) => (await api.post(`/liquidacion/${id}/anular`)).data,
    onSuccess: () => {
      toast.success('Planilla anulada');
      qc.invalidateQueries({ queryKey: ['liquidacion-pendientes'] });
      setPorAnular(null);
    },
    onError: (e) => {
      toast.error(e?.response?.data?.detail || 'No se pudo anular');
      setPorAnular(null);
    },
  });

  // El plano viaja con el token, así que se baja por blob y no por enlace.
  // El documento que se eligio para cada persona viaja con su id: en un
  // archivo con varias, una puede ir con CE y el resto con el suyo.
  const documentosElegidos = () => seleccionadas
    .map(p => {
      const tipo = docDescarga[p.planilla_id] || p.tipo_doc_sugerido || p.tipo_doc;
      return tipo ? `${p.planilla_id}:${tipo}` : null;
    })
    .filter(Boolean)
    .join(',');

  const descargarConjunto = async () => {
    const ids = seleccionadas.map(p => p.planilla_id).join(',');
    const docs = documentosElegidos();
    try {
      const r = await api.get(
        `/liquidacion/plano-conjunto?ids=${ids}&docs=${encodeURIComponent(docs)}`,
        { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([r.data], { type: 'text/plain' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `PILA_${empresaDeLaSeleccion}_${periodo}_${seleccionadas.length}cotizantes.txt`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No se pudo descargar el archivo');
    }
  };

  const enviarConjunto = useMutation({
    mutationFn: async () => {
      const ids = seleccionadas.map(p => p.planilla_id).join(',');
      const docs = encodeURIComponent(documentosElegidos());
      return (await api.post(
        `/liquidacion/enviar-conjunto?ids=${ids}&docs=${docs}`)).data;
    },
    onSuccess: (d) => {
      setRespuesta({ ...d, conjunto: true });
      setElegidas(new Set());
      qc.invalidateQueries({ queryKey: ['liquidacion-pendientes'] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'No se pudo enviar'),
  });

  const descargar = async (persona) => {
    // Si se eligió un documento distinto al de la persona, se manda al backend
    // para que cambie solo ese campo del registro.
    const tipo = docDescarga[persona.planilla_id] || persona.tipo_doc_sugerido
                 || persona.tipo_doc || 'CC';
    const qs = tipo && tipo !== persona.tipo_doc ? `?tipo_doc=${tipo}` : '';
    try {
      const r = await api.get(`/liquidacion/${persona.planilla_id}/plano${qs}`,
                              { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([r.data], { type: 'text/plain' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `PILA_${persona.doc}_${periodo}_${tipo}.txt`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('No se pudo descargar el archivo');
    }
  };

  const detalleDeBlob = async (err) => {
    const data = err?.response?.data;
    if (data instanceof Blob) {
      try {
        const j = JSON.parse(await data.text());
        return j.detail || '';
      } catch { return ''; }
    }
    return err?.response?.data?.detail || '';
  };

  const pagar = async (persona) => {
    try {
      const r = await api.post(`/liquidacion/${persona.planilla_id}/pago`);
      const url = r.data?.link_pago;
      if (!url) {
        toast.error('El operador no entregó el enlace de pago');
        return;
      }
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      a.remove();
      qc.invalidateQueries({ queryKey: ['liquidacion-pendientes'] });
    } catch (e) {
      toast.error(await detalleDeBlob(e) || e?.response?.data?.detail
                  || 'No se pudo abrir el pago');
    }
  };

  const descargarComprobante = async (persona) => {
    try {
      const r = await api.get(`/liquidacion/${persona.planilla_id}/comprobante`,
                              { responseType: 'blob' });
      const tipo = r.headers['content-type'] || 'application/pdf';
      const url = URL.createObjectURL(new Blob([r.data], { type: tipo }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `comprobante_${persona.numero_planilla}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(await detalleDeBlob(e) || 'No se pudo bajar el comprobante');
    }
  };

  if (isError) return <ErrorMsg message="Error al cargar los afiliados" onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Liquidación de planillas"
        subtitle={`${MESES[Number(mes) - 1] || ''} ${anio} · liquida, envía y descarga el comprobante`}
      />

      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Resumen etiqueta="Por liquidar" valor={pendientes}
                 detalle={pendientes ? 'Pagadas por el cliente, sin plano' : 'Este mes ya está liquidado'} />
        <Resumen etiqueta="Con plano" valor={personas.length - pendientes}
                 detalle="Listas para enviar o pagar" />
        <Resumen etiqueta="En pantalla" valor={`${visibles.length} de ${personas.length}`}
                 detalle={busqueda || empresa || clienteFiltro || subtipo || tipoDocFiltro || soloPendientes || estadoFactura !== 'pagado'
                   ? 'Con el filtro activo' : 'Solo facturas pagadas'} />
      </div>

      <div style={{
        border: `1px solid ${C.border}`, borderRadius: 12, padding: 14,
        background: C.surface, marginBottom: 16,
        display: 'grid', gap: 12,
      }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <Etiqueta color="#1D4ED8">Mes</Etiqueta>
            <select style={inp} value={mes} onChange={e => { setMes(e.target.value); setPrevia(null); setPagina(1); }}>
              {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
          </div>
          <div>
            <Etiqueta color="#1D4ED8">Año</Etiqueta>
            <input style={{ ...inp, width: 90 }} value={anio} inputMode="numeric"
                   onChange={e => { setAnio(e.target.value); setPrevia(null); setPagina(1); }} />
          </div>
          <div style={{ flex: 1, minWidth: 220 }}>
            <Etiqueta color="#0F766E">Buscar persona</Etiqueta>
            <input style={{ ...inp, width: '100%' }} value={busqueda}
                   placeholder="Nombre, documento o empresa…"
                   onChange={e => { setBusqueda(e.target.value); setPagina(1); }} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ minWidth: 170 }}>
            <Etiqueta color="#047857">Estado de la factura</Etiqueta>
            <select style={{ ...inp, width: '100%' }} value={estadoFactura}
                    onChange={e => { setEstadoFactura(e.target.value); setPagina(1); }}>
              <option value="pagado">Pagada</option>
              <option value="pendiente">Pendiente</option>
              <option value="planilla_pagada">Planilla pagada</option>
              <option value="todos">Todos</option>
            </select>
          </div>
          <div style={{ minWidth: 160, flex: 1 }}>
            <Etiqueta color="#6D28D9">Empresa</Etiqueta>
            <select style={{ ...inp, width: '100%' }} value={empresa}
                    onChange={e => { setEmpresa(e.target.value); setElegidas(new Set()); setPagina(1); }}>
              <option value="">Todas</option>
              {EMPRESAS.map(x => <option key={x} value={x}>{x}</option>)}
            </select>
          </div>
          <div style={{ minWidth: 180, flex: 1 }}>
            <Etiqueta color="#7C3AED">Cliente</Etiqueta>
            <select style={{ ...inp, width: '100%' }} value={clienteFiltro}
                    onChange={e => { setClienteFiltro(e.target.value); setPagina(1); }}>
              <option value="">Todos</option>
              {CLIENTES.map(x => <option key={x} value={x}>{x}</option>)}
            </select>
          </div>
          <div style={{ minWidth: 180, flex: 1 }}>
            <Etiqueta color="#C2410C">Subtipo</Etiqueta>
            <select style={{ ...inp, width: '100%' }} value={subtipo}
                    onChange={e => { setSubtipo(e.target.value); setPagina(1); }}>
              <option value="">Todos</option>
              {Object.entries(SUBTIPOS).map(([k, v]) =>
                <option key={k} value={k}>{k} · {v}</option>)}
            </select>
          </div>
          <div style={{ minWidth: 110 }}>
            <Etiqueta color="#0369A1">Documento</Etiqueta>
            <select style={{ ...inp, width: '100%' }} value={tipoDocFiltro}
                    onChange={e => { setTipoDocFiltro(e.target.value); setPagina(1); }}>
              <option value="">Todos</option>
              {TIPOS_DOC.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <label style={{
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 13,
            color: C.text, padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
            border: `1px solid ${soloPendientes ? '#FCD34D' : C.border}`,
            background: soloPendientes ? C.amberBg : C.surface, marginBottom: 0,
          }}>
            <input type="checkbox" checked={soloPendientes}
                   onChange={e => { setSoloPendientes(e.target.checked); setPagina(1); }} />
            Solo sin liquidar
          </label>
        </div>
      </div>

      {operador?.modo === 'simulacion' && (
        <div style={{
          border: '1px solid #FDE68A', background: '#FFFBEB', borderRadius: 10,
          padding: '10px 14px', marginBottom: 14, fontSize: 13, color: '#92400E',
        }}>
          <strong>Envío en simulación.</strong> El botón «Enviar al operador» arma la
          petición y la registra, pero no sale a la red. Enviar de verdad crea la
          planilla en el operador y su enlace de pago mueve dinero.
          {!operador?.credenciales && ' Además faltan credenciales configuradas.'}
        </div>
      )}

      {isLoading ? (
        <div style={{ display: 'grid', gap: 8 }}>
          {[1, 2, 3].map(i => <SkeletonCard key={i} height={64} />)}
        </div>
      ) : visibles.length === 0 ? (
        <div style={{
          padding: 36, textAlign: 'center', color: C.text2, fontSize: 14,
          border: `1px dashed ${C.border}`, borderRadius: 10,
        }}>
          {personas.length === 0
            ? (estadoFactura === 'pagado'
              ? `No hay facturas pagadas de ${periodo}. Entran a liquidar cuando el cliente ya pagó.`
              : estadoFactura === 'todos'
                ? `No hay facturas de ${periodo}.`
                : `No hay facturas en ese estado para ${periodo}.`)
            : 'Ninguna persona coincide con el filtro.'}
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {seleccionadas.length > 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
              border: `1px solid ${C.border}`, borderRadius: 10, padding: '10px 12px',
              background: '#EFF6FF',
            }}>
              <strong style={{ fontSize: 13 }}>
                {seleccionadas.length} {seleccionadas.length === 1 ? 'persona' : 'personas'}
                {' '}de <span style={{ color: '#6D28D9' }}>{empresaDeLaSeleccion}</span> en un mismo archivo
              </strong>
              <span style={{ fontSize: 12, color: C.text2 }}>
                {pesos(seleccionadas.reduce((t, x) => t + (x.total || 0), 0))}
              </span>
              <div style={{ flex: 1 }} />
              <Btn size="sm" variant="secondary" onClick={() => setElegidas(new Set())}>
                Quitar selección
              </Btn>
              <Btn size="sm" variant="secondary" onClick={descargarConjunto}>
                Descargar plano conjunto
              </Btn>
              <Btn size="sm" disabled={enviarConjunto.isPending
                                       || seleccionadas.some(x => x.desactualizada)}
                   title={seleccionadas.some(x => x.desactualizada)
                     ? 'Hay planillas desfasadas en la selección: anula y vuelve a liquidar'
                     : undefined}
                   onClick={() => enviarConjunto.mutate()}>
                {enviarConjunto.isPending ? 'Enviando…' : 'Enviar las ' + seleccionadas.length}
              </Btn>
            </div>
          )}
          <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
              <thead>
                <tr>
                  <th style={{ ...thBase, width: 36 }} />
                  {COLUMNAS.map(([nombre, color]) => (
                    <th key={nombre} style={{
                      ...thBase, color,
                      textAlign: nombre === 'Total' ? 'right' : 'left',
                    }}>{nombre}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {enPagina.map((p, i) => {
                  const elegida = elegidas.has(p.planilla_id);
                  const fondo = elegida ? '#EFF6FF' : (i % 2 ? '#F8FAFC' : C.surface);
                  const sub = SUBTIPOS[String(p.subtipo)] ;
                  return (
                    <React.Fragment key={p.id}>
                      <tr style={{ background: fondo }}
                          onMouseEnter={e => { if (!elegida) e.currentTarget.style.background = '#EEF2F7'; }}
                          onMouseLeave={e => { e.currentTarget.style.background = fondo; }}>
                        <td style={td}>
                          {p.planilla_id && p.se_envia !== false && (
                            <input type="checkbox" style={{ width: 15, height: 15 }}
                                   checked={elegida}
                                   onChange={() => alternar(p)}
                                   disabled={!!empresaDeLaSeleccion && empresaDeLaSeleccion !== p.empresa}
                                   title={empresaDeLaSeleccion && empresaDeLaSeleccion !== p.empresa
                                     ? `Un archivo plano lleva una sola empresa: ya hay ${empresaDeLaSeleccion} en la selección`
                                     : 'Incluir en un archivo con varias personas'} />
                          )}
                        </td>
                        <td style={{ ...td, fontWeight: 700 }}>{p.nombre}</td>
                        <td style={{ ...td, color: '#0369A1', fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
                          {p.tipo_doc} {p.doc}
                        </td>
                        <td style={{ ...td, color: '#6D28D9', fontWeight: 700 }}>{p.empresa || '—'}</td>
                        <td style={{ ...td, color: '#7C3AED', fontWeight: 600 }}>{p.cliente || '—'}</td>
                        <td style={{ ...td, color: '#C2410C', fontWeight: 600 }}>
                          {p.subtipo != null && p.subtipo !== ''
                            ? `${p.subtipo}${sub ? ` · ${sub}` : ''}` : '—'}
                        </td>
                        <td style={{ ...td, whiteSpace: 'normal' }}>
                          <Servicios lista={p.servicios} />
                        </td>
                        <td style={{
                          ...td, fontWeight: 700,
                          color: p.factura_estado === 'pendiente' ? '#B45309' : '#047857',
                        }}>
                          {p.factura_codigo || '—'}
                          {p.factura_estado ? ` · ${p.factura_estado}` : ''}
                        </td>
                        <td style={{
                          ...td, textAlign: 'right', fontWeight: 700,
                          fontVariantNumeric: 'tabular-nums', color: '#1D4ED8',
                        }}>
                          {p.planilla_id ? pesos(p.total) : '—'}
                        </td>
                        <td style={td}>
                          {p.planilla_id
                            ? <EstadoBadge estado={p.estado} />
                            : <span style={{ fontSize: 11, fontWeight: 800, color: '#B45309',
                                            letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                                Por liquidar
                              </span>}
                        </td>
                        <td style={{ ...td, whiteSpace: 'normal' }}>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                            {p.planilla_id ? (
                              <>
                                <select
                                  style={{ ...inp, padding: '6px 8px', fontSize: 12, width: 72 }}
                                  title="Documento con el que se identifica a la persona en el archivo"
                                  value={docDescarga[p.planilla_id] || p.tipo_doc_sugerido || p.tipo_doc || 'CC'}
                                  onChange={e => setDocDescarga(d => ({ ...d, [p.planilla_id]: e.target.value }))}
                                >
                                  {TIPOS_DOC.map(t => <option key={t} value={t}>{t}</option>)}
                                </select>
                                <Btn size="sm" variant="secondary" onClick={() => descargar(p)} title="Descargar el archivo plano">Plano</Btn>
                                {p.se_envia === false && (
                                  <span style={{ fontSize: 12, color: '#92400E' }}>Se tramita por fuera</span>
                                )}
                                {p.se_envia !== false && p.estado !== 'numerada' && p.estado !== 'pagada' && (
                                  <Btn size="sm" disabled={enviar.isPending || p.desactualizada}
                                       title={p.desactualizada
                                         ? 'Los datos cambiaron despues de liquidar: anula y vuelve a liquidar'
                                         : 'Enviar esta planilla al operador'}
                                       onClick={() => enviar.mutate(p)}>
                                    {p.codigo_planilla ? 'Reenviar' : 'Enviar'}
                                  </Btn>
                                )}
                                {p.codigo_planilla && !p.numero_planilla && p.estado !== 'pagada' && p.estado !== 'anulada' && (
                                  <Btn size="sm" disabled={corregir.isPending}
                                       title="Pedirle al operador que corrija los errores que él mismo marcó"
                                       onClick={() => corregir.mutate(p.planilla_id)}>
                                    {corregir.isPending ? 'Corrigiendo…' : 'Corregir'}
                                  </Btn>
                                )}
                                {(p.codigo_planilla || p.numero_planilla) && p.estado !== 'anulada' && p.estado !== 'pagada' && (
                                  <Btn size="sm" variant="success"
                                       title="Pedir el enlace al operador y abrir el pago"
                                       onClick={() => pagar(p)}>Pagar</Btn>
                                )}
                                {p.numero_planilla && (
                                  <Btn size="sm" variant="secondary" onClick={() => descargarComprobante(p)}>Comprobante</Btn>
                                )}
                                {p.estado !== 'pagada' && (
                                  <Btn size="sm" variant="danger" onClick={() => setPorAnular(p)}>Anular</Btn>
                                )}
                              </>
                            ) : (
                              <>
                                <Btn size="sm" variant="secondary"
                                     disabled={previsualizar.isPending || p.factura_estado !== 'pagado'}
                                     title={p.factura_estado !== 'pagado'
                                       ? 'Se liquida cuando la factura está pagada: el cliente ya entregó el dinero'
                                       : undefined}
                                     onClick={() => previsualizar.mutate(p)}>Previsualizar</Btn>
                                <Btn size="sm" disabled={liquidar.isPending || p.sin_afiliado || p.factura_estado !== 'pagado'}
                                     title={p.factura_estado !== 'pagado'
                                       ? 'Se liquida cuando la factura está pagada: el cliente ya entregó el dinero'
                                       : undefined}
                                     onClick={() => liquidar.mutate(p)}>Liquidar</Btn>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                      {(p.sin_afiliado || p.desactualizada) && (
                        <tr>
                          <td colSpan={11} style={{
                            ...td, fontSize: 12,
                            color: p.sin_afiliado ? '#B91C1C' : '#92400E',
                            background: p.sin_afiliado ? '#FEF2F2' : '#FFFBEB',
                          }}>
                            {p.sin_afiliado
                              ? `Hay factura de ${p.factura_codigo} pero el afiliado ya no está en el sistema. No se puede liquidar.`
                              : 'Los datos cambiaron después de liquidar. Anula y vuelve a liquidar antes de enviar.'}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          {totalPaginas > 1 && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              gap: 12, flexWrap: 'wrap', marginTop: 6, padding: '10px 4px',
            }}>
              <span style={{ fontSize: 13, color: C.text2 }}>
                <strong style={{ color: '#1D4ED8' }}>{POR_PAGINA}</strong> por página
                {' · '}
                {(paginaActual - 1) * POR_PAGINA + 1}
                –
                {Math.min(paginaActual * POR_PAGINA, visibles.length)}
                {' de '}
                <strong style={{ color: C.text }}>{visibles.length}</strong>
              </span>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <Btn size="sm" variant="secondary" disabled={paginaActual <= 1}
                     onClick={() => irAPagina(paginaActual - 1)}>Anterior</Btn>
                {Array.from({ length: totalPaginas }, (_, i) => i + 1)
                  .filter(n => n === 1 || n === totalPaginas || Math.abs(n - paginaActual) <= 1)
                  .map(n => (
                    <button key={n} type="button" onClick={() => irAPagina(n)}
                            style={{
                              minWidth: 32, height: 32, borderRadius: 8, cursor: 'pointer',
                              fontWeight: 700, fontSize: 13,
                              border: `1px solid ${n === paginaActual ? '#1D4ED8' : C.border}`,
                              background: n === paginaActual ? '#1D4ED8' : C.surface,
                              color: n === paginaActual ? '#fff' : C.text,
                            }}>{n}</button>
                  ))}
                <Btn size="sm" variant="secondary" disabled={paginaActual >= totalPaginas}
                     onClick={() => irAPagina(paginaActual + 1)}>Siguiente</Btn>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Lo que respondió el operador ──────────────────────────────────── */}
      <Modal open={!!respuesta} onClose={() => setRespuesta(null)}
             title="Respuesta del operador" width={700}>
        {respuesta && (
          <>
            <div style={{ fontSize: 13, color: C.text2, marginBottom: 14 }}>
              {respuesta.codigo_planilla
                ? <>Planilla <strong style={{ fontFamily: 'monospace', color: C.text }}>
                    {respuesta.codigo_planilla}</strong> recibida.{' '}
                   {respuesta.numero_planilla
                     ? <>Quedó numerada como <strong>{respuesta.numero_planilla}</strong>.</>
                     : 'El operador no la numera mientras tenga errores sin corregir.'}</>
                : 'No se envió nada: el cliente está en modo simulación.'}
            </div>

            {(respuesta.errores || []).map((e, i) => (
              <div key={i} style={{
                border: '1px solid #FECACA', background: '#FEF2F2', borderRadius: 8,
                padding: '10px 12px', marginBottom: 8, fontSize: 13,
              }}>
                <div style={{ fontWeight: 700, color: '#B91C1C', marginBottom: 3 }}>
                  Error {e.tipo === 'empresa' ? 'de la empresa' : 'del cotizante'}
                  {e.campos && <span style={{ fontWeight: 400, color: C.text2 }}>
                    {' '}· línea {e.linea}, posiciones {e.campos}</span>}
                  {e.autocorrige && <span style={{ color: '#059669', fontWeight: 400 }}>
                    {' '}· el operador puede corregirlo</span>}
                </div>
                <div style={{ color: C.text }}>{e.descripcion}</div>
              </div>
            ))}

            {(respuesta.advertencias || []).map((a, i) => (
              <div key={i} style={{
                border: '1px solid #FDE68A', background: '#FFFBEB', borderRadius: 8,
                padding: '10px 12px', marginBottom: 8, fontSize: 13, color: '#92400E',
              }}>
                {a.descripcion}
              </div>
            ))}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <Btn variant="secondary" onClick={() => setRespuesta(null)}>Cerrar</Btn>
              {(respuesta.errores || []).some(e => e.autocorrige) && respuesta.planilla_id && (
                <Btn disabled={corregir.isPending}
                     onClick={() => corregir.mutate(respuesta.planilla_id)}>
                  {corregir.isPending ? 'Corrigiendo…' : 'Que el operador corrija'}
                </Btn>
              )}
            </div>
          </>
        )}
      </Modal>

      {/* ── Previsualización de una persona ───────────────────────────────── */}
      <Modal
        open={!!previa}
        onClose={() => setPrevia(null)}
        title={previa ? `Planilla de ${previa.datos.afiliado.nombre}` : ''}
        width={640}
      >
        {previa && (
          <>
            <div style={{ fontSize: 12, color: C.text2, marginBottom: 14 }}>
              {previa.datos.afiliado.tipo_doc} {previa.datos.afiliado.doc} ·
              aportante {previa.datos.aportante.razon_social} ({previa.datos.aportante.nit}) ·
              pensión {previa.datos.periodo_pension} · salud {previa.datos.periodo_salud}
            </div>

            {previa.datos.detalle && (
              <div style={{
                display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 14,
                padding: '10px 14px', background: '#F9FAFB', borderRadius: 8,
                fontSize: 13,
              }}>
                <span><strong>{previa.datos.detalle.dias}</strong> días</span>
                <span>IBC <strong>{pesos(previa.datos.detalle.ibc)}</strong></span>
                <span>Tipo cotizante <strong>{previa.datos.detalle.tipo_cotizante}</strong></span>
                {(previa.datos.detalle.servicios || []).map(s => (
                  <span key={s} style={{
                    fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
                    background: '#EFF6FF', color: '#2563EB',
                  }}>{s}</span>
                ))}
                {previa.datos.detalle.exonerado && (
                  <span style={{ color: '#7C3AED' }}>exonerado 114-1</span>
                )}
                {previa.datos.detalle.novedades.map(n => (
                  <span key={n} style={{ color: '#D97706' }}>{n}</span>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Total etiqueta="Pensión" valor={previa.datos.totales.pension} />
              <Total etiqueta="Salud" valor={previa.datos.totales.salud} />
              <Total etiqueta="Riesgos" valor={previa.datos.totales.arl} />
              <Total etiqueta="Caja" valor={previa.datos.totales.ccf} />
              <Total etiqueta="SENA" valor={previa.datos.totales.sena} />
              <Total etiqueta="ICBF" valor={previa.datos.totales.icbf} />
              <Total etiqueta="FSP" valor={previa.datos.totales.fsp} />
              <Total etiqueta="Total" valor={previa.datos.totales.general} destacado />
            </div>

            {/* Los avisos deciden si la planilla sirve, asi que se quedan a la
                vista junto al boton y no solo en un toast que se desvanece. */}
            {!!previa.datos.avisos?.length && (
              <div style={{ marginTop: 16, padding: 12, borderRadius: 8,
                            background: '#FEF3C7', border: '1px solid #FCD34D' }}>
                <strong style={{ color: '#92400E', fontSize: 13 }}>
                  Revisa antes de liquidar
                </strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 18, color: '#78350F', fontSize: 13 }}>
                  {previa.datos.avisos.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
              <Btn variant="secondary" onClick={() => setPrevia(null)}>Cerrar</Btn>
              <Btn disabled={liquidar.isPending}
                   onClick={() => liquidar.mutate(previa.persona)}>
                {liquidar.isPending ? 'Liquidando…' : 'Liquidar'}
              </Btn>
            </div>
          </>
        )}
      </Modal>

      <ConfirmModal
        open={!!porAnular}
        title="Anular planilla"
        message={porAnular
          ? `¿Anular la planilla de ${porAnular.nombre} del período ${periodo}? Queda registrada como anulada y podrás volver a liquidar.`
          : ''}
        confirmLabel="Anular"
        onConfirm={() => anular.mutate(porAnular.planilla_id)}
        onCancel={() => setPorAnular(null)}
      />
    </div>
  );
}
