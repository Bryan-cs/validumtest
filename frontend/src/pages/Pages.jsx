// ─── COBRO PAGE ───────────────────────────────────────────────────────────────
import React, { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useReactTable, getCoreRowModel, getSortedRowModel, getPaginationRowModel, flexRender } from '@tanstack/react-table';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, PageHeader, StatCard, fmt } from '../components/UI';

const UP = v => (v||'').toUpperCase();

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
    alert(typeof msg === 'string' ? msg : 'Error generando reporte');
  }
}

// Todos los inputs de texto van en mayúsculas
const up = (e, setter) => setter(e.target.value.toUpperCase());

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

const NOW = new Date();
const MES_ACTUAL = NOW.getMonth() + 1;
const ANIO_ACTUAL = NOW.getFullYear();
const MESES_ES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

// ─── COBRO ────────────────────────────────────────────────────────────────────
export function Cobro() {
  const qc = useQueryClient();
  const [empresa, setEmp] = useState('');
  const [cliente, setCli] = useState('');
  const [tipo,    setTipo]= useState('');
  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });
  const { data: rows=[], isLoading } = useQuery({
    queryKey:['cobro',empresa,cliente,tipo],
    queryFn:()=>api.get('/cobro',{params:{empresa,cliente,tipo}}).then(r=>r.data),
    refetchInterval:60_000,
  });
  const { data: todosAfil=[] } = useQuery({ queryKey:['afiliados_all'], queryFn:()=>api.get('/afiliados').then(r=>r.data.items||[]), refetchInterval: false, staleTime: 60_000 });
  const clientes = ['', ...new Set(todosAfil.map(a=>a.cliente_txt).filter(Boolean))];

  const colorEstado = { VENCIDO:[C.red,C.redBg], HOY:[C.green,C.greenBg], PROXIMO:[C.text2,C.surface2], COBRADO:[C.blue,C.blueBg] };
  const totales = { hoy:0, venc:0, plan:0, cobrados:0 };
  rows.forEach(r=>{ if(r.estado==='HOY') totales.hoy++; else if(r.estado==='VENCIDO'){totales.venc++;totales.plan+=r.planilla;} else if(r.estado==='COBRADO') totales.cobrados++; });

  return (
    <div>
      <PageHeader title="💰 Módulo de cobro" subtitle="Estado de cobro por afiliado"
        action={<Btn variant="secondary" onClick={()=>dlExcel(`/reportes/cobro?empresa=${empresa}&cliente=${cliente}&tipo=${tipo}`,'cobro.xlsx')}>📊 Exportar Excel</Btn>} />
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        <StatCard label="Cobrar hoy"    value={totales.hoy}       color={C.green} />
        <StatCard label="Vencidos"      value={totales.venc}      color={C.red} />
        <StatCard label="Planilla pend."value={fmt(totales.plan)} color={C.amber} />
        <StatCard label="Cobrados mes"  value={totales.cobrados}  color={C.blue} />
      </div>
      <div style={{ display:'flex', gap:8, marginBottom:14, flexWrap:'wrap' }}>
        <select style={sel} value={empresa} onChange={e=>setEmp(e.target.value)}>
          {['', ...(listas.empresas||[])].map(e=><option key={e} value={e}>{e||'Todas las empresas'}</option>)}
        </select>
        <select style={sel} value={cliente} onChange={e=>setCli(e.target.value)}>
          {clientes.map(c=><option key={c} value={c}>{c||'Todos los clientes'}</option>)}
        </select>
        <select style={sel} value={tipo} onChange={e=>setTipo(e.target.value)}>
          {[['','Todos'],['HOY','Cobrar hoy'],['VENCIDO','Vencidos'],['PROXIMO','Próximos'],['COBRADO','Cobrados']].map(([v,l])=>(
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>
      <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
        <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
          <thead>
            <tr style={{ background:C.surface2 }}>
              {['Nombre','Empresa','Doc.','Cliente','Día cobro','Servicios','Planilla ($)','Estado'].map(h=>(
                <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600,
                  color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={8} style={{ padding:20, textAlign:'center', color:C.text2 }}>Cargando...</td></tr>}
            {!isLoading && rows.length===0 && <tr><td colSpan={8} style={{ padding:20, textAlign:'center', color:C.text2 }}>Sin registros</td></tr>}
            {rows.map(r=>{
              const [fg, bg] = colorEstado[r.estado]||[C.text2,C.surface2];
              return (
                <tr key={r.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}>{r.nombre}</td>
                  <td style={tdc}>{r.empresa}</td>
                  <td style={tdc}>{r.doc}</td>
                  <td style={tdc}>{r.cliente||'—'}</td>
                  <td style={tdc}>Día {r.dia_cobro}</td>
                  <td style={tdc}>{(r.servicios||[]).join(', ')||'—'}</td>
                  <td style={{ ...tdc, textAlign:'right' }}>{fmt(r.planilla)}</td>
                  <td style={tdc}>
                    <span style={{ background:bg, color:fg, borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>
                      {r.estado}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── RETIROS ──────────────────────────────────────────────────────────────────
export function Retiros() {
  const qc = useQueryClient();
  const [buscarH,  setBuscarH] = useState('');
  const [docConsulta, setDocConsulta] = useState('');
  const [modal, setModal] = useState(false);
  const [doc,   setDoc]  = useState('');
  const [fecha, setFecha]= useState(new Date().toISOString().slice(0,10));
  const [motivo,setMotivo]=useState('Renuncia');
  const [obs,   setObs]  = useState('');

  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });

  const aplicar = useMutation({
    mutationFn: ()=>api.post('/retiros',{doc,fecha,motivo,obs}),
    onSuccess: (res)=>{
      const n = res.data?.facturas_pendientes;
      toast.success(n ? `Retiro aplicado. ${n} factura(s) pendiente(s) del mes` : 'Retiro aplicado');
      qc.invalidateQueries({queryKey:['retiros']});
      qc.invalidateQueries({queryKey:['afiliados']});
      setModal(false); setDoc(''); setObs('');
    },
    onError:(e)=>{ const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Afiliado no encontrado')); },
  });

  const { data: resultadoConsulta=[], isLoading: loadConsulta, isFetched: consultaHecha } = useQuery({
    queryKey: ['retiro_consulta', docConsulta],
    queryFn: () => api.get('/retiros', { params: { doc: docConsulta } }).then(r => r.data.items||[]),
    enabled: !!docConsulta,
  });

  return (
    <div>
      <PageHeader title="📋 Historial de retirados"
        action={
          <div style={{ display:'flex', gap:8 }}>
            <Btn variant="secondary" onClick={()=>dlExcel(`/reportes/retiros`,`retiros.xlsx`)}>📊 Exportar Excel</Btn>
            <Btn variant="accent" onClick={()=>setModal(true)}>+ Aplicar retiro</Btn>
          </div>
        } />

      <>
        <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:20 }}>
          <div style={{ position:'relative' }}>
            <input
              type="text"
              value={buscarH}
              onChange={e => setBuscarH(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') setDocConsulta(buscarH.trim()); }}
              placeholder="N° documento..."
              style={{ padding:'8px 14px', paddingRight:90, borderRadius:7,
                border:`1px solid ${C.border}`, fontSize:13, color:C.text,
                background:C.surface, width:260, outline:'none' }}
            />
            <button
              onClick={() => setDocConsulta(buscarH.trim())}
              style={{ position:'absolute', right:4, top:'50%', transform:'translateY(-50%)',
                padding:'4px 12px', borderRadius:5, border:'none', background:C.primary,
                color:'#fff', fontSize:12, fontWeight:600, cursor:'pointer' }}>
              Consultar
            </button>
          </div>
          {docConsulta && (
            <button onClick={() => { setBuscarH(''); setDocConsulta(''); }}
              style={{ padding:'7px 12px', borderRadius:7, border:`1px solid ${C.border}`,
                background:C.surface2, fontSize:12, cursor:'pointer', color:C.text2 }}>
              ✕ Limpiar
            </button>
          )}
        </div>

        {!docConsulta && (
          <div style={{ textAlign:'center', padding:'48px 0', color:C.text2, fontSize:14 }}>
            Ingresa el número de documento para consultar si la persona fue retirada.
          </div>
        )}

        {docConsulta && loadConsulta && (
          <div style={{ textAlign:'center', padding:'32px 0', color:C.text2 }}>Consultando...</div>
        )}

        {docConsulta && !loadConsulta && consultaHecha && (
          resultadoConsulta.length === 0 ? (
            <div style={{ textAlign:'center', padding:'32px 0', borderRadius:10,
              border:`1px solid ${C.border}`, background:C.surface }}>
              <div style={{ fontSize:32, marginBottom:8 }}>✅</div>
              <div style={{ fontSize:14, color:C.text2 }}>
                No hay registro de retiro para el documento <strong style={{color:C.text}}>{docConsulta}</strong>
              </div>
            </div>
          ) : resultadoConsulta.map(r => (
            <div key={r.id} style={{ borderRadius:10, border:`1px solid ${C.red}`,
              background:C.redBg, padding:'20px 24px' }}>
              <div style={{ fontSize:13, fontWeight:700, color:C.red, marginBottom:14 }}>
                ↪️ Registro de retiro encontrado
              </div>
              <div style={{ display:'flex', flexWrap:'wrap', gap:20 }}>
                <div><div style={etiq}>Nombre</div><div style={val}>{r.nombre}</div></div>
                <div><div style={etiq}>Documento</div><div style={{ ...val, fontFamily:'monospace' }}>{r.doc}</div></div>
                <div><div style={etiq}>Empresa</div><div style={val}>{r.empresa || '—'}</div></div>
                <div><div style={etiq}>Fecha retiro</div><div style={val}>{r.fecha}</div></div>
                <div><div style={etiq}>Motivo</div>
                  <span style={{ background:C.red, color:'#fff', borderRadius:6,
                    padding:'2px 10px', fontSize:12, fontWeight:700 }}>{r.motivo || '—'}</span>
                </div>
                <div><div style={etiq}>Registrado por</div><div style={val}>{r.registrado_por || '—'}</div></div>
              </div>
              {r.obs && (
                <div style={{ marginTop:14, padding:'10px 14px', borderRadius:7,
                  background:'rgba(0,0,0,.06)', fontSize:13, color:C.text }}>
                  <span style={{ fontWeight:600, color:C.red }}>Observaciones: </span>{r.obs}
                </div>
              )}
            </div>
          ))
        )}
      </>
      {modal && (
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
          <div style={{ background:C.surface,borderRadius:14,padding:28,width:420,boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
            <h3 style={{ margin:'0 0 18px',color:C.primary }}>Aplicar retiro</h3>
            <label style={lbl}>Cédula del afiliado *</label>
            <input style={inp} value={doc} onChange={e=>setDoc(e.target.value)} placeholder="Número de documento" />
            <label style={lbl}>Fecha de retiro</label>
            <input type="date" style={inp} value={fecha} onChange={e=>setFecha(e.target.value)} />
            <label style={lbl}>Motivo</label>
            <select style={inp} value={motivo} onChange={e=>setMotivo(e.target.value)}>
              {(listas.motivos_retiro||['Renuncia','Despido','Pension','Otro']).map(m=><option key={m}>{m}</option>)}
            </select>
            <label style={lbl}>Observaciones</label>
            <textarea style={{ ...inp, height:70, textTransform:'uppercase' }} value={obs} onChange={e=>setObs(UP(e.target.value))} />
            <div style={{ display:'flex', gap:10, marginTop:14, justifyContent:'flex-end' }}>
              <Btn variant="secondary" onClick={()=>setModal(false)}>Cancelar</Btn>
              <Btn onClick={()=>aplicar.mutate()} disabled={aplicar.isPending||!doc}>
                {aplicar.isPending?'Procesando...':'Aplicar retiro'}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── FACTURACIÓN ──────────────────────────────────────────────────────────────
export function Facturacion() {
  const qc = useQueryClient();
  const [anio, setAnio] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_fact_filtros'))?.anio ?? new Date().getFullYear().toString(); } catch { return new Date().getFullYear().toString(); } });
  const [mes,  setMes]  = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_fact_filtros'))?.mes ?? ''; } catch { return ''; } });
  const [cliente,setCli]= useState(() => { try { return JSON.parse(localStorage.getItem('bbc_fact_filtros'))?.cliente ?? ''; } catch { return ''; } });
  const [estado,setEst] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_fact_filtros'))?.estado ?? ''; } catch { return ''; } });

  useEffect(() => { try { localStorage.setItem('bbc_fact_filtros', JSON.stringify({ anio, mes, cliente, estado })); } catch {} }, [anio, mes, cliente, estado]);

  const { data: rows=[], isLoading } = useQuery({
    queryKey:['facturas',anio,mes,cliente,estado],
    queryFn:()=>api.get('/facturas',{params:{anio,mes,cliente,estado}}).then(r=>r.data.items||[]),
  });

  const clientes = [...new Set(rows.map(r=>r.cliente).filter(Boolean))];
  const anios = [...new Set(rows.map(r=>r.anio).filter(Boolean))];

  const pagar = useMutation({
    mutationFn:(id)=>api.patch(`/facturas/${id}/pagar`),
    onSuccess:(res)=>{ toast.success('Factura marcada como pagada'); qc.setQueriesData({ queryKey: ['facturas'] }, (prev) => Array.isArray(prev) ? prev.map(f => f.id === res.data.id ? res.data : f) : prev); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error en la operación'),
  });
  const eliminar = useMutation({
    mutationFn:(id)=>api.delete(`/facturas/${id}`),
    onSuccess:(_, id)=>{ toast.success('Factura eliminada'); qc.setQueriesData({ queryKey: ['facturas'] }, (prev) => Array.isArray(prev) ? prev.filter(f => f.id !== id) : prev); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error en la operación'),
  });

  const [factSorting, setFactSorting] = useState([]);
  const [factPagination, setFactPagination] = useState({ pageIndex: 0, pageSize: 20 });

  const factColumns = useMemo(() => [
    {
      accessorKey: 'codigo',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Código {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ fontSize: 11, color: C.text2, fontFamily: 'monospace' }}>{row.original.codigo}</span>,
    },
    {
      accessorKey: 'nombre_afiliado',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Afiliado {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => {
        const f = row.original;
        const isHuerfana = f.afiliado_eliminado && f.estado === 'pendiente';
        return (
          <span style={{ color: isHuerfana ? C.red : C.text }}>
            {f.nombre_afiliado}{isHuerfana && <span style={{ fontSize: 10, marginLeft: 4 }}>⚠️ eliminado</span>}
          </span>
        );
      },
    },
    {
      accessorKey: 'cliente',
      header: 'Cliente',
      cell: ({ row }) => <span style={{ fontSize: 11 }}>{row.original.cliente || '—'}</span>,
    },
    {
      id: 'periodo',
      header: 'Mes/Año',
      accessorFn: row => `${row.mes} ${row.anio}`,
      cell: ({ row }) => <span style={{ fontSize: 11 }}>{row.original.mes} {row.original.anio}</span>,
    },
    {
      accessorKey: 'ingresos',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Ingresos {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ fontSize: 11, textAlign: 'right', display: 'block' }}>{fmt(row.original.ingresos)}</span>,
    },
    {
      accessorKey: 'costos',
      header: 'Planilla',
      cell: ({ row }) => <span style={{ fontSize: 11, textAlign: 'right', display: 'block' }}>{fmt(row.original.costos)}</span>,
    },
    {
      accessorKey: 'utilidad',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Utilidad {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ fontSize: 11, textAlign: 'right', display: 'block', color: row.original.utilidad >= 0 ? C.green : C.red }}>{fmt(row.original.utilidad)}</span>,
    },
    {
      accessorKey: 'banco',
      header: 'Banco',
      cell: ({ row }) => <span style={{ fontSize: 11, color: C.text2 }}>{row.original.banco || '—'}</span>,
    },
    {
      accessorKey: 'estado',
      header: 'Estado',
      enableSorting: false,
      cell: ({ row }) => {
        const f = row.original;
        return (
          <span style={{ background: f.estado === 'pagado' ? C.greenBg : C.amberBg, color: f.estado === 'pagado' ? C.green : C.amber, borderRadius: 10, padding: '2px 10px', fontSize: 11, fontWeight: 600 }}>
            {f.estado === 'pagado' ? 'Pagada' : 'Pendiente'}
          </span>
        );
      },
    },
    {
      id: 'acciones',
      header: '',
      enableSorting: false,
      cell: ({ row }) => {
        const f = row.original;
        return (
          <div style={{ display: 'flex', gap: 5 }}>
            {f.estado === 'pendiente' && <Btn size="sm" variant="success" onClick={() => pagar.mutate(f.id)}>✓ Pagada</Btn>}
            <Btn size="sm" variant="danger" onClick={() => { if (window.confirm('¿Eliminar factura?')) eliminar.mutate(f.id); }}>Eliminar</Btn>
          </div>
        );
      },
    },
  ], [pagar.isPending, eliminar.isPending]);

  const factTable = useReactTable({
    data: rows,
    columns: factColumns,
    state: { sorting: factSorting, pagination: factPagination },
    onSortingChange: setFactSorting,
    onPaginationChange: setFactPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const totIng  = rows.reduce((s,f)=>s+(f.ingresos||0),0);
  const totUtil = rows.reduce((s,f)=>s+(f.utilidad||0),0);
  const totPend = rows.filter(f=>f.estado==='pendiente').reduce((s,f)=>s+(f.ingresos||0),0);

  return (
    <div>
      <PageHeader title="🧾 Facturación" subtitle={`${rows.length} facturas`}
        action={<Btn variant="secondary" onClick={()=>dlExcel(`/reportes/financiero?anio=${anio}&mes=${mes}&cliente=${cliente}&estado=${estado}`,`financiero${anio?'_'+anio:''}${mes?'_'+mes:''}.xlsx`)}>📊 Exportar Excel</Btn>} />
      <div style={{ display:'flex', gap:10, marginBottom:14, flexWrap:'wrap' }}>
        <StatCard label="Total ingresos"    value={fmt(totIng)}  color={C.primary} />
        <StatCard label="Utilidad bruta"    value={fmt(totUtil)} color={C.green} />
        <StatCard label="Pendiente cobro"   value={fmt(totPend)} color={C.amber} />
        <StatCard label="Facturas pendientes" value={rows.filter(f=>f.estado==='pendiente').length} color={C.red} />
      </div>
      <div style={{ display:'flex', gap:8, marginBottom:14, flexWrap:'wrap' }}>
        <select style={sel} value={anio} onChange={e=>setAnio(e.target.value)}>
          {['', ...anios].map(a=><option key={a} value={a}>{a||'Todos los años'}</option>)}
        </select>
        <select style={sel} value={mes} onChange={e=>setMes(e.target.value)}>
          {['', ...MESES].map(m=><option key={m} value={m}>{m||'Todos los meses'}</option>)}
        </select>
        <select style={sel} value={cliente} onChange={e=>setCli(e.target.value)}>
          {['', ...clientes].map(c=><option key={c} value={c}>{c||'Todos los clientes'}</option>)}
        </select>
        <select style={sel} value={estado} onChange={e=>setEst(e.target.value)}>
          <option value="">Todos</option>
          <option value="pendiente">Pendiente</option>
          <option value="pagado">Pagado</option>
        </select>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead>
            {factTable.getHeaderGroups().map(hg => (
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
            {isLoading && <tr><td colSpan={factColumns.length} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Cargando...</td></tr>}
            {!isLoading && factTable.getRowModel().rows.length === 0 && <tr><td colSpan={factColumns.length} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin facturas</td></tr>}
            {factTable.getRowModel().rows.map(row => (
              <tr key={row.id} style={{ borderBottom: `1px solid ${C.border}`, background: (row.original.afiliado_eliminado && row.original.estado === 'pendiente') ? C.redBg : '#fff' }}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} style={{ padding: '8px 12px', fontSize: 13 }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
        <span style={{ fontSize: 12, color: C.text2 }}>
          Página {factTable.getState().pagination.pageIndex + 1} de {factTable.getPageCount()} — {rows.length} total
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          <Btn size="sm" variant="secondary" onClick={() => factTable.previousPage()} disabled={!factTable.getCanPreviousPage()}>← Ant.</Btn>
          <Btn size="sm" variant="secondary" onClick={() => factTable.nextPage()} disabled={!factTable.getCanNextPage()}>Sig. →</Btn>
        </div>
      </div>
    </div>
  );
}

// ─── EMPLEADOS ────────────────────────────────────────────────────────────────
export function Empleados() {
  const qc = useQueryClient();
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const sf = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const [mes, setMes] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_emp_filtros'))?.mes ?? MES_ACTUAL; } catch { return MES_ACTUAL; } });
  const [anio, setAnio] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_emp_filtros'))?.anio ?? ANIO_ACTUAL; } catch { return ANIO_ACTUAL; } });

  useEffect(() => { try { localStorage.setItem('bbc_emp_filtros', JSON.stringify({ mes, anio })); } catch {} }, [mes, anio]);

  const { data: emps = [] } = useQuery({ queryKey: ['empleados'], queryFn: () => api.get('/empleados').then(r => r.data) });
  const { data: usuarios = [] } = useQuery({ queryKey: ['usuarios'], queryFn: () => api.get('/usuarios').then(r => r.data) });
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
  const [gvalor, setGval] = useState(0);

  const addGasto = useMutation({
    mutationFn: () => api.post('/gastos', { nombre: gnombre, valor: +gvalor, mes, anio }),
    onSuccess: (res) => { toast.success('Gasto agregado'); qc.setQueryData(['gastos', mes, anio], prev => [...(prev || []), res.data]); setGnom(''); setGval(0); },
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
      cell: ({ row }) => <span style={{ fontWeight: 500 }}>{row.original.nombre}</span>,
    },
    {
      accessorKey: 'doc',
      header: 'Documento',
      cell: ({ row }) => <span style={{ color: C.text2, fontFamily: 'monospace', fontSize: 12 }}>{row.original.doc || '—'}</span>,
    },
    {
      accessorKey: 'cargo',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Cargo {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span style={{ fontSize: 12 }}>{row.original.cargo}</span>,
    },
    {
      accessorKey: 'tel',
      header: 'Teléfono',
      enableSorting: false,
      cell: ({ row }) => <span style={{ color: C.text2, fontSize: 12 }}>{row.original.tel || '—'}</span>,
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
            <Btn size="sm" variant="danger" onClick={() => { if (window.confirm(`¿Eliminar a ${e.nombre}?`)) eliminarEmp.mutate(e.id); }}>🗑️ Eliminar</Btn>
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
        <h3 style={{ margin: 0, color: C.primary }}>Empleados</h3>
        <Btn variant="accent" onClick={() => { setForm({ activo: true, nomina: 0 }); setModal('nuevo'); }}>+ Nuevo empleado</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}`, marginBottom: 24 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead>
            {empTable.getHeaderGroups().map(hg => (
              <tr key={hg.id} style={{ background: C.surface2 }}>
                {hg.headers.map(header => (
                  <th key={header.id} style={{ padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}` }}>
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
        <h3 style={{ margin: 0, color: C.primary }}>Nómina — {MESES_ES[mes - 1]} {anio}</h3>
        <Btn variant="secondary" onClick={() => copiarNomina.mutate()} disabled={copiarNomina.isPending}>Copiar mes anterior</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}`, marginBottom: 24 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead><tr style={{ background: C.surface2 }}>
            {['Empleado', 'Cargo', 'Salario base ref.', 'Pago este mes'].map(h => (
              <th key={h} style={{ padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {nomina.map(n => {
              const emp = emps.find(e => e.id === n.empleado_id);
              const base = emp?.nomina || 0;
              const diff = n.valor - base;
              return (
                <tr key={n.empleado_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={tdc}>{n.nombre}</td>
                  <td style={tdc}>{n.cargo}</td>
                  <td style={{ ...tdc, color: C.text2, fontSize: 12 }}>{base ? fmt(base) : '—'}</td>
                  <td style={tdc}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="number" style={{ ...inp, width: 130 }}
                        defaultValue={n.valor}
                        onBlur={e => updateNomina.mutate({ empleado_id: n.empleado_id, valor: +e.target.value })} />
                      {base > 0 && diff !== 0 && (
                        <span style={{ fontSize: 11, color: diff > 0 ? C.green : C.red, fontWeight: 600, whiteSpace: 'nowrap' }}>
                          {diff > 0 ? '+' : ''}{fmt(diff)}
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
        <h3 style={{ margin: 0, color: C.primary }}>Gastos — {MESES_ES[mes - 1]} {anio}</h3>
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
            {['Concepto', 'Valor', 'Acciones'].map(h => (
              <th key={h} style={{ padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {gastos.map(g => (
              <tr key={g.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={tdc}>{g.nombre}</td>
                <td style={{ ...tdc, textAlign: 'right', fontWeight: 600 }}>{fmt(g.valor)}</td>
                <td style={tdc}>
                  <Btn size="sm" variant="danger" onClick={() => { if (window.confirm('¿Eliminar gasto?')) delGasto.mutate(g.id); }}>Eliminar</Btn>
                </td>
              </tr>
            ))}
            {gastos.length === 0 && <tr><td colSpan={3} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin gastos este mes</td></tr>}
            {gastos.length > 0 && (
              <tr style={{ background: C.surface2, fontWeight: 700 }}>
                <td style={{ ...tdc, color: C.text2, fontSize: 12 }}>Total gastos:</td>
                <td style={{ ...tdc, textAlign: 'right', color: C.amber }}>{fmt(gasTotal)}</td>
                <td style={tdc} />
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
            <label style={lbl}>Usuario asignado</label>
            <select style={inp} value={form.usuario || ''} onChange={e => sf('usuario', e.target.value)}>
              <option value="">Sin asignar</option>
              {usuarios.filter(u => u.rol === 'empleado').map(u => <option key={u.id} value={u.username}>{u.username}</option>)}
            </select>
            <label style={lbl}>Salario base de referencia ($)</label>
            <input type="number" style={inp} value={form.nomina || 0} onChange={e => sf('nomina', +e.target.value)} />
            <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
              <Btn variant="secondary" onClick={() => setModal(null)}>Cancelar</Btn>
              <Btn onClick={() => guardarEmp.mutate()} disabled={guardarEmp.isPending || !form.nombre}>
                {guardarEmp.isPending ? 'Guardando...' : 'Guardar'}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── USUARIOS ─────────────────────────────────────────────────────────────────
export function Usuarios() {
  const qc = useQueryClient();
  const [modal,setModal]=useState(false);
  const [form,setForm]=useState({rol:'empleado'});
  const [err,setErr]=useState('');
  const sf=(k,v)=>setForm(f=>({...f,[k]:v}));
  const [pwModal,setPwModal]=useState(null); // {id, nombre}
  const [pwForm,setPwForm]=useState({});
  const [pwErr,setPwErr]=useState('');

  const { data: users=[] } = useQuery({ queryKey:['usuarios'], queryFn:()=>api.get('/usuarios').then(r=>r.data) });
  const { data: clientes=[] } = useQuery({ queryKey:['clientes-lista'], queryFn:()=>api.get('/clientes').then(r=>r.data) });

  const crear = useMutation({
    mutationFn:()=>{
      if(!form.nombre||!form.username||!form.password){setErr('Todos los campos son obligatorios.');return Promise.reject();}
      if(form.password!==form.password2){setErr('Las contraseñas no coinciden.');return Promise.reject();}
      if(form.rol==='cliente'&&!form.cliente_ref){setErr('Para rol cliente debes indicar el Cliente (cliente_ref).');return Promise.reject();}
      return api.post('/usuarios',{nombre:form.nombre,username:form.username,password:form.password,rol:form.rol,cliente_ref:form.cliente_ref||null});
    },
    onSuccess:(res)=>{ toast.success('Usuario creado'); qc.setQueryData(['usuarios'], prev => [...(prev || []), res.data]); setModal(false); setErr(''); },
    onError:(e)=>{ if(e?.response){ const d=e.response?.data?.detail; setErr(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); } },
  });

  const eliminar = useMutation({
    mutationFn:(id)=>api.delete(`/usuarios/${id}`),
    onSuccess:(_, id)=>{ toast.success('Usuario eliminado'); qc.setQueryData(['usuarios'], prev => prev?.filter(u => u.id !== id)); },
    onError:(e)=>{ const d=e.response?.data?.detail; toast.error(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); },
  });

  const cambiarPassword = useMutation({
    mutationFn:()=>{
      if(!pwForm.password){setPwErr('Ingresa la nueva contraseña.');return Promise.reject();}
      if(pwForm.password!==pwForm.password2){setPwErr('Las contraseñas no coinciden.');return Promise.reject();}
      return api.put(`/usuarios/${pwModal.id}/password`,{password:pwForm.password});
    },
    onSuccess:()=>{ toast.success('Contraseña actualizada'); setPwModal(null); setPwErr(''); setPwForm({}); },
    onError:(e)=>{ const d=e?.response?.data?.detail; setPwErr(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); },
  });

  const [userSorting, setUserSorting] = useState([]);

  const userColumns = useMemo(() => [
    {
      accessorKey: 'nombre',
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
          Nombre {column.getIsSorted() === 'asc' ? '↑' : column.getIsSorted() === 'desc' ? '↓' : '↕'}
        </button>
      ),
      cell: ({ row }) => <span>{row.original.nombre}</span>,
    },
    {
      accessorKey: 'username',
      header: 'Usuario',
      cell: ({ row }) => <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{row.original.username}</span>,
    },
    {
      accessorKey: 'rol',
      header: 'Rol',
      enableSorting: false,
      cell: ({ row }) => {
        const u = row.original;
        return (
          <span style={{
            background: u.rol === 'admin' ? C.blueBg : u.rol === 'cliente' ? '#FEF3C7' : C.greenBg,
            color: u.rol === 'admin' ? C.blue : u.rol === 'cliente' ? '#92400E' : C.green,
            borderRadius: 10, padding: '2px 10px', fontSize: 11, fontWeight: 600
          }}>{u.rol}</span>
        );
      },
    },
    {
      accessorKey: 'cliente_ref',
      header: 'Cliente Ref',
      enableSorting: false,
      cell: ({ row }) => <span style={{ fontSize: 12, color: C.text2 }}>{row.original.cliente_ref || '—'}</span>,
    },
    {
      accessorKey: 'activo',
      header: 'Estado',
      enableSorting: false,
      cell: ({ row }) => <span style={{ color: row.original.activo ? C.green : C.red, fontWeight: 600 }}>{row.original.activo ? 'Activo' : 'Inactivo'}</span>,
    },
    {
      id: 'acciones',
      header: '',
      enableSorting: false,
      cell: ({ row }) => {
        const u = row.original;
        return (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <Btn size="sm" variant="secondary" onClick={() => { setPwModal({ id: u.id, nombre: u.nombre }); setPwForm({}); setPwErr(''); }}>Contraseña</Btn>
            {u.username !== 'admin' && <Btn size="sm" variant="danger" onClick={() => { if (window.confirm('¿Eliminar usuario?')) eliminar.mutate(u.id); }}>Eliminar</Btn>}
          </div>
        );
      },
    },
  ], [eliminar.isPending]);

  const userTable = useReactTable({
    data: users,
    columns: userColumns,
    state: { sorting: userSorting },
    onSortingChange: setUserSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div>
      <PageHeader title="⚙️ Usuarios del sistema"
        action={<Btn variant="accent" onClick={()=>{setForm({rol:'empleado'});setErr('');setModal(true);}}>+ Nuevo usuario</Btn>} />
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead>
            {userTable.getHeaderGroups().map(hg => (
              <tr key={hg.id} style={{ background: C.surface2 }}>
                {hg.headers.map(header => (
                  <th key={header.id} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}` }}>
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {userTable.getRowModel().rows.map(row => (
              <tr key={row.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} style={{ padding: '8px 12px', fontSize: 13 }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pwModal&&(
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
          <div style={{ background:C.surface,borderRadius:14,padding:28,width:360,boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
            <h3 style={{ margin:'0 0 4px',color:C.primary }}>Cambiar contraseña</h3>
            <p style={{ margin:'0 0 16px',fontSize:13,color:C.text2 }}>{pwModal.nombre}</p>
            {[['Nueva contraseña *','password'],['Confirmar contraseña *','password2']].map(([l,k])=>(
              <div key={k} style={{ marginBottom:10 }}>
                <label style={lbl}>{l}</label>
                <input type="password" style={inp} value={pwForm[k]||''} onChange={e=>setPwForm(f=>({...f,[k]:e.target.value}))} />
              </div>
            ))}
            {pwErr&&<p style={{ color:C.red,fontSize:12,margin:'8px 0 0' }}>{pwErr}</p>}
            <div style={{ display:'flex',gap:10,marginTop:16,justifyContent:'flex-end' }}>
              <Btn variant="secondary" onClick={()=>setPwModal(null)}>Cancelar</Btn>
              <Btn onClick={()=>cambiarPassword.mutate()} disabled={cambiarPassword.isPending}>Guardar</Btn>
            </div>
          </div>
        </div>
      )}
      {modal&&(
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
          <div style={{ background:C.surface,borderRadius:14,padding:28,width:400,boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
            <h3 style={{ margin:'0 0 18px',color:C.primary }}>Nuevo usuario</h3>
            {[['Nombre completo *','nombre','text',true],['Usuario *','username','text',false],['Contraseña *','password','password',false],['Confirmar contraseña *','password2','password',false]].map(([l,k,t,ucase])=>(
              <div key={k} style={{ marginBottom:10 }}>
                <label style={lbl}>{l}</label>
                <input type={t} style={{ ...inp, textTransform: ucase?'uppercase':'none' }} value={form[k]||''} onChange={e=>sf(k, ucase?UP(e.target.value):e.target.value)} />
              </div>
            ))}
            <label style={lbl}>Rol</label>
            <select style={inp} value={form.rol||'empleado'} onChange={e=>sf('rol',e.target.value)}>
              <option value="admin">Admin</option>
              <option value="empleado">Empleado</option>
              <option value="cliente">Cliente (Portal)</option>
            </select>
            {form.rol==='cliente'&&(
              <div style={{ marginTop:10 }}>
                <label style={lbl}>Cliente *</label>
                <select style={inp} value={form.cliente_ref||''} onChange={e=>sf('cliente_ref',e.target.value)}>
                  <option value="">— Seleccionar cliente —</option>
                  {clientes.map(c=><option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            )}
            {err&&<p style={{ color:C.red,fontSize:12,margin:'8px 0 0' }}>{err}</p>}
            <div style={{ display:'flex',gap:10,marginTop:16,justifyContent:'flex-end' }}>
              <Btn variant="secondary" onClick={()=>setModal(false)}>Cancelar</Btn>
              <Btn onClick={()=>crear.mutate()} disabled={crear.isPending}>Crear usuario</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── LISTAS ───────────────────────────────────────────────────────────────────
export function Listas() {
  const qc = useQueryClient();
  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });
  const [sel, setSel] = useState('empresas');
  const [newItem, setNewItem] = useState('');

  const update = useMutation({
    mutationFn:(items)=>api.put(`/listas/${sel}`,{items}),
    onSuccess:(res)=>{ toast.success('Lista actualizada'); qc.setQueryData(['listas'], prev => ({ ...prev, [res.data.nombre]: res.data.items })); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error en la operación'),
  });

  const items = listas[sel]||[];
  const addItem = () => {
    if(!newItem.trim()) return;
    if(items.includes(newItem.trim())){ toast.error('Ya existe'); return; }
    update.mutate([...items, newItem.trim()]); setNewItem('');
  };
  const removeItem = (item) => { if(window.confirm(`¿Eliminar "${item}"?`)) update.mutate(items.filter(i=>i!==item)); };

  const listas_nombres = Object.keys(listas);
  return (
    <div>
      <PageHeader title="📋 Listas y opciones" subtitle="Gestiona los valores disponibles en formularios" />
      <div style={{ display:'flex',gap:10,marginBottom:16,flexWrap:'wrap' }}>
        {listas_nombres.map(n=>(
          <button key={n} onClick={()=>setSel(n)} style={{ padding:'6px 14px',borderRadius:7,border:`1px solid ${C.border}`,
            background:sel===n?C.primary:C.surface2,color:sel===n?'#fff':C.text,
            fontWeight:sel===n?600:400,cursor:'pointer',fontSize:13 }}>{n}</button>
        ))}
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:20 }}>
        <div style={{ display:'flex',gap:8,marginBottom:14 }}>
          <input style={{ ...sel_s,flex:1 }} placeholder={`Nueva opción para ${sel}...`}
            value={newItem} onChange={e=>setNewItem(e.target.value)}
            onKeyDown={e=>e.key==='Enter'&&addItem()} />
          <Btn onClick={addItem}>Añadir</Btn>
        </div>
        <div style={{ display:'flex',flexWrap:'wrap',gap:8 }}>
          {items.map(item=>(
            <div key={item} style={{ display:'flex',alignItems:'center',gap:6,background:C.surface2,
              border:`1px solid ${C.border}`,borderRadius:7,padding:'5px 12px',fontSize:13,color:C.text }}>
              <span>{item}</span>
              <button onClick={()=>removeItem(item)} style={{ border:'none',background:'none',
                color:C.red,cursor:'pointer',fontSize:16,lineHeight:1 }}>×</button>
            </div>
          ))}
          {items.length===0&&<p style={{ color:C.text2,margin:0 }}>Sin opciones. Agrega la primera.</p>}
        </div>
      </div>
    </div>
  );
}

// ─── CALCULADORA ──────────────────────────────────────────────────────────────
const PLANTILLA_DEFAULT =
`{{saludo}}!.
Señor@: {{nombre}}

 Estimado cliente;
Reciban un cordial saludo, por parte de CARSECOOP Y COOPERATIVA DE SERVICIOS GLOBALES TECHCOOP, identificado con Nit 901921756, por parte de Carsecoop le deseamos un excelente día.

Recordatorio de pago de su seguridad social del mes de {{mes}} {{anio}}, agradecemos su pago oportuno.

Fecha Emisión: {{fecha_emision}}
{{vencimiento}}
TOTAL: \${{total}}
{{servicios}}
*Medios de pago:*
-Nequi / Daviplata: 3170296773
-Davivienda (Ahorros): 0550108900642357
-Banco de Bogotá (Ahorros): 462547688
-Llave Banco Bogotá: @BBJMF23103
-Bancolombia (Ahorros): 91270274485`;

export function Calculadora() {
  const qc = useQueryClient();
  const { data: cfg={} } = useQuery({ queryKey:['config'], queryFn:()=>api.get('/config').then(r=>r.data) });
  const [ibc, setIbc] = useState('');
  const [pcts, setPcts] = useState({});
  const [plantilla, setPlantilla] = useState('');
  const [cargoAdicional, setCargoAdicional] = useState(2200);
  const [mesCobro, setMesCobro] = useState('');
  const [anioCobro, setAnioCobro] = useState('');

  React.useEffect(()=>{
    if(cfg.ibc_global) setIbc(cfg.ibc_global);
    if(cfg.porcentajes) setPcts({...cfg.porcentajes});
    if(cfg.plantilla_whatsapp !== undefined) setPlantilla(cfg.plantilla_whatsapp || PLANTILLA_DEFAULT);
    if(cfg.cargo_adicional !== undefined) setCargoAdicional(cfg.cargo_adicional ?? 2200);
    if(cfg.mes_inicio_cobro) setMesCobro(cfg.mes_inicio_cobro);
    if(cfg.anio_inicio_cobro) setAnioCobro(cfg.anio_inicio_cobro);
  },[cfg]);

  const guardar = useMutation({
    mutationFn:()=>api.put('/config',{ ibc_global:+ibc, porcentajes:pcts, plantilla_whatsapp:plantilla, cargo_adicional:+cargoAdicional, mes_inicio_cobro: mesCobro?+mesCobro:null, anio_inicio_cobro: anioCobro?+anioCobro:null }),
    onSuccess:(res)=>{ toast.success('Configuración actualizada'); qc.setQueryData(['config'], res.data); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error en la operación'),
  });

  const ibcN = +ibc || 0;
  const ceil100 = v => Math.ceil(v/100)*100;

  return (
    <div>
      <PageHeader title="🧮 Calculadora de aportes" subtitle="Configura IBC global y porcentajes" />
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <label style={{ ...lbl,fontSize:13 }}>IBC Global (Salario mínimo / base de cotización)</label>
        <input type="number" style={{ ...inp,width:240 }} value={ibc} onChange={e=>setIbc(e.target.value)} />
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <label style={{ ...lbl,fontSize:13 }}>Cargo adicional por impuestos (planilla)</label>
        <p style={{ margin:'0 0 10px',fontSize:12,color:C.text2 }}>Se suma al costo de planilla en cada factura. Editable individualmente por factura.</p>
        <input type="number" style={{ ...inp,width:240 }} value={cargoAdicional} onChange={e=>setCargoAdicional(e.target.value)} />
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <h3 style={{ margin:'0 0 16px',color:C.primary }}>Porcentajes de aporte</h3>
        <table style={{ width:'100%',borderCollapse:'collapse' }}>
          <thead><tr style={{ background:C.surface2 }}>
            {['Servicio','Porcentaje (%)','Valor 30 días','Valor 15 días'].map(h=>(
              <th key={h} style={{ padding:'9px 12px',textAlign:'left',fontSize:11,fontWeight:600,color:C.text2,borderBottom:`1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {Object.entries(pcts).map(([srv, pct])=>{
              const v30 = ceil100(ibcN * pct);
              const v15 = ceil100(ibcN * pct / 2);
              return (
                <tr key={srv} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ ...tdc,fontWeight:500 }}>{srv}</td>
                  <td style={tdc}>
                    <input type="number" step="0.001" style={{ ...inp,width:120 }}
                      value={(pct*100).toFixed(4)}
                      onChange={e=>setPcts(p=>({...p,[srv]:+e.target.value/100}))} />
                  </td>
                  <td style={{ ...tdc,textAlign:'right',color:C.red,fontWeight:600 }}>
                    $ {v30.toLocaleString('es-CO')}
                  </td>
                  <td style={{ ...tdc,textAlign:'right',color:C.amber,fontWeight:600 }}>
                    $ {v15.toLocaleString('es-CO')}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <h3 style={{ margin:'0 0 8px',color:C.primary }}>Plantilla mensaje WhatsApp</h3>
        <p style={{ margin:'0 0 12px',fontSize:12,color:C.text2 }}>
          Variables disponibles: <code>{'{{saludo}}'}</code> <code>{'{{nombre}}'}</code> <code>{'{{mes}}'}</code> <code>{'{{anio}}'}</code> <code>{'{{fecha_emision}}'}</code> <code>{'{{vencimiento}}'}</code> <code>{'{{total}}'}</code> <code>{'{{servicios}}'}</code>
        </p>
        <textarea
          rows={20}
          style={{ ...inp, fontFamily:'monospace', fontSize:12, resize:'vertical', whiteSpace:'pre' }}
          value={plantilla}
          onChange={e=>setPlantilla(e.target.value)}
        />
        <Btn size="sm" variant="secondary" style={{ marginTop:8 }} onClick={()=>setPlantilla(PLANTILLA_DEFAULT)}>
          Restaurar plantilla por defecto
        </Btn>
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <h3 style={{ margin:'0 0 6px',color:C.primary }}>Fecha de inicio del módulo de cobro</h3>
        <p style={{ margin:'0 0 14px',fontSize:12,color:C.text2 }}>El módulo de cobro solo mostrará recordatorios a partir de este mes. Meses anteriores serán ignorados aunque el afiliado tenga deuda sin factura.</p>
        <div style={{ display:'flex',gap:10,alignItems:'center',flexWrap:'wrap' }}>
          <div>
            <label style={lbl}>Mes</label>
            <select style={{ ...inp,width:150 }} value={mesCobro} onChange={e=>setMesCobro(e.target.value)}>
              <option value="">Sin límite</option>
              {MESES_ES.map((m,i)=><option key={i+1} value={i+1}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año</label>
            <input type="number" style={{ ...inp,width:110 }} placeholder="ej: 2026" value={anioCobro} onChange={e=>setAnioCobro(e.target.value)} />
          </div>
        </div>
      </div>
      <Btn onClick={()=>guardar.mutate()} disabled={guardar.isPending}>
        {guardar.isPending?'Guardando...':'💾 Guardar configuración'}
      </Btn>
    </div>
  );
}

// ─── SHARED STYLES ────────────────────────────────────────────────────────────
const tdc  = { padding:'10px 12px', fontSize:13, color:C.text, verticalAlign:'middle' };
const etiq = { fontSize:11, color:C.text2, fontWeight:500, marginBottom:3 };
const val  = { fontSize:14, fontWeight:600, color:C.text };
const sel = { padding:'8px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', background:C.surface, color:C.text };
const sel_s = { padding:'8px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', background:C.surface, color:C.text };
const lbl = { display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 };
const inp = { width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface };

// ─── NOVEDADES DE CLIENTES (solo admin) ───────────────────────────────────────
export function NovedadesClientes() {
  const qc = useQueryClient();
  const [tabNov, setTabNov] = useState('novedades');
  const [filtroCliente, setFiltroCliente] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_nov_filtros'))?.filtroCliente ?? ''; } catch { return ''; } });
  const [filtroEstado, setFiltroEstado] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_nov_filtros'))?.filtroEstado ?? ''; } catch { return ''; } });
  const hoy = new Date().toISOString().slice(0,10);
  const [filtroFecha, setFiltroFecha] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_nov_filtros'))?.filtroFecha ?? ''; } catch { return ''; } });

  useEffect(() => { try { localStorage.setItem('bbc_nov_filtros', JSON.stringify({ filtroCliente, filtroEstado, filtroFecha })); } catch {} }, [filtroCliente, filtroEstado, filtroFecha]);

  // ── Avisos (admin → cliente) ──
  const [avisoForm, setAvisoForm] = useState({ cliente_ref:'', titulo:'', mensaje:'' });
  const [avisoFiles, setAvisoFiles] = useState([]);
  const { data: avisos=[], isLoading: loadAvisos } = useQuery({
    queryKey:['admin-avisos'],
    queryFn:()=>api.get('/portal/avisos').then(r=>r.data),
    enabled: tabNov==='avisos',
    refetchInterval:60_000,
  });
  const { data: usuariosCliente=[] } = useQuery({
    queryKey:['usuarios-portal-clientes'],
    queryFn:()=>api.get('/usuarios').then(r=>r.data.filter(u=>u.rol==='cliente'&&u.activo!==false)),
  });
  const crearAviso = useMutation({
    mutationFn: async (body) => {
      const { data } = await api.post('/portal/avisos', body);
      if (avisoFiles.length > 0) {
        for (const file of avisoFiles) {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('afiliado_doc', '');
          fd.append('contexto', 'aviso');
          fd.append('contexto_id', String(data.id));
          await api.post('/documentos', fd);
        }
      }
      return data;
    },
    onSuccess: ()=>{ toast.success('Aviso enviado'); setAvisoForm({ cliente_ref:'', titulo:'', mensaje:'' }); setAvisoFiles([]); qc.invalidateQueries(['admin-avisos']); },
    onError: ()=>toast.error('Error al enviar aviso'),
  });
  const delAviso = useMutation({
    mutationFn:(id)=>api.delete(`/portal/avisos/${id}`),
    onSuccess:(_, id)=>{ toast.success('Aviso eliminado'); qc.setQueryData(['admin-avisos'], prev=>prev?.filter(a=>a.id!==id)); },
    onError:()=>toast.error('Error al eliminar'),
  });

  // Modal para responder al resolver
  const [modalResp, setModalResp] = useState(null); // { tipo, id, estado, label }
  const [respTexto, setRespTexto] = useState('');
  const [respFiles, setRespFiles] = useState([]);

  // Docs del cliente para la novedad abierta — contexto distinto por tipo
  const _ctxCliente = modalResp?.tipo === 'novedad' ? 'novedad_pago' : modalResp?.tipo === 'novedad-afil' ? 'novedad_afil' : 'novedad_retiro';
  const { data: docsNovedad=[] } = useQuery({
    queryKey: ['docs-novedad', modalResp?.id, modalResp?.tipo],
    queryFn: () => api.get('/documentos', { params: { contexto: _ctxCliente, contexto_id: modalResp.id } }).then(r => r.data),
    enabled: !!modalResp,
  });

  const { data: novedades=[], isLoading: loadNov } = useQuery({
    queryKey:['admin-novedades-pago'],
    queryFn:()=>api.get('/portal/novedades-pago').then(r=>r.data),
    refetchInterval:60_000,
  });
  const { data: solicitudes=[], isLoading: loadSol } = useQuery({
    queryKey:['admin-solicitudes-retiro'],
    queryFn:()=>api.get('/portal/solicitudes-retiro').then(r=>r.data),
    refetchInterval:60_000,
  });
  const { data: novedadesAfil=[], isLoading: loadNovAfil } = useQuery({
    queryKey:['admin-novedades-afil'],
    queryFn:()=>api.get('/portal/solicitudes-novedad').then(r=>r.data),
    refetchInterval:60_000,
  });

  const cerrarModalResp = () => { setModalResp(null); setRespTexto(''); setRespFiles([]); };

  const updNovedad = useMutation({
    mutationFn:({id,estado,respuesta})=>api.patch(`/portal/novedades-pago/${id}/estado`,{estado,respuesta}),
    onSuccess:(_, { id, estado, respuesta })=>{ toast.success('Estado actualizado'); qc.setQueryData(['admin-novedades-pago'], prev => prev?.map(n => n.id === id ? { ...n, estado, respuesta: respuesta ?? n.respuesta } : n)); cerrarModalResp(); },
    onError:()=>toast.error('Error al actualizar'),
  });
  const updSolicitud = useMutation({
    mutationFn:({id,estado,respuesta})=>api.patch(`/portal/solicitudes-retiro/${id}/estado`,{estado,respuesta}),
    onSuccess:(_, { id, estado, respuesta })=>{ toast.success('Estado actualizado'); qc.setQueryData(['admin-solicitudes-retiro'], prev => prev?.map(s => s.id === id ? { ...s, estado, respuesta: respuesta ?? s.respuesta } : s)); cerrarModalResp(); },
    onError:()=>toast.error('Error al actualizar'),
  });
  const updNovedadAfil = useMutation({
    mutationFn:({id,estado,respuesta})=>api.patch(`/portal/solicitudes-novedad/${id}/estado`,{estado,respuesta}),
    onSuccess:(_, { id, estado, respuesta })=>{ toast.success('Estado actualizado'); qc.setQueryData(['admin-novedades-afil'], prev => prev?.map(s => s.id === id ? { ...s, estado, respuesta: respuesta ?? s.respuesta } : s)); cerrarModalResp(); },
    onError:()=>toast.error('Error al actualizar'),
  });

  const delNovedad = useMutation({
    mutationFn:(id)=>api.delete(`/portal/novedades-pago/${id}`),
    onSuccess:(_, id)=>{ toast.success('Novedad eliminada'); qc.setQueryData(['admin-novedades-pago'], prev => prev?.filter(n => n.id !== id)); },
    onError:()=>toast.error('Error al eliminar'),
  });
  const delSolicitud = useMutation({
    mutationFn:(id)=>api.delete(`/portal/solicitudes-retiro/${id}`),
    onSuccess:(_, id)=>{ toast.success('Solicitud eliminada'); qc.setQueryData(['admin-solicitudes-retiro'], prev => prev?.filter(s => s.id !== id)); },
    onError:()=>toast.error('Error al eliminar'),
  });
  const delNovedadAfil = useMutation({
    mutationFn:(id)=>api.delete(`/portal/solicitudes-novedad/${id}`),
    onSuccess:(_, id)=>{ toast.success('Solicitud eliminada'); qc.setQueryData(['admin-novedades-afil'], prev => prev?.filter(s => s.id !== id)); },
    onError:()=>toast.error('Error al eliminar'),
  });

  const confirmarRespuesta = async () => {
    if(!modalResp) return;
    const payload = { id: modalResp.id, estado: modalResp.estado, respuesta: respTexto };
    // Subir archivos de respuesta si los hay
    if (respFiles.length > 0) {
      for (const file of respFiles) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('afiliado_doc', '');
        const _ctxResp = modalResp.tipo === 'novedad' ? 'resp_pago' : modalResp.tipo === 'novedad-afil' ? 'resp_afil' : 'resp_retiro';
        fd.append('contexto', _ctxResp);
        fd.append('contexto_id', String(modalResp.id));
        try {
          await api.post('/documentos', fd);
        } catch(err) {
          const det = err?.response?.data?.detail;
          const msg = typeof det === 'string' ? det : JSON.stringify(det);
          console.error('[confirmarRespuesta] upload error', err?.response?.status, err?.response?.data);
          toast.error('Error al subir archivo: ' + (msg || err.message || 'desconocido'));
          return;
        }
      }
    }
    if(modalResp.tipo==='novedad') updNovedad.mutate(payload);
    else if(modalResp.tipo==='retiro') updSolicitud.mutate(payload);
    else updNovedadAfil.mutate(payload);
  };


  const clientesNov = [...new Set(novedades.map(n=>n.username_cliente))].sort();
  const clientesSol = [...new Set(solicitudes.map(s=>s.username_cliente||s.cliente_ref))].sort();

  const aplicarFiltros = (lista, getCli) => lista.filter(r => {
    if(filtroCliente && getCli(r) !== filtroCliente) return false;
    if(filtroEstado  && r.estado !== filtroEstado) return false;
    if(filtroFecha   && r.creado?.slice(0,10) !== filtroFecha) return false;
    return true;
  });

  const novFiltradas     = aplicarFiltros(novedades,     n => n.username_cliente);
  const solFiltradas     = aplicarFiltros(solicitudes,   s => s.username_cliente||s.cliente_ref);
  const novAfilFiltradas = aplicarFiltros(novedadesAfil, n => n.username_cliente||n.cliente_ref);

  const badgeEstado = (est) => {
    const map = {
      pendiente:  { bg:'#FEF3C7', color:'#92400E' },
      procesado:  { bg:C.greenBg, color:C.green },
      ejecutado:  { bg:C.greenBg, color:C.green },
      rechazado:  { bg:C.redBg,   color:C.red },
    };
    const s = map[est] || { bg:C.surface2, color:C.text2 };
    return <span style={{ background:s.bg, color:s.color, borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>{est}</span>;
  };

  const limpiar = () => { setFiltroCliente(''); setFiltroEstado(''); setFiltroFecha(''); };

  return (
    <div>
      <PageHeader title="📬 Novedades de Clientes" />

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16, flexWrap:'wrap' }}>
        {[
          ['novedades',`Novedades de Pago (${novedades.filter(n=>n.estado==='pendiente').length} pendientes)`],
          ['solicitudes',`Solicitudes de Retiro (${solicitudes.filter(s=>s.estado==='pendiente').length} pendientes)`],
          ['novedades-afil',`Novedades Afiliados (${novedadesAfil.filter(n=>n.estado==='pendiente').length} pendientes)`],
          ['avisos','📩 Novedades a Clientes'],
        ].map(([id,label])=>(
          <button key={id} onClick={()=>{ setTabNov(id); limpiar(); }}
            style={{ padding:'8px 18px', borderRadius:8, border:'none', fontSize:13, fontWeight:600,
              cursor:'pointer', background:tabNov===id?C.primary:'#fff',
              color:tabNov===id?'#fff':C.text2, boxShadow:tabNov===id?'none':'0 1px 3px rgba(0,0,0,.1)' }}>
            {label}
          </button>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ background:C.surface, borderRadius:10, border:`1px solid ${C.border}`, padding:'12px 16px', marginBottom:16 }}>
        <div style={{ display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
          <div>
            <label style={lbl}>Cliente</label>
            <select style={sel} value={filtroCliente} onChange={e=>setFiltroCliente(e.target.value)}>
              <option value="">Todos</option>
              {(tabNov==='novedades'?clientesNov:clientesSol).map(c=><option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Estado</label>
            <select style={sel} value={filtroEstado} onChange={e=>setFiltroEstado(e.target.value)}>
              <option value="">Todos</option>
              {tabNov==='novedades'
                ? [['pendiente','Pendiente'],['procesado','Procesado']].map(([v,l])=><option key={v} value={v}>{l}</option>)
                : [['pendiente','Pendiente'],['ejecutado','Ejecutado'],['rechazado','Rechazado']].map(([v,l])=><option key={v} value={v}>{l}</option>)
              }
            </select>
          </div>
          <div>
            <label style={lbl}>Fecha</label>
            <input type="date" style={sel} value={filtroFecha} onChange={e=>setFiltroFecha(e.target.value)} />
          </div>
          {(filtroCliente||filtroEstado||filtroFecha) && <Btn variant="secondary" onClick={limpiar}>Limpiar</Btn>}
        </div>
      </div>

      {/* Tabla Novedades de Pago */}
      {tabNov==='novedades'&&(
        loadNov ? <p style={{ color:C.text2 }}>Cargando...</p> :
        novFiltradas.length===0 ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin novedades{(filtroCliente||filtroEstado||filtroFecha)?' con estos filtros':''}.</p> :
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
            <thead><tr style={{ background:C.surface2 }}>
              {['Cliente','Período','Afiliados','Observaciones','Estado','Respuesta admin','Registrado','Acción'].map(h=>(
                <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {novFiltradas.map(n=>(
                <tr key={n.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}><strong>{n.username_cliente}</strong>{n.cliente_ref&&<div style={{ fontSize:11,color:C.text2 }}>{n.cliente_ref}</div>}</td>
                  <td style={tdc}>{n.mes} {n.anio}</td>
                  <td style={tdc}>
                    <div style={{ fontSize:12 }}>{n.afiliados.length} persona(s)</div>
                    <div style={{ fontSize:11, color:C.text2, maxWidth:220 }}>
                      {n.afiliados.slice(0,2).join(', ')}{n.afiliados.length>2?` +${n.afiliados.length-2} más`:''}
                    </div>
                    {n.afiliados.length > 2 && (
                      <button
                        onClick={() => {
                          api.get(`/portal/novedades-pago/${n.id}/exportar-excel`, { responseType:'blob' })
                            .then(r => {
                              const url = window.URL.createObjectURL(new Blob([r.data]));
                              const a = document.createElement('a'); a.href = url;
                              a.download = `novedad-pago-${n.mes}-${n.anio}-${n.id}.xlsx`; a.click();
                              window.URL.revokeObjectURL(url);
                            })
                            .catch(() => toast.error('Error al exportar'));
                        }}
                        style={{ marginTop:4, fontSize:11, color:C.primary, background:'none', border:`1px solid ${C.border}`, borderRadius:5, padding:'2px 8px', cursor:'pointer', fontWeight:600 }}
                      >
                        Descargar lista
                      </button>
                    )}
                  </td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{n.obs||'—'}</span></td>
                  <td style={tdc}>{badgeEstado(n.estado)}</td>
                  <td style={tdc}><span style={{ fontSize:11,color:n.respuesta?C.blue:C.text2 }}>{n.respuesta||'—'}</span></td>
                  <td style={tdc}><span style={{ fontSize:11, color:C.text2 }}>{new Date(n.creado).toLocaleString('es-CO')}</span></td>
                  <td style={tdc}>
                    {n.estado==='pendiente'
                      ? <Btn size="sm" variant="success" onClick={()=>{ setModalResp({tipo:'novedad',id:n.id,estado:'procesado',label:`Novedad de pago ${n.mes} ${n.anio}`}); setRespTexto(n.respuesta||''); }}>Marcar procesado</Btn>
                      : <Btn size="sm" variant="secondary" onClick={()=>updNovedad.mutate({id:n.id,estado:'pendiente',respuesta:n.respuesta})} disabled={updNovedad.isPending}>Reabrir</Btn>
                    }
                    <Btn size="sm" variant="danger" style={{marginLeft:4}} onClick={()=>{ if(window.confirm('¿Eliminar esta novedad y sus adjuntos?')) delNovedad.mutate(n.id); }} disabled={delNovedad.isPending}>×</Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tabla Solicitudes de Retiro */}
      {tabNov==='solicitudes'&&(
        loadSol ? <p style={{ color:C.text2 }}>Cargando...</p> :
        solFiltradas.length===0 ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin solicitudes{(filtroCliente||filtroEstado||filtroFecha)?' con estos filtros':''}.</p> :
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
            <thead><tr style={{ background:C.surface2 }}>
              {['Cliente','Afiliado','Documento','Motivo','Observaciones','Estado','Respuesta admin','Registrado','Acción'].map(h=>(
                <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {solFiltradas.map(s=>(
                <tr key={s.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}><strong>{s.username_cliente||s.cliente_ref}</strong></td>
                  <td style={tdc}>{s.afiliado_nombre}</td>
                  <td style={tdc}><span style={{ color:C.text2, fontSize:12 }}>{s.afiliado_doc}</span></td>
                  <td style={tdc}>{s.motivo}</td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{s.obs||'—'}</span></td>
                  <td style={tdc}>{badgeEstado(s.estado)}</td>
                  <td style={tdc}><span style={{ fontSize:11,color:s.respuesta?C.blue:C.text2 }}>{s.respuesta||'—'}</span></td>
                  <td style={tdc}><span style={{ fontSize:11, color:C.text2 }}>{new Date(s.creado).toLocaleString('es-CO')}</span></td>
                  <td style={tdc}>
                    {s.estado==='pendiente'&&(
                      <div style={{ display:'flex', gap:6 }}>
                        <Btn size="sm" variant="success" onClick={()=>{ setModalResp({tipo:'retiro',id:s.id,estado:'ejecutado',label:`Retiro de ${s.afiliado_nombre}`}); setRespTexto(s.respuesta||''); }}>Ejecutado</Btn>
                        <Btn size="sm" variant="danger"  onClick={()=>{ setModalResp({tipo:'retiro',id:s.id,estado:'rechazado',label:`Retiro de ${s.afiliado_nombre}`}); setRespTexto(s.respuesta||''); }}>Rechazar</Btn>
                      </div>
                    )}
                    {s.estado!=='pendiente'&&<Btn size="sm" variant="secondary" onClick={()=>updSolicitud.mutate({id:s.id,estado:'pendiente',respuesta:s.respuesta})} disabled={updSolicitud.isPending}>Reabrir</Btn>}
                    <Btn size="sm" variant="danger" style={{marginLeft:4}} onClick={()=>{ if(window.confirm('¿Eliminar esta solicitud y sus adjuntos?')) delSolicitud.mutate(s.id); }} disabled={delSolicitud.isPending}>×</Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tabla Novedades de Afiliados */}
      {tabNov==='novedades-afil'&&(
        loadNovAfil ? <p style={{ color:C.text2 }}>Cargando...</p> :
        novAfilFiltradas.length===0
          ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin novedades{(filtroCliente||filtroEstado||filtroFecha)?' con estos filtros':''}.</p> :
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
            <thead><tr style={{ background:C.surface2 }}>
              {['Cliente','Afiliado','Documento','Tipo','Descripción','Estado','Respuesta admin','Registrado','Acción'].map(h=>(
                <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {novAfilFiltradas.map(n=>(
                <tr key={n.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}><strong>{n.username_cliente||n.cliente_ref}</strong></td>
                  <td style={tdc}>{n.afiliado_nombre}</td>
                  <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{n.afiliado_doc}</span></td>
                  <td style={tdc}><span style={{ fontWeight:600, color:C.blue, fontSize:12 }}>{n.tipo}</span></td>
                  <td style={{ ...tdc, maxWidth:220 }}><span style={{ fontSize:12, color:C.text2 }}>{n.descripcion}</span></td>
                  <td style={tdc}>{badgeEstado(n.estado)}</td>
                  <td style={tdc}><span style={{ fontSize:11,color:n.respuesta?C.blue:C.text2 }}>{n.respuesta||'—'}</span></td>
                  <td style={tdc}><span style={{ fontSize:11, color:C.text2 }}>{new Date(n.creado).toLocaleString('es-CO')}</span></td>
                  <td style={tdc}>
                    {n.estado==='pendiente'
                      ? <Btn size="sm" variant="success" onClick={()=>{ setModalResp({tipo:'novedad-afil',id:n.id,estado:'atendido',label:`Novedad ${n.tipo} — ${n.afiliado_nombre}`}); setRespTexto(n.respuesta||''); }}>Marcar atendido</Btn>
                      : <Btn size="sm" variant="secondary" onClick={()=>updNovedadAfil.mutate({id:n.id,estado:'pendiente',respuesta:n.respuesta})} disabled={updNovedadAfil.isPending}>Reabrir</Btn>
                    }
                    <Btn size="sm" variant="danger" style={{marginLeft:4}} onClick={()=>{ if(window.confirm('¿Eliminar esta novedad y sus adjuntos?')) delNovedadAfil.mutate(n.id); }} disabled={delNovedadAfil.isPending}>×</Btn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Avisos a Clientes ── */}
      {tabNov==='avisos'&&(
        <div>
          {/* Formulario crear aviso */}
          <div style={{ background:C.surface, borderRadius:10, border:`1px solid ${C.border}`, padding:'16px 20px', marginBottom:20 }}>
            <h4 style={{ margin:'0 0 12px', fontSize:14, fontWeight:700, color:C.text }}>Nueva Novedad al Cliente</h4>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:12 }}>
              <div>
                <label style={lbl}>Cliente destinatario</label>
                <select style={inp} value={avisoForm.cliente_ref} onChange={e=>setAvisoForm(p=>({...p,cliente_ref:e.target.value}))}>
                  <option value="">Seleccionar cliente...</option>
                  {usuariosCliente.filter(u=>u.cliente_ref).map(u=>(
                    <option key={u.id} value={u.cliente_ref}>{u.nombre} — {u.cliente_ref}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={lbl}>Título</label>
                <input style={inp} placeholder="Ej: Actualización de tarifas" value={avisoForm.titulo} onChange={e=>setAvisoForm(p=>({...p,titulo:e.target.value}))} maxLength={200} />
              </div>
            </div>
            <div style={{ marginBottom:12 }}>
              <label style={lbl}>Mensaje</label>
              <textarea style={{...inp,height:80,resize:'vertical'}} placeholder="Contenido de la novedad para el cliente..." value={avisoForm.mensaje} onChange={e=>setAvisoForm(p=>({...p,mensaje:e.target.value}))} />
            </div>
            {/* Adjuntos */}
            <div style={{ marginBottom:12 }}>
              <label style={{ display:'block', padding:'7px 12px', border:`2px dashed ${C.border}`, borderRadius:7,
                textAlign:'center', cursor:'pointer', color:C.text2, fontSize:12, background:C.surface2 }}>
                📎 {avisoFiles.length > 0 ? `${avisoFiles.length} archivo(s) adjunto(s)` : 'Adjuntar documentos (opcional)'}
                <input type="file" multiple style={{ display:'none' }} accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                  onChange={e => setAvisoFiles(p => [...p, ...Array.from(e.target.files)])} />
              </label>
              {avisoFiles.length > 0 && (
                <div style={{ marginTop:6, display:'flex', flexWrap:'wrap', gap:4 }}>
                  {avisoFiles.map((f, i) => (
                    <div key={i} style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 8px',
                      background:C.blueBg, border:`1px solid ${C.blue}`, borderRadius:5, fontSize:11 }}>
                      <span style={{ color:C.blue }}>{f.name}</span>
                      <span style={{ cursor:'pointer', color:C.red, fontWeight:700 }} onClick={() => setAvisoFiles(p => p.filter((_,j) => j !== i))}>×</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <Btn variant="primary"
              onClick={()=>{ if(!avisoForm.cliente_ref||!avisoForm.titulo.trim()||!avisoForm.mensaje.trim()){ toast.error('Completa todos los campos'); return; } crearAviso.mutate(avisoForm); }}
              disabled={crearAviso.isPending}>
              {crearAviso.isPending ? 'Enviando...' : '📩 Enviar Novedad'}
            </Btn>
          </div>

          {/* Tabla avisos enviados */}
          {loadAvisos ? <p style={{ color:C.text2 }}>Cargando...</p> :
           avisos.length===0 ? <p style={{ color:C.text2, padding:20, textAlign:'center' }}>Sin novedades enviadas aún.</p> :
          <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
            <table style={{ width:'100%', borderCollapse:'collapse', background:C.surface }}>
              <thead><tr style={{ background:C.surface2 }}>
                {['Cliente','Título','Mensaje','Adjuntos','Estado','Enviado por','Fecha','Acción'].map(h=>(
                  <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {avisos.map(a=>(
                  <tr key={a.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                    <td style={tdc}><strong>{a.cliente_ref}</strong></td>
                    <td style={tdc}><span style={{ fontWeight:600, fontSize:13 }}>{a.titulo}</span></td>
                    <td style={{ ...tdc, maxWidth:220 }}><span style={{ fontSize:12, color:C.text2, whiteSpace:'pre-wrap' }}>{a.mensaje}</span></td>
                    <td style={tdc}>
                      {(a.documentos||[]).length === 0
                        ? <span style={{ color:C.text2, fontSize:11 }}>—</span>
                        : (a.documentos||[]).map(d=>(
                          <div key={d.id} style={{ fontSize:11, color:C.blue, cursor:'pointer', textDecoration:'underline', marginBottom:2 }}
                            onClick={async()=>{
                              const res = await api.get(`/documentos/${d.id}/descargar`, { responseType:'blob' }).catch(()=>null);
                              if(!res) return toast.error('Error al descargar');
                              if(res.data?.url) { window.open(res.data.url,'_blank'); return; }
                              const u=URL.createObjectURL(res.data); const a2=document.createElement('a'); a2.href=u; a2.download=d.nombre; a2.click(); URL.revokeObjectURL(u);
                            }}>
                            📄 {d.nombre}
                          </div>
                        ))
                      }
                    </td>
                    <td style={tdc}>
                      {a.leido
                        ? <span style={{ background:C.greenBg, color:C.green, borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>Leído</span>
                        : <span style={{ background:'#FEF3C7', color:'#92400E', borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>No leído</span>
                      }
                    </td>
                    <td style={tdc}><span style={{ fontSize:12, color:C.text2 }}>{a.creado_por}</span></td>
                    <td style={tdc}><span style={{ fontSize:11, color:C.text2 }}>{new Date(a.creado).toLocaleString('es-CO')}</span></td>
                    <td style={tdc}>
                      <Btn size="sm" variant="danger" onClick={()=>{ if(window.confirm('¿Eliminar esta novedad y sus adjuntos?')) delAviso.mutate(a.id); }} disabled={delAviso.isPending}>×</Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
        </div>
      )}

      {/* ── Modal respuesta al resolver ── */}
      {modalResp&&(
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center'}}>
          <div style={{background:C.surface,borderRadius:14,padding:28,width:500,maxWidth:'95vw',boxShadow:'0 20px 60px rgba(0,0,0,.3)',maxHeight:'90vh',overflowY:'auto'}}>
            <h3 style={{margin:'0 0 6px',fontSize:15,fontWeight:700}}>Resolver solicitud</h3>
            <p style={{margin:'0 0 16px',fontSize:13,color:C.text2}}>{modalResp.label}</p>

            {/* Archivos adjuntos del cliente */}
            {docsNovedad.length > 0 && (
              <div style={{marginBottom:16,background:C.surface2,borderRadius:8,padding:'10px 12px'}}>
                <p style={{margin:'0 0 8px',fontSize:12,fontWeight:600,color:C.text2}}>📎 Adjuntos del cliente ({docsNovedad.length}):</p>
                {docsNovedad.map(d=>(
                  <div key={d.id} style={{display:'flex',alignItems:'center',gap:8,fontSize:12,marginBottom:4}}>
                    <span style={{flex:1,color:C.blue,cursor:'pointer',textDecoration:'underline'}}
                      onClick={async()=>{
                        const res = await api.get(`/documentos/${d.id}/descargar`,{responseType:'blob'});
                        const u=URL.createObjectURL(res.data); const a=document.createElement('a'); a.href=u; a.download=d.nombre; a.click(); URL.revokeObjectURL(u);
                      }}>
                      📄 {d.nombre}
                    </span>
                    <span style={{color:C.text2,fontSize:11}}>{d.subido_por}</span>
                  </div>
                ))}
              </div>
            )}

            <div style={{marginBottom:12}}>
              <label style={lbl}>Nota / respuesta para el cliente <span style={{fontWeight:400,color:C.text2}}>(opcional)</span></label>
              <textarea style={{...inp,height:80,resize:'vertical'}} placeholder="Ej: Se procesó el pago, se ejecutó el retiro el día..." value={respTexto} onChange={e=>setRespTexto(e.target.value)} autoFocus />
            </div>

            {/* Adjuntar doc de respuesta */}
            <div style={{marginBottom:16}}>
              <label style={{display:'block',padding:'7px 12px',border:`2px dashed ${C.border}`,borderRadius:7,
                textAlign:'center',cursor:'pointer',color:C.text2,fontSize:12,background:C.surface2}}>
                📎 {respFiles.length > 0 ? `${respFiles.length} archivo(s) de respuesta` : 'Adjuntar documento de respuesta (opcional)'}
                <input type="file" multiple style={{display:'none'}} accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                  onChange={e=>setRespFiles(p=>[...p,...Array.from(e.target.files)])} />
              </label>
              {respFiles.length > 0 && (
                <div style={{marginTop:6,display:'flex',flexWrap:'wrap',gap:4}}>
                  {respFiles.map((f,i)=>(
                    <div key={i} style={{display:'flex',alignItems:'center',gap:4,padding:'3px 8px',
                      background:C.blueBg,border:`1px solid ${C.blue}`,borderRadius:5,fontSize:11}}>
                      <span style={{color:C.blue}}>{f.name}</span>
                      <span style={{cursor:'pointer',color:C.red,fontWeight:700}} onClick={()=>setRespFiles(p=>p.filter((_,j)=>j!==i))}>×</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{display:'flex',gap:8,justifyContent:'flex-end'}}>
              <Btn variant="secondary" onClick={cerrarModalResp}>Cancelar</Btn>
              <Btn variant="success" onClick={confirmarRespuesta} disabled={updNovedad.isPending||updSolicitud.isPending||updNovedadAfil.isPending}>
                Confirmar y notificar cliente
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Re-exports
export default Cobro;
