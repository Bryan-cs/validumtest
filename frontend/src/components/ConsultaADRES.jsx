import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, Modal } from './UI';

/**
 * Consulta de afiliación en salud contra ADRES (BDUA) desde el alta de afiliado.
 *
 * Dos pasos, porque ADRES exige código de seguridad:
 *   1. /consultas/adres/iniciar  → devuelve el captcha (o los datos, si ya hay
 *      una consulta vigente en caché y no hace falta gastar otro captcha)
 *   2. /consultas/adres/resolver → con el código que escribió el empleado
 *
 * El captcha lo resuelve una persona, siempre. No se elude.
 *
 * Regla de oro: esto NUNCA sobrescribe el formulario solo. Muestra lo que trajo
 * al lado de lo que ya está cargado y el empleado marca campo por campo.
 */

const ETIQUETAS = {
  nombre:           'Nombre',
  eps:              'EPS',
  regimen:          'Régimen',
  estado:           'Estado afiliación',
  tipo_afiliado:    'Tipo de afiliado',
  fecha_afiliacion: 'Fecha afiliación',
  departamento:     'Departamento',
  municipio:        'Municipio',
};

// Orden de lectura en el panel de resultado.
const ORDEN = ['nombre', 'eps', 'regimen', 'estado', 'tipo_afiliado',
               'fecha_afiliacion', 'departamento', 'municipio'];

const card = {
  border: `1px solid ${C.border}`, borderRadius: 8, padding: 12, marginBottom: 12,
};

export default function ConsultaADRES({ open, onClose, tipoDoc, doc, valoresActuales = {}, onAplicar }) {
  const [paso, setPaso]           = useState('cargando');  // cargando | captcha | resultado
  const [sessionId, setSessionId] = useState(null);
  const [captchaImg, setCaptcha]  = useState(null);
  const [texto, setTexto]         = useState('');
  const [datos, setDatos]         = useState(null);
  const [sugerencia, setSug]      = useState(null);
  const [marcados, setMarcados]   = useState({});
  const [cargando, setCargando]   = useState(false);
  const [error, setError]         = useState(null);
  const [desdeCache, setCache]    = useState(false);

  const mostrarResultado = useCallback((d, s, cacheado) => {
    setDatos(d);
    setSug(s);
    setCache(!!cacheado);
    // Por defecto se marcan solo los campos que el formulario tiene vacíos:
    // rellenar un hueco es seguro, pisar algo que alguien escribió no lo es.
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
      const r = await api.post('/consultas/adres/iniciar', { tipo_doc: tipoDoc || 'CC', doc });
      if (r.data.cacheado) {
        mostrarResultado(r.data.datos, r.data.sugerencia, true);
      } else {
        setSessionId(r.data.session_id);
        setCaptcha(r.data.captcha);
        setPaso('captcha');
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo contactar a ADRES');
      setPaso('captcha');
    } finally {
      setCargando(false);
    }
  }, [tipoDoc, doc, mostrarResultado]);

  useEffect(() => {
    if (!open) return;
    setPaso('cargando'); setDatos(null); setSug(null);
    setCaptcha(null); setSessionId(null); setError(null); setCache(false);
    iniciar();
  }, [open, iniciar]);

  const resolver = async () => {
    if (!texto.trim()) return;
    setCargando(true); setError(null);
    try {
      const r = await api.post('/consultas/adres/resolver', { session_id: sessionId, captcha: texto.trim() });
      mostrarResultado(r.data.datos, r.data.sugerencia, false);
    } catch (e) {
      const detalle = e.response?.data?.detail || 'Falló la consulta';
      setError(detalle);
      // Captcha quemado o sesión vencida: hay que pedir uno nuevo, no reintentar.
      if ([400, 410].includes(e.response?.status)) iniciar();
    } finally {
      setCargando(false);
    }
  };

  const aplicar = () => {
    const campos = sugerencia?.campos || {};
    const aplicar = {};
    Object.keys(campos).forEach(k => { if (marcados[k]) aplicar[k] = campos[k]; });
    if (!Object.keys(aplicar).length) { toast.error('No marcaste ningún campo'); return; }
    onAplicar(aplicar);
    toast.success(`${Object.keys(aplicar).length} campo(s) aplicado(s) desde ADRES`);
    onClose();
  };

  const campos = sugerencia?.campos || {};
  const aplicables = Object.keys(campos);
  const nMarcados = aplicables.filter(k => marcados[k]).length;

  return (
    <Modal open={open} onClose={onClose} width={560}
      title={`🔍 Consulta ADRES — ${tipoDoc || 'CC'} ${doc || ''}`}>

      {paso === 'cargando' && (
        <p style={{ color: C.text2, padding: '18px 0' }}>Abriendo consulta con ADRES…</p>
      )}

      {error && (
        <div style={{ ...card, borderColor: C.red, background: C.redBg, color: C.red }}>
          {error}
        </div>
      )}

      {/* ─── paso captcha ─── */}
      {paso === 'captcha' && (
        <div>
          <p style={{ fontSize: 13, color: C.text2, marginBottom: 10 }}>
            ADRES pide un código de seguridad. Escribe lo que ves en la imagen.
          </p>
          {captchaImg && (
            <div style={{ ...card, textAlign: 'center' }}>
              <img src={captchaImg} alt="código de seguridad"
                style={{ maxWidth: '100%', imageRendering: 'pixelated' }} />
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              value={texto}
              onChange={e => setTexto(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && resolver()}
              placeholder="Código de la imagen"
              autoFocus
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

      {/* ─── paso resultado ─── */}
      {paso === 'resultado' && datos && (
        <div>
          {desdeCache && (
            <div style={{ ...card, borderColor: C.blue, background: C.blueBg, fontSize: 12, color: C.blue }}>
              Consulta previa vigente — no se gastó un código nuevo.
            </div>
          )}

          <div style={card}>
            {ORDEN.filter(k => datos[k]).map(k => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between',
                gap: 12, padding: '4px 0', fontSize: 13 }}>
                <span style={{ color: C.text2 }}>{ETIQUETAS[k] || k}</span>
                <strong style={{ textAlign: 'right' }}>{datos[k]}</strong>
              </div>
            ))}
          </div>

          {sugerencia?.eps_sin_match && (
            <div style={{ ...card, borderColor: C.amber, background: C.amberBg, fontSize: 12 }}>
              ADRES reporta <strong>{sugerencia.eps_sin_match}</strong>, que no coincide con
              ninguna EPS de la lista de esta empresa. Selecciónala a mano.
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
                const nuevo  = campos[k];
                const igual  = actual && actual.toUpperCase() === String(nuevo).toUpperCase();
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
                          {actual && (
                            <div style={{ color: C.text2, textDecoration: 'line-through' }}>{actual}</div>
                          )}
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
              La consulta no trajo campos que el formulario pueda llenar solo.
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
