import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../components/ui/tooltip';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api, { buildUploadForm } from '../utils/api';
import { empresaStyle } from '../utils/colors';
import { C, Btn, Modal, ConfirmModal, PageHeader, statusBadge, ErrorMsg } from '../components/UI';
import { BarraFiltros } from '../components/FiltroCheck';
import useAuthStore from '../hooks/useAuth';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
} from '@tanstack/react-table';

const SERVICIOS = ['EPS','AFP','CCF','ARL 1','ARL 2','ARL 3','ARL 4','ARL 5'];

function EmpresaBadge({ nombre }) {
  if (!nombre) return <span style={{ color: C.text2 }}>—</span>;
  const s = empresaStyle(nombre);
  return (
    <span style={{ fontSize: 12, fontWeight: 700, borderRadius: 6, padding: '2px 8px',
      background: s.bg, color: s.color, whiteSpace: 'nowrap' }}>
      {nombre}
    </span>
  );
}

async function dlExcel(url, filename) {
  try {
    const res = await api.get(url, { responseType: 'blob' });
    const objUrl = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = objUrl;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(objUrl);
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || 'Error generando reporte';
    const { toast: _toast } = await import('sonner');
    _toast.error(typeof msg === 'string' ? msg : 'Error generando reporte');
  }
}
const ESTADOS_SRV = ['ACTIVO','SUSPENDIDO','DOBLE AFILIACION','EN ESPERA DE ACTIVACION',
                     'RETIRADO','EN MORA','NO AFILIADO','PENDIENTE'];
const UP = (v) => (v||'').toUpperCase();

const InputUp = ({ label, value, onChange, placeholder, type='text', style, readOnly }) => (
  <div style={{ marginBottom:14, ...style }}>
    {label && <label style={lbl}>{label}</label>}
    <input type={type} value={value} readOnly={readOnly}
      onChange={e => onChange(type==='text'||type==='tel' ? UP(e.target.value) : e.target.value)}
      placeholder={placeholder}
      style={{ ...inp2,
        textTransform:(type==='text'||type==='tel')?'uppercase':'none',
        background: readOnly ? C.surface2 : C.surface,
        cursor: readOnly ? 'not-allowed' : 'text' }} />
  </div>
);

const Sel = ({ label, value, onChange, options=[], style }) => (
  <div style={{ marginBottom:14, ...style }}>
    {label && <label style={lbl}>{label}</label>}
    <select value={value} onChange={e=>onChange(e.target.value)}
      style={{ ...inp2, cursor:'pointer' }}>
      {options.map(o=>typeof o==='string'
        ?<option key={o} value={o}>{o||'—'}</option>
        :<option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  </div>
);

export default function Afiliados() {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const esAdmin   = user?.rol === 'admin';
  const esEmpleado = user?.rol === 'empleado';
  const [tab, setTab]           = useState('activos');
  const [busqueda, setBusqueda] = useState(() => {
    try { return localStorage.getItem('bbc_afil_busqueda') || ''; } catch { return ''; }
  });
  const [filtros,  setFiltros]  = useState(() => {
    try { return JSON.parse(localStorage.getItem('bbc_afil_filtros')) || { estado:[], empresa:[], cliente:[], subtipo:[], tipo_doc:[], ccf:[] }; } catch { return { estado:[], empresa:[], cliente:[], subtipo:[], tipo_doc:[], ccf:[] }; }
  });
  const [modal,    setModal]    = useState(null);
  const [confirm,  setConfirm]  = useState(null);  // { title, message, onConfirm }
  const [form,     setForm]     = useState({});

  // Pagos tab state
  const [docSeleccionado, setDocSeleccionado] = useState('');
  const [busquedaPagos,   setBusquedaPagos]   = useState('');
  const [anioFiltro,      setAnioFiltro]      = useState('Todos');

  // Documentos tab state
  const [docBusqDoc, setDocBusqDoc] = useState('');
  const [docDocSel,  setDocDocSel]  = useState('');
  const [uploading,  setUploading]  = useState(false);

  // Adjuntos pendientes en formulario de afiliado
  const [pendingFiles, setPendingFiles] = useState([]);

  // Seguimiento ARL state
  const [textoModal, setTextoModal] = useState(null); // { titulo, nombre, texto }
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [buscarElim,    setBuscarElim]    = useState('');
  const [elimFechaDesde, setElimFechaDesde] = useState('');
  const [elimFechaHasta, setElimFechaHasta] = useState('');
  const [elimAnio,       setElimAnio]       = useState(() => String(new Date().getFullYear()));
  const [elimMes,        setElimMes]        = useState(() => String(new Date().getMonth()+1).padStart(2,'0'));
  const [elimDia,        setElimDia]        = useState(() => String(new Date().getDate()).padStart(2,'0'));

  const [arlFiltroCliente, setArlFiltroCliente] = useState('');
  const [arlSeleccionados, setArlSeleccionados] = useState([]);
  const [arlBulkEstado, setArlBulkEstado] = useState('activo');
  const [arlModal, setArlModal] = useState(null);
  const [arlForm, setArlForm] = useState({
    nombre:'', documento:'', cliente:'', empresa:'',
    fecha_afiliacion:'', entidad_arl:'SURA', nivel_arl:'N/A', observaciones:''
  });

  const setFiltro = (key,vals) => { setFiltros(f=>({...f,[key]:vals})); setPagina(1); setTablePagination(p=>({...p,pageIndex:0})); };
  const limpiar = () => { setFiltros({ estado:[], empresa:[], cliente:[], subtipo:[], tipo_doc:[], ccf:[] }); setBusqueda(''); setPagina(1); setTablePagination(p=>({...p,pageIndex:0})); };

  useEffect(() => { try { localStorage.setItem('bbc_afil_filtros', JSON.stringify(filtros)); } catch {} }, [filtros]);
  useEffect(() => { try { localStorage.setItem('bbc_afil_busqueda', busqueda); } catch {} }, [busqueda]);

  const [pagina, setPagina] = useState(1);
  const [sorting, setSorting] = useState([]);
  const [tablePagination, setTablePagination] = useState({ pageIndex: 0, pageSize: 50 });
  const [columnVisibility, setColumnVisibility] = useState({});
  const colMenuRef = useRef(null);
  const [colMenuOpen, setColMenuOpen] = useState(false);

  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });

  // Opciones de filtros — endpoint ligero, cacheado en backend (no carga datos de afiliados)
  const { data: filterOpts={} } = useQuery({
    queryKey:['afiliados-filter-options'],
    queryFn:()=>api.get('/afiliados/filter-options').then(r=>r.data),
    staleTime: 120_000,
  });

  // Debounce búsqueda: evita recalcular en cada keystroke
  const [busquedaDefer, setBusquedaDefer] = useState('');
  const timerRef = useRef(null);
  useEffect(() => {
    timerRef.current = setTimeout(() => {
      setBusquedaDefer(busqueda);
      setPagina(1);
      setTablePagination(p => ({ ...p, pageIndex: 0 }));
    }, 300);
    return () => clearTimeout(timerRef.current);
  }, [busqueda]);

  // Construir params con filtros multi-valor (CSV) para el backend
  const filterParams = useMemo(() => {
    const p = {};
    if (busquedaDefer) p.q = busquedaDefer;
    if (filtros.estado.length)   p.estado   = filtros.estado.join(',');
    if (filtros.empresa.length)  p.empresa  = filtros.empresa.join(',');
    if (filtros.cliente.length)  p.cliente  = filtros.cliente.join(',');
    if (filtros.subtipo.length)  p.subtipo  = filtros.subtipo.join(',');
    if (filtros.tipo_doc.length) p.tipo_doc = filtros.tipo_doc.join(',');
    if (filtros.ccf?.length)     p.ccf      = filtros.ccf.join(',');
    if (fechaDesde) p.fecha_desde = fechaDesde;
    if (fechaHasta) p.fecha_hasta = fechaHasta;
    return p;
  }, [busquedaDefer, filtros, fechaDesde, fechaHasta]);

  // Query ÚNICA paginada — filtros van al backend como CSV
  const { data: resp={total:0,items:[]}, isLoading, isError: isErrorAfiliados, refetch: refetchAfiliados } = useQuery({
    queryKey:['afiliados', pagina, tablePagination.pageSize, filterParams],
    queryFn:()=>api.get('/afiliados', { params:{ ...filterParams, skip:(pagina-1)*tablePagination.pageSize, limit:tablePagination.pageSize } }).then(r=>r.data),
    placeholderData: (prev) => prev,
  });
  const data     = resp.items || [];
  const totalReg = resp.total || 0;

  // `todos` ligero — solo se carga bajo demanda para tabs de Pagos/Documentos (autocompletar)
  const [todosNeeded, setTodosNeeded] = useState(false);
  const { data: todos=[] } = useQuery({
    queryKey:['afiliados_all'],
    queryFn:()=>api.get('/afiliados').then(r=>r.data.items||[]),
    enabled: todosNeeded,
    staleTime: 120_000,
    refetchInterval: false,
  });
  const { data: actividad=[] } = useQuery({ queryKey:['actividad','Afiliados'], queryFn:()=>api.get('/actividad',{params:{modulo:'Afiliados'}}).then(r=>r.data?.items||r.data), enabled: esAdmin });
  const { data: eliminados=[], isLoading: loadElim } = useQuery({
    queryKey:['eliminados'], queryFn:()=>api.get('/eliminados').then(r=>r.data),
    enabled: (tab === 'eliminados' || tab === 'pagos') && (esAdmin || esEmpleado),
  });

  // Facturas del afiliado seleccionado en tab pagos
  // Si el afiliado fue retirado no está en `todos` — buscarlo en eliminados como fallback
  const afilSelObj = todos.find(a => a.doc === docSeleccionado) || (() => {
    if (!docSeleccionado) return null;
    const e = eliminados.find(x => x.doc === docSeleccionado);
    if (!e) return null;
    try {
      return { ...JSON.parse(e.datos_completos || '{}'), _retirado: true };
    } catch { return null; }
  })();
  const { data: factAfil=[], isLoading: loadFact } = useQuery({
    queryKey: ['facturas_afil', docSeleccionado],
    queryFn: () => api.get('/facturas', { params: { doc: docSeleccionado, limit: 0 } })
      .then(r => r.data.items || []),
    enabled: !!docSeleccionado,
    refetchInterval: false,
  });

  const qSegArl = useQuery({
    queryKey: ['seguimiento-arl'],
    queryFn: () => api.get('/seguimiento-arl').then(r => r.data),
    staleTime: 120_000,
    refetchOnWindowFocus: false,
    enabled: tab === 'arl',
  });
  const segArlData = qSegArl.data || [];

  // Cerrar menú de columnas al click fuera
  useEffect(() => {
    if (!colMenuOpen) return;
    const handler = (e) => { if (colMenuRef.current && !colMenuRef.current.contains(e.target)) setColMenuOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [colMenuOpen]);


  // Opciones de filtros desde endpoint ligero (no requiere cargar todos los afiliados)
  const clientesUnicos = filterOpts.clientes || [];
  const subtiposUnicos = filterOpts.subtipos || [];
  const estadosOpts    = filterOpts.estados  || [];

  const hayFiltrosActivos = busquedaDefer || Object.values(filtros).some(v => v.length > 0) || fechaDesde || fechaHasta;
  // Filtrado completamente server-side — `data` ya viene filtrada incluyendo fechas.
  const dataFiltrada = data;

  const sugerenciasPagos = useMemo(() => {
    if (busquedaPagos.length < 2) return [];
    const q = busquedaPagos.toLowerCase();
    const activos = todos.filter(a => `${a.nombre} ${a.doc}`.toLowerCase().includes(q)).slice(0, 8);
    const retirados = eliminados
      .filter(e => `${e.nombre} ${e.doc}`.toLowerCase().includes(q))
      .map(e => ({ ...e, _retirado: true, cliente_txt: (() => { try { return JSON.parse(e.datos_completos||'{}').cliente_txt||''; } catch { return ''; } })() }))
      .slice(0, 4);
    return [...activos, ...retirados].slice(0, 10);
  }, [todos, eliminados, busquedaPagos]);

  const columns = useMemo(() => [
    {
      accessorKey: 'nombre',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Nombre {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => (
        <div>
          <span style={{ fontWeight: 700, cursor: 'pointer', color: C.primary }}
            onClick={() => { setDocSeleccionado(row.original.doc); setTab('pagos'); setTodosNeeded(true); }}>
            {row.original.nombre}
          </span>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.text2, letterSpacing: '0.02em' }}>
            {row.original.tipo_doc || 'CC'} {row.original.doc}
          </div>
        </div>
      ),
    },
    {
      accessorKey: 'empresa',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Empresa {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <EmpresaBadge nombre={row.original.empresa} />,
    },
    {
      accessorKey: 'cliente_txt',
      header: 'Cliente',
      cell: ({ row }) => <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{row.original.cliente_txt || '—'}</span>,
    },
    {
      accessorKey: 'subtipo',
      header: 'Subtipo',
      cell: ({ row }) => row.original.subtipo ? <Chip>{row.original.subtipo}</Chip> : <span style={{ color: C.text2 }}>—</span>,
    },
    {
      accessorKey: 'eps',
      header: 'EPS',
      cell: ({ row }) => <span style={{ fontSize: 13, color: C.text, fontWeight: 700 }}>{row.original.eps || '—'}</span>,
    },
    {
      accessorKey: 'arl',
      header: 'ARL',
      cell: ({ row }) => <span style={{ fontSize: 13, color: C.text2 }}>{row.original.arl || '—'}</span>,
    },
    {
      accessorKey: 'servicios',
      header: 'Servicios',
      enableSorting: false,
      cell: ({ row }) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {(row.original.servicios || []).map(s => <SrvChip key={s}>{s}</SrvChip>)}
        </div>
      ),
    },
    {
      accessorKey: 'estado_srv',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Estado {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => statusBadge(row.original.estado_srv || row.original.estado),
    },
    {
      accessorKey: 'novedades',
      header: 'Novedades',
      enableSorting: false,
      cell: ({ row }) => row.original.novedades ? (
        <span style={{ fontSize: 13, color: C.amber, fontWeight: 600, cursor: 'pointer',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', maxWidth: 160 }}>
          📝 {row.original.novedades}
        </span>
      ) : <span style={{ fontSize: 13, color: C.text2 }}>—</span>,
    },
    {
      accessorKey: 'detalle',
      header: 'Detalle',
      enableSorting: false,
      cell: ({ row }) => row.original.detalle ? (
        <span style={{ fontSize: 13, color: C.blue, fontWeight: 600, cursor: 'pointer',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', maxWidth: 180 }}>
          💬 {row.original.detalle}
        </span>
      ) : <span style={{ fontSize: 13, color: C.text2 }}>—</span>,
    },
    {
      id: 'acciones',
      header: '',
      enableSorting: false,
      enableHiding: false,
      cell: ({ row }) => {
        const a = row.original;
        return (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            <Btn size="sm" variant="secondary" onClick={() => openEditar(a)}>✏️ Editar</Btn>
            <Btn size="sm" variant="secondary" onClick={() => dlExcel(`/afiliados/${a.id}/certificado`, `certificado_${a.nombre.replace(/ /g, '_')}.pdf`)}>📄 Cert.</Btn>
          </div>
        );
      },
    },
  ], [setTextoModal]);

  const table = useReactTable({
    data: dataFiltrada,
    columns,
    state: { sorting, columnVisibility },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,  // paginación es server-side
    pageCount: Math.ceil(totalReg / tablePagination.pageSize),
  });

  const sf = (k,v) => setForm(f=>({...f,[k]:v}));
  const openNuevo  = () => { setForm({ empresa:'', servicios:[], subtipo:'0', estado:'ACTIVO', estado_srv:'ACTIVO' }); setPendingFiles([]); setModal('nuevo'); };
  const openEditar = (a) => { setForm({...a}); setPendingFiles([]); setModal(a); };
  const toggleSrv  = (s) => {
    setForm(f => {
      const srvs = f.servicios || [];
      if (srvs.includes(s)) {
        return {
          ...f,
          servicios: srvs.filter(x => x !== s),
          arl: s.startsWith('ARL') ? '' : f.arl,
        };
      } else {
        const base = s.startsWith('ARL') ? srvs.filter(x => !x.startsWith('ARL')) : srvs;
        return {
          ...f,
          servicios: [...base, s],
          arl: s.startsWith('ARL') ? s.split(' ')[1] : f.arl,
        };
      }
    });
  };

  const guardar = useMutation({
    mutationFn: async () => {
      const payload = { ...form };
      const res = modal==='nuevo' ? await api.post('/afiliados',payload) : await api.put(`/afiliados/${modal.id}`,payload);
      return res;
    },
    onSuccess: async (res) => {
      toast.success(modal==='nuevo'?'Afiliado registrado':'Actualizado');
      // Subir documentos DESPUÉS de invalidar caché — error de docs no cancela el guardado
      const doc = res.data?.doc || form.doc;
      if (pendingFiles.length > 0 && doc) {
        try {
          await Promise.all(pendingFiles.map(file => {
            const { fd } = buildUploadForm(file, { afiliado_doc: doc, contexto: 'afiliado' });
            return api.post('/documentos', fd);
          }));
          toast.success(`${pendingFiles.length} documento(s) adjuntado(s)`);
        } catch {
          toast.error('Afiliado guardado. Error al subir documentos, intenta de nuevo.');
        }
      }
      if (modal === 'nuevo') {
        // invalidateQueries para ['afiliados'] (paginado): no sabemos en qué página aparece el nuevo registro
        qc.invalidateQueries({ queryKey: ['afiliados'] });
        qc.invalidateQueries({ queryKey: ['afiliados-filter-options'] });
        qc.invalidateQueries({ queryKey: ['afiliados-recientes'] });
        qc.setQueryData(['afiliados_all'], prev => [res.data, ...(prev || [])]);
      } else {
        qc.setQueriesData({ queryKey: ['afiliados'] }, prev =>
          prev && prev.items ? { ...prev, items: prev.items.map(a => a.id === res.data.id ? res.data : a) } : prev
        );
        qc.setQueryData(['afiliados_all'], prev => prev?.map(a => a.id === res.data.id ? res.data : a));
      }
      qc.invalidateQueries({queryKey:['facturas']});
      qc.invalidateQueries({queryKey:['documentos']});
      setModal(null);
    },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); },
  });

  const eliminar = useMutation({
    mutationFn: id => api.delete(`/afiliados/${id}`),
    onSuccess: (res, id) => {
      const n = res.data?.facturas_pendientes;
      toast.success(n ? `Eliminado. ${n} factura(s) conservadas` : 'Afiliado eliminado');
      qc.setQueriesData({ queryKey: ['afiliados'] }, prev =>
        prev && prev.items ? { ...prev, items: prev.items.filter(a => a.id !== id), total: Math.max(0, (prev.total || 0) - 1) } : prev
      );
      qc.setQueryData(['afiliados_all'], prev => prev?.filter(a => a.id !== id));
      qc.invalidateQueries({queryKey:['eliminados']});
      qc.invalidateQueries({queryKey:['afiliados-filter-options']});
      qc.invalidateQueries({queryKey:['dashboard']});
      qc.invalidateQueries({queryKey:['cobro']});
    },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); },
  });

  const restaurar = useMutation({
    mutationFn: id => api.post(`/eliminados/${id}/restaurar`),
    onSuccess: res => { toast.success(`${res.data.nombre} restaurado como ACTIVO`); qc.invalidateQueries({queryKey:['afiliados']}); qc.invalidateQueries({queryKey:['afiliados_all']}); qc.invalidateQueries({queryKey:['eliminados']}); },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error al restaurar')); },
  });

  const borrarPermanente = useMutation({
    mutationFn: id => api.delete(`/eliminados/${id}`),
    onSuccess: (_, id) => { toast.success('Eliminado permanentemente'); qc.setQueryData(['eliminados'], prev => prev?.filter(e => e.id !== id)); },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); },
  });

  const confirmarBorradoPermanente = async (e) => {
    try {
      const preview = await api.get(`/eliminados/${e.id}/preview`).then(r => r.data);
      const detalles = [
        preview.facturas    > 0 ? `${preview.facturas} factura(s)`             : null,
        preview.documentos  > 0 ? `${preview.documentos} documento(s)`         : null,
        preview.solicitudes > 0 ? `${preview.solicitudes} solicitud(es) portal`: null,
      ].filter(Boolean);
      const detalleTxt = detalles.length > 0 ? ` Se borrarán también: ${detalles.join(', ')}.` : '';
      setConfirm({
        title: '⚠️ Eliminar permanentemente',
        message: `¿Eliminar PERMANENTEMENTE a ${e.nombre} (${e.doc})?${detalleTxt} Esta acción NO se puede deshacer.`,
        confirmLabel: 'Sí, eliminar todo',
        onConfirm: () => borrarPermanente.mutate(e.id),
      });
    } catch {
      setConfirm({
        title: 'Eliminar permanentemente',
        message: `¿Eliminar PERMANENTEMENTE a ${e.nombre}? Esta acción no se puede deshacer.`,
        confirmLabel: 'Eliminar para siempre',
        onConfirm: () => borrarPermanente.mutate(e.id),
      });
    }
  };


  // Seguimiento state
  const [segBusqueda, setSegBusqueda] = useState('');
  const [segFiltros,  setSegFiltros]  = useState({ empresa:[], cliente:[] });

  const activarAfiliado = useMutation({
    mutationFn: (a) => api.put(`/afiliados/${a.id}`, { ...a, estado:'ACTIVO', estado_srv:'ACTIVO' }),
    onSuccess: (res) => {
      toast.success('Afiliado activado');
      qc.setQueriesData({ queryKey: ['afiliados'] }, prev =>
        prev && prev.items ? { ...prev, items: prev.items.map(a => a.id === res.data.id ? res.data : a) } : prev
      );
      qc.setQueryData(['afiliados_all'], prev => prev?.map(a => a.id === res.data.id ? res.data : a));
    },
    onError: e => { const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); },
  });

  const arlCrear = useMutation({
    mutationFn: d => api.post('/seguimiento-arl', d).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['seguimiento-arl'] }); setArlModal(null); toast.success('Registro creado'); },
    onError: () => toast.error('Error al crear registro'),
  });
  const arlEditar = useMutation({
    mutationFn: ({ id, ...d }) => api.put(`/seguimiento-arl/${id}`, d).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['seguimiento-arl'] }); setArlModal(null); toast.success('Registro actualizado'); },
    onError: () => toast.error('Error al actualizar'),
  });
  const arlEliminar = useMutation({
    mutationFn: id => api.delete(`/seguimiento-arl/${id}`).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['seguimiento-arl'] }); toast.success('Registro eliminado'); },
    onError: () => toast.error('Error al eliminar'),
  });
  const arlBulk = useMutation({
    mutationFn: ({ ids, estado }) => api.patch('/seguimiento-arl/bulk-estado', { ids, estado }).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['seguimiento-arl'] }); setArlSeleccionados([]); toast.success('Estados actualizados'); },
    onError: () => toast.error('Error al actualizar estados'),
  });

  const enSeguimiento = todos.filter(a => (a.estado_srv||a.estado||'').toUpperCase() === 'EN ESPERA DE ACTIVACION');
  const enSeguimientoFiltrado = enSeguimiento.filter(a => {
    const q = segBusqueda.toLowerCase();
    if (segBusqueda && !`${a.nombre} ${a.doc} ${a.empresa} ${a.cliente_txt}`.toLowerCase().includes(q)) return false;
    if (segFiltros.empresa.length && !segFiltros.empresa.includes(a.empresa)) return false;
    if (segFiltros.cliente.length && !segFiltros.cliente.includes(a.cliente_txt)) return false;
    return true;
  });

  const diasEnEspera = (a) => {
    if (!a.fecha_afiliacion) return null;
    const desde = new Date(a.fecha_afiliacion + 'T00:00:00');
    const hoy = new Date(); hoy.setHours(0,0,0,0);
    return Math.floor((hoy - desde) / 86400000);
  };

  const urgenciaEspera = (dias) => {
    if (dias === null) return null;
    if (dias > 10) return { color: C.red,   bg: C.redBg,   label: `⚠️ ${dias}d — VENCIDO`, nivel: 'critico' };
    if (dias >= 7)  return { color: C.amber, bg: C.amberBg, label: `⏰ ${dias}d — Revisar`, nivel: 'urgente' };
    return { color: C.text2, bg: 'transparent', label: `${dias}d`, nivel: 'ok' };
  };

  const criticos = enSeguimiento.filter(a => { const d=diasEnEspera(a); return d!==null && d>10; }).length;
  const urgentes = enSeguimiento.filter(a => { const d=diasEnEspera(a); return d!==null && d>=7 && d<=10; }).length;

  // Seguimiento ARL helpers
  const segArlFiltrado = useMemo(
    () => arlFiltroCliente ? segArlData.filter(r => r.cliente === arlFiltroCliente) : segArlData,
    [segArlData, arlFiltroCliente]
  );
  const todosArlSel = arlSeleccionados.length > 0 && arlSeleccionados.length === segArlFiltrado.length;
  function diasDesdeArl(fechaStr) {
    if (!fechaStr) return 0;
    return Math.floor((Date.now() - new Date(fechaStr).getTime()) / 86_400_000);
  }
  function arlAlerta(row) { return row.estado === 'activo' && diasDesdeArl(row.fecha_afiliacion) >= 25; }
  function diasRestantesArl(row) {
    if (!row.fecha_afiliacion || row.estado !== 'activo') return null;
    return 30 - diasDesdeArl(row.fecha_afiliacion);
  }
  function toggleTodosArl() { setArlSeleccionados(todosArlSel ? [] : segArlFiltrado.map(r => r.id)); }
  function toggleUnoArl(id) { setArlSeleccionados(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]); }
  function abrirNuevoArl() {
    setArlForm({ nombre:'', documento:'', cliente:'', empresa:'', fecha_afiliacion:'', entidad_arl:'SURA', nivel_arl:'N/A', observaciones:'' });
    setArlModal('nuevo');
  }
  function abrirEditarArl(row) {
    setArlForm({ nombre:row.nombre, documento:row.documento, cliente:row.cliente||'', empresa:row.empresa||'',
      fecha_afiliacion:row.fecha_afiliacion||'', entidad_arl:row.entidad_arl||'SURA',
      nivel_arl:row.nivel_arl||'N/A', observaciones:row.observaciones||'',
      estado: row.estado||'activo' });
    setArlModal(row);
  }
  function submitArlForm() {
    if (!arlForm.nombre || !arlForm.documento) { toast.error('Nombre y documento son requeridos'); return; }
    if (arlModal === 'nuevo') {
      arlCrear.mutate(arlForm);
    } else {
      arlEditar.mutate({ id: arlModal.id, ...arlForm });
    }
  }

  // Años disponibles en tab Eliminados
  const aniosElim = useMemo(() =>
    [...new Set(eliminados.map(e => (e.fecha_eliminacion||'').slice(0,4)).filter(Boolean))].sort().reverse()
  , [eliminados]);

  // Filtro por año y totales
  const aniosDisponibles = [...new Set(factAfil.map(f => String(f.anio)).filter(Boolean))].sort().reverse();
  const factAfil_filtradas = anioFiltro === 'Todos' ? factAfil : factAfil.filter(f => String(f.anio) === anioFiltro);
  const totalPagado    = factAfil_filtradas.filter(f=>f.estado==='pagado'||f.estado==='planilla_pagada').reduce((s,f)=>s+(f.ingresos||0),0);
  const totalPendiente = factAfil_filtradas.filter(f=>f.estado!=='pagado'&&f.estado!=='planilla_pagada').reduce((s,f)=>s+(f.ingresos||0),0);

  return (
    <div>
      <PageHeader title="👥 Afiliados"
        subtitle={tab==='activos' ? `${totalReg} registros${hayFiltrosActivos ? ' (filtrado)' : ''}` : tab==='eliminados' ? `${eliminados.length} eliminados` : ''}
        action={tab==='activos' && (
          <div style={{ display:'flex', gap:8 }}>
            <Btn variant="secondary" onClick={() => {
              const p = new URLSearchParams();
              if (busqueda) p.set('q', busqueda);
              if (filtros.estado.length) p.set('estado', filtros.estado.join(','));
              if (filtros.empresa.length) p.set('empresa', filtros.empresa.join(','));
              if (filtros.cliente.length) p.set('cliente', filtros.cliente.join(','));
              if (filtros.subtipo.length) p.set('subtipo', filtros.subtipo.join(','));
              dlExcel(`/reportes/afiliados?${p}`, 'afiliados.xlsx');
            }}>📊 Exportar Excel</Btn>
            <Btn variant="accent" onClick={openNuevo}>+ Nuevo afiliado</Btn>
          </div>
        )} />

      {/* Pestañas */}
      <div style={{ display:'flex', gap:4, marginBottom:16, borderBottom:`2px solid ${C.border}`, paddingBottom:0, overflowX:'auto', flexWrap:'nowrap' }}>
        {[
          { key:'activos',    label:`👥 Activos (${totalReg})` },
          { key:'eliminados', label:`🗑️ Eliminados (${eliminados.length || '...'})` },
          { key:'pagos',      label:'💳 Historial de pagos' },
          { key:'documentos', label:'📎 Documentos' },
          { key:'seguimiento', label:'📋 En seguimiento' },
          { key:'arl', label:'🔵 Seguimiento ARL' },
        ].map(t => (
          <button key={t.key} onClick={() => { setTab(t.key); if (t.key === 'pagos' || t.key === 'documentos' || t.key === 'seguimiento') setTodosNeeded(true); }} style={{
            padding:'9px 18px', border:'none', borderRadius:'7px 7px 0 0',
            background: tab===t.key ? C.primary : 'transparent',
            color: tab===t.key ? '#fff' : C.text2,
            fontWeight: tab===t.key ? 700 : 400, fontSize:13, cursor:'pointer',
            borderBottom: tab===t.key ? `2px solid ${C.primary}` : 'none',
            marginBottom: tab===t.key ? -2 : 0,
          }}>{t.label}</button>
        ))}
      </div>

      {/* ═══ TAB: ACTIVOS ═══ */}
      {tab === 'activos' && (
        <>
          <div style={{ display:'flex', gap:8, marginBottom:12, alignItems:'center' }}>
            <input placeholder="🔍 Buscar nombre, documento, empresa, cliente..."
              value={busqueda} onChange={e=>{ setBusqueda(e.target.value); setPagina(1); setTablePagination(p=>({...p,pageIndex:0})); }}
              style={{ flex:1,padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
                fontSize:14,outline:'none',boxSizing:'border-box',background:C.surface,color:C.text }} />
            <div ref={colMenuRef} style={{ position:'relative' }}>
              <button type="button" onClick={() => setColMenuOpen(o => !o)}
                style={{ padding:'10px 14px', border:`1px solid ${C.border}`, borderRadius:8,
                  background:C.surface, color:C.text, fontSize:13, cursor:'pointer', whiteSpace:'nowrap' }}>
                ⚙ Columnas
              </button>
              {colMenuOpen && (
                <div style={{ position:'absolute', right:0, top:'calc(100% + 4px)', background:C.surface,
                  border:`1px solid ${C.border}`, borderRadius:8, boxShadow:'0 4px 12px rgba(0,0,0,.1)',
                  zIndex:200, padding:'8px 0', minWidth:180 }}>
                  {table.getAllColumns().filter(col => col.getCanHide()).map(col => (
                    <label key={col.id} style={{ display:'flex', alignItems:'center', gap:8,
                      padding:'6px 14px', cursor:'pointer', fontSize:13, color:C.text,
                      userSelect:'none' }}
                      onMouseEnter={e=>e.currentTarget.style.background=C.surface2}
                      onMouseLeave={e=>e.currentTarget.style.background=''}>
                      <input type="checkbox" checked={col.getIsVisible()} onChange={col.getToggleVisibilityHandler()} />
                      {typeof col.columnDef.header === 'string' ? col.columnDef.header : col.id}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
          <BarraFiltros
            filtros={[
              { key:'empresa',  label:'Empresa',   icon:'🏢', options: listas.empresas||[] },
              { key:'cliente',  label:'Cliente',   icon:'👤', options: clientesUnicos },
              { key:'estado',   label:'Estado',    icon:'📌', options: estadosOpts },
              { key:'subtipo',  label:'Subtipo',   icon:'🔢', options: subtiposUnicos },
              { key:'tipo_doc', label:'Tipo doc',  icon:'🪪', options: ['CC','CE','PT','PA','NIT'] },
              { key:'ccf',      label:'CCF',       icon:'🏦', options: listas.ccf||[] },
            ]}
            valores={filtros} onChange={setFiltro} onLimpiar={() => { limpiar(); setFechaDesde(''); setFechaHasta(''); }}
          />
          <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:10, flexWrap:'wrap' }}>
            <span style={{ fontSize:12, color:C.text2, fontWeight:600 }}>Afiliación:</span>
            <input type="date" value={fechaDesde} onChange={e => { setFechaDesde(e.target.value); setPagina(1); setTablePagination(p=>({...p,pageIndex:0})); }}
              style={{ padding:'6px 10px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13,
                background:C.surface, color:C.text, outline:'none' }} />
            <span style={{ fontSize:12, color:C.text2 }}>—</span>
            <input type="date" value={fechaHasta} onChange={e => { setFechaHasta(e.target.value); setPagina(1); setTablePagination(p=>({...p,pageIndex:0})); }}
              style={{ padding:'6px 10px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13,
                background:C.surface, color:C.text, outline:'none' }} />
            {(fechaDesde || fechaHasta) && (
              <button onClick={() => { setFechaDesde(''); setFechaHasta(''); setPagina(1); }}
                style={{ padding:'5px 10px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:12,
                  background:C.surface, color:C.text2, cursor:'pointer' }}>✕ Limpiar fecha</button>
            )}
          </div>
          <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
              <thead>
                {table.getHeaderGroups().map(hg => (
                  <tr key={hg.id} style={{ background: C.surface2 }}>
                    {hg.headers.map(header => (
                      <th key={header.id} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap' }}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {isErrorAfiliados && <tr><td colSpan={columns.length}><ErrorMsg message="Error al cargar afiliados" onRetry={refetchAfiliados} /></td></tr>}
                {isLoading && <tr><td colSpan={columns.length} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Cargando...</td></tr>}
                {!isLoading && table.getRowModel().rows.length === 0 && (
                  <tr><td colSpan={columns.length} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin registros</td></tr>
                )}
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id}
                    style={{ borderBottom: `1px solid ${C.border}`, transition:'background .1s' }}
                    onMouseEnter={e=>e.currentTarget.style.background=C.surface2}
                    onMouseLeave={e=>e.currentTarget.style.background=''}>
                    {row.getVisibleCells().map(cell => {
                      const val = cell.column.id === 'novedades' ? row.original.novedades
                                : cell.column.id === 'detalle'   ? row.original.detalle
                                : null;
                      return (
                        <td key={cell.id} style={{ padding: '8px 12px', fontSize: 13 }}
                          onClick={val ? () => setTextoModal({ titulo: cell.column.id === 'novedades' ? 'Novedades' : 'Detalle', nombre: row.original.nombre, texto: val }) : undefined}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Paginación — siempre server-side (filtros van al backend como CSV) */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10, gap: 8, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 12, color: C.text2 }}>
                Página {pagina} de {Math.ceil(totalReg / tablePagination.pageSize) || 1} — {totalReg} resultado{totalReg !== 1 ? 's' : ''}
              </span>
              <select value={tablePagination.pageSize}
                onChange={e => { const sz = Number(e.target.value); table.setPageSize(sz); setTablePagination(p => ({ ...p, pageSize: sz, pageIndex: 0 })); setPagina(1); }}
                style={{ padding:'3px 8px', border:`1px solid ${C.border}`, borderRadius:6, fontSize:12, background:C.surface, color:C.text, cursor:'pointer' }}>
                {[25, 50, 100].map(n => <option key={n} value={n}>{n} / pág.</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <Btn size="sm" variant="secondary" onClick={() => setPagina(p => Math.max(1, p - 1))} disabled={pagina <= 1}>← Ant.</Btn>
              <Btn size="sm" variant="secondary" onClick={() => setPagina(p => p + 1)} disabled={pagina * tablePagination.pageSize >= totalReg}>Sig. →</Btn>
            </div>
          </div>
        </>
      )}

      {/* ═══ TAB: ELIMINADOS ═══ */}
      {tab === 'eliminados' && (
        <div>
          <div style={{ background:C.amberBg, border:`1px solid ${C.amber}`, borderRadius:8,
            padding:'10px 14px', marginBottom:14, fontSize:12, color:C.amber, fontWeight:500 }}>
            ⚠️ Afiliados eliminados del sistema. Puedes restaurarlos como ACTIVOS con el botón ↩ Restaurar.
          </div>
          <div style={{ display:'flex', gap:8, marginBottom:10, flexWrap:'wrap', alignItems:'center' }}>
            <input
              placeholder="🔍 Buscar por nombre, documento o empresa..."
              value={buscarElim}
              onChange={e => setBuscarElim(e.target.value)}
              style={{ flex:'1 1 220px', padding:'10px 14px', border:`1px solid ${C.border}`, borderRadius:8,
                fontSize:14, outline:'none', boxSizing:'border-box', background:C.surface, color:C.text }}
            />
            <div style={{ display:'flex', gap:6, alignItems:'center' }}>
              <select value={elimAnio} onChange={e=>setElimAnio(e.target.value)}
                style={{ padding:'8px 10px', border:`1px solid ${C.border}`, borderRadius:8, fontSize:13,
                  outline:'none', background:C.surface, color:elimAnio ? C.text : C.text2, cursor:'pointer' }}>
                <option value="">Año</option>
                {aniosElim.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
              <select value={elimMes} onChange={e=>setElimMes(e.target.value)}
                style={{ padding:'8px 10px', border:`1px solid ${C.border}`, borderRadius:8, fontSize:13,
                  outline:'none', background:C.surface, color:elimMes ? C.text : C.text2, cursor:'pointer' }}>
                <option value="">Mes</option>
                {['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'].map((m,i)=>(
                  <option key={m} value={String(i+1).padStart(2,'0')}>{m}</option>
                ))}
              </select>
              <select value={elimDia} onChange={e=>setElimDia(e.target.value)}
                style={{ padding:'8px 10px', border:`1px solid ${C.border}`, borderRadius:8, fontSize:13,
                  outline:'none', background:C.surface, color:elimDia ? C.text : C.text2, cursor:'pointer' }}>
                <option value="">Día</option>
                {Array.from({length:31},(_,i)=>String(i+1).padStart(2,'0')).map(d=>(
                  <option key={d} value={d}>{Number(d)}</option>
                ))}
              </select>
              {(elimMes || elimAnio || elimDia) && (
                <button onClick={() => { setElimMes(''); setElimAnio(''); setElimDia(''); }}
                  style={{ padding:'7px 10px', border:`1px solid ${C.border}`, borderRadius:8,
                    background:C.surface2, cursor:'pointer', fontSize:12, color:C.text2 }}>✕</button>
              )}
            </div>
          </div>
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
              <thead>
                <tr style={{ background:C.surface2 }}>
                  {['Nombre','Empresa','Documento','Mes','Fecha eliminación','Eliminado por','Acciones'].map(h=>(
                    <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                      color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loadElim && <tr><td colSpan={7} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
                {!loadElim && eliminados.length===0 && (
                  <tr><td colSpan={7} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin registros eliminados</td></tr>
                )}
                {eliminados.filter(e => {
                  if (buscarElim) {
                    const q = buscarElim.toLowerCase();
                    if (!((e.nombre||'').toLowerCase().includes(q) ||
                          (e.doc||'').toLowerCase().includes(q) ||
                          (e.empresa||'').toLowerCase().includes(q))) return false;
                  }
                  if (elimAnio && (e.fecha_eliminacion||'').slice(0,4) !== elimAnio) return false;
                  if (elimMes && (e.fecha_eliminacion||'').slice(5,7) !== elimMes) return false;
                  if (elimDia && (e.fecha_eliminacion||'').slice(8,10) !== elimDia) return false;
                  return true;
                }).map(e=>(
                  <tr key={e.id} style={{ borderBottom:`1px solid ${C.border}`, background:C.redBg }}>
                    <td style={{ ...tdc,fontWeight:600,color:C.red }}>{e.nombre}</td>
                    <td style={tdc}>{e.empresa||'—'}</td>
                    <td style={{ ...tdc,fontFamily:'monospace',fontSize:12 }}>{e.doc}</td>
                    <td style={tdc}>{e.mes||'—'}</td>
                    <td style={tdc}>{e.fecha_eliminacion||'—'}</td>
                    <td style={tdc}>{e.eliminado_por||'—'}</td>
                    <td style={tdc}>
                      <div style={{ display:'flex', gap:6 }}>
                        <Btn size="sm" variant="success"
                          onClick={() => setConfirm({ title:'Restaurar afiliado', message:`¿Restaurar a ${e.nombre} como ACTIVO?`, confirmLabel:'Restaurar', variant:'success', onConfirm:()=>restaurar.mutate(e.id) })}
                          disabled={restaurar.isPending}>
                          ↩ Restaurar
                        </Btn>

                        <Btn size="sm" variant="danger"
                          onClick={() => confirmarBorradoPermanente(e)}
                          disabled={borrarPermanente.isPending}>
                          🗑️ Borrar
                        </Btn>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ TAB: PAGOS POR AFILIADO ═══ */}
      {tab === 'pagos' && (
        <div>
          <div style={{ display:'flex', alignItems:'flex-start', gap:12, marginBottom:16, flexWrap:'wrap' }}>
            <div style={{ position:'relative', flex:'0 0 340px' }}>
              <input
                placeholder="🔍 Buscar afiliado por nombre o documento..."
                value={busquedaPagos}
                onChange={e => { setBusquedaPagos(e.target.value); if (!e.target.value) setDocSeleccionado(''); }}
                style={{ width:'100%',padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
                  fontSize:14,outline:'none',boxSizing:'border-box',background:C.surface,color:C.text }}
              />
              {sugerenciasPagos.length > 0 && !docSeleccionado && (
                <div style={{ position:'absolute',top:'100%',left:0,right:0,background:C.surface,
                  border:`1px solid ${C.border}`,borderRadius:8,boxShadow:'0 4px 12px rgba(0,0,0,.1)',
                  zIndex:100,maxHeight:200,overflowY:'auto' }}>
                  {sugerenciasPagos.map(a => (
                    <div key={a._retirado ? `elim-${a.id}` : a.id} onClick={() => { setDocSeleccionado(a.doc); setBusquedaPagos(a.nombre); }}
                      style={{ padding:'9px 14px',cursor:'pointer',fontSize:13,borderBottom:`1px solid ${C.border}`,
                        background: a._retirado ? C.amberBg : '' }}
                      onMouseEnter={e=>e.currentTarget.style.background=a._retirado ? '#fde68a' : C.surface2}
                      onMouseLeave={e=>e.currentTarget.style.background=a._retirado ? C.amberBg : ''}>
                      <strong>{a.nombre}</strong>
                      {a._retirado && <span style={{ marginLeft:6,fontSize:10,fontWeight:700,background:C.amber,color:'#fff',borderRadius:4,padding:'1px 6px' }}>RETIRADO</span>}
                      <span style={{ marginLeft:8,color:C.text2,fontSize:11 }}>{a.doc} · {a.empresa||''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {docSeleccionado && aniosDisponibles.length > 0 && (
              <select value={anioFiltro} onChange={e => setAnioFiltro(e.target.value)}
                style={{ padding:'8px 12px',border:`1px solid ${C.border}`,borderRadius:8,fontSize:13,outline:'none',background:C.surface }}>
                <option value="Todos">Todos los años</option>
                {aniosDisponibles.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            )}
            {docSeleccionado && (
              <Btn size="sm" variant="secondary" onClick={()=>{ setDocSeleccionado(''); setBusquedaPagos(''); setAnioFiltro('Todos'); }}>
                ✕ Limpiar
              </Btn>
            )}
            {docSeleccionado && afilSelObj && (
              <Btn size="sm" variant="secondary"
                onClick={()=>dlExcel(`/afiliados/${afilSelObj.id}/estado-cuenta`,`estado_cuenta_${afilSelObj.nombre.replace(/ /g,'_')}.pdf`)}>
                📑 Estado de cuenta PDF
              </Btn>
            )}
          </div>

          {!docSeleccionado && (
            <div style={{ padding:'40px 20px',textAlign:'center',color:C.text2,fontSize:13 }}>
              💳 Busca un afiliado para ver su historial de pagos
            </div>
          )}

          {docSeleccionado && afilSelObj && (
            <>
              {/* Info afiliado */}
              <div style={{ background: afilSelObj._retirado ? C.amberBg : C.blueBg, border:`1px solid ${afilSelObj._retirado ? C.amber : C.blue}`,borderRadius:8,
                padding:'10px 16px',marginBottom:14,display:'flex',gap:24,flexWrap:'wrap',fontSize:13 }}>
                <div style={{ display:'flex',gap:10,alignItems:'center' }}>
                  <strong style={{ color: afilSelObj._retirado ? C.amber : C.blue }}>{afilSelObj.nombre}</strong>
                  {afilSelObj._retirado && <span style={{ fontSize:10,fontWeight:700,background:C.amber,color:'#fff',borderRadius:6,padding:'2px 8px' }}>RETIRADO</span>}
                </div>
                <div style={{ color:C.text2 }}>Doc: <strong>{afilSelObj.doc}</strong></div>
                <div style={{ color:C.text2 }}>Empresa: <strong>{afilSelObj.empresa||'—'}</strong></div>
                <div style={{ color:C.text2 }}>Cliente: <strong>{afilSelObj.cliente_txt||'—'}</strong></div>
                {afilSelObj.novedades && (
                  <div style={{ color:C.text2 }}>Novedades: <strong style={{ color:C.amber }}>{afilSelObj.novedades}</strong></div>
                )}
                {afilSelObj.detalle && (
                  <div style={{ color:C.text2 }}>Detalle: <strong style={{ color:C.blue }}>{afilSelObj.detalle}</strong></div>
                )}
                <div style={{ marginLeft:'auto',display:'flex',gap:16 }}>
                  <span style={{ color:C.green,fontWeight:600 }}>
                    ✅ Pagado: ${totalPagado.toLocaleString('es-CO')}
                  </span>
                  <span style={{ color:C.red,fontWeight:600 }}>
                    ⏳ Pendiente: ${totalPendiente.toLocaleString('es-CO')}
                  </span>
                </div>
              </div>

              <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
                <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
                  <thead>
                    <tr style={{ background:C.surface2 }}>
                      {['Código','Mes','Año','Total ($)','Estado','Banco','Novedades'].map(h=>(
                        <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                          color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {loadFact && <tr><td colSpan={7} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
                    {!loadFact && factAfil_filtradas.length===0 && (
                      <tr><td colSpan={7} style={{ padding:20,textAlign:'center',color:C.text2 }}>
                        {anioFiltro !== 'Todos' ? `Sin facturas para el año ${anioFiltro}` : 'Sin facturas registradas'}
                      </td></tr>
                    )}
                    {factAfil_filtradas.map((f,i)=>(
                      <tr key={f.id} style={{ borderBottom:`1px solid ${C.border}`,
                        background: f.estado==='pagado' ? C.greenBg : C.redBg }}>
                        <td style={{ ...tdc,fontFamily:'monospace',fontSize:12 }}>{f.codigo}</td>
                        <td style={tdc}>{f.mes}</td>
                        <td style={tdc}>{f.anio}</td>
                        <td style={{ ...tdc,fontWeight:600 }}>${(f.ingresos||0).toLocaleString('es-CO')}</td>
                        <td style={tdc}>
                          <span style={{
                            padding:'3px 8px',borderRadius:6,fontSize:11,fontWeight:600,
                            background: f.estado==='pagado' ? C.greenBg : C.redBg,
                            color: f.estado==='pagado' ? C.green : C.red,
                          }}>
                            {(f.estado||'').toUpperCase()}
                          </span>
                        </td>
                        <td style={{ ...tdc,fontSize:12,color:C.text2 }}>{f.banco||'—'}</td>
                        <td style={{ ...tdc,fontSize:11,color:C.text2,maxWidth:180 }}>
                          <span style={{ display:'-webkit-box',WebkitLineClamp:2,
                            WebkitBoxOrient:'vertical',overflow:'hidden' }}>
                            {f.novedades||'—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══ TAB: DOCUMENTOS ═══ */}
      {tab === 'documentos' && (
        <DocumentosTab
          todos={todos} api={api} qc={qc}
          docBusqDoc={docBusqDoc} setDocBusqDoc={setDocBusqDoc}
          docDocSel={docDocSel} setDocDocSel={setDocDocSel}
          uploading={uploading} setUploading={setUploading}
        />
      )}

      {/* ═══ TAB: SEGUIMIENTO ═══ */}
      {tab === 'seguimiento' && (
        <div>
          {/* Banner política 10 días */}
          <div style={{ borderRadius:10, marginBottom:10, overflow:'hidden', border:`1px solid ${C.border}` }}>
            <div style={{ background:C.amberBg, padding:'10px 14px', display:'flex', alignItems:'center', gap:10 }}>
              <span style={{ fontSize:16 }}>⏱️</span>
              <div style={{ flex:1 }}>
                <span style={{ fontSize:13, fontWeight:700, color:C.amber }}>Política: máximo 10 días para activación</span>
                <span style={{ fontSize:12, color:C.text2, marginLeft:10 }}>
                  Revisa y activa a cada afiliado antes de que se cumpla el plazo.
                </span>
              </div>
              {(criticos > 0 || urgentes > 0) && (
                <div style={{ display:'flex', gap:6, flexShrink:0 }}>
                  {criticos > 0 && (
                    <span style={{ background:C.red, color:'#fff', borderRadius:20, padding:'2px 12px', fontSize:12, fontWeight:700 }}>
                      ⚠️ {criticos} vencido{criticos!==1?'s':''}
                    </span>
                  )}
                  {urgentes > 0 && (
                    <span style={{ background:C.amber, color:'#fff', borderRadius:20, padding:'2px 12px', fontSize:12, fontWeight:700 }}>
                      ⏰ {urgentes} urgente{urgentes!==1?'s':''}
                    </span>
                  )}
                </div>
              )}
            </div>
            {/* Barra de urgencia visual */}
            {enSeguimiento.length > 0 && (
              <div style={{ display:'flex', height:4 }}>
                {criticos > 0 && <div style={{ flex:criticos, background:C.red }} />}
                {urgentes > 0 && <div style={{ flex:urgentes, background:C.amber }} />}
                {(enSeguimiento.length - criticos - urgentes) > 0 && (
                  <div style={{ flex: enSeguimiento.length - criticos - urgentes, background:C.greenBg }} />
                )}
              </div>
            )}
          </div>
          <input placeholder="🔍 Buscar nombre, documento, empresa, cliente..."
            value={segBusqueda} onChange={e=>setSegBusqueda(e.target.value)}
            style={{ width:'100%',padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
              fontSize:14,outline:'none',marginBottom:12,boxSizing:'border-box',background:C.surface,color:C.text }} />
          <BarraFiltros
            filtros={[
              { key:'empresa', label:'Empresa', icon:'🏢', options: listas.empresas||[] },
              { key:'cliente', label:'Cliente', icon:'👤', options: clientesUnicos },
            ]}
            valores={segFiltros}
            onChange={(key,vals) => setSegFiltros(f=>({...f,[key]:vals}))}
            onLimpiar={() => setSegFiltros({ empresa:[], cliente:[] })}
          />
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
              <thead>
                <tr style={{ background:C.surface2 }}>
                  {['Nombre','Empresa','Documento','Cliente','EPS','AFP','ARL','CCF','Días','Novedades','Detalle','Acciones'].map(h=>(
                    <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                      color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {enSeguimientoFiltrado.length===0 && (
                  <tr><td colSpan={12} style={{ padding:30,textAlign:'center',color:C.text2 }}>
                    No hay afiliados en espera de activación
                  </td></tr>
                )}
                {enSeguimientoFiltrado.map(a=>{
                  const dias = diasEnEspera(a);
                  const urg  = urgenciaEspera(dias);
                  const rowBg = urg?.nivel==='critico' ? C.redBg : urg?.nivel==='urgente' ? C.amberBg : C.surface;
                  return (
                  <tr key={a.id}
                    style={{ borderBottom:`1px solid ${C.border}`, background:rowBg, transition:'background .1s' }}
                    onMouseEnter={e=>{ if(urg?.nivel==='ok'||!urg) e.currentTarget.style.background=C.surface2; }}
                    onMouseLeave={e=>{ e.currentTarget.style.background=rowBg; }}>
                    <td style={{ ...tdc }}>
                      <div style={{ fontWeight:700, color: urg?.nivel==='critico' ? C.red : urg?.nivel==='urgente' ? C.amber : C.text }}>
                        {a.nombre}
                      </div>
                    </td>
                    <td style={tdc}>{a.empresa||'—'}</td>
                    <td style={{ ...tdc,fontFamily:'monospace',fontSize:12 }}>
                      <span style={{ fontSize:10,fontWeight:700,color:C.text2,marginRight:4 }}>{a.tipo_doc||'CC'}</span>{a.doc}
                    </td>
                    <td style={tdc}>{a.cliente_txt||'—'}</td>
                    <td style={{ ...tdc,fontSize:11,fontWeight:700,color:C.text }}>{a.eps||'—'}</td>
                    <td style={{ ...tdc,fontSize:11,color:C.text2 }}>{a.afp||'—'}</td>
                    <td style={{ ...tdc,fontSize:11,color:C.text2 }}>{a.arl||'—'}</td>
                    <td style={{ ...tdc,fontSize:11,color:C.text2 }}>{a.ccf||'—'}</td>
                    <td style={tdc}>
                      {urg ? (
                        <span style={{ fontSize:11, fontWeight:700, borderRadius:20, padding:'2px 10px',
                          background: urg.nivel==='critico' ? C.red : urg.nivel==='urgente' ? C.amber : C.surface2,
                          color: urg.nivel==='ok' ? C.text2 : '#fff', whiteSpace:'nowrap' }}>
                          {urg.label}
                        </span>
                      ) : <span style={{ fontSize:11,color:C.text2 }}>—</span>}
                    </td>
                    <td style={{ ...tdc,maxWidth:160 }}>
                      {a.novedades ? (
                        <span onClick={() => setTextoModal({ titulo:'Novedades', nombre:a.nombre, texto:a.novedades })}
                          style={{ fontSize:11,color:C.amber,fontWeight:600,cursor:'pointer',display:'-webkit-box',
                            WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden' }}>
                          📝 {a.novedades}
                        </span>
                      ) : <span style={{ fontSize:11,color:C.text2 }}>—</span>}
                    </td>
                    <td style={{ ...tdc,maxWidth:180 }}>
                      {a.detalle ? (
                        <span onClick={() => setTextoModal({ titulo:'Detalle', nombre:a.nombre, texto:a.detalle })}
                          style={{ fontSize:11,color:C.blue,fontWeight:600,cursor:'pointer',display:'-webkit-box',
                            WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden' }}>
                          💬 {a.detalle}
                        </span>
                      ) : <span style={{ fontSize:11,color:C.text2 }}>—</span>}
                    </td>
                    <td style={tdc}>
                      <div style={{ display:'flex',gap:4 }}>
                        <Btn size="sm" variant="success" disabled={activarAfiliado.isPending}
                          onClick={()=>setConfirm({ title:'Activar afiliado',
                            message:`¿Activar a "${a.nombre}"? Su estado cambiará a ACTIVO.`,
                            confirmLabel:'Activar', variant:'success',
                            onConfirm:()=>activarAfiliado.mutate(a) })}>
                          ✓ Activar
                        </Btn>
                        <Btn size="sm" variant="secondary" onClick={()=>openEditar(a)}>✏️ Editar</Btn>
                      </div>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ TAB: SEGUIMIENTO ARL ═══ */}
      {tab === 'arl' && (
        <div>
          {/* Barra superior */}
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14, gap:10, flexWrap:'wrap' }}>
            <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
              <select value={arlFiltroCliente} onChange={e => { setArlFiltroCliente(e.target.value); setArlSeleccionados([]); }}
                style={{ padding:'8px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', color:C.text, background:C.surface }}>
                <option value="">👤 Todos los clientes</option>
                {clientesUnicos.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              {arlSeleccionados.length > 0 && (
                <div style={{ display:'flex', gap:6, alignItems:'center' }}>
                  <span style={{ fontSize:12, color:C.text2 }}>{arlSeleccionados.length} seleccionados</span>
                  <select value={arlBulkEstado} onChange={e => setArlBulkEstado(e.target.value)}
                    style={{ padding:'7px 10px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:12, outline:'none', color:C.text, background:C.surface }}>
                    <option value="activo">Activo</option>
                    <option value="retirar">Retirar</option>
                    <option value="retirado">Retirado</option>
                  </select>
                  <Btn size="sm" variant="primary" disabled={arlBulk.isPending}
                    onClick={() => arlBulk.mutate({ ids: arlSeleccionados, estado: arlBulkEstado })}>Aplicar</Btn>
                  <Btn size="sm" variant="secondary" onClick={() => setArlSeleccionados([])}>Cancelar</Btn>
                </div>
              )}
            </div>
            <Btn size="sm" variant="primary" onClick={abrirNuevoArl}>+ Nuevo registro</Btn>
          </div>

          {/* Tabla */}
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
              <thead>
                <tr style={{ background:C.surface2 }}>
                  <th style={{ padding:'10px 12px', width:36 }}>
                    <input type="checkbox" checked={todosArlSel} onChange={toggleTodosArl} />
                  </th>
                  {['Nombre','Documento','Cliente','Empresa','Fecha afiliación','Días','Entidad ARL','Nivel ARL','Estado','Observaciones','Acciones'].map(h => (
                    <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600,
                      color:C.text2, borderBottom:`1px solid ${C.border}`, whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {segArlFiltrado.length === 0 && (
                  <tr><td colSpan={12} style={{ padding:30, textAlign:'center', color:C.text2 }}>
                    No hay registros de seguimiento ARL
                  </td></tr>
                )}
                {segArlFiltrado.map(row => {
                  const alerta = arlAlerta(row);
                  const restantes = diasRestantesArl(row);
                  const restColor = restantes === null ? C.text2
                    : restantes <= 0  ? C.red
                    : restantes <= 5  ? C.amber
                    : C.green;
                  const restBg = restantes === null ? 'transparent'
                    : restantes <= 0  ? C.redBg
                    : restantes <= 5  ? C.amberBg
                    : C.greenBg;
                  return (
                    <tr key={row.id} style={{ borderBottom:`1px solid ${C.border}`, background: alerta ? C.amberBg : C.surface }}>
                      <td style={{ ...tdc, width:36 }}>
                        <input type="checkbox" checked={arlSeleccionados.includes(row.id)} onChange={() => toggleUnoArl(row.id)} />
                      </td>
                      <td style={{ ...tdc, fontWeight:600 }}>{row.nombre}</td>
                      <td style={{ ...tdc, fontFamily:'monospace', fontSize:12 }}>{row.documento}</td>
                      <td style={tdc}>{row.cliente||'—'}</td>
                      <td style={tdc}>{row.empresa||'—'}</td>
                      <td style={tdc}>{row.fecha_afiliacion||'—'}</td>
                      <td style={{ ...tdc, textAlign:'center' }}>
                        {restantes === null ? <span style={{ color:C.text2 }}>—</span>
                          : <span style={{ fontSize:12, fontWeight:700, color:restColor, background:restBg,
                              borderRadius:6, padding:'2px 8px', whiteSpace:'nowrap' }}>
                              {restantes <= 0 ? `Vencido ${Math.abs(restantes)}d` : `${restantes}d`}
                            </span>
                        }
                      </td>
                      <td style={{ ...tdc, fontSize:12, fontWeight:600 }}>{row.entidad_arl||'SURA'}</td>
                      <td style={{ ...tdc, fontSize:12 }}>{row.nivel_arl||'N/A'}</td>
                      <td style={tdc}>{statusBadge(row.estado==='activo'?'ACTIVO':row.estado==='retirar'?'PENDIENTE DE RETIRAR':'RETIRADO')}</td>
                      <td style={{ ...tdc, maxWidth:180, fontSize:12, color:C.text2 }}>{row.observaciones||'—'}</td>
                      <td style={tdc}>
                        <div style={{ display:'flex', gap:4 }}>
                          <Btn size="sm" variant="secondary" onClick={() => abrirEditarArl(row)}>✏️</Btn>
                          <Btn size="sm" variant="danger" disabled={arlEliminar.isPending}
                            onClick={() => setConfirm({ title:'Eliminar registro',
                              message:`¿Eliminar a "${row.nombre}"? Esta acción no se puede deshacer.`,
                              confirmLabel:'Eliminar', variant:'danger',
                              onConfirm:() => arlEliminar.mutate(row.id) })}>🗑️</Btn>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

        </div>
      )}

      {/* ─── MODAL SEGUIMIENTO ARL ─── */}
      <Modal open={arlModal !== null} onClose={() => setArlModal(null)}
        title={arlModal === 'nuevo' ? 'Nuevo registro ARL' : 'Editar registro ARL'}>
        <InputUp label="Nombre" value={arlForm.nombre} onChange={v => setArlForm(f=>({...f,nombre:v}))} placeholder="Nombre completo" />
        <InputUp label="Documento" value={arlForm.documento} onChange={v => setArlForm(f=>({...f,documento:v}))} placeholder="Número de documento" />
        <Sel label="Cliente" value={arlForm.cliente} onChange={v => setArlForm(f=>({...f,cliente:v}))}
          options={['', ...(listas.clientes||[])].map(c=>({value:c, label:c||'— Seleccionar cliente'}))} />
        <Sel label="Empresa" value={arlForm.empresa} onChange={v => setArlForm(f=>({...f,empresa:v}))}
          options={['', ...(listas.empresas||[])].map(e=>({value:e, label:e||'— Seleccionar'}))} />
        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Fecha de afiliación</label>
          <input type="date" value={arlForm.fecha_afiliacion}
            onChange={e => setArlForm(f=>({...f,fecha_afiliacion:e.target.value}))}
            style={{ width:'100%',padding:'9px 12px',border:`1px solid ${C.border}`,borderRadius:7,
              fontSize:13,outline:'none',boxSizing:'border-box',color:C.text,background:C.surface,colorScheme:'inherit' }} />
        </div>
        <Sel label="Entidad ARL" value={arlForm.entidad_arl} onChange={v => setArlForm(f=>({...f,entidad_arl:v}))}
          options={[{value:'SURA',label:'SURA'},{value:'POSITIVA',label:'POSITIVA'}]} />
        <Sel label="Nivel ARL" value={arlForm.nivel_arl} onChange={v => setArlForm(f=>({...f,nivel_arl:v}))}
          options={['N/A','1','2','3','4','5']} />
        <div style={{ marginBottom:12 }}>
          <label style={lbl}>Observaciones</label>
          <textarea value={arlForm.observaciones||''} onChange={e => setArlForm(f=>({...f,observaciones:e.target.value}))}
            rows={3} placeholder="Opcional..."
            style={{ width:'100%',padding:'9px 12px',border:`1px solid ${C.border}`,borderRadius:7,
              fontSize:13,outline:'none',boxSizing:'border-box',color:C.text,background:C.surface,resize:'vertical' }} />
        </div>
        {arlModal !== 'nuevo' && (
          <Sel label="Estado" value={arlForm.estado||'activo'} onChange={v => setArlForm(f=>({...f,estado:v}))}
            options={[{value:'activo',label:'Activo'},{value:'retirar',label:'Retirar'},{value:'retirado',label:'Retirado'}]} />
        )}
        <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:8 }}>
          <Btn variant="secondary" onClick={() => setArlModal(null)}>Cancelar</Btn>
          <Btn variant="primary" disabled={arlCrear.isPending||arlEditar.isPending} onClick={submitArlForm}>
            {arlModal === 'nuevo' ? 'Crear' : 'Guardar'}
          </Btn>
        </div>
      </Modal>

      <ConfirmModal
        open={!!confirm}
        title={confirm?.title}
        message={confirm?.message}
        confirmLabel={confirm?.confirmLabel || 'Eliminar'}
        variant={confirm?.variant || 'danger'}
        onConfirm={() => { confirm?.onConfirm(); setConfirm(null); }}
        onCancel={() => setConfirm(null)}
      />

      {/* ─── MODAL FORMULARIO ─── */}
      <Modal open={!!modal} onClose={()=>setModal(null)} width={720}
        title={modal==='nuevo'?'➕ Nuevo afiliado':`✏️ Editar — ${form.nombre||''}`}>
        <Seccion title="Datos personales" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <InputUp label="Nombre completo *" value={form.nombre||''}
            onChange={v=>sf('nombre', v.replace(/[^a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s]/g, ''))} />
          <div style={{ marginBottom:14 }}>
            <label style={lbl}>Tipo y N° Documento *</label>
            <div style={{ display:'flex', gap:8 }}>
              <select value={form.tipo_doc||'CC'} onChange={e=>sf('tipo_doc',e.target.value)}
                style={{ ...inp2, width:'auto', flexShrink:0, paddingRight:24 }}>
                <option value="CC">CC</option>
                <option value="CE">CE</option>
                <option value="PT">PT</option>
                <option value="PA">PA</option>
                <option value="NIT">NIT</option>
              </select>
              <input value={form.doc||''} onChange={e=>sf('doc',e.target.value.replace(/[^0-9]/g,''))}
                placeholder="SOLO NÚMEROS"
                inputMode="numeric"
                style={{ ...inp2, flex:1 }} />
            </div>
          </div>
          <InputUp label="Cargo"    value={form.cargo||''}
            onChange={v=>sf('cargo', v.replace(/[^a-zA-ZáéíóúÁÉÍÓÚüÜñÑ0-9\s]/g, ''))} />
          <InputUp label="Teléfono" value={form.tel||''}
            onChange={v=>sf('tel', v.replace(/[^0-9]/g,''))} type="tel" />
          <InputUp label="Email"             value={form.email||''} onChange={v=>sf('email',v)} style={{ gridColumn:'1/-1' }} />
          <InputUp label="Dirección"         value={form.dir||''} onChange={v=>sf('dir',v)} />
          <InputUp label="Ciudad"            value={form.ciudad||''} onChange={v=>sf('ciudad',v)} />
        </div>

        <Seccion title="Empresa y contrato" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <div style={{ marginBottom:14 }}>
            <label style={lbl}>Razón Social *</label>
            <select value={form.empresa||''} onChange={e=>sf('empresa',e.target.value)}
              style={{ ...inp2, cursor:'pointer',
                border:`1px solid ${!form.empresa ? C.red : C.border}`,
                boxShadow: !form.empresa ? `0 0 0 2px ${C.red}22` : 'none' }}>
              <option value="">— Seleccionar empresa (requerido)</option>
              {(listas.empresas||[]).map(e=><option key={e} value={e}>{e}</option>)}
            </select>
            {!form.empresa && (
              <span style={{ fontSize:11, color:C.red, marginTop:3, display:'block' }}>
                Selecciona una empresa para continuar
              </span>
            )}
          </div>
          <Sel label="Subtipo" value={form.subtipo||'0'} onChange={v=>sf('subtipo',v)}
            options={(listas.subtipos||['0','3','4','20','22']).map(s=>({value:s,label:s}))} />
          <Sel label="Cliente (empresa o persona que contrata)" value={form.cliente_txt||''}
            onChange={v=>sf('cliente_txt',v)} style={{ gridColumn:'1/-1' }}
            options={['', ...(listas.clientes||[])].map(c=>({value:c, label:c||'— Seleccionar cliente'}))} />
        </div>

        <Seccion title="Afiliaciones SS" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <Sel label="EPS"        value={form.eps||''} onChange={v=>sf('eps',v)} options={[''].concat(listas.eps||[])} />
          <Sel label="CCF (caja)" value={form.ccf||''} onChange={v=>sf('ccf',v)} options={[''].concat(listas.ccf||[])} />
          <Sel label="AFP"        value={form.afp||''} onChange={v=>sf('afp',v)} options={[''].concat(listas.afp||[])} />
        </div>

        <div style={{ marginBottom:14 }}>
          <label style={{ ...lbl, marginBottom:8, display:'block' }}>
            Servicios contratados
            {form.arl && form.arl !== '' && form.arl !== 'N/A' && (
              <span style={{ marginLeft:8,color:C.blue,fontWeight:600,fontSize:11 }}>
                · ARL nivel {form.arl} activo
              </span>
            )}
          </label>
          <div style={{ display:'flex',flexWrap:'wrap',gap:8,padding:'12px 14px',
            background:C.surface2,border:`1px solid ${C.border}`,borderRadius:8 }}>
            {SERVICIOS.map(s=>{
              const checked = (form.servicios||[]).includes(s);
              return (
                <button key={s} type="button" onClick={()=>toggleSrv(s)} style={{
                  display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
                  gap:6, cursor:'pointer', padding:'12px 16px', borderRadius:10,
                  minWidth:72,
                  background: checked ? C.primary : C.surface,
                  border: `2px solid ${checked ? C.primary : C.border}`,
                  color: checked ? '#fff' : C.text2,
                  fontWeight: checked ? 700 : 500,
                  fontSize: 13,
                  transition: 'all .15s',
                  boxShadow: checked ? '0 2px 8px rgba(0,0,0,.15)' : 'none',
                  outline: 'none',
                }}>
                  <span style={{ fontSize:18, lineHeight:1 }}>{checked ? '✓' : '○'}</span>
                  {s}
                </button>
              );
            })}
          </div>
        </div>

        <Seccion title="Estado" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <Sel label="Estado del afiliado" value={form.estado||'ACTIVO'}
            onChange={v=>{ sf('estado',v); sf('estado_srv',v); }}
            options={(listas.estados_srv||ESTADOS_SRV).map(e=>({value:e,label:e}))} />
          <InputUp label="Fecha afiliación *" type="date" value={form.fecha_afiliacion||''} onChange={v=>sf('fecha_afiliacion',v)} />
        </div>

        <Seccion title="IBC, novedades y detalle" />
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <div style={{ marginBottom:14 }}>
            <label style={lbl}>IBC individual ($) — vacío = usa global</label>
            <input type="number" value={form.ibc||''} onChange={e=>sf('ibc',e.target.value?+e.target.value:null)}
              placeholder={`IBC global: ${(1750905).toLocaleString('es-CO')}`}
              style={inp2} />
          </div>
          <div style={{ marginBottom:14 }}>
            <label style={lbl}>Novedades</label>
            <textarea value={form.novedades||''} onChange={e=>sf('novedades',UP(e.target.value))}
              placeholder="NOVEDADES DEL AFILIADO..." rows={2}
              style={{ ...inp2, resize:'vertical', textTransform:'uppercase' }} />
          </div>
        </div>
        <div style={{ marginBottom:14 }}>
          <label style={lbl}>Detalle</label>
          <textarea value={form.detalle||''} onChange={e=>sf('detalle',e.target.value)}
            placeholder="Información adicional visible en el portal del cliente y dashboard..."
            rows={3}
            style={{ ...inp2, resize:'vertical' }} />
        </div>

        <Seccion title="Adjuntar documentos (opcional)" />
        <div style={{ marginBottom:12 }}>
          <label style={{ display:'block', border:`2px dashed ${C.border}`, borderRadius:10,
            cursor:'pointer', background:C.surface2, overflow:'hidden' }}>
            <div style={{ padding:'20px 16px', textAlign:'center' }}>
              <div style={{ fontSize:22, marginBottom:6 }}>📎</div>
              <div style={{ fontSize:13, fontWeight:600, color:C.text, marginBottom:2 }}>
                Haz clic o arrastra archivos aquí
              </div>
              <div style={{ fontSize:11, color:C.text2 }}>PDF, Word, Excel, imágenes</div>
            </div>
            <input type="file" multiple style={{ display:'none' }}
              accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
              onChange={e => setPendingFiles(prev => [...prev, ...Array.from(e.target.files)])} />
          </label>
          {pendingFiles.length > 0 && (
            <div style={{ marginTop:10, display:'flex', flexWrap:'wrap', gap:6 }}>
              {pendingFiles.map((f,i) => (
                <div key={i} style={{ display:'flex', alignItems:'center', gap:6, padding:'5px 10px',
                  background:C.blueBg, border:`1px solid ${C.blue}`, borderRadius:7, fontSize:12 }}>
                  <span style={{ color:C.blue }}>📄 {f.name}</span>
                  <button onClick={()=>setPendingFiles(prev=>prev.filter((_,j)=>j!==i))}
                    style={{ border:'none',background:'none',cursor:'pointer',color:C.red,fontWeight:700,padding:0,fontSize:15,lineHeight:1 }}>×</button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display:'flex',justifyContent:'flex-end',gap:10,marginTop:8,
          borderTop:`1px solid ${C.border}`,paddingTop:14 }}>
          <Btn variant="secondary" onClick={()=>setModal(null)}>Cancelar</Btn>
          <Btn onClick={()=>guardar.mutate()}
            disabled={guardar.isPending || !form.empresa || !form.nombre?.trim() || !form.doc?.trim() || !form.cliente_txt?.trim() || !form.fecha_afiliacion}
            title={!form.empresa?'Selecciona una empresa':!form.nombre?.trim()?'Ingresa el nombre':!form.doc?.trim()?'Ingresa el documento':!form.cliente_txt?.trim()?'Selecciona el cliente':''}>
            {guardar.isPending?'Guardando...':'💾 Guardar afiliado'}
          </Btn>
        </div>
      </Modal>

      {/* Overlay texto completo (novedades / detalle) — sin Radix, sin click-outside issues */}
      {textoModal && (
        <div
          style={{ position:'fixed', inset:0, zIndex:9999, background:'rgba(0,0,0,0.55)',
            display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}
          onClick={() => setTextoModal(null)}
        >
          <div
            style={{ background:C.surface, borderRadius:14, padding:'24px 28px', maxWidth:540,
              width:'100%', maxHeight:'80vh', overflowY:'auto', position:'relative',
              boxShadow:'0 8px 40px rgba(0,0,0,0.3)', border:`1px solid ${C.border}` }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ fontWeight:700, fontSize:16, marginBottom:16, color:C.text, paddingRight:28 }}>
              {textoModal.titulo === 'Novedades' ? '📝' : '💬'} {textoModal.titulo} — {textoModal.nombre}
            </div>
            <p style={{ margin:0, fontSize:14, color:C.text, lineHeight:1.6, whiteSpace:'pre-wrap' }}>
              {textoModal.texto}
            </p>
            <button onClick={() => setTextoModal(null)}
              style={{ position:'absolute', top:14, right:18, background:'none', border:'none',
                cursor:'pointer', fontSize:20, color:C.text2, lineHeight:1, padding:0 }}>✕</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Seccion({ title }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, marginTop:20, marginBottom:12 }}>
      <div style={{ width:3, height:16, borderRadius:2, background:C.primary, flexShrink:0 }} />
      <span style={{ fontSize:11, fontWeight:700, color:C.primary, textTransform:'uppercase', letterSpacing:'0.08em' }}>
        {title}
      </span>
      <div style={{ flex:1, height:1, background:C.border }} />
    </div>
  );
}
function Chip({ children }) {
  return <span style={{ background:C.surface2,color:C.text,border:`1px solid ${C.border}`,borderRadius:5,padding:'2px 8px',fontSize:11 }}>{children}</span>;
}
const SRV_TOOLTIP = {
  'EPS':   'Entidad Promotora de Salud',
  'AFP':   'Administradora Fondos de Pensiones',
  'CCF':   'Caja de Compensación Familiar',
  'ARL 1': 'Administradora Riesgos Laborales (nivel 1)',
  'ARL 2': 'Administradora Riesgos Laborales (nivel 2)',
  'ARL 3': 'Administradora Riesgos Laborales (nivel 3)',
  'ARL 4': 'Administradora Riesgos Laborales (nivel 4)',
  'ARL 5': 'Administradora Riesgos Laborales (nivel 5)',
  'N/A':   'Sin servicio',
};
function SrvChip({ children }) {
  const chip = (
    <span style={{ background:C.blueBg,color:C.blue,borderRadius:5,padding:'1px 7px',fontSize:10,fontWeight:600 }}>
      {children}
    </span>
  );
  const label = SRV_TOOLTIP[children];
  if (!label) return chip;
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{chip}</TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

const tdc = { padding:'10px 12px',fontSize:13,color:C.text,verticalAlign:'middle' };
const lbl = { display:'block',fontSize:11,color:C.text2,fontWeight:700,marginBottom:6,textTransform:'uppercase',letterSpacing:'0.06em' };
const inp2 = { width:'100%',padding:'10px 12px',border:`1.5px solid ${C.border}`,borderRadius:8,fontSize:14,outline:'none',color:C.text,background:C.surface,boxSizing:'border-box',transition:'border-color .15s' };
const btnPag = {
  padding:'6px 12px', border:`1px solid ${C.border}`, borderRadius:6,
  background:C.surface, cursor:'pointer', fontSize:13, color:C.text,
};

// ─── TAB DOCUMENTOS ─────────────────────────────────────────────────────────
function DocumentosTab({ todos, api, qc, docBusqDoc, setDocBusqDoc, docDocSel, setDocDocSel, uploading, setUploading }) {
  const [docConfirm, setDocConfirm] = React.useState({ open: false, title: '', message: '', onConfirm: null });
  const sugerencias = docBusqDoc.length >= 2 && !docDocSel
    ? todos.filter(a => `${a.nombre} ${a.doc}`.toLowerCase().includes(docBusqDoc.toLowerCase())).slice(0,8)
    : [];

  const { data: docs=[], isLoading } = useQuery({
    queryKey: ['documentos', docDocSel],
    queryFn: () => api.get('/documentos', { params: { afiliado_doc: docDocSel } }).then(r=>r.data),
    enabled: !!docDocSel,
  });
  const afilSel = todos.find(a=>a.doc===docDocSel);

  const handleUpload = async (files) => {
    if (!docDocSel || !files.length || uploading) return;  // guard doble click/drop
    setUploading(true);
    // Generar upload_id por archivo ANTES de la petición para que los reintentos sean idempotentes
    const uploads = files.map(file => ({
      file,
      ...buildUploadForm(file, { afiliado_doc: docDocSel, contexto: 'afiliado' }),
    }));
    const resultados = await Promise.allSettled(
      uploads.map(({ fd }) => api.post('/documentos', fd))
    );
    await qc.refetchQueries({ queryKey: ['documentos', docDocSel] });
    setUploading(false);
    const errores = resultados
      .map((r, i) => r.status === 'rejected' ? `${files[i].name}: ${r.reason?.response?.data?.detail || 'Error'}` : null)
      .filter(Boolean);
    if (errores.length) toast.error(`Error al subir ${errores.length} archivo(s)`);
  };

  const handleDelete = (id) => {
    setDocConfirm({
      open: true,
      title: 'Eliminar documento',
      message: '¿Eliminar este documento? Esta acción no se puede deshacer.',
      onConfirm: async () => {
        setDocConfirm(s => ({ ...s, open: false }));
        try {
          await api.delete(`/documentos/${id}`);
          qc.invalidateQueries({ queryKey: ['documentos', docDocSel] });
        } catch (e) {
          toast.error(e.response?.data?.detail || 'Error eliminando documento');
        }
      },
    });
  };

  const handleDownload = async (doc) => {
    try {
      const res = await api.get(`/documentos/${doc.id}/descargar`);
      if (res.data?.url) {
        window.open(res.data.url, '_blank');
        return;
      }
      // Fallback local (dev): refetch como blob
      const res2 = await api.get(`/documentos/${doc.id}/descargar`, { responseType: 'blob' });
      const objUrl = URL.createObjectURL(res2.data);
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = doc.nombre;
      a.click();
      URL.revokeObjectURL(objUrl);
    } catch (e) {
      toast.error('Error descargando archivo');
    }
  };

  const fmtSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes/1024).toFixed(1)} KB`;
    return `${(bytes/1048576).toFixed(1)} MB`;
  };

  const iconByType = (tipo) => {
    if (['jpg','jpeg','png','gif'].includes(tipo)) return '🖼️';
    if (tipo === 'pdf') return '📕';
    if (['doc','docx'].includes(tipo)) return '📝';
    if (['xls','xlsx'].includes(tipo)) return '📊';
    return '📄';
  };

  return (
    <div>
      <div style={{ display:'flex',alignItems:'flex-start',gap:12,marginBottom:16,flexWrap:'wrap' }}>
        <div style={{ position:'relative',flex:'0 0 340px' }}>
          <input placeholder="🔍 Buscar afiliado por nombre o documento..."
            value={docBusqDoc}
            onChange={e=>{ setDocBusqDoc(e.target.value); if(!e.target.value) setDocDocSel(''); }}
            style={{ width:'100%',padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
              fontSize:14,outline:'none',boxSizing:'border-box',background:C.surface,color:C.text }} />
          {sugerencias.length > 0 && (
            <div style={{ position:'absolute',top:'100%',left:0,right:0,background:C.surface,
              border:`1px solid ${C.border}`,borderRadius:8,boxShadow:'0 4px 12px rgba(0,0,0,.1)',
              zIndex:100,maxHeight:200,overflowY:'auto' }}>
              {sugerencias.map(a => (
                <div key={a.id} onClick={()=>{ setDocDocSel(a.doc); setDocBusqDoc(a.nombre); }}
                  style={{ padding:'9px 14px',cursor:'pointer',fontSize:13,borderBottom:`1px solid ${C.border}` }}
                  onMouseEnter={e=>e.currentTarget.style.background=C.surface2}
                  onMouseLeave={e=>e.currentTarget.style.background=''}>
                  <strong>{a.nombre}</strong>
                  <span style={{ marginLeft:8,color:C.text2,fontSize:11 }}>{a.doc} · {a.empresa||''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {docDocSel && (
          <Btn size="sm" variant="secondary" onClick={()=>{ setDocDocSel(''); setDocBusqDoc(''); }}>✕ Limpiar</Btn>
        )}
      </div>

      {!docDocSel && (
        <div style={{ padding:'40px 20px',textAlign:'center',color:C.text2,fontSize:13 }}>
          📎 Busca un afiliado para ver y gestionar sus documentos
        </div>
      )}

      {docDocSel && afilSel && (
        <>
          <div style={{ background:C.blueBg,border:`1px solid ${C.blue}`,borderRadius:8,
            padding:'10px 16px',marginBottom:14,display:'flex',gap:24,flexWrap:'wrap',fontSize:13 }}>
            <div><strong style={{ color:C.blue }}>{afilSel.nombre}</strong></div>
            <div style={{ color:C.text2 }}>Doc: <strong>{afilSel.doc}</strong></div>
            <div style={{ color:C.text2 }}>Empresa: <strong>{afilSel.empresa||'—'}</strong></div>
          </div>

          {/* Zona de upload */}
          <div style={{ border:`2px dashed ${uploading ? C.text2 : C.border}`,borderRadius:10,padding:'20px',
            textAlign:'center',marginBottom:14,background:C.surface2,
            cursor: uploading ? 'not-allowed' : 'pointer',
            opacity: uploading ? 0.7 : 1, position:'relative' }}
            onClick={()=>{ if (!uploading) document.getElementById('doc-file-input')?.click(); }}
            onDragOver={e=>{ if (uploading) return; e.preventDefault();e.currentTarget.style.borderColor=C.blue;}}
            onDragLeave={e=>{e.currentTarget.style.borderColor=uploading ? C.text2 : C.border;}}
            onDrop={e=>{ if (uploading) return; e.preventDefault();e.currentTarget.style.borderColor=C.border;handleUpload(Array.from(e.dataTransfer.files));}}>
            <input id="doc-file-input" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx"
              style={{ display:'none' }} disabled={uploading}
              onChange={e=>{ if(!uploading && e.target.files.length) handleUpload(Array.from(e.target.files)); e.target.value=''; }} />
            <div style={{ fontSize:28,marginBottom:6 }}>📂</div>
            <div style={{ fontSize:13,color:C.text2 }}>
              {uploading ? 'Subiendo...' : 'Click o arrastra archivos aquí (PDF, imágenes, Word, Excel — máx 10 MB)'}
            </div>
          </div>

          {/* Lista de documentos */}
          {isLoading && <div style={{ textAlign:'center',color:C.text2,padding:20 }}>Cargando...</div>}
          {!isLoading && docs.length === 0 && (
            <div style={{ textAlign:'center',color:C.text2,padding:20,fontSize:13 }}>
              Sin documentos. Sube el primer archivo arriba.
            </div>
          )}
          {docs.length > 0 && (
            <div style={{ overflowX:'auto',borderRadius:10,border:`1px solid ${C.border}` }}>
              <table style={{ width:'100%',borderCollapse:'collapse',background:C.surface }}>
                <thead>
                  <tr style={{ background:C.surface2 }}>
                    {['','Nombre','Tipo','Tamaño','Subido por','Fecha','Acciones'].map(h=>(
                      <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                        color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {docs.map(d=>(
                    <tr key={d.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                      <td style={{ ...tdc,fontSize:20,width:30,textAlign:'center' }}>{iconByType(d.tipo)}</td>
                      <td style={{ ...tdc,fontWeight:500 }}>{d.nombre}</td>
                      <td style={{ ...tdc,fontSize:11,textTransform:'uppercase' }}>{d.tipo}</td>
                      <td style={{ ...tdc,fontSize:12,color:C.text2 }}>{fmtSize(d.tamano)}</td>
                      <td style={{ ...tdc,fontSize:12,color:C.text2 }}>{d.subido_por||'—'}</td>
                      <td style={{ ...tdc,fontSize:12,color:C.text2 }}>{d.creado ? new Date(d.creado).toLocaleDateString('es-CO') : '—'}</td>
                      <td style={tdc}>
                        <div style={{ display:'flex',gap:5 }}>
                          <Btn size="sm" variant="secondary" onClick={()=>handleDownload(d)}>⬇ Descargar</Btn>
                          <Btn size="sm" variant="danger" onClick={()=>handleDelete(d.id)}>×</Btn>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <ConfirmModal
        open={docConfirm.open}
        title={docConfirm.title}
        message={docConfirm.message}
        onConfirm={docConfirm.onConfirm}
        onCancel={() => setDocConfirm(s => ({ ...s, open: false }))}
      />
    </div>
  );
}
