import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, Modal } from './UI';

/**
 * Consulta de afiliaciones a seguridad social desde el alta de afiliado.
 *
 * El backend elige la fuente: RUAF si hay fecha de expedición, ADRES si no o si
 * RUAF está caído. RUAF trae EPS, AFP, ARL, CCF y cesantías; ADRES solo salud.
 *
 * Dos pasos, porque ambas fuentes exigen código de seguridad:
 *   1. /consultas/iniciar  → captcha (o los datos, si hay caché vigente)
 *   2. /consultas/resolver → con el código que escribió el empleado
 *
 * El captcha lo resuelve una persona, siempre. No se elude.
 *
 * Regla de oro: esto NUNCA sobrescribe el formulario solo. Muestra lo que trajo
 * al lado de lo que ya está cargado y el empleado marca campo por campo.
 */

const ETIQUETAS = {
  nombre: 'Nombre',
  eps: 'EPS',
  afp: 'AFP (pensiones)',
  ccf: 'Caja de compensación',
  ciudad: 'Ciudad',
};

// Secciones de RUAF, en orden de lectura.
const SECCIONES = [
  ['salud', 'Salud'],
  ['pensiones', 'Pensiones'],
  ['riesgos_laborales', 'Riesgos laborales'],
  ['compensacion_familiar', 'Compensación familiar'],
  ['cesantias', 'Cesantías'],
];

// Campos planos de ADRES.
const CAMPOS_ADRES = [
  ['nombre', 'Nombre'], ['eps', 'EPS'], ['regimen', 'Régimen'],
  ['estado', 'Estado'], ['tipo_afiliado', 'Tipo de afiliado'],
  ['fecha_afiliacion', 'Fecha afiliación'], ['municipio', 'Municipio'],
];

const card = { border: `1px solid ${C.border}`, borderRadius: 8, padding: 12, marginBottom: 12 };

const col = (fila, clave) => {
  const k = Object.keys(fila).find(x => x.toLowerCase().includes(clave));
  return k ? fila[k] : '';
};

const vigente = estado => {
  const n = (estado || '').toLowerCase();
  return n.startsWith('activ') || n.includes('vigente');
};

export default function ConsultaSS({ open, onClose, tipoDoc, doc, fechaExpedicion,
                                     valoresActuales = {}, onAplicar }) {
  const [paso, setPaso]         = useState('cargando');   // cargando | captcha | resultado
  const [fuente, setFuente]     = useState(null);          // ruaf | adres
  const [sessionId, setSession] = useState(null);
  const [captchaImg, setImg]    = useState(null);
  const [sensible, setSensible] = useState(false);
  const [texto, setTexto]       = useState('');
  const [datos, setDatos]       = useState(null);
  const [sug, setSug]           = useState(null);
  const [marcados, setMarcados] = useState({});
  const [cargando, setCargando] = useState(false);
  const [error, setError]       = useState(null);
  const [desdeCache, setCache]  = useState(false);

  const mostrar = useCallback((d, s, f, cacheado) => {
    setDatos(d); setSug(s); setFuente(f); setCache(!!cacheado);
    // Por defecto se marcan solo los campos vacíos del formulario: rellenar un
    // hueco es seguro, pisar algo que alguien escribió no lo es.
    const previos = {};
    Object.keys(s?.campos || {}).forEach(k => {
      previos[k] = !String(valoresActuales[k] || '').trim();
    });
    setMarcados(previos);
    setPaso('resultado');
  }, [valoresActuales]);

  const iniciar = useCallback(async () => {
    setCargando(true); setError(null); setTexto('');
    try {
      const r = await api.post('/consultas/iniciar', {
        tipo_doc: tipoDoc || 'CC',
        doc,
        fecha_expedicion: fechaExpedicion || '',
      });
      if (r.data.cacheado) {
        mostrar(r.data.datos, r.data.sugerencia, r.data.fuente, true);
      } else {
        setSession(r.data.session_id);
        setImg(r.data.captcha);
        setFuente(r.data.fuente);
        setSensible(!!r.data.captcha_sensible_mayusculas);
        setPaso('captcha');
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo contactar la fuente oficial');
      setPaso('captcha');
    } finally {
      setCargando(false);
    }
  }, [tipoDoc, doc, fechaExpedicion, mostrar]);

  useEffect(() => {
    if (!open) return;
    setPaso('cargando'); setDatos(null); setSug(null); setImg(null);
    setSession(null); setError(null); setCache(false); setFuente(null);
    iniciar();
  }, [open, iniciar]);

  const resolver = async () => {
    if (!texto.trim()) return;
    setCargando(true); setError(null);
    try {
      const r = await api.post('/consultas/resolver', {
        session_id: sessionId, captcha: texto.trim(),
      });
      mostrar(r.data.datos, r.data.sugerencia, r.data.fuente, false);
    } catch (e) {
      setError(e.response?.data?.detail || 'Falló la consulta');
      // Código quemado o sesión vencida: hay que pedir uno nuevo, no reintentar.
      if ([400, 410].includes(e.response?.status)) iniciar();
    } finally {
      setCargando(false);
    }
  };

  const aplicar = () => {
    const campos = sug?.campos || {};
    const salida = {};
    Object.keys(campos).forEach(k => { if (marcados[k]) salida[k] = campos[k]; });
    if (!Object.keys(salida).length) { toast.error('No marcaste ningún campo'); return; }
    onAplicar(salida);
    toast.success(`${Object.keys(salida).length} campo(s) aplicado(s) desde ${(fuente || '').toUpperCase()}`);
    onClose();
  };

  const campos = sug?.campos || {};
  const aplicables = Object.keys(campos);
  const nMarcados = aplicables.filter(k => marcados[k]).length;
  const sinMatch = sug?.sin_match || (sug?.eps_sin_match ? { eps: sug.eps_sin_match } : null);

  const Chip = ({ children, color }) => (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 6,
      background: `${color}22`, color, marginLeft: 6 }}>{children}</span>
  );

  return (
    <Modal open={open} onClose={onClose} width={620}
      title={`🔍 Consulta seguridad social — ${tipoDoc || 'CC'} ${doc || ''}`}>

      {paso === 'cargando' && (
        <p style={{ color: C.text2, padding: '18px 0' }}>Abriendo consulta…</p>
      )}

      {error && (
        <div style={{ ...card, borderColor: C.red, background: C.redBg, color: C.red }}>
          {error}
        </div>
      )}

      {/* ─── captcha ─── */}
      {paso === 'captcha' && (
        <div>
          <p style={{ fontSize: 13, color: C.text2, marginBottom: 10 }}>
            {fuente ? <>Consultando <strong>{fuente.toUpperCase()}</strong>. </> : null}
            Escribe el código de seguridad que ves en la imagen.
            {sensible && <strong> Distingue mayúsculas de minúsculas.</strong>}
          </p>
          {captchaImg && (
            <div style={{ ...card, textAlign: 'center' }}>
              <img src={captchaImg} alt="código de seguridad" style={{ maxWidth: '100%' }} />
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={texto}
              onChange={e => setTexto(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && resolver()}
              placeholder="Código de la imagen"
              autoFocus
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              style={{ flex: 1, padding: '9px 11px', borderRadius: 8,
                border: `1px solid ${C.border}`, fontSize: 14, letterSpacing: 2 }} />
            <Btn variant="secondary" onClick={iniciar} disabled={cargando}>↻ Otro</Btn>
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
            <Btn onClick={resolver} disabled={cargando || !texto.trim()}>
              {cargando ? 'Consultando…' : 'Consultar'}
            </Btn>
          </div>
        </div>
      )}

      {/* ─── resultado ─── */}
      {paso === 'resultado' && datos && (
        <div>
          <div style={{ fontSize: 12, color: C.text2, marginBottom: 10 }}>
            Fuente: <strong>{(fuente || '').toUpperCase()}</strong>
            {desdeCache && <Chip color={C.blue}>consulta previa vigente</Chip>}
          </div>

          {fuente === 'ruaf' ? (
            <>
              {datos.nombre && (
                <div style={{ ...card, display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: C.text2, fontSize: 13 }}>Nombre</span>
                  <strong style={{ fontSize: 13 }}>{datos.nombre}</strong>
                </div>
              )}
              {SECCIONES.map(([clave, titulo]) => {
                const filas = datos[clave] || [];
                if (!filas.length) return null;
                return (
                  <div key={clave} style={card}>
                    <div style={{ fontSize: 11, fontWeight: 800, color: C.text2,
                      textTransform: 'uppercase', marginBottom: 6 }}>{titulo}</div>
                    {filas.map((f, i) => {
                      const adm = col(f, 'administradora') || '—';
                      const est = col(f, 'estado');
                      return (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between',
                          gap: 10, padding: '3px 0', fontSize: 13 }}>
                          <span style={{ minWidth: 0 }}>{adm}</span>
                          <span style={{ flexShrink: 0, fontWeight: 700,
                            color: vigente(est) ? C.green : C.text2 }}>{est || '—'}</span>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
              {sug?.arl_reportada && (
                <div style={{ ...card, borderColor: C.blue, background: C.blueBg, fontSize: 12 }}>
                  ARL reportada: <strong>{sug.arl_reportada}</strong>. No se aplica al
                  formulario porque el campo ARL guarda el <em>nivel</em> de riesgo, no la entidad.
                </div>
              )}
            </>
          ) : (
            <div style={card}>
              {CAMPOS_ADRES.filter(([k]) => datos[k]).map(([k, label]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between',
                  gap: 12, padding: '4px 0', fontSize: 13 }}>
                  <span style={{ color: C.text2 }}>{label}</span>
                  <strong style={{ textAlign: 'right' }}>{datos[k]}</strong>
                </div>
              ))}
            </div>
          )}

          {sinMatch && (
            <div style={{ ...card, borderColor: C.amber, background: C.amberBg, fontSize: 12 }}>
              {Object.entries(sinMatch).map(([k, v]) => (
                <div key={k}>
                  <strong>{ETIQUETAS[k] || k}:</strong> {v} — no coincide con ninguna opción
                  de la lista de esta empresa. Selecciónala a mano.
                </div>
              ))}
            </div>
          )}

          {aplicables.length > 0 ? (
            <>
              <p style={{ fontSize: 12, color: C.text2, margin: '4px 0 8px' }}>
                Marca lo que quieras llevar al formulario. Los campos que ya tienen
                algo escrito vienen desmarcados.
              </p>
              {aplicables.map(k => {
                const actual = String(valoresActuales[k] || '').trim();
                const nuevo = campos[k];
                const igual = actual && actual.toUpperCase() === String(nuevo).toUpperCase();
                return (
                  <label key={k} style={{ ...card, display: 'flex', gap: 10,
                    alignItems: 'flex-start', cursor: igual ? 'default' : 'pointer',
                    opacity: igual ? 0.55 : 1, marginBottom: 8 }}>
                    <input type="checkbox" checked={!!marcados[k]} disabled={igual}
                      onChange={e => setMarcados(m => ({ ...m, [k]: e.target.checked }))}
                      style={{ marginTop: 3 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 700 }}>{ETIQUETAS[k] || k}</div>
                      {igual ? (
                        <div style={{ fontSize: 12, color: C.text2 }}>Ya coincide con el formulario</div>
                      ) : (
                        <div style={{ fontSize: 12 }}>
                          {actual && <div style={{ color: C.text2, textDecoration: 'line-through' }}>{actual}</div>}
                          <div style={{ color: C.green, fontWeight: 600 }}>{nuevo}</div>
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </>
          ) : (
            <p style={{ fontSize: 12, color: C.text2 }}>
              La consulta no trajo campos vigentes que el formulario pueda llenar solo.
            </p>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <Btn variant="secondary" onClick={onClose}>Cerrar</Btn>
            <Btn onClick={aplicar} disabled={!nMarcados}>
              Aplicar {nMarcados || ''} al formulario
            </Btn>
          </div>
        </div>
      )}
    </Modal>
  );
}
