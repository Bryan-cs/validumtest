// frontend/src/components/WelcomeModal.jsx
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';

const MESES_ES = ['enero','febrero','marzo','abril','mayo','junio',
                  'julio','agosto','septiembre','octubre','noviembre','diciembre'];
const DIAS_ES  = ['domingo','lunes','martes','miércoles','jueves','viernes','sábado'];

function fmtFechaFormal(d) {
  return `${DIAS_ES[d.getDay()]}, ${d.getDate()} de ${MESES_ES[d.getMonth()]} de ${d.getFullYear()}`;
}

function fmtFechaCort(iso) {
  const d = new Date(iso + 'T00:00:00');
  return `${d.getDate()} ${MESES_ES[d.getMonth()].slice(0,3)}. ${d.getFullYear()}`;
}

function saludo(hora) {
  if (hora < 12) return 'Buenos días';
  if (hora < 19) return 'Buenas tardes';
  return 'Buenas noches';
}

function Pill({ count, color, label }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 700,
      background: `${color}18`, color, border: `1px solid ${color}35`,
    }}>
      {count} {label}
    </span>
  );
}

function TareaItem({ tarea, color, textoFecha }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,.06)',
    }}>
      <div style={{
        width: 6, height: 6, borderRadius: '50%', background: color,
        flexShrink: 0, marginTop: 6,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: '#e2e8f0', lineHeight: 1.4, wordBreak: 'break-word' }}>
          {tarea.titulo}
        </div>
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{textoFecha}</div>
      </div>
    </div>
  );
}

export default function WelcomeModal({ user, onClose }) {
  const navigate = useNavigate();
  const ref = useRef(null);
  const now = new Date();
  const hora = now.getHours();

  const [items, setItems]   = useState(null);  // null = cargando
  const [error, setError]   = useState(false);

  useEffect(() => {
    api.get('/tareas', { params: { limit: 200 } })
      .then(r => setItems(r.data.items ?? []))
      .catch(() => setError(true));
  }, []);

  useEffect(() => {
    const fn = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [onClose]);

  const hoy    = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const en7    = new Date(hoy); en7.setDate(hoy.getDate() + 7);

  const toDate = (iso) => iso ? new Date(iso + 'T00:00:00') : null;

  const vencidas  = (items || []).filter(t =>
    (t.estado === 'pendiente' || t.estado === 'en_proceso') &&
    toDate(t.fecha_limite) && toDate(t.fecha_limite) < hoy
  );
  const proximas  = (items || []).filter(t =>
    (t.estado === 'pendiente' || t.estado === 'en_proceso') &&
    toDate(t.fecha_limite) && toDate(t.fecha_limite) >= hoy && toDate(t.fecha_limite) <= en7
  );
  const porIniciar = (items || []).filter(t =>
    t.estado === 'pendiente' &&
    (!t.fecha_limite || toDate(t.fecha_limite) > en7)
  );

  const hayTareas = vencidas.length > 0 || proximas.length > 0 || porIniciar.length > 0;

  useEffect(() => {
    if (items !== null && !error && !hayTareas) onClose();
  }, [items, error, hayTareas, onClose]);
  const mostrarPorIniciar = vencidas.length === 0 && proximas.length === 0;

  const nombreCompleto = user?.nombre || user?.username || '';

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 4000,
        background: 'rgba(0,0,0,.62)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
      }}
      onClick={e => { if (!ref.current?.contains(e.target)) onClose(); }}
    >
      <div
        ref={ref}
        style={{
          background: '#1e1e2e', borderRadius: 16, maxWidth: 500, width: '100%',
          boxShadow: '0 32px 80px rgba(0,0,0,.5)', overflow: 'hidden',
        }}
      >
        {/* Barra superior degradado */}
        <div style={{ height: 4, background: 'linear-gradient(90deg, #4F46E5, #7C3AED)' }} />

        <div style={{ padding: '22px 24px 24px' }}>
          {/* Encabezado formal */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4, fontWeight: 500 }}>
              {fmtFechaFormal(now)}
            </div>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#f1f5f9', lineHeight: 1.4 }}>
              {saludo(hora)}, {nombreCompleto}.
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#94a3b8' }}>
              Ha iniciado sesión en el Sistema de Gestión BBC File.
            </p>
          </div>

          {/* Separador */}
          <div style={{ height: 1, background: 'rgba(255,255,255,.08)', marginBottom: 16 }} />

          {/* Sección tareas */}
          {items === null && !error && (
            <div style={{ padding: '12px 0', color: '#64748b', fontSize: 13 }}>Cargando tareas...</div>
          )}

          {error && (
            <div style={{ padding: '12px 0', color: '#94a3b8', fontSize: 13 }}>
              No se pudo cargar el resumen de tareas.
            </div>
          )}

          {items !== null && !error && hayTareas && (
            <div>
              {/* Pills resumen */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                {vencidas.length > 0 &&
                  <Pill count={vencidas.length} color="#ef4444" label={vencidas.length === 1 ? 'vencida' : 'vencidas'} />}
                {proximas.length > 0 &&
                  <Pill count={proximas.length} color="#f59e0b" label={proximas.length === 1 ? 'próxima' : 'próximas'} />}
                {mostrarPorIniciar && porIniciar.length > 0 &&
                  <Pill count={porIniciar.length} color="#6366f1" label="por iniciar" />}
              </div>

              {/* Lista vencidas */}
              {vencidas.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#ef4444', letterSpacing: '.1em', marginBottom: 4, textTransform: 'uppercase' }}>
                    Vencidas
                  </div>
                  {vencidas.slice(0, 4).map(t => (
                    <TareaItem key={t.id} tarea={t} color="#ef4444"
                      textoFecha={`Venció ${fmtFechaCort(t.fecha_limite)}`} />
                  ))}
                </div>
              )}

              {/* Lista próximas */}
              {proximas.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#f59e0b', letterSpacing: '.1em', marginBottom: 4, textTransform: 'uppercase' }}>
                    Próximas (7 días)
                  </div>
                  {proximas.slice(0, 3).map(t => (
                    <TareaItem key={t.id} tarea={t} color="#f59e0b"
                      textoFecha={`Vence ${fmtFechaCort(t.fecha_limite)}`} />
                  ))}
                </div>
              )}

              {/* Lista por iniciar (solo si no hay vencidas ni próximas) */}
              {mostrarPorIniciar && porIniciar.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#6366f1', letterSpacing: '.1em', marginBottom: 4, textTransform: 'uppercase' }}>
                    Por iniciar
                  </div>
                  {porIniciar.slice(0, 3).map(t => (
                    <TareaItem key={t.id} tarea={t} color="#6366f1"
                      textoFecha={t.fecha_limite ? `Límite ${fmtFechaCort(t.fecha_limite)}` : 'Sin fecha límite'} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Botones */}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 }}>
            {hayTareas && items !== null && (
              <button
                onClick={() => { onClose(); navigate('/tareas'); }}
                style={{
                  padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
                  background: '#4F46E5', color: '#fff', fontWeight: 700, fontSize: 13,
                }}
              >
                Ver mis tareas →
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,.15)',
                cursor: 'pointer', background: 'transparent', color: '#94a3b8', fontSize: 13,
              }}
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
