import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Btn, Modal, ConfirmModal, ErrorMsg, SkeletonCard } from '../components/UI';

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
const TIPOS_DOC = ['CC', 'CE', 'TI', 'PA', 'CD', 'SC', 'PE', 'PT'];

const inp = {
  padding: '9px 12px', borderRadius: 8, border: `1px solid ${C.border}`,
  background: C.surface, fontSize: 13, color: C.text, outline: 'none',
  fontFamily: 'inherit', boxSizing: 'border-box',
};
const lbl = {
  fontSize: 11, fontWeight: 700, color: C.text2, textTransform: 'uppercase',
  letterSpacing: '0.05em', marginBottom: 4, display: 'block',
};

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
  const [soloPendientes, setSoloPendientes] = useState(false);
  const [previa, setPrevia] = useState(null);      // { afiliado, resumen }
  const [porAnular, setPorAnular] = useState(null);
  const [docDescarga, setDocDescarga] = useState({});   // planilla_id → tipo de documento

  const periodo = `${anio}-${String(mes).padStart(2, '0')}`;

  const { data: operador } = useQuery({
    queryKey: ['operador-estado'],
    queryFn: async () => (await api.get('/liquidacion/operador/estado')).data,
    staleTime: 5 * 60 * 1000,
  });

  const { data: personas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['liquidacion-pendientes', anio, mes],
    queryFn: async () =>
      (await api.get(`/liquidacion/pendientes?anio=${anio}&mes=${mes}`)).data,
  });

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return personas.filter(p => {
      if (soloPendientes && p.planilla_id) return false;
      if (!q) return true;
      return [p.nombre, p.doc, p.cliente].some(v => (v || '').toLowerCase().includes(q));
    });
  }, [personas, busqueda, soloPendientes]);

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

  const enviar = useMutation({
    mutationFn: async (persona) =>
      (await api.post(`/liquidacion/${persona.planilla_id}/enviar`)).data,
    onSuccess: (d) => {
      if (d.simulado) {
        toast.info('Simulación: no se envió nada al operador. ' +
                   'Cambia SUAPORTE_MODO a "real" para enviar de verdad.');
      } else if (d.numero_planilla) {
        toast.success(`Planilla numerada: ${d.numero_planilla}`);
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
  const descargar = async (persona) => {
    // Si se eligió un documento distinto al de la persona, se manda al backend
    // para que cambie solo ese campo del registro.
    const tipo = docDescarga[persona.planilla_id] || persona.tipo_doc || 'CC';
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

  if (isError) return <ErrorMsg message="Error al cargar los afiliados" onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Liquidación de planillas"
        subtitle="Una planilla por persona y período, con su propio archivo plano"
      />

      <div style={{
        border: `1px solid ${C.border}`, borderRadius: 10, padding: 16,
        background: C.surface, marginBottom: 18,
        display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap',
      }}>
        <div>
          <label style={lbl}>Mes de cotización</label>
          <select style={inp} value={mes} onChange={e => { setMes(e.target.value); setPrevia(null); }}>
            {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </div>
        <div>
          <label style={lbl}>Año</label>
          <input style={{ ...inp, width: 90 }} value={anio} inputMode="numeric"
                 onChange={e => { setAnio(e.target.value); setPrevia(null); }} />
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label style={lbl}>Buscar</label>
          <input style={{ ...inp, width: '100%' }} value={busqueda}
                 placeholder="Nombre, documento o cliente…"
                 onChange={e => setBusqueda(e.target.value)} />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6,
                        fontSize: 13, color: C.text2, paddingBottom: 9 }}>
          <input type="checkbox" checked={soloPendientes}
                 onChange={e => setSoloPendientes(e.target.checked)} />
          Solo sin liquidar
        </label>
        <div style={{ fontSize: 12, color: C.text2, paddingBottom: 10 }}>
          {pendientes} de {personas.length} sin planilla en {periodo}
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
            ? 'No hay afiliados activos. Carga afiliados para poder liquidar.'
            : 'Ningún afiliado coincide con el filtro.'}
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {visibles.map(p => (
            <div key={p.id} style={{
              border: `1px solid ${C.border}`, borderRadius: 10, padding: 12,
              background: C.surface, display: 'flex', alignItems: 'center',
              gap: 12, flexWrap: 'wrap',
            }}>
              <div style={{ flex: 1, minWidth: 210 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{p.nombre}</div>
                <div style={{ fontSize: 12, color: C.text2, fontFamily: 'monospace' }}>
                  {p.tipo_doc} {p.doc}
                  {p.cliente && <span style={{ fontFamily: 'inherit' }}> · {p.cliente}</span>}
                </div>
              </div>

              {p.planilla_id ? (
                <>
                  <div style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                    {pesos(p.total)}
                  </div>
                  <EstadoBadge estado={p.estado} />
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <select
                      style={{ ...inp, padding: '6px 8px', fontSize: 12, width: 72 }}
                      title="Documento con el que se identifica a la persona en el archivo"
                      value={docDescarga[p.planilla_id] || p.tipo_doc || 'CC'}
                      onChange={e => setDocDescarga(d => ({ ...d, [p.planilla_id]: e.target.value }))}
                    >
                      {TIPOS_DOC.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <Btn size="sm" variant="secondary" onClick={() => descargar(p)}>
                      Descargar plano
                    </Btn>
                    {p.estado !== 'numerada' && p.estado !== 'pagada' && (
                      <Btn size="sm" disabled={enviar.isPending}
                           onClick={() => enviar.mutate(p)}>
                        Enviar al operador
                      </Btn>
                    )}
                    {p.estado !== 'pagada' && (
                      <Btn size="sm" variant="danger" onClick={() => setPorAnular(p)}>
                        Anular
                      </Btn>
                    )}
                  </div>
                </>
              ) : (
                <div style={{ display: 'flex', gap: 6 }}>
                  <Btn size="sm" variant="secondary"
                       disabled={previsualizar.isPending}
                       onClick={() => previsualizar.mutate(p)}>
                    Previsualizar
                  </Btn>
                  <Btn size="sm" disabled={liquidar.isPending}
                       onClick={() => liquidar.mutate(p)}>
                    Liquidar
                  </Btn>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

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
              cotización {previa.datos.periodo_cotizacion}, se paga en {previa.datos.periodo_pago}
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
