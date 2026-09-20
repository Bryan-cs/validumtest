import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Btn, Modal, ConfirmModal, ErrorMsg, SkeletonCard } from '../components/UI';
import useAuthStore from '../hooks/useAuth';

const TIPOS_DOC = ['NI', 'CC', 'CE', 'TI', 'PA'];
const CLASES_RIESGO = ['1', '2', '3', '4', '5'];

const RIESGO_STYLE = {
  '1': { bg: '#ECFDF5', color: '#059669' },
  '2': { bg: '#EFF6FF', color: '#2563EB' },
  '3': { bg: '#FFFBEB', color: '#D97706' },
  '4': { bg: '#FFF7ED', color: '#EA580C' },
  '5': { bg: '#FEF2F2', color: '#DC2626' },
};

const EMPTY_FORM = {
  cliente_ref: '', razon_social: '', tipo_doc: 'NI', num_doc: '', dv: '',
  tipo_persona: 'J', tipo_aportante: '01', clase_aportante: '', cod_arl: '',
  clase_riesgo: '', actividad_economica: '', cod_depto: '', cod_municipio: '',
  cod_sucursal: '', nombre_sucursal: '', exonerado_parafiscales: false,
  direccion: '', telefono: '', email: '',
};

const lbl = {
  fontSize: 11, fontWeight: 700, color: C.text2, textTransform: 'uppercase',
  letterSpacing: '0.05em', marginBottom: 4, display: 'block',
};
const inp = {
  padding: '9px 12px', borderRadius: 8, border: `1px solid ${C.border}`,
  background: C.surface, fontSize: 13, color: C.text, outline: 'none',
  fontFamily: 'inherit', width: '100%', boxSizing: 'border-box',
};
const mono = { ...inp, fontFamily: 'monospace' };
const seccion = {
  fontSize: 11, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
  color: C.text2, margin: '18px 0 10px', paddingBottom: 6,
  borderBottom: `1px solid ${C.border}`,
};

// Los catálogos son normativos: no cambian dentro de una sesión.
const CATALOGO_OPTS = { staleTime: 60 * 60 * 1000 };

function useCatalogo(tipo, padre) {
  return useQuery({
    queryKey: ['pila-codigos', tipo, padre || null],
    queryFn: async () => {
      const qs = padre ? `?tipo=${tipo}&padre=${padre}` : `?tipo=${tipo}`;
      return (await api.get(`/pila/codigos${qs}`)).data.items;
    },
    enabled: padre !== null,
    ...CATALOGO_OPTS,
  });
}

function RiesgoBadge({ clase }) {
  if (!clase) return null;
  const s = RIESGO_STYLE[clase] || { bg: '#F3F4F6', color: '#6B7280' };
  return (
    <span style={{
      fontSize: 10, fontWeight: 800, padding: '3px 8px', borderRadius: 4,
      background: s.bg, color: s.color, fontFamily: 'monospace', whiteSpace: 'nowrap',
    }}>
      RIESGO {clase}
    </span>
  );
}

function Campo({ label, children, ancho }) {
  return (
    <div style={{ gridColumn: ancho ? `span ${ancho}` : undefined }}>
      <label style={lbl}>{label}</label>
      {children}
    </div>
  );
}

export default function Aportantes() {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const isAdmin = user?.rol === 'admin';

  const [busqueda, setBusqueda] = useState('');
  const [soloActivos, setSoloActivos] = useState(true);
  const [modal, setModal] = useState(false);
  const [editando, setEditando] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [porBorrar, setPorBorrar] = useState(null);

  // Todo lo que antes era texto libre ahora sale de `pila_codigos`: los tipos de
  // aportante del anexo, las ARL de la lista de la UGPP y los códigos DANE.
  const { data: tiposAportante = [] } = useCatalogo('TIPO_APORTANTE');
  const { data: arls = [] } = useCatalogo('ARL');
  const { data: deptos = [] } = useCatalogo('DEPTO');
  // Los 1.122 municipios no se traen de una: solo los del departamento elegido.
  const { data: municipios = [] } = useCatalogo('MUNICIPIO', form.cod_depto || null);

  const { data: aportantes = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['aportantes'],
    queryFn: async () => (await api.get('/aportantes')).data,
  });

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return aportantes.filter(a => {
      if (soloActivos && !a.activo) return false;
      if (!q) return true;
      return [a.razon_social, a.cliente_ref, a.num_doc]
        .some(v => (v || '').toLowerCase().includes(q));
    });
  }, [aportantes, busqueda, soloActivos]);

  const set = (campo, valor) => setForm(f => ({ ...f, [campo]: valor }));

  // Cambiar de departamento invalida el municipio: el código DANE de municipio
  // solo tiene sentido dentro de su departamento.
  const setDepto = (valor) => setForm(f => ({ ...f, cod_depto: valor, cod_municipio: '' }));

  // El DV lo calcula el backend con el algoritmo de la DIAN. Se pide al salir
  // del campo para que el usuario lo vea antes de guardar, no después de que
  // el operador rechace la planilla.
  const completarDv = async () => {
    const nit = (form.num_doc || '').replace(/\D/g, '');
    if (form.tipo_doc !== 'NI' || !nit) return;
    try {
      const { data } = await api.get(`/aportantes/dv/${nit}`);
      setForm(f => ({ ...f, num_doc: data.num_doc, dv: data.dv }));
    } catch {
      /* si falla, el backend igual lo calcula al guardar */
    }
  };

  const abrirNuevo = () => { setEditando(null); setForm(EMPTY_FORM); setModal(true); };

  const abrirEditar = (a) => {
    setEditando(a);
    setForm({
      ...EMPTY_FORM,
      ...Object.fromEntries(Object.entries(a).map(([k, v]) => [k, v ?? ''])),
      exonerado_parafiscales: !!a.exonerado_parafiscales,
    });
    setModal(true);
  };

  const guardar = useMutation({
    mutationFn: async () => {
      const payload = { ...form };
      delete payload.id; delete payload.nit_completo;
      delete payload.creado; delete payload.actualizado; delete payload.afiliados;
      // El backend distingue null de cadena vacía: mandar '' pisaría el dato.
      Object.keys(payload).forEach(k => { if (payload[k] === '') delete payload[k]; });
      if (editando) return (await api.put(`/aportantes/${editando.id}`, payload)).data;
      return (await api.post('/aportantes', payload)).data;
    },
    onSuccess: () => {
      toast.success(editando ? 'Aportante actualizado' : 'Aportante creado');
      qc.invalidateQueries({ queryKey: ['aportantes'] });
      setModal(false);
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'No se pudo guardar'),
  });

  const borrar = useMutation({
    mutationFn: async (id) => (await api.delete(`/aportantes/${id}`)).data,
    onSuccess: () => {
      toast.success('Aportante eliminado');
      qc.invalidateQueries({ queryKey: ['aportantes'] });
      setPorBorrar(null);
    },
    onError: (e) => {
      toast.error(e?.response?.data?.detail || 'No se pudo eliminar');
      setPorBorrar(null);
    },
  });

  if (isError) return <ErrorMsg message="Error al cargar aportantes" onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Aportantes"
        subtitle="Empresas que pagan aportes — datos del encabezado de la planilla PILA"
        action={<Btn onClick={abrirNuevo}>+ Nuevo aportante</Btn>}
      />

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          style={{ ...inp, maxWidth: 320 }}
          placeholder="Buscar por razón social, cliente o NIT…"
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: C.text2 }}>
          <input type="checkbox" checked={soloActivos} onChange={e => setSoloActivos(e.target.checked)} />
          Solo activos
        </label>
        <span style={{ fontSize: 12, color: C.text2, marginLeft: 'auto' }}>
          {visibles.length} de {aportantes.length}
        </span>
      </div>

      {isLoading ? (
        <div style={{ display: 'grid', gap: 10 }}>
          {[1, 2, 3].map(i => <SkeletonCard key={i} height={90} />)}
        </div>
      ) : visibles.length === 0 ? (
        <div style={{
          padding: 40, textAlign: 'center', color: C.text2, fontSize: 14,
          border: `1px dashed ${C.border}`, borderRadius: 10,
        }}>
          {aportantes.length === 0
            ? 'Todavía no hay aportantes. Crea el primero para poder liquidar planillas.'
            : 'Ningún aportante coincide con la búsqueda.'}
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 10 }}>
          {visibles.map(a => (
            <div key={a.id} style={{
              border: `1px solid ${C.border}`, borderRadius: 10, padding: 14,
              background: C.surface, opacity: a.activo ? 1 : 0.6,
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <div style={{ fontWeight: 700, fontSize: 15, color: C.text }}>
                    {a.razon_social}
                  </div>
                  <div style={{ fontFamily: 'monospace', fontSize: 12, color: C.text2, marginTop: 2 }}>
                    {a.tipo_doc} {a.nit_completo}
                  </div>
                  <div style={{ fontSize: 12, color: C.text2, marginTop: 4 }}>
                    Cliente: <strong>{a.cliente_ref}</strong>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                  {a.tipo_aportante && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                      background: '#F3F4F6', color: '#4B5563', fontFamily: 'monospace',
                    }}>
                      TIPO {a.tipo_aportante}
                    </span>
                  )}
                  <RiesgoBadge clase={a.clase_riesgo} />
                  {a.exonerado_parafiscales && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                      background: '#F5F3FF', color: '#7C3AED',
                    }}>
                      EXONERADO 114-1
                    </span>
                  )}
                  {!a.activo && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                      background: '#F3F4F6', color: '#6B7280',
                    }}>
                      INACTIVO
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 6 }}>
                  <Btn size="sm" variant="secondary" onClick={() => abrirEditar(a)}>Editar</Btn>
                  {isAdmin && (
                    <Btn size="sm" variant="danger" onClick={() => setPorBorrar(a)}>Eliminar</Btn>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editando ? 'Editar aportante' : 'Nuevo aportante'}
        width={720}
      >
        <div style={seccion}>Identificación</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <Campo label="Cliente (enlace con afiliados)" ancho={2}>
            <input style={inp} value={form.cliente_ref}
                   onChange={e => set('cliente_ref', e.target.value)}
                   placeholder="Igual al cliente del afiliado" />
          </Campo>
          <Campo label="Razón social" ancho={2}>
            <input style={inp} value={form.razon_social}
                   onChange={e => set('razon_social', e.target.value)} />
          </Campo>
          <Campo label="Tipo doc.">
            <select style={inp} value={form.tipo_doc} onChange={e => set('tipo_doc', e.target.value)}>
              {TIPOS_DOC.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </Campo>
          <Campo label="Número">
            <input style={mono} value={form.num_doc} onBlur={completarDv}
                   onChange={e => set('num_doc', e.target.value)} />
          </Campo>
          <Campo label="DV">
            <input style={{ ...mono, background: '#F9FAFB' }} value={form.dv}
                   onChange={e => set('dv', e.target.value)}
                   placeholder="auto" readOnly={form.tipo_doc !== 'NI'} />
          </Campo>
          <Campo label="Persona">
            <select style={inp} value={form.tipo_persona}
                    onChange={e => set('tipo_persona', e.target.value)}>
              <option value="J">Jurídica</option>
              <option value="N">Natural</option>
            </select>
          </Campo>
        </div>

        <div style={seccion}>Clasificación PILA</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <Campo label="Tipo de aportante" ancho={4}>
            <select style={inp} value={form.tipo_aportante}
                    onChange={e => set('tipo_aportante', e.target.value)}>
              {tiposAportante.length === 0 && (
                <option value="">Catálogo PILA no disponible</option>
              )}
              {tiposAportante.map(t => (
                <option key={t.codigo} value={t.codigo}>{t.codigo} — {t.nombre}</option>
              ))}
            </select>
          </Campo>
          <Campo label="Clase aportante">
            <input style={mono} value={form.clase_aportante} maxLength={1}
                   onChange={e => set('clase_aportante', e.target.value.toUpperCase())} />
          </Campo>
          <Campo label="ARL" ancho={2}>
            <select style={inp} value={form.cod_arl}
                    onChange={e => set('cod_arl', e.target.value)}>
              <option value="">—</option>
              {arls.map(a => (
                <option key={a.codigo} value={a.codigo}>{a.nombre} ({a.codigo})</option>
              ))}
            </select>
          </Campo>
          <Campo label="Clase de riesgo">
            <select style={inp} value={form.clase_riesgo}
                    onChange={e => set('clase_riesgo', e.target.value)}>
              <option value="">—</option>
              {CLASES_RIESGO.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </Campo>
          <Campo label="Actividad económica">
            <input style={mono} value={form.actividad_economica} maxLength={7}
                   onChange={e => set('actividad_economica', e.target.value)}
                   placeholder="CIIU" />
          </Campo>
          <Campo label="Exoneración" ancho={3}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: C.text }}>
              <input type="checkbox" checked={form.exonerado_parafiscales}
                     onChange={e => set('exonerado_parafiscales', e.target.checked)} />
              Exonerado de SENA, ICBF y salud patronal (art. 114-1 ET)
            </label>
          </Campo>
        </div>

        <div style={seccion}>Ubicación y sucursal</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <Campo label="Departamento" ancho={2}>
            <select style={inp} value={form.cod_depto} onChange={e => setDepto(e.target.value)}>
              <option value="">—</option>
              {deptos.map(d => (
                <option key={d.codigo} value={d.codigo}>{d.nombre}</option>
              ))}
            </select>
          </Campo>
          <Campo label="Municipio" ancho={2}>
            <select style={inp} value={form.cod_municipio} disabled={!form.cod_depto}
                    onChange={e => set('cod_municipio', e.target.value)}>
              <option value="">{form.cod_depto ? '—' : 'Elige departamento'}</option>
              {municipios.map(m => (
                // El catálogo guarda el código DANE completo; al aportante solo
                // le corresponden los 3 últimos dígitos.
                <option key={m.codigo} value={m.codigo.slice(2)}>{m.nombre}</option>
              ))}
            </select>
          </Campo>
          <Campo label="Cód. sucursal">
            <input style={mono} value={form.cod_sucursal}
                   onChange={e => set('cod_sucursal', e.target.value)} />
          </Campo>
          <Campo label="Nombre sucursal" ancho={3}>
            <input style={inp} value={form.nombre_sucursal}
                   onChange={e => set('nombre_sucursal', e.target.value)} />
          </Campo>
        </div>

        <div style={seccion}>Contacto</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <Campo label="Dirección" ancho={2}>
            <input style={inp} value={form.direccion}
                   onChange={e => set('direccion', e.target.value)} />
          </Campo>
          <Campo label="Teléfono">
            <input style={inp} value={form.telefono}
                   onChange={e => set('telefono', e.target.value)} />
          </Campo>
          <Campo label="Email">
            <input style={inp} value={form.email}
                   onChange={e => set('email', e.target.value)} />
          </Campo>
        </div>

        {editando && (
          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: C.text }}>
              <input type="checkbox" checked={form.activo !== false}
                     onChange={e => set('activo', e.target.checked)} />
              Activo
            </label>
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 22 }}>
          <Btn variant="secondary" onClick={() => setModal(false)}>Cancelar</Btn>
          <Btn onClick={() => guardar.mutate()} disabled={guardar.isPending}>
            {guardar.isPending ? 'Guardando…' : 'Guardar'}
          </Btn>
        </div>
      </Modal>

      <ConfirmModal
        open={!!porBorrar}
        title="Eliminar aportante"
        message={porBorrar
          ? `¿Eliminar "${porBorrar.razon_social}"? Si ya tiene planillas liquidadas no se podrá borrar: desactívalo en su lugar.`
          : ''}
        onConfirm={() => borrar.mutate(porBorrar.id)}
        onCancel={() => setPorBorrar(null)}
      />
    </div>
  );
}
