import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useReactTable, getCoreRowModel, getSortedRowModel, flexRender } from '@tanstack/react-table';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, PageHeader, StatCard, fmt, ConfirmModal, ErrorMsg } from '../components/UI';

const UP = v => (v || '').toUpperCase();

const NOW = new Date();
const MES_ACTUAL = NOW.getMonth() + 1;
const ANIO_ACTUAL = NOW.getFullYear();
const MESES_ES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

const sel = { padding:'8px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', background:C.surface, color:C.text };
const tdc = { padding:'10px 12px', fontSize:13, color:C.text, verticalAlign:'middle' };
const lbl = { display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 };
const inp = { width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface };

export default function Empleados() {
  const qc = useQueryClient();
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [confirmState, setConfirmState] = useState({ open: false, title: '', message: '', onConfirm: null });
  const sf = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const [mes, setMes] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_emp_filtros'))?.mes ?? MES_ACTUAL; } catch { return MES_ACTUAL; } });
  const [anio, setAnio] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_emp_filtros'))?.anio ?? ANIO_ACTUAL; } catch { return ANIO_ACTUAL; } });

  useEffect(() => { try { localStorage.setItem('bbc_emp_filtros', JSON.stringify({ mes, anio })); } catch {} }, [mes, anio]);

  const { data: emps = [], isError: isErrorEmps, refetch: refetchEmps } = useQuery({ queryKey: ['empleados'], queryFn: () => api.get('/empleados').then(r => r.data), staleTime: 300_000 });
  const { data: usuarios = [] } = useQuery({ queryKey: ['usuarios'], queryFn: () => api.get('/usuarios').then(r => r.data), staleTime: 300_000 });
  const { data: gastos = [] } = useQuery({ queryKey: ['gastos', mes, anio], queryFn: () => api.get('/gastos', { params: { mes, anio } }).then(r => r.data) });
  const { data: nomina = [] } = useQuery({ queryKey: ['nomina', mes, anio], queryFn: () => api.get('/nomina', { params: { mes, anio } }).then(r => r.data) });

  const nomTotal = nomina.reduce((s, n) => s + n.valor, 0);
  const gasTotal = gastos.reduce((s, g) => s + g.valor, 0);

  const guardarEmp = useMutation({
    mutationFn: () => modal === 'nuevo' ? api.post('/empleados', form) : api.put(`/empleados/${modal.id}`, form),
    onSuccess: (res) => {
      toast.success('Empleado guardado');
      if (modal === 'nuevo') {
        qc.setQueryData(['empleados'], prev => [...(prev || []), res.data]);
      } else {
        qc.setQueryData(['empleados'], prev => prev?.map(e => e.id === res.data.id ? res.data : e));
      }
      setModal(null);
    },
    onError: (e) => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  const eliminarEmp = useMutation({
    mutationFn: (id) => api.delete(`/empleados/${id}`),
    onSuccess: (_, id) => { toast.success('Empleado eliminado'); qc.setQueryData(['empleados'], prev => prev?.filter(e => e.id !== id)); },
    onError: (e) => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  const updateNomina = useMutation({
    mutationFn: ({ empleado_id, valor }) => api.put(`/nomina/${empleado_id}`, { valor }, { params: { mes, anio } }),
    onSuccess: (res) => {
      qc.setQueryData(['nomina', mes, anio], prev =>
        prev?.map(n => n.empleado_id === res.data.empleado_id ? { ...n, valor: res.data.valor } : n));
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const copiarNomina = useMutation({
    mutationFn: () => {
      const om = mes === 1 ? 12 : mes - 1;
      const oa = mes === 1 ? anio - 1 : anio;
      return api.post('/nomina/copiar', { mes_origen: om, anio_origen: oa, mes_destino: mes, anio_destino: anio });
    },
    onSuccess: (res) => { toast.success('Nómina copiada del mes anterior'); qc.setQueryData(['nomina', mes, anio], res.data); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const [gnombre, setGnom] = useState('');
  const [gvalor, setGval] = useState('');

  const addGasto = useMutation({
    mutationFn: () => api.post('/gastos', { nombre: gnombre, valor: parseFloat(gvalor) || 0, mes, anio }),
    onSuccess: (res) => { toast.success('Gasto agregado'); qc.setQueryData(['gastos', mes, anio], prev => [...(prev || []), res.data]); setGnom(''); setGval(''); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const delGasto = useMutation({
    mutationFn: (id) => api.delete(`/gastos/${id}`),
    onSuccess: (_, id) => { toast.success('Gasto eliminado'); qc.setQueryData(['gastos', mes, anio], prev => prev?.filter(g => g.id !== id)); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const copiarGastos = useMutation({
    mutationFn: () => {
      const om = mes === 1 ? 12 : mes - 1;
      const oa = mes === 1 ? anio - 1 : anio;
      return api.post('/gastos/copiar', { mes_origen: om, anio_origen: oa, mes_destino: mes, anio_destino: anio });
    },
    onSuccess: (res) => { toast.success('Gastos copiados del mes anterior'); qc.setQueryData(['gastos', mes, anio], res.data); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const anios = [ANIO_ACTUAL - 1, ANIO_ACTUAL, ANIO_ACTUAL + 1];

  const [empSorting, setEmpSorting] = useState([]);

  const empColumns = useMemo(() => [
    {
      accessorKey: 'nombre',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Nombre {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ fontWeight: 700, fontSize: 14 }}>{row.original.nombre}</span>,
    },
    {
      accessorKey: 'doc',
      header: 'Documento',
      cell: ({ row }) => <span style={{ fontFamily: 'monospace', fontSize: 13, fontWeight: 600 }}>{row.original.doc || '—'}</span>,
    },
    {
      accessorKey: 'cargo',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Cargo {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ fontSize: 13, fontWeight: 600 }}>{row.original.cargo}</span>,
    },
    {
      accessorKey: 'tel',
      header: 'Teléfono',
      enableSorting: false,
      cell: ({ row }) => <span style={{ fontSize: 13, fontWeight: 600 }}>{row.original.tel || '—'}</span>,
    },
    {
      accessorKey: 'activo',
      header: 'Estado',
      enableSorting: false,
      cell: ({ row }) => (
        <span style={{ background: row.original.activo ? C.greenBg : C.redBg, color: row.original.activo ? C.green : C.red, borderRadius: 10, padding: '2px 10px', fontSize: 11, fontWeight: 600 }}>
          {row.original.activo ? 'Activo' : 'Inactivo'}
        </span>
      ),
    },
    {
      id: 'acciones',
      header: '',
      enableSorting: false,
      cell: ({ row }) => {
        const e = row.original;
        return (
          <div style={{ display: 'flex', gap: 6 }}>
            <Btn size="sm" variant="secondary" onClick={() => { setForm({ ...e }); setModal(e); }}>✏️ Editar</Btn>
            <Btn size="sm" variant="danger" onClick={() => setConfirmState({ open:true, title:'Eliminar empleado', message:`¿Eliminar a ${e.nombre}? Esta acción no se puede deshacer.`, onConfirm:()=>{ eliminarEmp.mutate(e.id); setConfirmState(s=>({...s,open:false})); } })}>🗑️ Eliminar</Btn>
          </div>
        );
      },
    },
  ], [eliminarEmp.isPending]);

  const empTable = useReactTable({
    data: emps,
    columns: empColumns,
    state: { sorting: empSorting },
    onSortingChange: setEmpSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div>
      <PageHeader title="👔 Empleados y gastos" />
      {isErrorEmps && <ErrorMsg message="Error al cargar empleados" onRetry={refetchEmps} />}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <select style={sel} value={mes} onChange={e => setMes(+e.target.value)}>
          {MESES_ES.map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
        </select>
        <select style={sel} value={anio} onChange={e => setAnio(+e.target.value)}>
          {anios.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <StatCard label="Nómina del mes"    value={fmt(nomTotal)} color={C.red} />
        <StatCard label="Gastos del mes"    value={fmt(gasTotal)} color={C.amber} />
        <StatCard label="Total egresos"     value={fmt(nomTotal + gasTotal)} color={C.red} />
        <StatCard label="Empleados activos" value={emps.filter(e => e.activo).length} color={C.primary} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#fff', background: C.primary, borderRadius: 8, padding: '6px 16px', letterSpacing: '0.02em' }}>👔 Empleados</h3>
        <Btn variant="accent" onClick={() => { setForm({ activo: true, nomina: 0 }); setModal('nuevo'); }}>+ Nuevo empleado</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}`, marginBottom: 24 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead>
            {empTable.getHeaderGroups().map(hg => (
              <tr key={hg.id} style={{ background: C.surface2 }}>
                {hg.headers.map(header => (
                  <th key={header.id} style={{ padding: '11px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: C.text, background: C.surface2, borderBottom: `2px solid ${C.border}`, whiteSpace: 'nowrap', letterSpacing: '0.03em', textTransform: 'uppercase' }}>
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {empTable.getRowModel().rows.length === 0
              ? <tr><td colSpan={empColumns.length} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin empleados</td></tr>
              : empTable.getRowModel().rows.map(row => (
                <tr key={row.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} style={{ padding: '8px 12px', fontSize: 13 }}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#fff', background: C.amber, borderRadius: 8, padding: '6px 16px', letterSpacing: '0.02em' }}>💰 Nómina — {MESES_ES[mes - 1]} {anio}</h3>
        <Btn variant="secondary" onClick={() => copiarNomina.mutate()} disabled={copiarNomina.isPending}>Copiar mes anterior</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}`, marginBottom: 24 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead><tr style={{ background: C.surface2 }}>
            {['Empleado', 'Cargo', 'Salario base ref.', 'Pago este mes'].map(h => (
              <th key={h} style={{ padding: '11px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: C.text, background: C.surface2, borderBottom: `2px solid ${C.border}`, whiteSpace: 'nowrap', letterSpacing: '0.03em', textTransform: 'uppercase' }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {nomina.map(n => {
              const emp = emps.find(e => e.id === n.empleado_id);
              const base = emp?.nomina || 0;
              const diff = n.valor - base;
              return (
                <tr key={n.empleado_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ ...tdc, fontWeight: 700, fontSize: 14 }}>{n.nombre}</td>
                  <td style={{ ...tdc, fontWeight: 600 }}>{n.cargo}</td>
                  <td style={{ ...tdc, fontWeight: 700, fontSize: 14, fontVariantNumeric: 'tabular-nums' }}>{base ? fmt(base) : '—'}</td>
                  <td style={tdc}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="number" style={{ ...inp, width: 130 }}
                        defaultValue={n.valor}
                        onBlur={e => updateNomina.mutate({ empleado_id: n.empleado_id, valor: +e.target.value })} />
                      {base > 0 && diff > 0 && (
                        <span style={{ fontSize: 11, color: C.green, fontWeight: 600, whiteSpace: 'nowrap' }}>
                          +{fmt(diff)}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {nomina.length === 0 && <tr><td colSpan={4} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin empleados activos</td></tr>}
            {nomina.length > 0 && (
              <tr style={{ background: C.surface2, fontWeight: 700 }}>
                <td colSpan={3} style={{ ...tdc, textAlign: 'right', color: C.text2, fontSize: 12 }}>Total nómina:</td>
                <td style={{ ...tdc, color: C.red }}>{fmt(nomTotal)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#fff', background: C.red, borderRadius: 8, padding: '6px 16px', letterSpacing: '0.02em' }}>💸 Gastos — {MESES_ES[mes - 1]} {anio}</h3>
        <Btn variant="secondary" onClick={() => copiarGastos.mutate()} disabled={copiarGastos.isPending}>Copiar mes anterior</Btn>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input style={{ ...sel, flex: 2, textTransform: 'uppercase' }} placeholder="NOMBRE DEL GASTO..." value={gnombre} onChange={e => setGnom(UP(e.target.value))} />
        <input type="number" style={sel} placeholder="Valor $" value={gvalor} onChange={e => setGval(e.target.value)} />
        <Btn onClick={() => addGasto.mutate()} disabled={!gnombre}>+ Agregar</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead><tr style={{ background: C.surface2 }}>
            {['Concepto', 'Valor', 'Fecha', 'Acciones'].map(h => (
              <th key={h} style={{ padding: '11px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: C.text, background: C.surface2, borderBottom: `2px solid ${C.border}`, whiteSpace: 'nowrap', letterSpacing: '0.03em', textTransform: 'uppercase' }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {[...gastos].sort((a,b)=> new Date(b.creado||0) - new Date(a.creado||0)).map(g => (
              <tr key={g.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ ...tdc, fontWeight: 700, fontSize: 14 }}>{g.nombre}</td>
                <td style={{ ...tdc, textAlign: 'right', fontWeight: 600 }}>{fmt(g.valor)}</td>
                <td style={{ ...tdc, fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>{g.creado ? new Date(g.creado).toLocaleDateString('es-CO', { day:'2-digit', month:'2-digit', year:'numeric' }) : '—'}</td>
                <td style={tdc}>
                  <Btn size="sm" variant="danger" onClick={() => setConfirmState({ open:true, title:'Eliminar gasto', message:`¿Eliminar el gasto "${g.nombre}"?`, onConfirm:()=>{ delGasto.mutate(g.id); setConfirmState(s=>({...s,open:false})); } })}>Eliminar</Btn>
                </td>
              </tr>
            ))}
            {gastos.length === 0 && <tr><td colSpan={4} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin gastos este mes</td></tr>}
            {gastos.length > 0 && (
              <tr style={{ background: C.surface2, fontWeight: 700 }}>
                <td style={{ ...tdc, color: C.text2, fontSize: 12 }}>Total gastos:</td>
                <td style={{ ...tdc, textAlign: 'right', color: C.amber }}>{fmt(gasTotal)}</td>
                <td style={tdc} /><td style={tdc} />
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: C.surface, borderRadius: 14, padding: 28, width: 460, boxShadow: '0 20px 60px rgba(0,0,0,.25)', maxHeight: '90vh', overflow: 'auto' }}>
            <h3 style={{ margin: '0 0 18px', color: C.primary }}>{modal === 'nuevo' ? 'Nuevo empleado' : 'Editar empleado'}</h3>
            {[['Nombre *', 'nombre', 'text', true], ['Documento', 'doc', 'text', false], ['Cargo', 'cargo', 'text', true], ['Teléfono', 'tel', 'tel', true], ['Email', 'email', 'email', false]].map(([l, k, t, ucase]) => (
              <div key={k} style={{ marginBottom: 10 }}>
                <label style={lbl}>{l}</label>
                <input type={t || 'text'} style={{ ...inp, textTransform: ucase ? 'uppercase' : 'none' }} value={form[k] || ''} onChange={e => sf(k, ucase ? UP(e.target.value) : e.target.value)} />
              </div>
            ))}
            <label style={lbl}>Salario base de referencia ($)</label>
            <input type="number" style={inp} value={form.nomina ?? ''} onChange={e => sf('nomina', +e.target.value)} />
            <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
              <Btn variant="secondary" onClick={() => setModal(null)}>Cancelar</Btn>
              <Btn onClick={() => guardarEmp.mutate()} disabled={guardarEmp.isPending || !form.nombre}>
                {guardarEmp.isPending ? 'Guardando...' : 'Guardar'}
              </Btn>
            </div>
          </div>
        </div>
      )}
      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState(s => ({ ...s, open: false }))}
      />
    </div>
  );
}
