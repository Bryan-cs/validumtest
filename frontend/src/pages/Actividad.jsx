import React, { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useReactTable, getCoreRowModel, getSortedRowModel, getPaginationRowModel, flexRender } from '@tanstack/react-table';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Card, Btn, ConfirmModal } from '../components/UI';

// ── Colores por módulo ────────────────────────────────────────────────────────
const MODULO_COLOR = {
  'Afiliados':    { bg: C.blueBg,   color: C.blue   },
  'Facturación':  { bg: C.greenBg,  color: C.green  },
  'Retiros':      { bg: C.amberBg,  color: C.amber  },
  'Sistema':      { bg: C.redBg,    color: C.red    },
  'Listas':       { bg: '#F3E8FF',  color: '#7C3AED'},
  'Config':       { bg: '#FEE2E2',  color: '#DC2626'},
  'Empleados':    { bg: '#ECFDF5',  color: '#059669'},
  'Usuarios':     { bg: '#FFF7ED',  color: '#EA580C'},
  'Tareas':       { bg: C.blueBg,   color: C.blue   },
};

function ModuloBadge({ modulo }) {
  const cfg = MODULO_COLOR[modulo] || { bg: C.surface2, color: C.text2 };
  return (
    <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 6, padding: '2px 8px',
      background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap' }}>
      {modulo}
    </span>
  );
}

// Icono según tipo de acción
function accionIcon(accion = '') {
  const a = accion.toLowerCase();
  if (a.includes('cre') || a.includes('regis') || a.includes('insert')) return '➕';
  if (a.includes('elim') || a.includes('borr') || a.includes('limpió')) return '🗑️';
  if (a.includes('edit') || a.includes('actua') || a.includes('modif')) return '✏️';
  if (a.includes('retir')) return '↪️';
  if (a.includes('login') || a.includes('sesión')) return '🔑';
  if (a.includes('export') || a.includes('descarg')) return '📥';
  if (a.includes('complet') || a.includes('finaliz')) return '✅';
  if (a.includes('tarea') || a.includes('asign')) return '📋';
  return '•';
}

const PER_PAGE = 50;

const sel = { padding: '8px 12px', border: `1px solid ${C.border}`, borderRadius: 7,
  fontSize: 13, outline: 'none', background: C.surface, color: C.text };

const MODULOS = ['', 'Afiliados', 'Facturación', 'Retiros', 'Empleados',
                 'Usuarios', 'Listas', 'Config', 'Sistema', 'Tareas'];

export default function Actividad() {
  const qc = useQueryClient();

  const hoy = new Date().toISOString().slice(0, 10);
  const haceUnMes = new Date(Date.now() - 30 * 86400_000).toISOString().slice(0, 10);

  const [desde,   setDesde]   = useState(haceUnMes);
  const [hasta,   setHasta]   = useState(hoy);
  const [modulo,  setModulo]  = useState('');
  const [usuario, setUsuario] = useState('');
  const [buscar,  setBuscar]  = useState('');
  const [confirm, setConfirm] = useState(false);
  const [actSorting, setActSorting] = useState([]);
  const [actPagination, setActPagination] = useState({ pageIndex: 0, pageSize: PER_PAGE });

  const { data: actRaw = { total: 0, items: [] }, isLoading } = useQuery({
    queryKey: ['actividad', desde, hasta, modulo, usuario],
    queryFn: () => api.get('/actividad', { params: { desde, hasta, modulo, usuario, limit: 500 } }).then(r => r.data),
    refetchInterval: 120_000,
  });
  const act = actRaw.items || actRaw;

  // Filtro local por texto libre
  const filtradas = buscar.trim()
    ? act.filter(a =>
        [a.usuario, a.accion, a.modulo, a.detalle, a.fecha]
          .join(' ').toLowerCase().includes(buscar.toLowerCase())
      )
    : act;

  const actColumns = useMemo(() => [
    {
      id: 'icono',
      header: '',
      enableSorting: false,
      cell: ({ row }) => <span style={{ fontSize: 15, display: 'block', textAlign: 'center', width: 32 }}>{accionIcon(row.original.accion)}</span>,
    },
    {
      accessorKey: 'fecha',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Fecha y hora {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ color: C.text2, whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: 11 }}>{row.original.fecha}</span>,
    },
    {
      accessorKey: 'usuario',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Usuario {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ fontWeight: 600, color: C.primary, whiteSpace: 'nowrap' }}>{row.original.usuario}</span>,
    },
    {
      accessorKey: 'modulo',
      header: 'Módulo',
      enableSorting: false,
      cell: ({ row }) => <ModuloBadge modulo={row.original.modulo} />,
    },
    {
      accessorKey: 'accion',
      header: 'Acción',
      enableSorting: false,
      cell: ({ row }) => <span style={{ color: C.text }}>{row.original.accion}</span>,
    },
    {
      accessorKey: 'detalle',
      header: 'Detalle',
      enableSorting: false,
      cell: ({ row }) => (
        <span style={{ color: C.text2, maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}
          title={row.original.detalle}>
          {row.original.detalle || '—'}
        </span>
      ),
    },
  ], []);

  const actTable = useReactTable({
    data: filtradas,
    columns: actColumns,
    state: { sorting: actSorting, pagination: actPagination },
    onSortingChange: setActSorting,
    onPaginationChange: setActPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  // Usuarios únicos para el selector
  const usuariosUnicos = [...new Set(act.map(a => a.usuario).filter(Boolean))].sort();

  const handleLimpiar = async () => {
    try {
      await api.delete('/actividad');
      qc.invalidateQueries({ queryKey: ['actividad'] });
      toast.success('Historial limpiado');
    } catch { toast.error('Error al limpiar historial'); }
    setConfirm(false);
  };

  const limpiarFiltros = () => {
    setDesde(haceUnMes); setHasta(hoy);
    setModulo(''); setUsuario(''); setBuscar('');
    setActPagination(p => ({ ...p, pageIndex: 0 }));
  };

  return (
    <div>
      <PageHeader
        title="Registro de actividad"
        subtitle="Trazabilidad completa de todas las acciones del sistema"
        action={
          <Btn variant="danger" onClick={() => setConfirm(true)}>🗑️ Limpiar historial</Btn>
        }
      />

      {/* Filtros */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>DESDE</label>
            <input type="date" style={sel} value={desde} onChange={e => setDesde(e.target.value)} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>HASTA</label>
            <input type="date" style={sel} value={hasta} onChange={e => setHasta(e.target.value)} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>MÓDULO</label>
            <select style={sel} value={modulo} onChange={e => setModulo(e.target.value)}>
              {MODULOS.map(m => <option key={m} value={m}>{m || 'Todos los módulos'}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>USUARIO</label>
            <select style={sel} value={usuario} onChange={e => setUsuario(e.target.value)}>
              <option value="">Todos los usuarios</option>
              {usuariosUnicos.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div style={{ flex: 1, minWidth: 160 }}>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>BUSCAR</label>
            <input style={sel} placeholder="Buscar en logs..."
              value={buscar} onChange={e => setBuscar(e.target.value)} />
          </div>
          <Btn variant="secondary" onClick={limpiarFiltros}>↺ Limpiar</Btn>
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: C.text2 }}>
          {isLoading ? 'Cargando...' : (
            <><strong style={{ color: C.primary }}>{filtradas.length}</strong> registro{filtradas.length !== 1 ? 's' : ''}
            {buscar && ` de ${act.length} totales`}
            {filtradas.length > PER_PAGE && <span style={{ marginLeft: 8 }}>— página <strong style={{ color: C.primary }}>{actTable.getState().pagination.pageIndex + 1}</strong> de {actTable.getPageCount()}</span>}</>
          )}
        </div>
      </Card>

      {/* Log */}
      <Card style={{ padding: 0 }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              {actTable.getHeaderGroups().map(hg => (
                <tr key={hg.id} style={{ background: C.surface2 }}>
                  {hg.headers.map(header => (
                    <th key={header.id} style={{ padding: '10px 12px', textAlign: 'left', color: C.text2, fontWeight: 600, borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap', fontSize: 11, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={actColumns.length} style={{ padding: 24, textAlign: 'center', color: C.text2 }}>Cargando...</td></tr>
              ) : actTable.getRowModel().rows.length === 0 ? (
                <tr><td colSpan={actColumns.length} style={{ padding: 24, textAlign: 'center', color: C.text2 }}>Sin registros para los filtros seleccionados</td></tr>
              ) : actTable.getRowModel().rows.map((row, i) => (
                <tr key={row.id} style={{ borderBottom: `1px solid ${C.border}`, background: i % 2 === 0 ? C.surface : C.surface2 }}>
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} style={{ padding: '8px 12px' }}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
        <span style={{ fontSize: 13, color: C.text2 }}>
          Página {actTable.getState().pagination.pageIndex + 1} de {actTable.getPageCount()} — {filtradas.length} total
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Btn variant="secondary" size="sm" disabled={!actTable.getCanPreviousPage()} onClick={() => actTable.previousPage()}>← Anterior</Btn>
          <Btn variant="secondary" size="sm" disabled={!actTable.getCanNextPage()} onClick={() => actTable.nextPage()}>Siguiente →</Btn>
        </div>
      </div>

      <ConfirmModal
        open={confirm}
        title="Limpiar historial de actividad"
        message="Se eliminarán todos los registros de actividad. Esta acción no se puede deshacer."
        confirmLabel="Limpiar todo"
        variant="danger"
        onConfirm={handleLimpiar}
        onCancel={() => setConfirm(false)}
      />
    </div>
  );
}
