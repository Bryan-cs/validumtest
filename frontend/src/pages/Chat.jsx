// frontend/src/pages/Chat.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';
import { C } from '../components/UI';

const WS_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000')
  .replace(/^https?/, (m) => (m === 'https' ? 'wss' : 'ws'));

function fmtHora(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
}

function fmtFecha(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
}

let _audioCtx = null;
function _getAudioCtx() {
  if (!_audioCtx || _audioCtx.state === 'closed') {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return _audioCtx;
}

function _beep() {
  try {
    const ctx = _getAudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(1000, ctx.currentTime);
    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.2);
  } catch (_) {}
}

export default function Chat() {
  const { user, token } = useAuthStore();
  const isAdmin = user?.rol === 'admin';
  const qc = useQueryClient();

  const [tab, setTab] = useState('grupal');
  const [clienteActivo, setClienteActivo] = useState(null);
  const [mensajes, setMensajes] = useState([]);
  const [texto, setTexto] = useState('');
  const wsRef = useRef(null);
  const bottomRef = useRef(null);
  const userRef = useRef(user);

  useEffect(() => { userRef.current = user; }, [user]);

  // Lista de clientes con conversaciones (solo admin)
  const { data: clientes = [] } = useQuery({
    queryKey: ['chat-clientes'],
    queryFn: () => api.get('/chat/clientes-activos').then(r => r.data),
    enabled: isAdmin,
    refetchInterval: 30_000,
  });

  const cargarHistorial = useCallback(async (tipo, ref) => {
    const params = { tipo };
    if (tipo === 'privado' && ref) params.cliente_ref = ref;
    try {
      const res = await api.get('/chat/mensajes', { params });
      setMensajes(res.data);
    } catch (_) {}
  }, []);

  const conectarWS = useCallback((tipo, ref) => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    let url = `${WS_BASE}/ws/chat?token=${token}&tipo=${tipo}`;
    if (tipo === 'privado' && ref) url += `&cliente_ref=${encodeURIComponent(ref)}`;
    const ws = new WebSocket(url);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        setMensajes(prev => [...prev, msg]);
        if (msg.remitente !== userRef.current?.username) _beep();
      } catch (_) {}
    };
    wsRef.current = ws;
    return ws;
  }, [token]);

  // Reconectar al cambiar de canal
  useEffect(() => {
    let ws;
    if (tab === 'grupal') {
      cargarHistorial('grupal', null);
      ws = conectarWS('grupal', null);
    } else if (tab === 'privado' && clienteActivo) {
      cargarHistorial('privado', clienteActivo);
      ws = conectarWS('privado', clienteActivo);
      api.put(`/chat/mensajes/${clienteActivo}/leer`)
        .then(() => qc.invalidateQueries({ queryKey: ['chat-clientes'] }))
        .catch(() => {});
    }
    return () => { if (ws) { ws.close(); wsRef.current = null; } };
  }, [tab, clienteActivo, cargarHistorial, conectarWS, qc]);

  // Auto-scroll
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [mensajes]);

  const enviar = () => {
    const t = texto.trim();
    if (!t || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ texto: t }));
    setTexto('');
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); }
  };

  // Agrupar mensajes por fecha
  const conSeparadores = mensajes.reduce((acc, m, i) => {
    const fecha = m.creado ? new Date(m.creado).toDateString() : '';
    const prevFecha = i > 0 && mensajes[i - 1].creado
      ? new Date(mensajes[i - 1].creado).toDateString() : '';
    if (fecha !== prevFecha) acc.push({ _sep: true, fecha: fmtFecha(m.creado) });
    acc.push(m);
    return acc;
  }, []);

  const inputVisible = tab === 'grupal' || (tab === 'privado' && clienteActivo);

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 48px)', background: C.bg }}>

      {/* Panel izquierdo — solo admin */}
      {isAdmin && (
        <div style={{ width: 240, flexShrink: 0, background: C.surface, borderRight: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column' }}>
          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: `1px solid ${C.border}` }}>
            {[['grupal', '👥 Interno'], ['privado', '💬 Clientes']].map(([id, label]) => (
              <button key={id}
                onClick={() => { setTab(id); if (id === 'grupal') setClienteActivo(null); }}
                style={{
                  flex: 1, padding: '11px 6px', border: 'none', fontSize: 12, fontWeight: 600,
                  cursor: 'pointer', background: 'transparent',
                  color: tab === id ? C.primary : C.text2,
                  borderBottom: tab === id ? `2px solid ${C.primary}` : '2px solid transparent',
                }}>
                {label}
              </button>
            ))}
          </div>

          {/* Tab: Interno */}
          {tab === 'grupal' && (
            <div style={{ padding: '14px 16px' }}>
              <p style={{ color: C.text2, fontSize: 12, margin: 0 }}>Canal grupal — admin y empleados.</p>
            </div>
          )}

          {/* Tab: Clientes */}
          {tab === 'privado' && (
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {clientes.length === 0 && (
                <p style={{ padding: 16, color: C.text2, fontSize: 12, margin: 0 }}>Sin conversaciones aún.</p>
              )}
              {clientes.map(c => (
                <div key={c.cliente_ref}
                  onClick={() => setClienteActivo(c.cliente_ref)}
                  style={{
                    padding: '10px 14px', cursor: 'pointer', fontSize: 13,
                    background: clienteActivo === c.cliente_ref ? C.surface2 : 'transparent',
                    borderBottom: `1px solid ${C.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                  <span style={{ color: C.text, fontWeight: clienteActivo === c.cliente_ref ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.cliente_ref}
                  </span>
                  {c.no_leidos > 0 && (
                    <span style={{ background: C.primary, color: '#fff', borderRadius: 10, padding: '1px 7px', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>
                      {c.no_leidos}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Panel de chat */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header */}
        <div style={{ padding: '14px 20px', borderBottom: `1px solid ${C.border}`, background: C.surface, fontWeight: 700, fontSize: 14, color: C.text, flexShrink: 0 }}>
          {tab === 'grupal' ? '👥 Chat interno' : clienteActivo ? `💬 ${clienteActivo}` : 'Selecciona un cliente'}
        </div>

        {/* Mensajes */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {tab === 'privado' && !clienteActivo ? (
            <p style={{ color: C.text2, textAlign: 'center', marginTop: 60, fontSize: 13 }}>Selecciona un cliente de la lista</p>
          ) : conSeparadores.length === 0 ? (
            <p style={{ color: C.text2, textAlign: 'center', marginTop: 60, fontSize: 13 }}>Sin mensajes aún</p>
          ) : conSeparadores.map((item, i) => {
            if (item._sep) return (
              <div key={`sep-${i}`} style={{ textAlign: 'center', margin: '8px 0' }}>
                <span style={{ background: C.surface2, color: C.text2, borderRadius: 10, padding: '2px 12px', fontSize: 11 }}>{item.fecha}</span>
              </div>
            );
            const mio = item.remitente === user?.username;
            return (
              <div key={item.id} style={{ display: 'flex', flexDirection: 'column', alignItems: mio ? 'flex-end' : 'flex-start', marginBottom: 2 }}>
                {!mio && <span style={{ fontSize: 11, color: C.text2, marginBottom: 2, marginLeft: 2 }}>{item.remitente_nombre}</span>}
                <div style={{
                  maxWidth: '72%', padding: '8px 12px',
                  borderRadius: mio ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                  background: mio ? C.primary : C.surface2,
                  color: mio ? '#fff' : C.text, fontSize: 13, lineHeight: 1.45, wordBreak: 'break-word',
                }}>
                  {item.texto}
                </div>
                <span style={{ fontSize: 10, color: C.text2, marginTop: 2, marginLeft: 2, marginRight: 2 }}>{fmtHora(item.creado)}</span>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        {inputVisible && (
          <div style={{ padding: '12px 16px', borderTop: `1px solid ${C.border}`, background: C.surface, display: 'flex', gap: 8, flexShrink: 0 }}>
            <textarea
              value={texto}
              onChange={e => setTexto(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Escribe un mensaje… (Enter para enviar, Shift+Enter para nueva línea)"
              style={{ flex: 1, padding: '9px 12px', border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 13, color: C.text, background: C.bg, resize: 'none', outline: 'none', fontFamily: 'inherit' }}
            />
            <button onClick={enviar} style={{ background: C.primary, border: 'none', color: '#fff', borderRadius: 8, padding: '0 18px', cursor: 'pointer', fontWeight: 700, fontSize: 18 }}>➤</button>
          </div>
        )}
      </div>
    </div>
  );
}
