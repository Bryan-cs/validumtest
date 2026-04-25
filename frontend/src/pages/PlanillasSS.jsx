import React, { useState, useRef, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Card, Btn, ConfirmModal } from '../components/UI';
import useAuthStore from '../hooks/useAuth';

const MESES = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear();
const ANIOS = ['', String(anioActual - 1), String(anioActual), String(anioActual + 1)];

const sel = { padding: '8px 12px', border: `1px solid ${C.border}`, borderRadius: 7,
  fontSize: 13, outline: 'none', background: C.surface, color: C.text };

export default function PlanillasSS() {
  const qc = useQueryClient();
  const rol = useAuthStore(s => s.user?.rol);
  const [filtroCliente, setFiltroCliente] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_planillas_filtros'))?.filtroCliente ?? ''; } catch { return ''; } });
  const [filtroMes, setFiltroMes] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_planillas_filtros'))?.filtroMes ?? ''; } catch { return ''; } });
  const [filtroAnio, setFiltroAnio] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_planillas_filtros'))?.filtroAnio ?? ''; } catch { return ''; } });

  useEffect(() => { try { localStorage.setItem('bbc_planillas_filtros', JSON.stringify({ filtroCliente, filtroMes, filtroAnio })); } catch {} }, [filtroCliente, filtroMes, filtroAnio]);
  const [showModal, setShowModal] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);

  const { data: planillas = [], isLoading } = useQuery({
    queryKey: ['planillas', filtroCliente, filtroMes, filtroAnio],
    queryFn: () => api.get('/planillas', { params: { cliente: filtroCliente, mes: filtroMes, anio: filtroAnio } }).then(r => r.data.items || []),
  });

  const { data: clientes = [] } = useQuery({
    queryKey: ['clientes-lista'],
    queryFn: () => api.get('/clientes').then(r => r.data),
    staleTime: 300_000,
  });

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await api.delete(`/planillas/${confirmDel}`);
      qc.invalidateQueries({ queryKey: ['planillas'] });
      toast.success('Planilla eliminada');
    } catch { toast.error('Error al eliminar'); }
    setConfirmDel(null);
  };

  const descargarArchivo = async (docId, nombre) => {
    try {
      const res = await api.get(`/documentos/${docId}/descargar`);
      const presigned = res.data?.url;
      if (presigned) {
        const a = document.createElement('a');
        a.href = presigned;
        a.download = nombre;
        a.click();
      } else {
        // fallback local dev (blob directo)
        const r2 = await api.get(`/documentos/${docId}/descargar`, { responseType: 'blob' });
        const url = URL.createObjectURL(r2.data);
        const a = document.createElement('a');
        a.href = url;
        a.download = nombre;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { toast.error('Error al descargar'); }
  };

  return (
    <div>
      <PageHeader
        title="Planillas de Seguridad Social"
        subtitle="Adjunta y gestiona las planillas de pago SS por cliente"
        action={<Btn onClick={() => setShowModal(true)}>+ Subir planilla</Btn>}
      />

      {/* Filtros */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>CLIENTE</label>
            <select style={{ ...sel, minWidth: 180 }} value={filtroCliente} onChange={e => setFiltroCliente(e.target.value)}>
              <option value="">Todos los clientes</option>
              {clientes.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>MES</label>
            <select style={sel} value={filtroMes} onChange={e => setFiltroMes(e.target.value)}>
              {MESES.map(m => <option key={m} value={m}>{m || 'Todos'}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>AÑO</label>
            <select style={sel} value={filtroAnio} onChange={e => setFiltroAnio(e.target.value)}>
              {ANIOS.map(a => <option key={a} value={a}>{a || 'Todos'}</option>)}
            </select>
          </div>
          {(filtroCliente || filtroMes || filtroAnio) && (
            <Btn variant="secondary" onClick={() => { setFiltroCliente(''); setFiltroMes(''); setFiltroAnio(''); }}>↺ Limpiar</Btn>
          )}
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: C.text2 }}>
          {isLoading ? 'Cargando...' : <><strong style={{ color: C.primary }}>{planillas.length}</strong> planilla{planillas.length !== 1 ? 's' : ''}</>}
        </div>
      </Card>

      {/* Lista */}
      {planillas.length === 0 && !isLoading ? (
        <Card style={{ textAlign: 'center', padding: 40, color: C.text2 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>📋</div>
          No hay planillas para los filtros seleccionados
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
          {planillas.map(p => (
            <Card key={p.id} style={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14, color: C.primary }}>{p.cliente_ref}</div>
                  <div style={{ fontSize: 13, color: C.text, marginTop: 2 }}>
                    <span style={{ background: C.blueBg, color: C.blue, borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                      {p.mes} {p.anio}
                    </span>
                  </div>
                </div>
                {rol === 'admin' && <Btn variant="danger" size="sm" onClick={() => setConfirmDel(p.id)}>Eliminar</Btn>}
              </div>
              {p.observaciones && (
                <div style={{ fontSize: 12, color: C.text2, marginBottom: 8 }}>{p.observaciones}</div>
              )}
              {/* Archivos */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {(p.archivos || []).map(a => (
                  <div key={a.id} style={{
                    display: 'flex', alignItems: 'center', gap: 8, fontSize: 12,
                    background: C.surface2, padding: '6px 10px', borderRadius: 6,
                  }}>
                    <span style={{ color: C.blue, cursor: 'pointer', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      onClick={() => descargarArchivo(a.id, a.nombre)}>
                      📄 {a.nombre}
                    </span>
                    <span style={{ color: C.text2, fontSize: 10, flexShrink: 0 }}>{(a.tamano / 1024).toFixed(0)} KB</span>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 11, color: C.text2, marginTop: 8 }}>
                Subido por {p.subido_por} — {new Date(p.creado).toLocaleString('es-CO')}
              </div>
            </Card>
          ))}
        </div>
      )}

      {showModal && <ModalSubirPlanilla clientes={clientes} onClose={() => setShowModal(false)}
        onSuccess={() => { qc.invalidateQueries({ queryKey: ['planillas'] }); setShowModal(false); }} />}

      <ConfirmModal
        open={!!confirmDel}
        title="Eliminar planilla"
        message="Se eliminará esta planilla y sus archivos adjuntos. Esta acción no se puede deshacer."
        confirmLabel="Eliminar"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}

const MESES_NUM = { 'Enero':1,'Febrero':2,'Marzo':3,'Abril':4,'Mayo':5,'Junio':6,
  'Julio':7,'Agosto':8,'Septiembre':9,'Octubre':10,'Noviembre':11,'Diciembre':12 };

const ARL_OPCIONES = [
  'POSITIVA','SURA','AXA COLPATRIA','LIBERTY','BOLIVAR','EQUIDAD','MAPFRE','QBE'
];

function ModalGenerarPila({ onClose }) {
  const [empresa, setEmpresa] = useState('');
  const [nit, setNit] = useState('');
  const [dv, setDv] = useState('0');
  const [razonSocial, setRazonSocial] = useState('');
  const [mes, setMes] = useState(MESES[new Date().getMonth() + 1] || 'Enero');
  const [anio, setAnio] = useState(String(anioActual));
  const [arl, setArl] = useState('POSITIVA');
  const [generando, setGenerando] = useState(false);

  const { data: empresas = [] } = useQuery({
    queryKey: ['empresas-lista-pila'],
    queryFn: () => api.get('/afiliados/filter-options').then(r => r.data.empresas || []),
    staleTime: 300_000,
  });

  const handleGenerar = async () => {
    if (!empresa) { toast.error('Selecciona una empresa'); return; }
    if (!nit) { toast.error('Ingresa el NIT'); return; }
    const mesNum = MESES_NUM[mes] || 1;
    setGenerando(true);
    try {
      const res = await api.get('/reportes/pila', {
        params: {
          empresa,
          nit: nit.replace(/[^0-9]/g, ''),
          razon_social: razonSocial || empresa,
          dv,
          mes: mesNum,
          anio: parseInt(anio),
          arl,
        },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/plain' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `PILA_${empresa.toUpperCase().replace(/\s+/g, '_')}_${anio}${String(mesNum).padStart(2,'0')}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Archivo PILA generado — verificar antes de envío oficial');
      onClose();
    } catch (e) {
      const msg = e?.response?.data?.detail || 'Error al generar PILA';
      toast.error(typeof msg === 'string' ? msg : 'Error al generar PILA');
    }
    setGenerando(false);
  };

  const inp = { width: '100%', padding: '8px 10px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, boxSizing: 'border-box', outline: 'none', color: C.text, background: C.surface };
  const lbl = { fontSize: 12, fontWeight: 600, color: C.text2, display: 'block', marginBottom: 4 };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: C.surface, borderRadius: 14, padding: 28, width: 480, boxShadow: '0 20px 60px rgba(0,0,0,.3)', maxHeight: '90vh', overflowY: 'auto' }}>
        <h3 style={{ margin: '0 0 4px', color: C.primary, fontSize: 16 }}>Generar Archivo PILA</h3>
        <p style={{ margin: '0 0 18px', fontSize: 12, color: C.text2 }}>
          Genera el archivo de ancho fijo para el sistema PILA. Verifica los valores antes de envío oficial.
        </p>

        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Empresa aportante *</label>
          <select style={inp} value={empresa} onChange={e => { setEmpresa(e.target.value); setRazonSocial(e.target.value); }}>
            <option value="">— Seleccionar empresa —</option>
            {empresas.map(e => <option key={e} value={e}>{e}</option>)}
          </select>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={lbl}>NIT (sin dígito verificación) *</label>
            <input style={inp} type="text" value={nit} onChange={e => setNit(e.target.value.replace(/[^0-9]/g, ''))} placeholder="901760008" maxLength={9} />
          </div>
          <div>
            <label style={lbl}>D.V.</label>
            <input style={inp} type="text" value={dv} onChange={e => setDv(e.target.value.replace(/[^0-9]/g, ''))} maxLength={1} />
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Razón social (opcional — si difiere del nombre empresa)</label>
          <input style={inp} type="text" value={razonSocial} onChange={e => setRazonSocial(e.target.value)} placeholder={empresa || 'Razón social exacta'} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={lbl}>Mes del período *</label>
            <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
              {MESES.filter(Boolean).map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año *</label>
            <select style={inp} value={anio} onChange={e => setAnio(e.target.value)}>
              {ANIOS.filter(Boolean).map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>

        <div style={{ marginBottom: 18 }}>
          <label style={lbl}>ARL del aportante</label>
          <select style={inp} value={arl} onChange={e => setArl(e.target.value)}>
            {ARL_OPCIONES.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8, padding: '10px 14px', marginBottom: 18, fontSize: 12, color: C.text2 }}>
          ⚠️ <strong>Borrador</strong> — Este archivo es generado con los datos actuales de afiliados activos en la empresa seleccionada. Valida los montos y códigos antes de enviar al sistema PILA oficial.
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn onClick={handleGenerar} disabled={generando || !empresa || !nit}>
            {generando ? 'Generando...' : 'Descargar PILA .txt'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

function ModalSubirPlanilla({ clientes, onClose, onSuccess }) {
  const [cliente, setCliente] = useState('');
  const [mes, setMes] = useState(MESES[new Date().getMonth() + 1] || 'Enero');
  const [anio, setAnio] = useState(String(anioActual));
  const [obs, setObs] = useState('');
  const [archivos, setArchivos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);
  const fileRef = useRef(null);

  const handleSubmit = async () => {
    if (subiendo) return;  // guard doble-click / race condition de render
    if (!cliente) { toast.error('Selecciona un cliente'); return; }
    if (archivos.length === 0) { toast.error('Adjunta al menos un archivo'); return; }
    setSubiendo(true);
    try {
      const fd = new FormData();
      fd.append('cliente_ref', cliente);
      fd.append('mes', mes);
      fd.append('anio', anio);
      fd.append('observaciones', obs);
      archivos.forEach(f => fd.append('files', f));
      const res = await api.post('/planillas', fd);
      const { archivos: guardados = [], omitidos = [] } = res.data;
      if (omitidos.length === 0) {
        toast.success(`Planilla subida — ${guardados.length} archivo${guardados.length !== 1 ? 's' : ''} guardado${guardados.length !== 1 ? 's' : ''}`);
      } else if (guardados.length === 0) {
        toast.error(`No se guardó ningún archivo. ${omitidos.length} omitido${omitidos.length !== 1 ? 's' : ''}: ${omitidos.map(o => o.nombre).join(', ')}`);
        setSubiendo(false);
        return;
      } else {
        toast.success(`${guardados.length} archivo${guardados.length !== 1 ? 's' : ''} guardado${guardados.length !== 1 ? 's' : ''}`);
        toast.error(`${omitidos.length} omitido${omitidos.length !== 1 ? 's' : ''}: ${omitidos.map(o => `${o.nombre} (${o.motivo})`).join(' | ')}`, { duration: 8000 });
      }
      onSuccess();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al subir planilla');
    }
    setSubiendo(false);
  };

  const inp = { width: '100%', padding: '8px 10px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, boxSizing: 'border-box', outline: 'none', color: C.text, background: C.surface };
  const lbl = { fontSize: 12, fontWeight: 600, color: C.text2, display: 'block', marginBottom: 4 };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: C.surface, borderRadius: 14, padding: 28, width: 500, boxShadow: '0 20px 60px rgba(0,0,0,.3)', maxHeight: '90vh', overflowY: 'auto' }}>
        <h3 style={{ margin: '0 0 16px', color: C.primary, fontSize: 16 }}>Subir Planilla de Pago SS</h3>

        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Cliente *</label>
          <select style={inp} value={cliente} onChange={e => setCliente(e.target.value)}>
            <option value="">— Seleccionar cliente —</option>
            {clientes.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={lbl}>Mes *</label>
            <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
              {MESES.filter(Boolean).map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año *</label>
            <select style={inp} value={anio} onChange={e => setAnio(e.target.value)}>
              {ANIOS.filter(Boolean).map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Observaciones (opcional)</label>
          <textarea style={{ ...inp, resize: 'vertical', minHeight: 60 }} value={obs} onChange={e => setObs(e.target.value)} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={lbl}>Archivos de planilla *</label>
          <label htmlFor="planilla-file-input" style={{
            display: 'block', border: `2px dashed ${C.border}`, borderRadius: 8, padding: 14,
            textAlign: 'center', background: C.surface2, cursor: 'pointer',
          }}>
            <input id="planilla-file-input" ref={fileRef} type="file" multiple
              accept=".pdf,.jpg,.jpeg,.png,.xls,.xlsx"
              style={{ display: 'none' }}
              onChange={e => {
                const nuevos = Array.from(e.target.files || []);
                if (nuevos.length) setArchivos(prev => [...prev, ...nuevos]);
                e.target.value = '';
              }} />
            <div style={{ fontSize: 13, color: C.text2 }}>📂 Click para seleccionar archivos</div>
          </label>
          {archivos.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {archivos.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: C.text,
                  background: C.surface2, padding: '4px 8px', borderRadius: 6,
                }}>
                  <span style={{ flex: 1 }}>📄 {f.name} ({(f.size / 1024).toFixed(0)} KB)</span>
                  <span style={{ cursor: 'pointer', color: C.red, fontWeight: 700 }}
                    onClick={e => { e.preventDefault(); setArchivos(prev => prev.filter((_, j) => j !== i)); }}>×</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn onClick={handleSubmit} disabled={subiendo || !cliente || archivos.length === 0}>
            {subiendo ? 'Subiendo...' : 'Subir planilla'}
          </Btn>
        </div>
      </div>
    </div>
  );
}
