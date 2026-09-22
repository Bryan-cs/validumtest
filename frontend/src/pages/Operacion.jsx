import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { C, PageHeader, Btn } from '../components/UI';
import { campo, celda } from '../estilos';

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

const TABS = [
  ['cierre', 'Cierre'],
  ['rechazos', 'Rechazos'],
  ['novedades', 'Novedades'],
  ['conciliacion', 'Pagos'],
  ['diferencias', 'Ficha vs consulta'],
];

const NIVEL = {
  rojo: { bg: '#FEF2F2', color: '#DC2626', label: 'Rojo' },
  amarillo: { bg: '#FFFBEB', color: '#D97706', label: 'Amarillo' },
  listo: { bg: '#ECFDF5', color: '#059669', label: 'Listo' },
};

const CRUCE = {
  cliente_sin_pila: 'El cliente pagó y la PILA sigue abierta',
  pila_sin_cliente: 'La PILA está pagada y la factura sigue pendiente',
  al_dia: 'Cliente y PILA al día',
  pendiente: 'Todavía no cierran los dos',
};

const inp = campo(C);
const td = celda(C);
const th = { ...td, fontSize: 11, fontWeight: 800, textTransform: 'uppercase', background: '#F8FAFC' };

export default function Operacion() {
  const hoy = new Date();
  const [anio, setAnio] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() + 1);
  const [tab, setTab] = useState('cierre');
  const [porqueId, setPorqueId] = useState(null);

  const params = { anio, mes };
  const cierre = useQuery({
    queryKey: ['op-cierre', anio, mes],
    queryFn: () => api.get('/operacion/cierre', { params }).then(r => r.data),
    enabled: tab === 'cierre',
  });
  const rechazos = useQuery({
    queryKey: ['op-rechazos', anio, mes],
    queryFn: () => api.get('/operacion/rechazos', { params }).then(r => r.data),
    enabled: tab === 'rechazos',
  });
  const novedades = useQuery({
    queryKey: ['op-novedades', anio, mes],
    queryFn: () => api.get('/operacion/novedades', { params }).then(r => r.data),
    enabled: tab === 'novedades',
  });
  const pagos = useQuery({
    queryKey: ['op-pagos', anio, mes],
    queryFn: () => api.get('/operacion/conciliacion', { params }).then(r => r.data),
    enabled: tab === 'conciliacion',
  });
  const difs = useQuery({
    queryKey: ['op-difs'],
    queryFn: () => api.get('/operacion/diferencias').then(r => r.data),
    enabled: tab === 'diferencias',
  });
  const porque = useQuery({
    queryKey: ['op-porque', porqueId],
    queryFn: () => api.get(`/operacion/porque/${porqueId}`).then(r => r.data),
    enabled: !!porqueId,
  });

  return (
    <div>
      <PageHeader
        title="Cierre del mes"
        subtitle="Qué falta por liquidar, qué devolvió el operador y qué no cuadra con el pago."
      />
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={mes} onChange={e => setMes(Number(e.target.value))} style={inp}>
          {MESES.map((nombre, i) => <option key={nombre} value={i + 1}>{nombre}</option>)}
        </select>
        <input type="number" value={anio} onChange={e => setAnio(Number(e.target.value))}
          style={{ ...inp, width: 100 }} />
        {TABS.map(([id, label]) => (
          <Btn key={id} size="sm" variant={tab === id ? 'primary' : 'secondary'}
            onClick={() => setTab(id)}>{label}</Btn>
        ))}
      </div>

      {tab === 'cierre' && <TablaCierre data={cierre.data} cargando={cierre.isLoading} error={cierre.error} />}
      {tab === 'rechazos' && <TablaRechazos data={rechazos.data} cargando={rechazos.isLoading} error={rechazos.error} onPorque={setPorqueId} />}
      {tab === 'novedades' && <TablaNovedades data={novedades.data} cargando={novedades.isLoading} error={novedades.error} />}
      {tab === 'conciliacion' && <TablaPagos data={pagos.data} cargando={pagos.isLoading} error={pagos.error} onPorque={setPorqueId} />}
      {tab === 'diferencias' && <TablaDifs data={difs.data} cargando={difs.isLoading} error={difs.error} />}

      {porqueId && (
        <div style={{ marginTop: 16, padding: 14, border: `1px solid ${C.border}`, borderRadius: 8, background: C.surface }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>
            Por qué salió el monto {porque.data ? `· ${porque.data.nombre}` : ''}
          </div>
          {porque.isLoading && <div style={{ color: C.text2 }}>Leyendo la línea congelada…</div>}
          {(porque.data?.notas || []).map(n => (
            <div key={n} style={{ fontSize: 13, padding: '4px 0' }}>{n}</div>
          ))}
          <Btn size="sm" variant="secondary" onClick={() => setPorqueId(null)}>Cerrar</Btn>
        </div>
      )}
    </div>
  );
}

function Aviso({ error }) {
  if (!error) return null;
  const det = error.response?.data?.detail;
  return <div style={{ color: C.red, marginBottom: 10 }}>{typeof det === 'string' ? det : 'No se pudo cargar'}</div>;
}

function Vacio({ texto, cargando }) {
  if (cargando) return <div style={{ color: C.text2 }}>Cargando…</div>;
  return <div style={{ color: C.text2, fontSize: 13 }}>{texto}</div>;
}

function Chip({ nivel }) {
  const s = NIVEL[nivel] || NIVEL.amarillo;
  return <span style={{ background: s.bg, color: s.color, borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 700 }}>{s.label}</span>;
}

function TablaCierre({ data, cargando, error }) {
  const filas = data?.filas || [];
  return (
    <div>
      <Aviso error={error} />
      {data && (
        <div style={{ fontSize: 13, marginBottom: 10, color: C.text2 }}>
          Sin planilla: {filas.length}. Rojo {data.cuentas.rojo} · amarillo {data.cuentas.amarillo} · listos {data.cuentas.listo}.
          El rojo impide el número. El amarillo no.
        </div>
      )}
      {!filas.length ? <Vacio cargando={cargando} texto="No hay facturas pagadas de este mes sin planilla." /> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['', 'Persona', 'Empresa', 'Qué hacer'].map(h => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {filas.map(f => (
              <tr key={f.doc + f.factura}>
                <td style={td}><Chip nivel={f.nivel} /></td>
                <td style={td}><strong>{f.nombre}</strong><div style={{ color: C.text2, fontSize: 12 }}>{f.doc}</div></td>
                <td style={td}>{f.empresa}</td>
                <td style={td}>{f.accion}{f.avisos?.[0] ? <div style={{ color: C.text2, fontSize: 12 }}>{f.avisos[0]}</div> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TablaRechazos({ data, cargando, error, onPorque }) {
  const grupos = data?.grupos || [];
  return (
    <div>
      <Aviso error={error} />
      {!grupos.length ? <Vacio cargando={cargando} texto="Este mes no hay respuestas del operador guardadas." /> : grupos.map(g => (
        <div key={g.descripcion} style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: 12, marginBottom: 10 }}>
          <Chip nivel={g.nivel} />
          <div style={{ fontWeight: 700, margin: '8px 0 4px' }}>{g.descripcion}</div>
          <div style={{ fontSize: 13, color: C.text2, marginBottom: 8 }}>{g.accion}</div>
          {g.planillas.map(p => (
            <div key={p.id} style={{ fontSize: 13, display: 'flex', gap: 8, alignItems: 'center' }}>
              <span>{p.nombre} · {p.doc} · {p.estado}</span>
              <Btn size="sm" variant="secondary" onClick={() => onPorque(p.id)}>Por qué el monto</Btn>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function TablaNovedades({ data, cargando, error }) {
  const filas = data?.filas || [];
  return (
    <div>
      <Aviso error={error} />
      {!filas.length ? <Vacio cargando={cargando} texto="Este mes no hay ingresos, retiros ni cambios de sueldo." /> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['Tipo', 'Persona', 'Detalle', 'Días'].map(h => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={f.tipo + f.doc + i}>
                <td style={td}>{f.marca}</td>
                <td style={td}><strong>{f.nombre}</strong><div style={{ color: C.text2, fontSize: 12 }}>{f.empresa}</div></td>
                <td style={td}>{f.detalle}</td>
                <td style={td}>{f.dias ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TablaPagos({ data, cargando, error, onPorque }) {
  const filas = data?.filas || [];
  return (
    <div>
      <Aviso error={error} />
      {data && (
        <div style={{ fontSize: 13, marginBottom: 10, color: C.text2 }}>
          Cliente pagó y PILA abierta: {data.cuentas.cliente_sin_pila}. PILA pagada y factura pendiente: {data.cuentas.pila_sin_cliente}.
        </div>
      )}
      {!filas.length ? <Vacio cargando={cargando} texto="No hay facturas ni planillas en este mes." /> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['Persona', 'Factura', 'Planilla', 'Límite', ''].map(h => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {filas.map(f => (
              <tr key={f.doc + f.planilla_id}>
                <td style={td}><strong>{f.nombre}</strong><div style={{ fontSize: 12, color: C.text2 }}>{CRUCE[f.cruce]}</div></td>
                <td style={td}>{f.factura_estado}</td>
                <td style={td}>{f.planilla_estado}</td>
                <td style={td}>{f.fecha_limite || '—'}</td>
                <td style={td}>{f.planilla_id ? <Btn size="sm" variant="secondary" onClick={() => onPorque(f.planilla_id)}>Por qué</Btn> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TablaDifs({ data, cargando, error }) {
  const filas = data?.filas || [];
  return (
    <div>
      <Aviso error={error} />
      <div style={{ fontSize: 13, color: C.text2, marginBottom: 10 }}>
        La consulta no se copia a la ficha. Hay que aplicarla a mano en Afiliados.
      </div>
      {!filas.length ? <Vacio cargando={cargando} texto="No hay diferencias entre la última consulta y la ficha." /> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['Persona', 'Fuente', 'En la ficha', 'En la consulta'].map(h => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {filas.map(f => (
              <tr key={f.doc + f.fuente}>
                <td style={td}><strong>{f.nombre}</strong><div style={{ color: C.text2, fontSize: 12 }}>{f.doc}</div></td>
                <td style={td}>{(f.fuente || '').toUpperCase()}</td>
                <td style={td}>{f.eps_ficha || '—'}</td>
                <td style={td}>{f.eps_consulta || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
