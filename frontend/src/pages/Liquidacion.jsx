import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Btn, ConfirmModal, ErrorMsg, SkeletonCard } from '../components/UI';

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

const ESTADO_STYLE = {
  borrador: { bg: '#F3F4F6', color: '#6B7280' },
  generada: { bg: '#EFF6FF', color: '#2563EB' },
  enviada:  { bg: '#FFFBEB', color: '#D97706' },
  numerada: { bg: '#F5F3FF', color: '#7C3AED' },
  pagada:   { bg: '#ECFDF5', color: '#059669' },
  anulada:  { bg: '#FEF2F2', color: '#DC2626' },
};

const pesos = (n) => '$' + (Number(n) || 0).toLocaleString('es-CO');

const inp = {
  padding: '9px 12px', borderRadius: 8, border: `1px solid ${C.border}`,
  background: C.surface, fontSize: 13, color: C.text, outline: 'none',
  fontFamily: 'inherit', boxSizing: 'border-box',
};
const lbl = {
  fontSize: 11, fontWeight: 700, color: C.text2, textTransform: 'uppercase',
  letterSpacing: '0.05em', marginBottom: 4, display: 'block',
};
const th = {
  textAlign: 'right', padding: '8px 10px', fontSize: 11, fontWeight: 700,
  color: C.text2, textTransform: 'uppercase', letterSpacing: '0.04em',
  borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap',
};
const td = {
  textAlign: 'right', padding: '7px 10px', fontSize: 13, color: C.text,
  borderBottom: `1px solid ${C.border}`, fontVariantNumeric: 'tabular-nums',
  whiteSpace: 'nowrap',
};

function EstadoBadge({ estado }) {
  const s = ESTADO_STYLE[estado] || ESTADO_STYLE.borrador;
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
  return (
    <div style={{
      padding: '10px 14px', borderRadius: 8,
      background: destacado ? '#EFF6FF' : C.surface,
      border: `1px solid ${destacado ? '#BFDBFE' : C.border}`, minWidth: 130,
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: C.text2,
                    textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {etiqueta}
      </div>
      <div style={{ fontSize: destacado ? 18 : 15, fontWeight: 700,
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

  const [aportanteId, setAportanteId] = useState('');
  const [anio, setAnio] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() + 1);
  const [previa, setPrevia] = useState(null);
  const [porAnular, setPorAnular] = useState(null);

  const { data: aportantes = [] } = useQuery({
    queryKey: ['aportantes'],
    queryFn: async () => (await api.get('/aportantes')).data,
  });

  const { data: planillas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['liquidaciones'],
    queryFn: async () => (await api.get('/liquidacion')).data,
  });

  const aportanteSel = useMemo(
    () => aportantes.find(a => String(a.id) === String(aportanteId)),
    [aportantes, aportanteId]);

  const previsualizar = useMutation({
    mutationFn: async () => (await api.post('/liquidacion/previsualizar', {
      aportante_id: Number(aportanteId), anio: Number(anio), mes: Number(mes),
    })).data,
    onSuccess: (d) => {
      setPrevia(d);
      if (d.avisos?.length) d.avisos.forEach(a => toast.warning(a));
    },
    onError: (e) => {
      setPrevia(null);
      toast.error(e?.response?.data?.detail || 'No se pudo calcular');
    },
  });

  const liquidar = useMutation({
    mutationFn: async () => (await api.post('/liquidacion', {
      aportante_id: Number(aportanteId), anio: Number(anio), mes: Number(mes),
    })).data,
    onSuccess: (d) => {
      toast.success(`Planilla liquidada: ${d.total_cotizantes} cotizantes, ${pesos(d.totales.general)}`);
      setPrevia(null);
      qc.invalidateQueries({ queryKey: ['liquidaciones'] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'No se pudo liquidar'),
  });

  const anular = useMutation({
    mutationFn: async (id) => (await api.post(`/liquidacion/${id}/anular`)).data,
    onSuccess: () => {
      toast.success('Planilla anulada');
      qc.invalidateQueries({ queryKey: ['liquidaciones'] });
      setPorAnular(null);
    },
    onError: (e) => {
      toast.error(e?.response?.data?.detail || 'No se pudo anular');
      setPorAnular(null);
    },
  });

  // El plano se pide con el token del cliente y se entrega como descarga; por
  // eso pasa por blob en vez de un enlace directo.
  const descargar = async (planilla) => {
    try {
      const r = await api.get(`/liquidacion/${planilla.id}/plano`, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([r.data], { type: 'text/plain' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `PILA_${planilla.cliente_ref}_${planilla.periodo_cotizacion}.txt`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('No se pudo descargar el archivo');
    }
  };

  if (isError) return <ErrorMsg message="Error al cargar las planillas" onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Liquidación de planillas"
        subtitle="Calcula los aportes del período y genera el archivo plano PILA"
      />

      {/* ── Selección del período ─────────────────────────────────────────── */}
      <div style={{
        border: `1px solid ${C.border}`, borderRadius: 10, padding: 16,
        background: C.surface, marginBottom: 18,
      }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <label style={lbl}>Aportante</label>
            <select style={{ ...inp, width: '100%' }} value={aportanteId}
                    onChange={e => { setAportanteId(e.target.value); setPrevia(null); }}>
              <option value="">Elige la empresa…</option>
              {aportantes.filter(a => a.activo).map(a => (
                <option key={a.id} value={a.id}>{a.razon_social} — {a.nit_completo}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={lbl}>Mes de cotización</label>
            <select style={inp} value={mes}
                    onChange={e => { setMes(e.target.value); setPrevia(null); }}>
              {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año</label>
            <input style={{ ...inp, width: 90 }} value={anio} inputMode="numeric"
                   onChange={e => { setAnio(e.target.value); setPrevia(null); }} />
          </div>
          <Btn variant="secondary" disabled={!aportanteId || previsualizar.isPending}
               onClick={() => previsualizar.mutate()}>
            {previsualizar.isPending ? 'Calculando…' : 'Previsualizar'}
          </Btn>
          <Btn disabled={!previa || liquidar.isPending} onClick={() => liquidar.mutate()}>
            {liquidar.isPending ? 'Liquidando…' : 'Liquidar'}
          </Btn>
        </div>

        {aportanteSel?.exonerado_parafiscales && (
          <div style={{ marginTop: 10, fontSize: 12, color: '#7C3AED' }}>
            Esta empresa está exonerada del artículo 114-1: los cotizantes por debajo de
            10 salarios mínimos no pagan SENA, ICBF ni la parte patronal de salud.
          </div>
        )}
      </div>

      {/* ── Previsualización ──────────────────────────────────────────────── */}
      {previa && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
            <Total etiqueta="Pensión" valor={previa.totales.pension} />
            <Total etiqueta="Salud" valor={previa.totales.salud} />
            <Total etiqueta="Riesgos" valor={previa.totales.arl} />
            <Total etiqueta="Caja" valor={previa.totales.ccf} />
            <Total etiqueta="SENA" valor={previa.totales.sena} />
            <Total etiqueta="ICBF" valor={previa.totales.icbf} />
            <Total etiqueta="FSP" valor={previa.totales.fsp} />
            <Total etiqueta="Total a pagar" valor={previa.totales.general} destacado />
          </div>

          <div style={{ overflowX: 'auto', border: `1px solid ${C.border}`, borderRadius: 10 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
              <thead>
                <tr>
                  <th style={{ ...th, textAlign: 'left' }}>Cotizante</th>
                  <th style={th}>Días</th>
                  <th style={th}>IBC</th>
                  <th style={th}>Pensión</th>
                  <th style={th}>Salud</th>
                  <th style={th}>Riesgos</th>
                  <th style={th}>Caja</th>
                  <th style={th}>FSP</th>
                  <th style={th}>Total</th>
                </tr>
              </thead>
              <tbody>
                {previa.detalles.map(d => (
                  <tr key={d.doc}>
                    <td style={{ ...td, textAlign: 'left' }}>
                      <div style={{ fontWeight: 600 }}>{d.nombre}</div>
                      <div style={{ fontSize: 11, color: C.text2, fontFamily: 'monospace' }}>
                        {d.tipo_doc} {d.doc}
                        {d.exonerado && <span style={{ color: '#7C3AED' }}> · exonerado</span>}
                        {d.novedades.map(n => (
                          <span key={n} style={{ color: '#D97706' }}> · {n}</span>
                        ))}
                      </div>
                    </td>
                    <td style={td}>{d.dias}</td>
                    <td style={td}>{pesos(d.ibc)}</td>
                    <td style={td}>{pesos(d.cot_pension)}</td>
                    <td style={td}>{pesos(d.cot_salud)}</td>
                    <td style={td}>{pesos(d.cot_arl)}</td>
                    <td style={td}>{pesos(d.valor_ccf)}</td>
                    <td style={td}>{pesos(d.fsp)}</td>
                    <td style={{ ...td, fontWeight: 700 }}>{pesos(d.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: 12, color: C.text2, marginTop: 8 }}>
            Período de cotización {previa.periodo_cotizacion} · se paga en {previa.periodo_pago}.
            Todavía no se ha guardado nada.
          </div>
        </div>
      )}

      {/* ── Planillas liquidadas ──────────────────────────────────────────── */}
      <h2 style={{ fontSize: 14, fontWeight: 700, color: C.text, margin: '0 0 10px' }}>
        Planillas liquidadas
      </h2>

      {isLoading ? (
        <SkeletonCard height={80} />
      ) : planillas.length === 0 ? (
        <div style={{
          padding: 30, textAlign: 'center', color: C.text2, fontSize: 14,
          border: `1px dashed ${C.border}`, borderRadius: 10,
        }}>
          Todavía no hay planillas liquidadas.
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {planillas.map(p => (
            <div key={p.id} style={{
              border: `1px solid ${C.border}`, borderRadius: 10, padding: 12,
              background: C.surface, display: 'flex', alignItems: 'center',
              gap: 12, flexWrap: 'wrap',
            }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{p.cliente_ref}</div>
                <div style={{ fontSize: 12, color: C.text2 }}>
                  Tipo {p.tipo_planilla} · cotización {p.periodo_cotizacion} ·
                  pago {p.periodo_pago} · {p.total_cotizantes} cotizantes
                  {p.numero_planilla && ` · N.º ${p.numero_planilla}`}
                </div>
              </div>
              <div style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                {pesos(p.total_general)}
              </div>
              <EstadoBadge estado={p.estado} />
              <div style={{ display: 'flex', gap: 6 }}>
                <Btn size="sm" variant="secondary" onClick={() => descargar(p)}>
                  Descargar plano
                </Btn>
                {p.estado !== 'anulada' && p.estado !== 'pagada' && (
                  <Btn size="sm" variant="danger" onClick={() => setPorAnular(p)}>
                    Anular
                  </Btn>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmModal
        open={!!porAnular}
        title="Anular planilla"
        message={porAnular
          ? `¿Anular la planilla de ${porAnular.cliente_ref} del período ${porAnular.periodo_cotizacion}? Queda registrada como anulada y podrás volver a liquidar ese período.`
          : ''}
        confirmLabel="Anular"
        onConfirm={() => anular.mutate(porAnular.id)}
        onCancel={() => setPorAnular(null)}
      />
    </div>
  );
}
