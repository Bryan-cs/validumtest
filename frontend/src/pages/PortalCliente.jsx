import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import api, { buildUploadForm } from '../utils/api';
import useAuthStore from '../hooks/useAuth';
import { empresaStyle } from '../utils/colors';
import { C, Btn } from '../components/UI';
import useAppBadge from '../hooks/useAppBadge';

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear();
const ANIOS = [anioActual-1, anioActual, anioActual+1].map(String);

const _moneyFmt = new Intl.NumberFormat('es-CO', { style:'currency', currency:'COP', maximumFractionDigits:0 });
const money = (v) => _moneyFmt.format(v || 0);

const inp = { width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`, borderRadius:8, fontSize:13, fontFamily:"'Outfit',system-ui,sans-serif", boxSizing:'border-box', outline:'none', color:C.text, background:C.surface };
const lbl = { fontSize:12, fontWeight:600, color:C.text2, display:'block', marginBottom:5, fontFamily:"'Outfit',system-ui,sans-serif" };
const tdc = { padding:'10px 14px', fontSize:13, color:C.text, verticalAlign:'middle' };

// ── CSS ──────────────────────────────────────────────────────────────────────
const PORTAL_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap');
.pcc,.pcc *{box-sizing:border-box;}
.pcc{font-family:'Outfit',system-ui,sans-serif;min-height:100vh;background:var(--c-bg);}

.pcc-hdr{background:var(--c-sidebar);position:sticky;top:0;z-index:100;box-shadow:0 2px 20px rgba(0,0,0,.28);}
.pcc-hdr-in{max-width:1200px;margin:0 auto;padding:0 24px;}
.pcc-topbar{display:flex;align-items:center;justify-content:space-between;padding:14px 0 12px;}
.pcc-logo-main{color:#fff;font-size:20px;font-weight:800;letter-spacing:-.5px;}
.pcc-logo-sub{color:rgba(255,255,255,.42);font-size:11px;font-weight:400;letter-spacing:.5px;margin-left:10px;}
.pcc-actions{display:flex;align-items:center;gap:10px;}
.pcc-user{color:rgba(255,255,255,.7);font-size:13px;font-weight:500;}
.pcc-glass{padding:6px 14px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);border-radius:8px;color:#fff;cursor:pointer;font-size:13px;font-weight:500;font-family:'Outfit',system-ui,sans-serif;transition:background .15s;}
.pcc-glass:hover{background:rgba(255,255,255,.22);}
.pcc-stats{display:flex;flex-wrap:wrap;gap:0;padding:10px 0 16px;border-top:1px solid rgba(255,255,255,.1);}
.pcc-stat{padding:0 28px 0 0;margin-right:28px;border-right:1px solid rgba(255,255,255,.12);}
.pcc-stat:last-child{border-right:none;padding-right:0;margin-right:0;}
.pcc-stat-lbl{font-size:10px;font-weight:600;color:rgba(255,255,255,.45);text-transform:uppercase;letter-spacing:.1em;margin-bottom:1px;}
.pcc-stat-val{font-size:26px;font-weight:800;line-height:1.1;}

.pcc-nav{max-width:1200px;margin:0 auto;padding:20px 24px 0;}
.pcc-tabs{display:flex;gap:3px;background:var(--c-surface2);border-radius:12px;padding:4px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;}
.pcc-tabs::-webkit-scrollbar{display:none;}
.pcc-tab{flex-shrink:0;padding:8px 18px;border-radius:8px;border:none;font-family:'Outfit',system-ui,sans-serif;font-size:13px;font-weight:600;cursor:pointer;background:transparent;color:var(--c-text2);white-space:nowrap;position:relative;transition:all .15s;}
.pcc-tab.act{background:var(--c-surface);color:var(--c-primary);box-shadow:0 1px 5px rgba(0,0,0,.1);}
.pcc-tab-dot{position:absolute;top:5px;right:5px;background:#ef4444;color:#fff;border-radius:50%;width:15px;height:15px;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;}

.pcc-body{max-width:1200px;margin:0 auto;padding:20px 24px 36px;}

.pcc-filters{background:var(--c-surface);border:1px solid var(--c-border);border-radius:12px;padding:14px 18px;margin-bottom:18px;}
.pcc-frow{display:flex;flex-wrap:wrap;gap:10px;align-items:center;}
.pcc-fsearch{position:relative;flex:1;min-width:180px;}
.pcc-fsrch-ico{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--c-text2);font-size:13px;pointer-events:none;}
.pcc-fi{width:100%;padding:8px 10px 8px 32px;border:1px solid var(--c-border);border-radius:8px;font-size:13px;font-family:'Outfit',system-ui,sans-serif;background:var(--c-bg);color:var(--c-text);outline:none;transition:border-color .15s;}
.pcc-fi:focus{border-color:var(--c-primary);}
.pcc-fsel{padding:8px 10px;border:1px solid var(--c-border);border-radius:8px;font-size:13px;font-family:'Outfit',system-ui,sans-serif;background:var(--c-bg);color:var(--c-text);outline:none;cursor:pointer;}
.pcc-selbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px;padding-top:10px;border-top:1px solid var(--c-border);}
.pcc-selct{font-size:13px;font-weight:600;color:var(--c-primary);}

.pcc-tw{border-radius:12px;border:1px solid var(--c-border);overflow:clip;background:var(--c-surface);}
.pcc-tbl{width:100%;border-collapse:collapse;font-size:13px;font-family:'Outfit',system-ui,sans-serif;}
.pcc-th{padding:8px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--c-text);text-transform:uppercase;letter-spacing:.06em;background:var(--c-surface2);border-bottom:2px solid var(--c-border);white-space:nowrap;position:sticky;top:0;z-index:10;}
@keyframes pcc-shimmer{0%{background-position:-600px 0}100%{background-position:600px 0}}
.pcc-skel{background:linear-gradient(90deg,var(--c-surface2) 25%,var(--c-border) 50%,var(--c-surface2) 75%);background-size:600px 100%;animation:pcc-shimmer 1.5s infinite;border-radius:5px;display:inline-block;}
.pcc-td{padding:5px 12px;color:var(--c-text);vertical-align:middle;border-bottom:1px solid var(--c-border);}
.pcc-tr:last-child .pcc-td{border-bottom:none;}
.pcc-tr:hover .pcc-td{background:var(--c-surface2);}

.pcc-badge{display:inline-block;padding:2px 10px;border-radius:100px;font-size:11px;font-weight:700;white-space:nowrap;}

.pcc-pager{display:flex;gap:8px;justify-content:center;align-items:center;padding:14px 0 0;}
.pcc-pager-i{font-size:13px;color:var(--c-text2);}

.pcc-empty{text-align:center;padding:56px 24px;color:var(--c-text2);}
.pcc-empty-ico{font-size:40px;margin-bottom:10px;}
.pcc-empty-txt{font-size:14px;font-weight:500;}

.pcc-ov{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);z-index:1000;display:flex;align-items:flex-start;justify-content:center;padding:36px 16px;overflow-y:auto;}
.pcc-modal{background:var(--c-surface);border-radius:20px;padding:28px;box-shadow:0 24px 80px rgba(0,0,0,.3);margin:auto;}
.pcc-mhd{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--c-border);}
.pcc-mtitle{font-size:17px;font-weight:700;color:var(--c-text);margin:0;}
.pcc-mx{background:var(--c-surface2);border:none;width:32px;height:32px;border-radius:8px;font-size:18px;cursor:pointer;color:var(--c-text2);display:flex;align-items:center;justify-content:center;line-height:1;transition:background .15s;}
.pcc-mx:hover{background:var(--c-border);}
.pcc-mftr{display:flex;gap:10px;justify-content:flex-end;margin-top:8px;}

.pcc-hcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;}
.pcc-hcard{background:var(--c-surface);border:1px solid var(--c-border);border-radius:12px;padding:14px;}
.pcc-hcard-hd{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;}

.pcc-card{background:var(--c-surface);border:1px solid var(--c-border);border-radius:12px;padding:18px 20px;margin-bottom:16px;}
.pcc-slbl{font-size:11px;font-weight:700;color:var(--c-text2);text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px;}
.pcc-dz{border:2px dashed var(--c-border);border-radius:10px;padding:16px;text-align:center;background:var(--c-surface2);cursor:pointer;transition:border-color .2s;}
.pcc-dz:hover{border-color:var(--c-primary);}

.pcc-ndrop{position:absolute;right:0;top:calc(100% + 8px);width:340px;max-height:420px;overflow-y:auto;background:var(--c-surface);border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.2);z-index:200;border:1px solid var(--c-border);}
.pcc-ndrop-hd{padding:12px 16px;border-bottom:1px solid var(--c-border);display:flex;justify-content:space-between;align-items:center;}
.pcc-nitem{padding:10px 16px;border-bottom:1px solid var(--c-border);}
.pcc-nitem:last-child{border-bottom:none;}

@media(max-width:767px){
  .pcc-hdr-in,.pcc-nav,.pcc-body{padding-left:14px;padding-right:14px;}
  .pcc-stat{padding-right:16px;margin-right:16px;}
  .pcc-stat-val{font-size:21px;}
  .pcc-logo-sub,.pcc-user{display:none;}
  .pcc-modal{border-radius:16px;padding:20px;}
}
`;

function PortalStyles() {
  useEffect(() => {
    if (document.getElementById('pcc-styles')) return;
    const el = document.createElement('style');
    el.id = 'pcc-styles';
    el.textContent = PORTAL_CSS;
    document.head.appendChild(el);
    return () => { document.getElementById('pcc-styles')?.remove(); };
  }, []);
  return null;
}

// ── Badges ───────────────────────────────────────────────────────────────────
function EmpresaBadge({ nombre }) {
  if (!nombre) return <span style={{ color:C.text2 }}>—</span>;
  const s = empresaStyle(nombre);
  return <span className="pcc-badge" style={{ background:s.bg, color:s.color }}>{nombre}</span>;
}

function ColorBadge({ color, bg, children }) {
  return <span className="pcc-badge" style={{ background:bg, color }}>{children}</span>;
}

// ── Modal Resumen ────────────────────────────────────────────────────────────
function ModalResumen({ doc, onClose }) {
  const { data, isLoading } = useQuery({
    queryKey: ['portal-resumen', doc],
    queryFn: () => api.get(`/portal/afiliados/${doc}/resumen`).then(r => r.data),
    enabled: !!doc,
  });

  const descargarPDF = () => {
    if (!data?.afiliado) return;
    api.get(`/portal/afiliados/${doc}/estado-cuenta`, { responseType:'blob' })
      .then(r => {
        const url = window.URL.createObjectURL(new Blob([r.data], { type:'application/pdf' }));
        const a = document.createElement('a'); a.href = url;
        a.download = `estado-cuenta-${doc}.pdf`; a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => toast.error('Error al descargar PDF'));
  };

  return (
    <div className="pcc-ov">
      <div className="pcc-modal" style={{ width:700, maxWidth:'100%' }}>
        <div className="pcc-mhd">
          <h3 className="pcc-mtitle">Resumen del Afiliado</h3>
          <button className="pcc-mx" onClick={onClose}>×</button>
        </div>
        {isLoading ? (
          <p style={{ textAlign:'center', color:C.text2, padding:40 }}>Cargando...</p>
        ) : data ? (
          <>
            <div style={{ background:C.surface2, borderRadius:12, padding:16, marginBottom:16 }}>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
                {[
                  ['Nombre', data.afiliado.nombre],
                  ['Documento', `${data.afiliado.tipo_doc} ${data.afiliado.doc}`],
                  ['Empresa', data.afiliado.empresa],
                  ['Cargo', data.afiliado.cargo],
                  ['EPS', data.afiliado.eps],
                  ['AFP', data.afiliado.afp],
                  ['CCF', data.afiliado.ccf],
                  ['ARL', data.afiliado.arl],
                  ['Teléfono', data.afiliado.tel],
                  ['Email', data.afiliado.email],
                  ['Fecha afiliación', data.afiliado.fecha_afiliacion],
                  ['Detalle', data.afiliado.detalle],
                ].map(([k, v]) => v ? (
                  <div key={k}>
                    <div style={{ fontSize:10, color:C.text2, fontWeight:700, textTransform:'uppercase', letterSpacing:'.06em', marginBottom:2 }}>{k}</div>
                    <div style={{ fontSize:13, color:C.text }}>
                      {k === 'Empresa' ? <EmpresaBadge nombre={v} /> : v}
                    </div>
                  </div>
                ) : null)}
              </div>
              <div style={{ marginTop:10, display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
                <ColorBadge color={data.afiliado.estado==='ACTIVO'?C.green:C.red} bg={data.afiliado.estado==='ACTIVO'?C.greenBg:C.redBg}>
                  {data.afiliado.estado}
                </ColorBadge>
              </div>
            </div>

            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:16 }}>
              <div style={{ background:C.greenBg, borderRadius:10, padding:14, textAlign:'center' }}>
                <div style={{ fontSize:11, color:C.green, fontWeight:600, marginBottom:4 }}>Total pagado</div>
                <div style={{ fontSize:18, color:C.green, fontWeight:800 }}>{money(data.total_pagado)}</div>
              </div>
              <div style={{ background:C.redBg, borderRadius:10, padding:14, textAlign:'center' }}>
                <div style={{ fontSize:11, color:C.red, fontWeight:600, marginBottom:4 }}>Total pendiente</div>
                <div style={{ fontSize:18, color:C.red, fontWeight:800 }}>{money(data.total_pendiente)}</div>
              </div>
            </div>

            {data.facturas.length > 0 && (
              <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}`, marginBottom:16 }}>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
                  <thead><tr style={{ background:C.surface2 }}>
                    {['Período','Código','Estado','Total','Banco'].map(h => (
                      <th key={h} style={{ padding:'8px 12px', textAlign:'left', fontWeight:700, fontSize:10, color:C.text2, textTransform:'uppercase', letterSpacing:'.07em', borderBottom:`1px solid ${C.border}` }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {data.facturas.map(f => (
                      <tr key={f.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                        <td style={tdc}>{f.mes} {f.anio}</td>
                        <td style={tdc}>{f.codigo}</td>
                        <td style={tdc}>{(() => {
                          const pagado = f.estado === 'pagado' || f.estado === 'planilla_pagada';
                          return <ColorBadge color={pagado?C.green:C.red} bg={pagado?C.greenBg:C.redBg}>{pagado?'PAGADA':(f.estado?.toUpperCase()??'—')}</ColorBadge>;
                        })()}</td>
                        <td style={tdc}>{money(f.ingresos)}</td>
                        <td style={tdc}>{f.banco||'—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="pcc-mftr">
              <Btn variant="accent" onClick={descargarPDF}>Descargar Estado de Cuenta PDF</Btn>
              <Btn variant="secondary" onClick={onClose}>Cerrar</Btn>
            </div>
          </>
        ) : (
          <p style={{ textAlign:'center', color:C.red }}>Error al cargar datos</p>
        )}
      </div>
    </div>
  );
}

// ── Modal Novedad de Pago ────────────────────────────────────────────────────
function ModalNovedadPago({ afiliados, onClose, onSuccess }) {
  const [mes, setMes] = useState(MESES[new Date().getMonth()]);
  const [anio, setAnio] = useState(String(anioActual));
  const [obs, setObs] = useState('');
  const [archivos, setArchivos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);
  const [selDocs, setSelDocs] = useState([]);
  const [selSearch, setSelSearch] = useState('');

  const afilFiltrados = useMemo(() => {
    if (!selSearch.trim()) return afiliados;
    const lower = selSearch.toLowerCase();
    return afiliados.filter(a => a.nombre.toLowerCase().includes(lower) || a.doc.includes(selSearch));
  }, [afiliados, selSearch]);

  const toggleDoc = (doc) => setSelDocs(prev => prev.includes(doc) ? prev.filter(d => d !== doc) : [...prev, doc]);

  const crear = useMutation({
    mutationFn: async () => {
      if (selDocs.length === 0) throw new Error('Selecciona al menos un afiliado');
      const res = await api.post('/portal/novedades-pago', { mes, anio, afiliados_docs: selDocs, obs });
      const novId = res.data?.id ?? res.data?.novedad_id ?? null;
      if (archivos.length > 0) {
        if (!novId) {
          toast.error(`Adjunto no enviado: no se obtuvo ID de novedad (respuesta: ${JSON.stringify(res.data)})`);
        } else {
          setSubiendo(true);
          try {
            await Promise.all(archivos.map(file => {
              const { fd } = buildUploadForm(file, { contexto: 'novedad_pago', contexto_id: String(novId) });
              return api.post('/documentos', fd);
            }));
            toast.success(`${archivos.length} adjunto(s) guardado(s)`);
          } catch (uploadErr) {
            const det = uploadErr?.response?.data?.detail;
            const msg = Array.isArray(det) ? det.map(d => d.msg).join(', ') : (det || uploadErr?.message || 'Error desconocido');
            toast.error(`Novedad creada, pero falló el adjunto: ${msg}`);
          } finally {
            setSubiendo(false);
          }
        }
      }
      return res;
    },
    onSuccess: () => { toast.success('Novedad de pago reportada al administrador'); onSuccess(); onClose(); },
    onError: (e) => {
      const det = e?.response?.data?.detail;
      const msg = Array.isArray(det) ? det.map(d => d.msg).join(', ') : (det || e?.message || 'Error al reportar novedad');
      toast.error(msg);
    },
  });

  return (
    <div className="pcc-ov">
      <div className="pcc-modal" style={{ width: 520, maxWidth: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="pcc-mhd">
          <h3 className="pcc-mtitle">Nueva Novedad de Pago SS</h3>
          <button className="pcc-mx" onClick={onClose}>×</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <div>
            <label style={lbl}>Mes</label>
            <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
              {MESES.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año</label>
            <select style={inp} value={anio} onChange={e => setAnio(e.target.value)}>
              {ANIOS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <label style={lbl}>Seleccionar afiliados *</label>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setSelDocs(afilFiltrados.map(a => a.doc))}
                style={{ fontSize: 11, color: C.primary, background: 'none', border: 'none', cursor: 'pointer', fontFamily: "'Outfit',system-ui,sans-serif", fontWeight: 600 }}>
                Todos
              </button>
              <button onClick={() => setSelDocs([])}
                style={{ fontSize: 11, color: C.text2, background: 'none', border: 'none', cursor: 'pointer', fontFamily: "'Outfit',system-ui,sans-serif" }}>
                Ninguno
              </button>
            </div>
          </div>
          <input
            type="text"
            placeholder="Buscar por nombre o documento..."
            value={selSearch}
            onChange={e => setSelSearch(e.target.value)}
            style={{ ...inp, marginBottom: 6 }}
          />
          <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, maxHeight: 200, overflowY: 'auto', background: C.bg }}>
            {afilFiltrados.length === 0
              ? <div style={{ padding: 14, textAlign: 'center', color: C.text2, fontSize: 13 }}>Sin resultados</div>
              : afilFiltrados.map(a => {
                const sel = selDocs.includes(a.doc);
                return (
                  <div key={a.doc}
                    onClick={() => toggleDoc(a.doc)}
                    style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px', cursor: 'pointer', borderBottom: `1px solid ${C.border}`, fontSize: 13, color: C.text, userSelect: 'none', background: sel ? C.blueBg : undefined, transition: 'background .1s' }}>
                    <div style={{ width: 20, height: 20, borderRadius: 5, border: `2px solid ${sel ? C.primary : C.border}`, background: sel ? C.primary : C.surface, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all .1s' }}>
                      {sel && <span style={{ color: '#fff', fontSize: 12, lineHeight: 1, fontWeight: 700 }}>✓</span>}
                    </div>
                    <span style={{ fontWeight: sel ? 600 : 500, flex: 1 }}>{a.nombre}</span>
                    <span style={{ color: sel ? C.primary : C.text, fontSize: 13, fontWeight: 700, whiteSpace: 'nowrap', fontFamily: "'IBM Plex Mono',monospace", letterSpacing: '.02em' }}>{a.doc}</span>
                  </div>
                );
              })
            }
          </div>
          {selDocs.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 12, color: C.primary, fontWeight: 700 }}>
              ✓ {selDocs.length} afiliado(s) seleccionado(s)
            </div>
          )}
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Observaciones (opcional)</label>
          <textarea style={{ ...inp, resize: 'vertical', minHeight: 60 }} value={obs} onChange={e => setObs(e.target.value)} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={lbl}>Adjuntar documentos (opcional)</label>
          <div className="pcc-dz" onClick={() => document.getElementById('portal-pago-files')?.click()}>
            <input id="portal-pago-files" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx"
              style={{ display: 'none' }}
              onChange={e => { setArchivos(prev => [...prev, ...Array.from(e.target.files)]); e.target.value = ''; }} />
            <div style={{ fontSize: 12, color: C.text2 }}>📂 Click para adjuntar comprobantes</div>
          </div>
          {archivos.length > 0 && (
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 3 }}>
              {archivos.map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: C.text, background: C.surface2, padding: '3px 8px', borderRadius: 6 }}>
                  <span style={{ flex: 1 }}>{f.name}</span>
                  <span style={{ cursor: 'pointer', color: C.red, fontWeight: 700 }} onClick={() => setArchivos(prev => prev.filter((_, j) => j !== i))}>×</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="pcc-mftr">
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="success" onClick={() => crear.mutate()} disabled={crear.isPending || subiendo || selDocs.length === 0}>
            {subiendo ? 'Subiendo archivos...' : crear.isPending ? 'Enviando...' : 'Confirmar y Notificar'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

// ── Modal Novedad de Afiliado ─────────────────────────────────────────────────
function ModalNovedadAfiliado({ afiliado, onClose, onSuccess }) {
  const TIPOS = ['Incapacidad médica','Licencia de maternidad/paternidad','Accidente laboral','Cambio de salario','Cambio de cargo','Suspensión','Ausentismo','Otro'];
  const [tipo, setTipo] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [archivos, setArchivos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);

  const crear = useMutation({
    mutationFn: async () => {
      if (!tipo) throw new Error('Selecciona el tipo de novedad');
      if (!descripcion.trim()) throw new Error('La descripción es obligatoria');
      const res = await api.post('/portal/solicitudes-novedad', { afiliado_doc:afiliado.doc, tipo, descripcion });
      const novId = res.data?.id;
      if (archivos.length > 0 && novId) {
        setSubiendo(true);
        await Promise.all(archivos.map(file => {
          const { fd } = buildUploadForm(file, { afiliado_doc:afiliado.doc, contexto:'novedad_afil', contexto_id:String(novId) });
          return api.post('/documentos', fd);
        }));
        setSubiendo(false);
      }
      return res;
    },
    onSuccess: () => { toast.success('Novedad enviada al administrador'); onSuccess(); onClose(); },
    onError: (e) => { setSubiendo(false); toast.error(e?.message||e?.response?.data?.detail||'Error'); },
  });

  const removeFile = (idx) => setArchivos(prev => prev.filter((_,i) => i!==idx));

  return (
    <div className="pcc-ov">
      <div className="pcc-modal" style={{ width:500, maxWidth:'100%', maxHeight:'90vh', overflowY:'auto' }}>
        <div className="pcc-mhd">
          <h3 className="pcc-mtitle">Reportar Novedad del Afiliado</h3>
          <button className="pcc-mx" onClick={onClose}>×</button>
        </div>

        <div style={{ background:C.surface2, borderRadius:10, padding:12, marginBottom:16 }}>
          <div style={{ fontWeight:700, fontSize:14, color:C.text }}>{afiliado.nombre}</div>
          <div style={{ fontSize:12, color:C.text2, marginTop:2 }}>{afiliado.tipo_doc} {afiliado.doc} — <EmpresaBadge nombre={afiliado.empresa} /></div>
        </div>

        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Tipo de novedad *</label>
          <select style={inp} value={tipo} onChange={e => setTipo(e.target.value)}>
            <option value="">— Seleccionar tipo —</option>
            {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Descripción *</label>
          <textarea style={{ ...inp, resize:'vertical', minHeight:90 }}
            placeholder="Describe la situación del afiliado..."
            value={descripcion} onChange={e => setDescripcion(e.target.value)} />
        </div>

        <div style={{ marginBottom:16 }}>
          <label style={lbl}>Adjuntar documentos (opcional)</label>
          <div className="pcc-dz" onClick={() => document.getElementById('portal-nov-files')?.click()}>
            <input id="portal-nov-files" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx"
              style={{ display:'none' }}
              onChange={e => { setArchivos(prev => [...prev, ...Array.from(e.target.files)]); e.target.value=''; }} />
            <div style={{ fontSize:13, color:C.text2 }}>📂 Click para seleccionar archivos</div>
          </div>
          {archivos.length > 0 && (
            <div style={{ marginTop:8, display:'flex', flexDirection:'column', gap:4 }}>
              {archivos.map((f,i) => (
                <div key={i} style={{ display:'flex', alignItems:'center', gap:8, fontSize:12, color:C.text, background:C.surface2, padding:'4px 8px', borderRadius:6 }}>
                  <span style={{ flex:1 }}>{f.name} ({(f.size/1024).toFixed(0)} KB)</span>
                  <span style={{ cursor:'pointer', color:C.red, fontWeight:700 }} onClick={() => removeFile(i)}>×</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="pcc-mftr">
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="accent" onClick={() => crear.mutate()} disabled={crear.isPending||subiendo||!tipo||!descripcion.trim()}>
            {subiendo ? 'Subiendo archivos...' : crear.isPending ? 'Enviando...' : 'Enviar novedad'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

// ── Modal Solicitar Retiro ────────────────────────────────────────────────────
const MOTIVOS_RETIRO_DEFAULT = ['Renuncia voluntaria','Terminación de contrato','Pensión','Fallecimiento','Otro'];

function ModalRetiro({ afiliado, onClose, onSuccess }) {
  const [motivo, setMotivo] = useState('');
  const [obs, setObs] = useState('');
  const { data: motivosRetiro = MOTIVOS_RETIRO_DEFAULT } = useQuery({
    queryKey: ['listas-motivos-retiro'],
    queryFn: () => api.get('/listas').then(r => {
      const lista = r.data.find(l => l.nombre === 'motivos_retiro');
      return lista ? JSON.parse(lista.items) : MOTIVOS_RETIRO_DEFAULT;
    }),
    staleTime: 300_000,
  });

  const crear = useMutation({
    mutationFn: () => {
      if (!motivo.trim()) return Promise.reject(new Error('El motivo es obligatorio'));
      return api.post('/portal/solicitar-retiro', { afiliado_doc:afiliado.doc, motivo, obs });
    },
    onSuccess: () => { toast.success('Solicitud de retiro enviada al administrador'); onSuccess(); onClose(); },
    onError: (e) => toast.error(e?.message||e?.response?.data?.detail||'Error'),
  });

  return (
    <div className="pcc-ov">
      <div className="pcc-modal" style={{ width:440, maxWidth:'100%' }}>
        <div className="pcc-mhd">
          <h3 className="pcc-mtitle">Solicitar Retiro</h3>
          <button className="pcc-mx" onClick={onClose}>×</button>
        </div>

        <div style={{ background:C.surface2, borderRadius:10, padding:12, marginBottom:16 }}>
          <div style={{ fontWeight:700, fontSize:14, color:C.text }}>{afiliado.nombre}</div>
          <div style={{ fontSize:12, color:C.text2, marginTop:2 }}>{afiliado.tipo_doc} {afiliado.doc} — <EmpresaBadge nombre={afiliado.empresa} /></div>
        </div>

        <p style={{ fontSize:13, color:C.text2, marginBottom:12 }}>
          El retiro será gestionado por el empleado correspondiente. Solo se registra la solicitud.
        </p>

        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Motivo *</label>
          <select style={inp} value={motivo} onChange={e => setMotivo(e.target.value)}>
            <option value="">— Seleccionar motivo —</option>
            {motivosRetiro.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        <div style={{ marginBottom:16 }}>
          <label style={lbl}>Observaciones</label>
          <textarea style={{ ...inp, resize:'vertical', minHeight:70 }} value={obs} onChange={e => setObs(e.target.value)} />
        </div>

        <div className="pcc-mftr">
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn variant="danger" onClick={() => crear.mutate()} disabled={crear.isPending||!motivo}>
            {crear.isPending ? 'Enviando...' : 'Solicitar retiro'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

// ── Adjuntos por Novedad ──────────────────────────────────────────────────────
function DocsNovedad({ novedadId, contexto = 'novedad_resp' }) {
  const [open, setOpen] = useState(false);
  const { data: docs=[], isLoading } = useQuery({
    queryKey: ['docs-novedad-portal', contexto, novedadId],
    queryFn: () => api.get('/documentos', { params:{ contexto, contexto_id:novedadId } }).then(r => r.data),
    enabled: open,
  });

  if (!open) return (
    <button onClick={() => setOpen(true)}
      style={{ fontSize:11, color:C.blue, background:'none', border:'none', cursor:'pointer', padding:0, textDecoration:'underline', marginTop:6, display:'block' }}>
      📎 Ver adjuntos
    </button>
  );

  return (
    <div style={{ marginTop:8 }}>
      {isLoading ? <span style={{ fontSize:11, color:C.text2 }}>Cargando...</span> :
        docs.length === 0 ? <span style={{ fontSize:11, color:C.text2 }}>Sin adjuntos</span> :
        docs.map(d => (
          <div key={d.id} style={{ fontSize:12, marginBottom:3 }}>
            <span style={{ color:C.blue, cursor:'pointer', textDecoration:'underline' }}
              onClick={async () => {
                try {
                  const res = await api.get(`/documentos/${d.id}/descargar`);
                  if (res.data?.url) {
                    const a = document.createElement('a'); a.href = res.data.url; a.download = res.data.nombre||d.nombre;
                    document.body.appendChild(a); a.click(); document.body.removeChild(a);
                  } else {
                    const blobRes = await api.get(`/documentos/${d.id}/descargar`, { responseType:'blob' });
                    const u = URL.createObjectURL(blobRes.data);
                    const a = document.createElement('a'); a.href = u; a.download = d.nombre; a.click(); URL.revokeObjectURL(u);
                  }
                } catch { toast.error('Error al descargar archivo'); }
              }}>
              📄 {d.nombre}
            </span>
            <span style={{ color:C.text2, fontSize:10, marginLeft:6 }}>{d.subido_por}</span>
          </div>
        ))
      }
      <button onClick={() => setOpen(false)}
        style={{ fontSize:10, color:C.text2, background:'none', border:'none', cursor:'pointer', padding:0, marginTop:4 }}>
        Ocultar
      </button>
    </div>
  );
}

// ── Tab Historial ─────────────────────────────────────────────────────────────
function TabHistorial() {
  const [subtab, setSubtab] = useState('novedades');
  const [fecha, setFecha] = useState('');
  const [estado, setEstado] = useState('');

  const { data: novedades=[] } = useQuery({ queryKey:['portal-novedades'], queryFn:()=>api.get('/portal/novedades-pago').then(r=>r.data), refetchInterval:60_000 });
  const { data: retiros=[] }   = useQuery({ queryKey:['portal-retiros'],   queryFn:()=>api.get('/portal/solicitudes-retiro').then(r=>r.data), refetchInterval:60_000 });
  const { data: novAfil=[] }   = useQuery({ queryKey:['portal-novedades-afil'], queryFn:()=>api.get('/portal/solicitudes-novedad').then(r=>r.data), refetchInterval:60_000 });

  const TABS = [
    { id:'novedades', label:`💳 Novedades de Pago (${novedades.length})` },
    { id:'retiros',   label:`🚪 Retiros (${retiros.length})` },
    { id:'afiliados', label:`📝 Novedades Afiliados (${novAfil.length})` },
  ];

  const listas = { novedades, retiros, afiliados: novAfil };
  const estadoOpts = {
    novedades: ['pendiente','procesado'],
    retiros:   ['pendiente','ejecutado','rechazado'],
    afiliados: ['pendiente','atendido'],
  };

  const filtrada = (listas[subtab]||[]).filter(item => {
    if (fecha  && item.creado?.slice(0,10) !== fecha) return false;
    if (estado && item.estado !== estado) return false;
    return true;
  });

  const colorEstado = (e) => {
    if (e === 'procesado' || e === 'ejecutado' || e === 'atendido') return [C.green, C.greenBg];
    if (e === 'rechazado') return [C.red, C.redBg];
    return [C.amber, C.amberBg];
  };

  const fStyle = { padding:'7px 10px', border:`1px solid ${C.border}`, borderRadius:8, fontSize:12, outline:'none', color:C.text, background:C.surface, fontFamily:"'Outfit',system-ui,sans-serif" };

  return (
    <div>
      <div style={{ display:'flex', gap:3, marginBottom:16, background:C.surface2, borderRadius:10, padding:4, flexWrap:'wrap' }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => { setSubtab(t.id); setFecha(''); setEstado(''); }} style={{
            padding:'7px 14px', borderRadius:7, border:'none', fontSize:12, fontWeight:600, cursor:'pointer',
            fontFamily:"'Outfit',system-ui,sans-serif",
            background: subtab===t.id ? C.surface : 'transparent',
            color: subtab===t.id ? C.primary : C.text2,
            boxShadow: subtab===t.id ? '0 1px 4px rgba(0,0,0,.1)' : 'none',
          }}>{t.label}</button>
        ))}
      </div>

      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} style={fStyle} />
        <select value={estado} onChange={e => setEstado(e.target.value)} style={fStyle}>
          <option value="">Todos los estados</option>
          {(estadoOpts[subtab]||[]).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {(fecha || estado) && (
          <button onClick={() => { setFecha(''); setEstado(''); }}
            style={{ background:'none', border:'none', cursor:'pointer', color:C.text2, fontSize:12, fontFamily:"'Outfit',system-ui,sans-serif" }}>
            ✕ Limpiar
          </button>
        )}
        <span style={{ fontSize:12, color:C.text2, marginLeft:'auto', fontFamily:"'Outfit',system-ui,sans-serif" }}>{filtrada.length} resultado(s)</span>
      </div>

      {filtrada.length === 0 ? (
        <div className="pcc-empty"><div className="pcc-empty-ico">📭</div><div className="pcc-empty-txt">Sin registros</div></div>
      ) : (
        <div className="pcc-hcards">
          {filtrada.map(item => {
            const [color, bg] = colorEstado(item.estado);
            return (
              <div key={item.id} className="pcc-hcard">
                <div className="pcc-hcard-hd">
                  <div style={{ fontWeight:700, fontSize:13, color:C.text }}>
                    {subtab === 'novedades' ? `${item.mes} ${item.anio}` : item.afiliado_nombre}
                  </div>
                  <ColorBadge color={color} bg={bg}>{item.estado}</ColorBadge>
                </div>
                {subtab === 'novedades' && (
                  <div style={{ fontSize:12, color:C.text2 }}>
                    <span style={{ fontWeight:600 }}>{item.afiliados?.length} afiliado(s):</span>{' '}
                    {(item.afiliados || []).join(', ')}
                  </div>
                )}
                {subtab === 'retiros' && (
                  <>
                    <div style={{ fontSize:12, color:C.text2 }}>Doc: {item.afiliado_doc}</div>
                    <div style={{ fontSize:12, color:C.text2 }}>Motivo: {item.motivo}</div>
                  </>
                )}
                {subtab === 'afiliados' && (
                  <>
                    <div style={{ fontSize:12, color:C.blue, fontWeight:600 }}>{item.tipo}</div>
                    <div style={{ fontSize:12, color:C.text2, marginTop:2 }}>{item.descripcion}</div>
                  </>
                )}
                {item.obs && <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>Obs: {item.obs}</div>}
                {item.respuesta && (
                  <div style={{ fontSize:12, color:C.blue, background:C.blueBg, borderRadius:8, padding:'6px 10px', marginTop:8 }}>
                    <strong>✅ Respuesta:</strong> {item.respuesta}
                  </div>
                )}
                <DocsNovedad novedadId={item.id} contexto={subtab==='novedades'?'resp_pago':subtab==='retiros'?'resp_retiro':'resp_afil'} />
                <div style={{ fontSize:11, color:C.text2, marginTop:6 }}>{new Date(item.creado).toLocaleString('es-CO')}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Tab Reportes ──────────────────────────────────────────────────────────────
function TabReportes() {
  const [mes, setMes] = useState(MESES[new Date().getMonth()]);
  const [anio, setAnio] = useState(String(anioActual));
  const [descargando, setDescargando] = useState('');

  const descargar = async (formato) => {
    setDescargando(formato);
    try {
      const params = new URLSearchParams({ mes, anio, formato });
      const res = await api.get(`/portal/reportes?${params}`, { responseType:'blob' });
      const ext  = formato === 'excel' ? 'xlsx' : 'pdf';
      const mime = formato === 'excel'
        ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        : 'application/pdf';
      const url = URL.createObjectURL(new Blob([res.data], { type:mime }));
      const a = document.createElement('a'); a.href = url; a.download = `reporte-afiliados-${mes}-${anio}.${ext}`; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error('Error al generar reporte'); }
    finally { setDescargando(''); }
  };

  const fs = { padding:'7px 10px', border:`1px solid ${C.border}`, borderRadius:8, fontSize:12, outline:'none', color:C.text, background:C.surface, fontFamily:"'Outfit',system-ui,sans-serif" };

  return (
    <div>
      <div className="pcc-card">
        <h4 style={{ margin:'0 0 10px', color:C.primary, fontSize:14, fontWeight:700, fontFamily:"'Outfit',system-ui,sans-serif" }}>Descargar reporte de afiliados por período</h4>
        <p style={{ margin:'0 0 16px', fontSize:13, color:C.text2, lineHeight:1.5, fontFamily:"'Outfit',system-ui,sans-serif" }}>
          El reporte incluye todos sus afiliados con estado de pago, valor y fecha para el período seleccionado.
          Afiliados sin factura en ese período aparecen destacados.
        </p>
        <div style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
          <div>
            <label style={lbl}>Mes</label>
            <select style={fs} value={mes} onChange={e => setMes(e.target.value)}>
              {MESES.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año</label>
            <select style={fs} value={anio} onChange={e => setAnio(e.target.value)}>
              {ANIOS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            <Btn variant="success" onClick={() => descargar('excel')} disabled={!!descargando}>
              {descargando === 'excel' ? 'Generando...' : '⬇ Excel'}
            </Btn>
          </div>
        </div>
      </div>

      <div style={{ display:'flex', gap:16, flexWrap:'wrap', fontSize:12, color:C.text2, fontFamily:"'Outfit',system-ui,sans-serif" }}>
        {[['#D1FAE5','Pagada'],['#FEE2E2','Pendiente'],['#FEF9C3','Sin factura en el período']].map(([bg,label]) => (
          <div key={label} style={{ display:'flex', alignItems:'center', gap:6 }}>
            <span style={{ width:14, height:14, borderRadius:4, background:bg, display:'inline-block' }} />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tab Planillas ─────────────────────────────────────────────────────────────
function TabPlanillas() {
  const [mesFiltro, setMesFiltro] = useState('');
  const [anioFiltro, setAnioFiltro] = useState('');

  const { data: planillas=[], isLoading } = useQuery({
    queryKey: ['portal-planillas', mesFiltro, anioFiltro],
    queryFn: () => api.get('/portal/planillas', { params:{ mes:mesFiltro, anio:anioFiltro } }).then(r => r.data),
    refetchInterval: 120_000,
  });

  const descargar = async (docId, nombre) => {
    try {
      const res = await api.get(`/documentos/${docId}/descargar`);
      if (res.data?.url) {
        const a = document.createElement('a'); a.href = res.data.url; a.download = res.data.nombre || nombre; a.click();
      } else {
        const blob = await api.get(`/documentos/${docId}/descargar`, { responseType:'blob' });
        const url = URL.createObjectURL(blob.data);
        const a = document.createElement('a'); a.href = url; a.download = nombre; a.click(); URL.revokeObjectURL(url);
      }
    } catch { toast.error('Error al descargar'); }
  };

  const fs = { padding:'7px 10px', border:`1px solid ${C.border}`, borderRadius:8, fontSize:12, outline:'none', color:C.text, background:C.surface, fontFamily:"'Outfit',system-ui,sans-serif" };

  return (
    <div>
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <select value={mesFiltro} onChange={e => setMesFiltro(e.target.value)} style={fs}>
          <option value="">Todos los meses</option>
          {MESES.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={anioFiltro} onChange={e => setAnioFiltro(e.target.value)} style={fs}>
          <option value="">Todos los años</option>
          {ANIOS.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        {(mesFiltro || anioFiltro) && (
          <button onClick={() => { setMesFiltro(''); setAnioFiltro(''); }}
            style={{ background:'none', border:'none', cursor:'pointer', color:C.text2, fontSize:12, fontFamily:"'Outfit',system-ui,sans-serif" }}>
            ✕ Limpiar
          </button>
        )}
        <span style={{ fontSize:12, color:C.text2, marginLeft:'auto', fontFamily:"'Outfit',system-ui,sans-serif" }}>
          {isLoading ? 'Cargando...' : `${planillas.length} planilla(s)`}
        </span>
      </div>

      {!isLoading && planillas.length === 0 ? (
        <div className="pcc-empty">
          <div className="pcc-empty-ico">📋</div>
          <div className="pcc-empty-txt">No hay planillas pagadas{mesFiltro||anioFiltro ? ' para el período seleccionado' : ''}</div>
        </div>
      ) : (
        <div className="pcc-hcards">
          {planillas.map(p => (
            <div key={p.id} className="pcc-hcard">
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
                <span style={{ background:C.blueBg, color:C.blue, borderRadius:100, padding:'3px 12px', fontSize:12, fontWeight:700 }}>
                  {p.mes} {p.anio}
                </span>
              </div>
              {p.observaciones && (
                <div style={{ fontSize:12, color:C.text2, marginBottom:8 }}>{p.observaciones}</div>
              )}
              <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                {(p.archivos||[]).map(a => (
                  <div key={a.id} style={{ display:'flex', alignItems:'center', gap:8, fontSize:12, background:C.surface2, padding:'6px 10px', borderRadius:8 }}>
                    <span style={{ color:C.blue, cursor:'pointer', flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', textDecoration:'underline' }}
                      onClick={() => descargar(a.id, a.nombre)}>
                      📄 {a.nombre}
                    </span>
                    <span style={{ color:C.text2, fontSize:10, flexShrink:0 }}>{(a.tamano/1024).toFixed(0)} KB</span>
                  </div>
                ))}
              </div>
              <div style={{ fontSize:11, color:C.text2, marginTop:8 }}>{new Date(p.creado).toLocaleString('es-CO')}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab Avisos ────────────────────────────────────────────────────────────────
function TabAvisos() {
  const qc = useQueryClient();

  const { data: avisos=[], isLoading } = useQuery({
    queryKey: ['portal-avisos'],
    queryFn: () => api.get('/portal/avisos').then(r => r.data),
    refetchInterval: 60_000,
  });

  const marcarLeido = useMutation({
    mutationFn: (id) => api.patch(`/portal/avisos/${id}/leer`),
    onSuccess: (_, id) => qc.setQueryData(['portal-avisos'], prev => prev?.map(a => a.id===id ? { ...a, leido:true } : a)),
  });

  const noLeidos = avisos.filter(a => !a.leido);
  const leidos   = avisos.filter(a =>  a.leido);

  const dlDoc = async (d) => {
    try {
      const res = await api.get(`/documentos/${d.id}/descargar`, { responseType:'blob' });
      if (res.data?.url) { window.open(res.data.url, '_blank'); return; }
      const u = URL.createObjectURL(res.data);
      const el = document.createElement('a'); el.href = u; el.download = d.nombre; el.click(); URL.revokeObjectURL(u);
    } catch { toast.error('Error al descargar'); }
  };

  return (
    <div>
      {isLoading && <p style={{ color:C.text2, fontFamily:"'Outfit',system-ui,sans-serif" }}>Cargando avisos...</p>}
      {!isLoading && avisos.length === 0 && (
        <div className="pcc-empty"><div className="pcc-empty-ico">📭</div><div className="pcc-empty-txt">Sin novedades de tu administrador.</div></div>
      )}
      {noLeidos.length > 0 && (
        <div style={{ marginBottom:20 }}>
          <p className="pcc-slbl">Nuevos ({noLeidos.length})</p>
          {noLeidos.map(a => (
            <div key={a.id} style={{ background:C.blueBg, border:`1px solid ${C.blue}`, borderRadius:12, padding:'16px 20px', marginBottom:10 }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:12 }}>
                <div style={{ flex:1 }}>
                  <div style={{ fontWeight:700, fontSize:14, color:C.text, marginBottom:4, fontFamily:"'Outfit',system-ui,sans-serif" }}>📢 {a.titulo}</div>
                  <div style={{ fontSize:13, color:C.text2, whiteSpace:'pre-wrap', lineHeight:1.5, fontFamily:"'Outfit',system-ui,sans-serif" }}>{a.mensaje}</div>
                  {(a.documentos||[]).length > 0 && (
                    <div style={{ marginTop:10, display:'flex', flexWrap:'wrap', gap:6 }}>
                      {(a.documentos||[]).map(d => (
                        <button key={d.id} onClick={() => dlDoc(d)}
                          style={{ display:'flex', alignItems:'center', gap:4, padding:'4px 10px', background:'rgba(255,255,255,.6)', border:`1px solid ${C.blue}`, borderRadius:8, fontSize:12, color:C.blue, cursor:'pointer', fontWeight:600, fontFamily:"'Outfit',system-ui,sans-serif" }}>
                          📄 {d.nombre}
                        </button>
                      ))}
                    </div>
                  )}
                  <div style={{ fontSize:11, color:C.text2, marginTop:8 }}>{new Date(a.creado).toLocaleString('es-CO')}</div>
                </div>
                <button onClick={() => marcarLeido.mutate(a.id)} disabled={marcarLeido.isPending}
                  style={{ flexShrink:0, padding:'5px 12px', background:C.primary, border:'none', borderRadius:8, color:'#fff', fontSize:12, fontWeight:600, cursor:'pointer', fontFamily:"'Outfit',system-ui,sans-serif" }}>
                  Marcar leído
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {leidos.length > 0 && (
        <div>
          <p className="pcc-slbl">Anteriores</p>
          {leidos.map(a => (
            <div key={a.id} style={{ background:C.surface, border:`1px solid ${C.border}`, borderRadius:12, padding:'12px 16px', marginBottom:8, opacity:.8 }}>
              <div style={{ fontWeight:600, fontSize:13, color:C.text, marginBottom:3, fontFamily:"'Outfit',system-ui,sans-serif" }}>📢 {a.titulo}</div>
              <div style={{ fontSize:12, color:C.text2, whiteSpace:'pre-wrap', lineHeight:1.5, fontFamily:"'Outfit',system-ui,sans-serif" }}>{a.mensaje}</div>
              {(a.documentos||[]).length > 0 && (
                <div style={{ marginTop:8, display:'flex', flexWrap:'wrap', gap:6 }}>
                  {(a.documentos||[]).map(d => (
                    <button key={d.id} onClick={() => dlDoc(d)}
                      style={{ display:'flex', alignItems:'center', gap:4, padding:'4px 10px', background:C.surface2, border:`1px solid ${C.border}`, borderRadius:8, fontSize:12, color:C.text2, cursor:'pointer', fontFamily:"'Outfit',system-ui,sans-serif" }}>
                      📄 {d.nombre}
                    </button>
                  ))}
                </div>
              )}
              <div style={{ fontSize:11, color:C.text2, marginTop:6 }}>{new Date(a.creado).toLocaleString('es-CO')}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Campana de Notificaciones ─────────────────────────────────────────────────
function CampanaNotif() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const { data: notifs=[] } = useQuery({
    queryKey: ['portal-notifs'],
    queryFn: () => api.get('/tareas/notificaciones').then(r => r.data),
    refetchInterval: 60_000,
  });

  const leer = useMutation({
    mutationFn: () => api.put('/tareas/notificaciones/leer'),
    onSuccess: () => qc.setQueryData(['portal-notifs'], prev => prev?.map(n => ({ ...n, leida:true }))),
    onError: (e) => toast.error(e?.response?.data?.detail||'Error al marcar como leídas'),
  });
  const limpiar = useMutation({
    mutationFn: () => api.delete('/tareas/notificaciones'),
    onSuccess: () => { qc.setQueryData(['portal-notifs'], []); setOpen(false); },
    onError: (e) => toast.error(e?.response?.data?.detail||'Error al limpiar notificaciones'),
  });

  const noLeidas = notifs.filter(n => !n.leida).length;

  const handleOpen = () => {
    setOpen(v => !v);
    if (!open && noLeidas > 0) leer.mutate();
  };

  return (
    <div ref={ref} style={{ position:'relative' }}>
      <button onClick={handleOpen} className="pcc-glass" style={{ fontSize:16, padding:'6px 12px', position:'relative' }}>
        🔔
        {noLeidas > 0 && (
          <span style={{ position:'absolute', top:-6, right:-6, background:C.red, color:'#fff', borderRadius:'50%', width:18, height:18, fontSize:10, fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center' }}>
            {noLeidas > 9 ? '9+' : noLeidas}
          </span>
        )}
      </button>
      {open && (
        <div className="pcc-ndrop">
          <div className="pcc-ndrop-hd">
            <span style={{ fontWeight:700, fontSize:14, color:C.text, fontFamily:"'Outfit',system-ui,sans-serif" }}>Notificaciones</span>
            {notifs.length > 0 && (
              <button onClick={() => limpiar.mutate()}
                style={{ background:'none', border:'none', fontSize:11, color:C.text2, cursor:'pointer', fontFamily:"'Outfit',system-ui,sans-serif" }}>
                Limpiar
              </button>
            )}
          </div>
          {notifs.length === 0 ? (
            <p style={{ padding:'20px 16px', color:C.text2, fontSize:13, margin:0, fontFamily:"'Outfit',system-ui,sans-serif" }}>Sin notificaciones.</p>
          ) : notifs.map(n => (
            <div key={n.id} className="pcc-nitem" style={{ background:n.leida ? undefined : C.blueBg }}>
              <div style={{ fontSize:13, color:C.text, lineHeight:1.4, fontFamily:"'Outfit',system-ui,sans-serif" }}>{n.mensaje}</div>
              <div style={{ fontSize:11, color:C.text2, marginTop:4 }}>{new Date(n.creado).toLocaleString('es-CO')}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Portal Principal ──────────────────────────────────────────────────────────
export default function PortalCliente() {
  const { user, logout } = useAuthStore();
  const verDetalle = !!user?.ver_detalle || user?.rol === 'admin';
  const navigate = useNavigate();
  const qc = useQueryClient();

  const handleLogout = () => { logout(); navigate('/login'); };

  const [dark, setDark] = useState(() => localStorage.getItem('theme-portal') === 'dark');
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme-portal', dark ? 'dark' : 'light');
  }, [dark]);

  const [q, setQ] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroEmpresa, setFiltroEmpresa] = useState('');
  const [tab, setTab] = useState('afiliados');
  const [resumenDoc, setResumenDoc] = useState(null);
  const [detalleTexto, setDetalleTexto] = useState(null);   // { nombre, texto } — ver detalle completo
  const [retiroAfil, setRetiroAfil] = useState(null);
  const [novedadAfil, setNovedadAfil] = useState(null);
  const [showNovedadModal, setShowNovedadModal] = useState(false);
  const [pagina, setPagina] = useState(1);
  const POR_PAGINA = 50;
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);

  useEffect(() => {
    const fn = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);

  const { data: afiliados=[], isLoading, isError: isErrorPortal, refetch: refetchPortal } = useQuery({
    queryKey: ['portal-afiliados'],
    queryFn: () => api.get('/portal/afiliados').then(r => r.data),
    refetchInterval: 120_000,
  });

  useEffect(() => {
    const handler = (e) => {
      if (e.key !== 'Escape') return;
      if (detalleTexto) { setDetalleTexto(null); return; }
      if (resumenDoc) { setResumenDoc(null); return; }
      if (showNovedadModal) { setShowNovedadModal(false); return; }
      if (retiroAfil) { setRetiroAfil(null); return; }
      if (novedadAfil) { setNovedadAfil(null); return; }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [detalleTexto, resumenDoc, showNovedadModal, retiroAfil, novedadAfil]);

  const { data: _avisosCount=[] } = useQuery({
    queryKey: ['portal-avisos'],
    queryFn: () => api.get('/portal/avisos').then(r => r.data),
    refetchInterval: 120_000,
  });
  const avisosNoLeidos = _avisosCount.filter(a => !a.leido).length;

  const { data: _novPago=[] }  = useQuery({ queryKey:['portal-novedades'],     queryFn:()=>api.get('/portal/novedades-pago').then(r=>r.data),     refetchInterval:120_000 });
  const { data: _novRetiro=[] } = useQuery({ queryKey:['portal-retiros'],       queryFn:()=>api.get('/portal/solicitudes-retiro').then(r=>r.data), refetchInterval:120_000 });
  const { data: _novAfil=[] }   = useQuery({ queryKey:['portal-novedades-afil'],queryFn:()=>api.get('/portal/solicitudes-novedad').then(r=>r.data),refetchInterval:120_000 });
  const historialPendientes = [..._novPago, ..._novRetiro, ..._novAfil].filter(x => x.estado === 'pendiente').length;
  useAppBadge(avisosNoLeidos + historialPendientes);

  const empresasUnicas = useMemo(() => [...new Set(afiliados.map(a => a.empresa).filter(Boolean))].sort(), [afiliados]);
  const estadosUnicos  = useMemo(() => [...new Set(afiliados.map(a => a.estado).filter(Boolean))].sort(), [afiliados]);

  const filtrados = useMemo(() => afiliados.filter(a => {
    if (q.trim()) {
      const lower = q.toLowerCase();
      if (!a.nombre.toLowerCase().includes(lower) && !a.doc.includes(lower)) return false;
    }
    if (filtroEstado  && a.estado  !== filtroEstado)  return false;
    if (filtroEmpresa && a.empresa !== filtroEmpresa) return false;
    return true;
  }), [afiliados, q, filtroEstado, filtroEmpresa]);

  const limpiarFiltros = () => { setQ(''); setFiltroEstado(''); setFiltroEmpresa(''); setPagina(1); };
  useEffect(() => { setPagina(1); }, [q, filtroEstado, filtroEmpresa]);

  const paginados = useMemo(() => {
    const start = (pagina - 1) * POR_PAGINA;
    return filtrados.slice(start, start + POR_PAGINA);
  }, [filtrados, pagina]);

  const totalPaginas = Math.ceil(filtrados.length / POR_PAGINA);

  const descargarExcel = useCallback(() => {
    api.get('/portal/exportar-excel', { responseType:'blob' })
      .then(r => {
        const url = window.URL.createObjectURL(new Blob([r.data]));
        const a = document.createElement('a'); a.href = url; a.download = 'mis-afiliados.xlsx'; a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => toast.error('Error al exportar Excel'));
  }, []);

  const { activos, suspendidos } = useMemo(() => {
    let act=0, sus=0;
    for (const a of afiliados) {
      if (a.estado==='ACTIVO') act++;
      else if (a.estado==='SUSPENDIDO') sus++;
    }
    return { activos:act, suspendidos:sus };
  }, [afiliados]);

  const TABS_DEF = [
    { id:'afiliados', label:'👥 Mis Afiliados' },
    { id:'historial', label:'📋 Historial',  badge: historialPendientes },
    { id:'planillas', label:'📄 Planillas' },
    { id:'reportes',  label:'📊 Reportes' },
    { id:'avisos',    label:'📩 Novedades', badge: avisosNoLeidos },
  ];

  return (
    <>
      <PortalStyles />
      <div className="pcc">
        {/* ── Header ── */}
        <div className="pcc-hdr">
          <div className="pcc-hdr-in">
            <div className="pcc-topbar">
              <div style={{ display:'flex', alignItems:'baseline' }}>
                <span className="pcc-logo-main">BBC <span style={{ color:C.accent }}>File</span></span>
                <span className="pcc-logo-sub">Portal del Cliente</span>
              </div>
              <div className="pcc-actions">
                <span className="pcc-user">👤 {user?.nombre}</span>
                <CampanaNotif />
                <button onClick={() => setDark(d => !d)} className="pcc-glass" title={dark ? 'Modo claro' : 'Modo oscuro'} style={{ fontSize:15 }}>
                  {dark ? '☀️' : '🌙'}
                </button>
                <button onClick={handleLogout} className="pcc-glass">Salir</button>
              </div>
            </div>

            <div className="pcc-stats">
              {[
                ['Total', afiliados.length, C.accent],
                ['Activos', activos, '#4ade80'],
                ['Suspendidos', suspendidos, '#fcd34d'],
              ].map(([label, val, color]) => (
                <div key={label} className="pcc-stat">
                  <div className="pcc-stat-lbl">{label}</div>
                  <div className="pcc-stat-val" style={{ color }}>{val}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className="pcc-nav">
          <div className="pcc-tabs">
            {TABS_DEF.map(({ id, label, badge }) => (
              <button key={id} className={`pcc-tab${tab===id?' act':''}`} onClick={() => setTab(id)}>
                {label}
                {badge > 0 && (
                  <span className="pcc-tab-dot">{badge > 9 ? '9+' : badge}</span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* ── Body ── */}
        <div className="pcc-body">

          {tab === 'afiliados' && (
            <>
              {/* Filtros */}
              <div className="pcc-filters">
                <div className="pcc-frow">
                  <div className="pcc-fsearch">
                    <span className="pcc-fsrch-ico">🔍</span>
                    <input type="text" placeholder="Nombre o cédula..." value={q} onChange={e => setQ(e.target.value)} className="pcc-fi" />
                  </div>
                  <select className="pcc-fsel" value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}>
                    <option value="">Todos los estados</option>
                    {estadosUnicos.map(e => <option key={e} value={e}>{e}</option>)}
                  </select>
                  <select className="pcc-fsel" value={filtroEmpresa} onChange={e => setFiltroEmpresa(e.target.value)}>
                    <option value="">Todas las empresas</option>
                    {empresasUnicas.map(e => <option key={e} value={e}>{e}</option>)}
                  </select>
                  {(q || filtroEstado || filtroEmpresa) && (
                    <Btn variant="secondary" onClick={limpiarFiltros}>Limpiar filtros</Btn>
                  )}
                  <Btn variant="success" onClick={() => setShowNovedadModal(true)}>📝 Novedad de pago</Btn>
                  <Btn variant="secondary" onClick={descargarExcel}>↓ Excel</Btn>
                </div>
              </div>

              {/* Tabla */}
              {isErrorPortal ? (
                <div style={{ padding:40, textAlign:'center' }}>
                  <p style={{ color:C.red, fontSize:14, margin:'0 0 12px', fontFamily:"'Outfit',system-ui,sans-serif" }}>Error al cargar afiliados</p>
                  <button onClick={refetchPortal} style={{ padding:'6px 16px', border:`1px solid ${C.border}`, borderRadius:8, cursor:'pointer', fontSize:13, background:C.surface2, fontFamily:"'Outfit',system-ui,sans-serif" }}>Reintentar</button>
                </div>
              ) : isLoading ? (
                <div className="pcc-tw" style={{ overflowX:'auto' }}>
                  <table className="pcc-tbl">
                    <thead><tr>
                      {['Nombre','Documento','Empresa','EPS','Estado','Acciones'].map(h => (
                        <th key={h} className="pcc-th">{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {Array.from({length:8}).map((_,i) => (
                        <tr key={i} className="pcc-tr">
                          {[160,110,100,80,70,70].map((w,j) => (
                            <td key={j} className="pcc-td">
                              <span className="pcc-skel" style={{ width:w, height:11 }}>&nbsp;</span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : filtrados.length === 0 ? (
                <div className="pcc-empty">
                  <div className="pcc-empty-ico">🔍</div>
                  <div className="pcc-empty-txt">{q ? `Sin resultados para "${q}"` : 'No hay afiliados registrados.'}</div>
                </div>
              ) : (
                <div className="pcc-tw" style={{ overflowX:'auto' }}>
                  <table className="pcc-tbl">
                    <thead>
                      <tr>
                        {(isMobile
                          ? ['Nombre','Empresa','EPS','Estado','Acciones']
                          : ['Nombre','Documento','Empresa','EPS','AFP','CCF','Estado', ...(verDetalle ? ['Detalle'] : []), 'Acciones']
                        ).map(h => <th key={h} className="pcc-th">{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {paginados.map(a => {
                        const estadoBg = a.estado==='ACTIVO' ? C.greenBg : C.redBg;
                        const estadoC  = a.estado==='ACTIVO' ? C.green : C.red;
                        return (
                          <tr key={a.id} className="pcc-tr">
                            <td className="pcc-td">
                              <span style={{ fontWeight:600, fontSize:isMobile?12:13, whiteSpace:isMobile?'nowrap':undefined, overflow:'hidden', textOverflow:'ellipsis', display:'block', maxWidth:isMobile?120:undefined }}>
                                {a.nombre}
                              </span>
                            </td>
                            {!isMobile && (
                              <td className="pcc-td">
                                <span style={{ fontSize:10, fontWeight:700, color:C.text2, textTransform:'uppercase', letterSpacing:'.05em', display:'block', lineHeight:1 }}>{a.tipo_doc}</span>
                                <span style={{ fontWeight:700, fontSize:13, color:C.text, fontFamily:"'Outfit',system-ui,sans-serif", letterSpacing:'.02em' }}>{a.doc}</span>
                              </td>
                            )}
                            <td className="pcc-td"><EmpresaBadge nombre={a.empresa} /></td>
                            <td className="pcc-td">
                              {a.eps
                                ? <span style={{ background:C.blueBg, color:C.blue, borderRadius:100, padding:'2px 9px', fontSize:11, fontWeight:700, whiteSpace:'nowrap' }}>{a.eps}</span>
                                : <span style={{ color:C.text2 }}>—</span>}
                            </td>
                            {!isMobile && <td className="pcc-td">{a.afp||'—'}</td>}
                            {!isMobile && <td className="pcc-td">{a.ccf||'—'}</td>}
                            <td className="pcc-td"><ColorBadge color={estadoC} bg={estadoBg}>{a.estado}</ColorBadge></td>
                            {!isMobile && verDetalle && (
                              <td className="pcc-td">
                                {a.detalle ? (
                                  <div style={{ display:'flex', alignItems:'center', gap:6, maxWidth:230 }}>
                                    <span style={{ fontSize:13, color:C.text, fontWeight:500, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }} title={a.detalle}>{a.detalle}</span>
                                    {a.detalle.length > 30 && (
                                      <button onClick={() => setDetalleTexto({ nombre:a.nombre, texto:a.detalle })}
                                        style={{ flexShrink:0, background:C.blueBg, color:C.blue, border:`1px solid ${C.blue}`, borderRadius:6, padding:'2px 8px', fontSize:11, fontWeight:700, cursor:'pointer', whiteSpace:'nowrap' }}>
                                        ver
                                      </button>
                                    )}
                                  </div>
                                ) : <span style={{ color:C.text2 }}>—</span>}
                              </td>
                            )}
                            <td className="pcc-td">
                              <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
                                <Btn size="sm" onClick={() => setResumenDoc(a.doc)}>Ver</Btn>
                                {!isMobile && <Btn size="sm" variant="accent" onClick={() => setNovedadAfil(a)}>Novedad</Btn>}
                                {!isMobile && <Btn size="sm" variant="danger" onClick={() => setRetiroAfil(a)}>Retiro</Btn>}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {totalPaginas > 1 && (
                <div className="pcc-pager">
                  <Btn variant="secondary" size="sm" onClick={() => setPagina(p => Math.max(1,p-1))} disabled={pagina===1}>← Anterior</Btn>
                  <span className="pcc-pager-i">{isMobile ? `${pagina}/${totalPaginas}` : `Página ${pagina} de ${totalPaginas} (${filtrados.length} afiliados)`}</span>
                  <Btn variant="secondary" size="sm" onClick={() => setPagina(p => Math.min(totalPaginas,p+1))} disabled={pagina===totalPaginas}>Siguiente →</Btn>
                </div>
              )}

              {/* Redes sociales */}
              <div style={{ marginTop:36, textAlign:'center', paddingBottom:24 }}>
                <p style={{ fontSize:11, letterSpacing:'0.15em', textTransform:'uppercase', color:'#1877F2', fontWeight:700, margin:'0 0 14px', fontFamily:"'Outfit',system-ui,sans-serif" }}>
                  Síguenos en Facebook
                </p>
                <div style={{ display:'flex', justifyContent:'center', gap:10, flexWrap:'wrap', marginBottom:16 }}>
                  {[
                    { href:'https://www.facebook.com/TechPlanetEsal',                        label:'Techplanet' },
                    { href:'https://www.facebook.com/profile.php?id=61584899039203',         label:'Protsecoop' },
                    { href:'https://www.facebook.com/profile.php?id=61586640354662',         label:'Carsecoop'  },
                  ].map(({ href, label }) => (
                    <a key={label} href={href} target="_blank" rel="noreferrer"
                      style={{ position:'relative', width:108, height:44, overflow:'hidden',
                        background:'#fff', borderRadius:10, textDecoration:'none',
                        display:'inline-flex', alignItems:'center', justifyContent:'center',
                        boxShadow:'inset -6px 0 12px -8px rgba(0,0,0,.35), inset 6px 0 12px -8px rgba(0,0,0,.35)', cursor:'pointer' }}
                      onMouseEnter={e => {
                        e.currentTarget.querySelectorAll('.p-fb-top').forEach(el => el.style.top='-50%');
                        e.currentTarget.querySelectorAll('.p-fb-bot').forEach(el => el.style.top='100%');
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.querySelectorAll('.p-fb-top').forEach(el => el.style.top='0');
                        e.currentTarget.querySelectorAll('.p-fb-bot').forEach(el => el.style.top='50%');
                      }}
                    >
                      <div className="p-fb-top" style={{ position:'absolute', left:0, top:0, width:'100%', height:'50%', background:'#0D3B6E', overflow:'hidden', zIndex:2, transition:'top 400ms ease-in-out' }}>
                        <img src="/facebook-f.svg" alt="" style={{ position:'absolute', height:22, width:'auto', left:'50%', transform:'translateX(-50%)', top:11, pointerEvents:'none' }} />
                      </div>
                      <div className="p-fb-bot" style={{ position:'absolute', left:0, top:'50%', width:'100%', height:'50%', background:'#0D3B6E', overflow:'hidden', zIndex:2, transition:'top 400ms ease-in-out' }}>
                        <img src="/facebook-f.svg" alt="" style={{ position:'absolute', height:22, width:'auto', left:'50%', transform:'translateX(-50%)', top:-11, pointerEvents:'none' }} />
                      </div>
                      <span style={{ position:'relative', zIndex:1, color:'#1877F2', fontSize:13, fontWeight:700, letterSpacing:.3, fontFamily:"'Outfit',system-ui,sans-serif" }}>{label}</span>
                    </a>
                  ))}
                </div>
                <p style={{ fontSize:12.5, color:'#1877F2', letterSpacing:.3, fontFamily:"'Outfit',system-ui,sans-serif", margin:0 }}>
                  Copyright © 2026 — "BBC File" Todos los derechos reservados
                </p>
              </div>
            </>
          )}

          {tab === 'historial' && <TabHistorial />}
          {tab === 'planillas' && <TabPlanillas />}
          {tab === 'reportes'  && <TabReportes />}
          {tab === 'avisos'    && <TabAvisos />}

        </div>

        {/* Modales */}
        {resumenDoc && <ModalResumen doc={resumenDoc} onClose={() => setResumenDoc(null)} />}

        {detalleTexto && (
          <div className="pcc-ov" onClick={() => setDetalleTexto(null)}>
            <div className="pcc-modal" style={{ width:480, maxWidth:'100%' }} onClick={e => e.stopPropagation()}>
              <div className="pcc-mhd">
                <h3 className="pcc-mtitle">Detalle — {detalleTexto.nombre}</h3>
                <button className="pcc-mx" onClick={() => setDetalleTexto(null)}>×</button>
              </div>
              <div style={{ fontSize:14, color:C.text, whiteSpace:'pre-wrap', wordBreak:'break-word', lineHeight:1.6 }}>
                {detalleTexto.texto}
              </div>
            </div>
          </div>
        )}

        {showNovedadModal && (
          <ModalNovedadPago
            afiliados={afiliados}
            onClose={() => setShowNovedadModal(false)}
            onSuccess={() => qc.invalidateQueries({ queryKey: ['portal-novedades'] })}
          />
        )}

        {retiroAfil && (
          <ModalRetiro
            afiliado={retiroAfil}
            onClose={() => setRetiroAfil(null)}
            onSuccess={() => qc.invalidateQueries({ queryKey:['portal-retiros'] })}
          />
        )}

        {novedadAfil && (
          <ModalNovedadAfiliado
            afiliado={novedadAfil}
            onClose={() => setNovedadAfil(null)}
            onSuccess={() => qc.invalidateQueries({ queryKey:['portal-novedades-afil'] })}
          />
        )}
      </div>
    </>
  );
}
