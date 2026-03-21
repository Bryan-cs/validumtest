// ─── COBRO PAGE ───────────────────────────────────────────────────────────────
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import { C, Btn, PageHeader, StatCard, fmt } from '../components/UI';

const UP = v => (v||'').toUpperCase();

async function dlExcel(url, filename) {
  try {
    const res = await api.get(url, { responseType: 'blob' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(res.data);
    a.download = filename;
    a.click();
  } catch (e) {
    alert('Error generando reporte');
  }
}

// Todos los inputs de texto van en mayúsculas
const up = (e, setter) => setter(e.target.value.toUpperCase());

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

// ─── COBRO ────────────────────────────────────────────────────────────────────
export function Cobro() {
  const qc = useQueryClient();
  const [empresa, setEmp] = useState('');
  const [cliente, setCli] = useState('');
  const [tipo,    setTipo]= useState('');
  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data) });
  const { data: rows=[], isLoading } = useQuery({
    queryKey:['cobro',empresa,cliente,tipo],
    queryFn:()=>api.get('/cobro',{params:{empresa,cliente,tipo}}).then(r=>r.data),
    refetchInterval:60_000,
  });
  const { data: todosAfil=[] } = useQuery({ queryKey:['afiliados_all'], queryFn:()=>api.get('/afiliados').then(r=>r.data.items||[]) });
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
        <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
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
  const [tab,   setTab]  = useState('retiros');
  const [anio, setAnio] = useState('');
  const [mes,  setMes]  = useState('');
  const [modal, setModal] = useState(false);
  const [doc,   setDoc]  = useState('');
  const [fecha, setFecha]= useState(new Date().toISOString().slice(0,10));
  const [motivo,setMotivo]=useState('Renuncia');
  const [obs,   setObs]  = useState('');

  const { data: rows=[], isLoading } = useQuery({
    queryKey:['retiros',anio,mes],
    queryFn:()=>api.get('/retiros',{params:{anio,mes}}).then(r=>r.data),
  });
  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data) });

  const aplicar = useMutation({
    mutationFn: ()=>api.post('/retiros',{doc,fecha,motivo,obs}),
    onSuccess: (r)=>{
      const n = r.data?.facturas_pendientes;
      toast.success(n ? `Retiro aplicado. ${n} factura(s) pendiente(s) del mes` : 'Retiro aplicado');
      qc.invalidateQueries({queryKey:['retiros']}); qc.invalidateQueries({queryKey:['afiliados']});
      setModal(false); setDoc(''); setObs('');
    },
    onError:(e)=>toast.error(e.response?.data?.detail||'Afiliado no encontrado'),
  });

  const eliminar = useMutation({
    mutationFn:(id)=>api.delete(`/retiros/${id}`),
    onSuccess:()=>{ toast.success('Retiro eliminado'); qc.invalidateQueries({queryKey:['retiros']}); },
  });

  const anios = [...new Set(rows.map(r=>r.anio).filter(Boolean))];

  const { data: historial=[] } = useQuery({
    queryKey: ['actividad','Retiros'],
    queryFn: () => api.get('/actividad', { params:{ modulo:'Retiros' } }).then(r=>r.data),
    enabled: tab === 'historial',
  });

  return (
    <div>
      <PageHeader title="↪️ Retiros" subtitle={`${rows.length} retiros`}
        action={
          <div style={{ display:'flex', gap:8 }}>
            <Btn variant="secondary" onClick={()=>dlExcel(`/reportes/retiros?anio=${anio}&mes=${mes}`,`retiros${anio?'_'+anio:''}${mes?'_'+mes:''}.xlsx`)}>📊 Exportar Excel</Btn>
            <Btn variant="accent" onClick={()=>setModal(true)}>+ Aplicar retiro</Btn>
          </div>
        } />
      {/* Pestañas */}
      <div style={{ display:'flex', gap:4, marginBottom:16, borderBottom:`2px solid ${C.border}` }}>
        {[
          { key:'retiros',   label:`↪️ Retiros (${rows.length})` },
          { key:'historial', label:'📋 Historial de cambios' },
        ].map(t=>(
          <button key={t.key} onClick={()=>setTab(t.key)} style={{
            padding:'9px 18px', border:'none', borderRadius:'7px 7px 0 0',
            background: tab===t.key ? C.primary : 'transparent',
            color: tab===t.key ? '#fff' : C.text2,
            fontWeight: tab===t.key ? 700 : 400, fontSize:13, cursor:'pointer',
          }}>{t.label}</button>
        ))}
      </div>

      {tab === 'retiros' && (<>
        <div style={{ display:'flex', gap:8, marginBottom:14 }}>
          <select style={sel} value={anio} onChange={e=>setAnio(e.target.value)}>
            {['', ...anios].map(a=><option key={a} value={a}>{a||'Todos los años'}</option>)}
          </select>
          <select style={sel} value={mes} onChange={e=>setMes(e.target.value)}>
            {['', ...MESES].map(m=><option key={m} value={m}>{m||'Todos los meses'}</option>)}
          </select>
        </div>
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
            <thead>
              <tr style={{ background:C.surface2 }}>
                {['#','Nombre','Empresa','Documento','Fecha','Motivo','Registrado por','Acciones'].map(h=>(
                  <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={8} style={{ padding:20, textAlign:'center', color:C.text2 }}>Cargando...</td></tr>}
              {rows.map((r,i)=>(
                <tr key={r.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={tdc}>{i+1}</td>
                  <td style={tdc}>{r.nombre}</td>
                  <td style={tdc}>{r.empresa}</td>
                  <td style={tdc}>{r.doc}</td>
                  <td style={tdc}>{r.fecha}</td>
                  <td style={tdc}>{r.motivo}</td>
                  <td style={tdc}>{r.registrado_por}</td>
                  <td style={tdc}>
                    <Btn size="sm" variant="danger" onClick={()=>{ if(window.confirm('¿Eliminar retiro?')) eliminar.mutate(r.id); }}>Eliminar</Btn>
                  </td>
                </tr>
              ))}
              {!isLoading&&rows.length===0&&<tr><td colSpan={8} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin retiros</td></tr>}
            </tbody>
          </table>
        </div>
      </>)}

      {tab === 'historial' && (
        <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
          <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
            <thead>
              <tr style={{ background:C.surface2 }}>
                {['Fecha','Usuario','Acción','Detalle'].map(h=>(
                  <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}`, whiteSpace:'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {historial.map((a,i)=>(
                <tr key={i} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ ...tdc, fontSize:11, color:C.text2, whiteSpace:'nowrap' }}>{a.fecha}</td>
                  <td style={{ ...tdc, fontWeight:600 }}>{a.usuario}</td>
                  <td style={tdc}>{a.accion}</td>
                  <td style={{ ...tdc, color:C.text2, fontSize:12 }}>{a.detalle}</td>
                </tr>
              ))}
              {historial.length===0&&<tr><td colSpan={4} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin historial de retiros</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      {modal && (
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
          <div style={{ background:'#fff',borderRadius:14,padding:28,width:420,boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
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
  const [anio, setAnio] = useState(new Date().getFullYear().toString());
  const [mes,  setMes]  = useState('');
  const [cliente,setCli]= useState('');
  const [estado,setEst] = useState('');

  const { data: rows=[], isLoading } = useQuery({
    queryKey:['facturas',anio,mes,cliente,estado],
    queryFn:()=>api.get('/facturas',{params:{anio,mes,cliente,estado}}).then(r=>r.data.items||[]),
  });

  const clientes = [...new Set(rows.map(r=>r.cliente).filter(Boolean))];
  const anios = [...new Set(rows.map(r=>r.anio).filter(Boolean))];

  const pagar = useMutation({
    mutationFn:(id)=>api.patch(`/facturas/${id}/pagar`),
    onSuccess:()=>{ toast.success('Factura marcada como pagada'); qc.invalidateQueries({queryKey:['facturas']}); },
  });
  const eliminar = useMutation({
    mutationFn:(id)=>api.delete(`/facturas/${id}`),
    onSuccess:()=>{ toast.success('Factura eliminada'); qc.invalidateQueries({queryKey:['facturas']}); },
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
      <div style={{ overflowX:'auto', borderRadius:10, border:`1px solid ${C.border}` }}>
        <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
          <thead>
            <tr style={{ background:C.surface2 }}>
              {['Código','Afiliado','Cliente','Mes/Año','Ingresos','Planilla','Utilidad','Banco','Estado','Acciones'].map(h=>(
                <th key={h} style={{ padding:'10px 12px', textAlign:'left', fontSize:11, fontWeight:600, color:C.text2, borderBottom:`1px solid ${C.border}`, whiteSpace:'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading&&<tr><td colSpan={10} style={{ padding:20,textAlign:'center',color:C.text2 }}>Cargando...</td></tr>}
            {rows.map(f=>{
              const isHuerfana = f.afiliado_eliminado && f.estado==='pendiente';
              return (
                <tr key={f.id} style={{ borderBottom:`1px solid ${C.border}`, background: isHuerfana?C.redBg:'#fff' }}>
                  <td style={tdc}>{f.codigo}</td>
                  <td style={{ ...tdc, color: isHuerfana?C.red:C.text }}>
                    {f.nombre_afiliado}
                    {isHuerfana&&<span style={{ fontSize:10, marginLeft:4 }}>⚠️ eliminado</span>}
                  </td>
                  <td style={tdc}>{f.cliente||'—'}</td>
                  <td style={tdc}>{f.mes} {f.anio}</td>
                  <td style={{ ...tdc, textAlign:'right' }}>{fmt(f.ingresos)}</td>
                  <td style={{ ...tdc, textAlign:'right' }}>{fmt(f.costos)}</td>
                  <td style={{ ...tdc, textAlign:'right', color:(f.utilidad>=0?C.green:C.red) }}>{fmt(f.utilidad)}</td>
                  <td style={tdc}>{f.banco||'—'}</td>
                  <td style={tdc}>
                    <span style={{ background:f.estado==='pagado'?C.greenBg:C.amberBg,
                      color:f.estado==='pagado'?C.green:C.amber, borderRadius:10, padding:'2px 10px', fontSize:11, fontWeight:600 }}>
                      {f.estado==='pagado'?'Pagada':'Pendiente'}
                    </span>
                  </td>
                  <td style={tdc}>
                    <div style={{ display:'flex', gap:5 }}>
                      {f.estado==='pendiente'&&(
                        <Btn size="sm" variant="success" onClick={()=>pagar.mutate(f.id)}>✓ Pagada</Btn>
                      )}
                      <Btn size="sm" variant="danger" onClick={()=>{ if(window.confirm('¿Eliminar factura?')) eliminar.mutate(f.id); }}>Eliminar</Btn>
                    </div>
                  </td>
                </tr>
              );
            })}
            {!isLoading&&rows.length===0&&<tr><td colSpan={10} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin facturas</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── EMPLEADOS ────────────────────────────────────────────────────────────────
export function Empleados() {
  const qc = useQueryClient();
  const [modal,setModal]= useState(null);
  const [form, setForm] = useState({});
  const sf = (k,v)=>setForm(f=>({...f,[k]:v}));

  const { data: emps=[] } = useQuery({ queryKey:['empleados'], queryFn:()=>api.get('/empleados').then(r=>r.data) });
  const { data: gastos=[] }= useQuery({ queryKey:['gastos'],   queryFn:()=>api.get('/gastos').then(r=>r.data) });
  const { data: usuarios=[] }= useQuery({ queryKey:['usuarios'], queryFn:()=>api.get('/usuarios').then(r=>r.data) });

  const nomTotal = emps.filter(e=>e.activo).reduce((s,e)=>s+e.nomina,0);
  const gasTotal = gastos.filter(g=>g.activo).reduce((s,g)=>s+g.valor,0);

  const guardarEmp = useMutation({
    mutationFn:()=>modal==='nuevo'?api.post('/empleados',form):api.put(`/empleados/${modal.id}`,form),
    onSuccess:()=>{ toast.success('Empleado guardado'); qc.invalidateQueries({queryKey:['empleados']}); setModal(null); },
    onError:(e)=>toast.error(e.response?.data?.detail||'Error'),
  });

  const eliminarEmp = useMutation({
    mutationFn:(id)=>api.delete(`/empleados/${id}`),
    onSuccess:()=>{ toast.success('Empleado eliminado'); qc.invalidateQueries({queryKey:['empleados']}); },
    onError:(e)=>toast.error(e.response?.data?.detail||'Error'),
  });

  const [gnombre,setGnom]=useState(''); const [gvalor,setGval]=useState(0);
  const addGasto = useMutation({
    mutationFn:()=>api.post('/gastos',{nombre:gnombre,valor:+gvalor}),
    onSuccess:()=>{ toast.success('Gasto agregado'); qc.invalidateQueries({queryKey:['gastos']}); setGnom(''); setGval(0); },
  });
  const toggleG = useMutation({
    mutationFn:(id)=>api.patch(`/gastos/${id}/toggle`),
    onSuccess:()=>qc.invalidateQueries({queryKey:['gastos']}),
  });
  const delGasto = useMutation({
    mutationFn:(id)=>api.delete(`/gastos/${id}`),
    onSuccess:()=>{ toast.success('Gasto eliminado'); qc.invalidateQueries({queryKey:['gastos']}); },
  });

  return (
    <div>
      <PageHeader title="👔 Empleados y gastos" />
      <div style={{ display:'flex',gap:10,marginBottom:20,flexWrap:'wrap' }}>
        <StatCard label="Nómina mensual"     value={fmt(nomTotal)} color={C.red} />
        <StatCard label="Gastos mensuales"   value={fmt(gasTotal)} color={C.amber} />
        <StatCard label="Total egresos"      value={fmt(nomTotal+gasTotal)} color={C.red} />
        <StatCard label="Empleados activos"  value={emps.filter(e=>e.activo).length} color={C.primary} />
      </div>

      {/* Empleados */}
      <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10 }}>
        <h3 style={{ margin:0,color:C.primary }}>Empleados</h3>
        <Btn variant="accent" onClick={()=>{setForm({activo:true,nomina:0});setModal('nuevo');}}>+ Nuevo empleado</Btn>
      </div>
      <div style={{ overflowX:'auto',borderRadius:10,border:`1px solid ${C.border}`,marginBottom:24 }}>
        <table style={{ width:'100%',borderCollapse:'collapse',background:'#fff' }}>
          <thead><tr style={{ background:C.surface2 }}>
            {['Nombre','Documento','Cargo','Usuario','Nómina ($)','Estado','Acciones'].map(h=>(
              <th key={h} style={{ padding:'9px 12px',textAlign:'left',fontSize:11,fontWeight:600,color:C.text2,borderBottom:`1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {emps.map(e=>(
              <tr key={e.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                <td style={tdc}>{e.nombre}</td><td style={tdc}>{e.doc}</td>
                <td style={tdc}>{e.cargo}</td><td style={tdc}>{e.usuario||'—'}</td>
                <td style={{ ...tdc,textAlign:'right' }}>{fmt(e.nomina)}</td>
                <td style={tdc}><span style={{ background:e.activo?C.greenBg:C.redBg,color:e.activo?C.green:C.red,borderRadius:10,padding:'2px 10px',fontSize:11,fontWeight:600 }}>{e.activo?'Activo':'Inactivo'}</span></td>
                <td style={tdc}>
                  <div style={{ display:'flex', gap:6 }}>
                    <Btn size="sm" variant="secondary" onClick={()=>{setForm({...e});setModal(e);}}>✏️ Editar</Btn>
                    <Btn size="sm" variant="danger" onClick={()=>{ if(window.confirm(`¿Eliminar a ${e.nombre}?`)) eliminarEmp.mutate(e.id); }}>🗑️ Eliminar</Btn>
                  </div>
                </td>
              </tr>
            ))}
            {emps.length===0&&<tr><td colSpan={7} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin empleados</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Gastos */}
      <h3 style={{ margin:'0 0 10px',color:C.primary }}>Gastos mensuales fijos</h3>
      <div style={{ display:'flex',gap:8,marginBottom:12,flexWrap:'wrap' }}>
        <input style={{ ...sel,flex:2,textTransform:'uppercase' }} placeholder="NOMBRE DEL GASTO..." value={gnombre} onChange={e=>setGnom(UP(e.target.value))} />
        <input type="number" style={sel} placeholder="Valor $" value={gvalor} onChange={e=>setGval(e.target.value)} />
        <Btn onClick={()=>addGasto.mutate()} disabled={!gnombre}>+ Agregar</Btn>
      </div>
      <div style={{ overflowX:'auto',borderRadius:10,border:`1px solid ${C.border}` }}>
        <table style={{ width:'100%',borderCollapse:'collapse',background:'#fff' }}>
          <thead><tr style={{ background:C.surface2 }}>
            {['Concepto','Valor mensual','Estado','Acciones'].map(h=>(
              <th key={h} style={{ padding:'9px 12px',textAlign:'left',fontSize:11,fontWeight:600,color:C.text2,borderBottom:`1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {gastos.map(g=>(
              <tr key={g.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                <td style={tdc}>{g.nombre}</td>
                <td style={{ ...tdc,textAlign:'right' }}>{fmt(g.valor)}</td>
                <td style={tdc}><span style={{ background:g.activo?C.greenBg:C.redBg,color:g.activo?C.green:C.red,borderRadius:10,padding:'2px 10px',fontSize:11,fontWeight:600 }}>{g.activo?'Activo':'Inactivo'}</span></td>
                <td style={tdc}>
                  <div style={{ display:'flex',gap:6 }}>
                    <Btn size="sm" variant="secondary" onClick={()=>toggleG.mutate(g.id)}>{g.activo?'Desactivar':'Activar'}</Btn>
                    <Btn size="sm" variant="danger" onClick={()=>{ if(window.confirm('¿Eliminar gasto?')) delGasto.mutate(g.id); }}>Eliminar</Btn>
                  </div>
                </td>
              </tr>
            ))}
            {gastos.length===0&&<tr><td colSpan={4} style={{ padding:20,textAlign:'center',color:C.text2 }}>Sin gastos registrados</td></tr>}
          </tbody>
        </table>
      </div>

      {modal&&(
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
          <div style={{ background:'#fff',borderRadius:14,padding:28,width:460,boxShadow:'0 20px 60px rgba(0,0,0,.25)',maxHeight:'90vh',overflow:'auto' }}>
            <h3 style={{ margin:'0 0 18px',color:C.primary }}>{modal==='nuevo'?'Nuevo empleado':'Editar empleado'}</h3>
            {[['Nombre *','nombre','text',true],['Documento','doc','text',false],['Cargo','cargo','text',true],['Teléfono','tel','tel',true],['Email','email','email',false]].map(([l,k,t,ucase])=>(
              <div key={k} style={{ marginBottom:10 }}>
                <label style={lbl}>{l}</label>
                <input type={t||'text'} style={{ ...inp, textTransform: ucase?'uppercase':'none' }} value={form[k]||''} onChange={e=>sf(k, ucase?UP(e.target.value):e.target.value)} />
              </div>
            ))}
            <label style={lbl}>Usuario asignado</label>
            <select style={inp} value={form.usuario||''} onChange={e=>sf('usuario',e.target.value)}>
              <option value="">Sin asignar</option>
              {usuarios.filter(u=>u.rol==='empleado').map(u=><option key={u.id} value={u.username}>{u.username}</option>)}
            </select>
            <label style={lbl}>Nómina mensual ($)</label>
            <input type="number" style={inp} value={form.nomina||0} onChange={e=>sf('nomina',+e.target.value)} />
            <div style={{ display:'flex',gap:10,marginTop:16,justifyContent:'flex-end' }}>
              <Btn variant="secondary" onClick={()=>setModal(null)}>Cancelar</Btn>
              <Btn onClick={()=>guardarEmp.mutate()} disabled={guardarEmp.isPending||!form.nombre}>
                {guardarEmp.isPending?'Guardando...':'Guardar'}
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

  const { data: users=[] } = useQuery({ queryKey:['usuarios'], queryFn:()=>api.get('/usuarios').then(r=>r.data) });

  const crear = useMutation({
    mutationFn:()=>{
      if(!form.nombre||!form.username||!form.password){setErr('Todos los campos son obligatorios.');return Promise.reject();}
      if(form.password!==form.password2){setErr('Las contraseñas no coinciden.');return Promise.reject();}
      return api.post('/usuarios',{nombre:form.nombre,username:form.username,password:form.password,rol:form.rol});
    },
    onSuccess:()=>{ toast.success('Usuario creado'); qc.invalidateQueries({queryKey:['usuarios']}); setModal(false); setErr(''); },
    onError:(e)=>{ if(e?.response){ const d=e.response?.data?.detail; setErr(Array.isArray(d)?d.map(x=>x.msg).join(', '):(d||'Error')); } },
  });

  const eliminar = useMutation({
    mutationFn:(id)=>api.delete(`/usuarios/${id}`),
    onSuccess:()=>{ toast.success('Usuario eliminado'); qc.invalidateQueries({queryKey:['usuarios']}); },
    onError:(e)=>toast.error(e.response?.data?.detail||'Error'),
  });

  return (
    <div>
      <PageHeader title="⚙️ Usuarios del sistema"
        action={<Btn variant="accent" onClick={()=>{setForm({rol:'empleado'});setErr('');setModal(true);}}>+ Nuevo usuario</Btn>} />
      <div style={{ overflowX:'auto',borderRadius:10,border:`1px solid ${C.border}` }}>
        <table style={{ width:'100%',borderCollapse:'collapse',background:'#fff' }}>
          <thead><tr style={{ background:C.surface2 }}>
            {['Nombre','Usuario','Rol','Estado','Acciones'].map(h=>(
              <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,color:C.text2,borderBottom:`1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {users.map(u=>(
              <tr key={u.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                <td style={tdc}>{u.nombre}</td><td style={tdc}>{u.username}</td>
                <td style={tdc}><span style={{ background:u.rol==='admin'?C.blueBg:C.greenBg,color:u.rol==='admin'?C.blue:C.green,borderRadius:10,padding:'2px 10px',fontSize:11,fontWeight:600 }}>{u.rol}</span></td>
                <td style={tdc}><span style={{ color:u.activo?C.green:C.red,fontWeight:600 }}>{u.activo?'Activo':'Inactivo'}</span></td>
                <td style={tdc}>{u.username!=='admin'&&<Btn size="sm" variant="danger" onClick={()=>{ if(window.confirm('¿Eliminar usuario?')) eliminar.mutate(u.id); }}>Eliminar</Btn>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {modal&&(
        <div style={{ position:'fixed',inset:0,background:'rgba(0,0,0,.45)',zIndex:1000,display:'flex',alignItems:'center',justifyContent:'center' }}>
          <div style={{ background:'#fff',borderRadius:14,padding:28,width:400,boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
            <h3 style={{ margin:'0 0 18px',color:C.primary }}>Nuevo usuario</h3>
            {[['Nombre completo *','nombre','text',true],['Usuario *','username','text',false],['Contraseña *','password','password',false],['Confirmar contraseña *','password2','password',false]].map(([l,k,t,ucase])=>(
              <div key={k} style={{ marginBottom:10 }}>
                <label style={lbl}>{l}</label>
                <input type={t} style={{ ...inp, textTransform: ucase?'uppercase':'none' }} value={form[k]||''} onChange={e=>sf(k, ucase?UP(e.target.value):e.target.value)} />
              </div>
            ))}
            <label style={lbl}>Rol</label>
            <select style={inp} value={form.rol||'empleado'} onChange={e=>sf('rol',e.target.value)}>
              <option value="admin">Admin</option><option value="empleado">Empleado</option>
            </select>
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
  const { data: listas={} } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data) });
  const [sel, setSel] = useState('empresas');
  const [newItem, setNewItem] = useState('');

  const update = useMutation({
    mutationFn:(items)=>api.put(`/listas/${sel}`,{items}),
    onSuccess:()=>{ toast.success('Lista actualizada'); qc.invalidateQueries({queryKey:['listas']}); },
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
      <div style={{ background:'#fff',borderRadius:10,border:`1px solid ${C.border}`,padding:20 }}>
        <div style={{ display:'flex',gap:8,marginBottom:14 }}>
          <input style={{ ...sel_s,flex:1 }} placeholder={`Nueva opción para ${sel}...`}
            value={newItem} onChange={e=>setNewItem(e.target.value)}
            onKeyDown={e=>e.key==='Enter'&&addItem()} />
          <Btn onClick={addItem}>Añadir</Btn>
        </div>
        <div style={{ display:'flex',flexWrap:'wrap',gap:8 }}>
          {items.map(item=>(
            <div key={item} style={{ display:'flex',alignItems:'center',gap:6,background:C.surface2,
              border:`1px solid ${C.border}`,borderRadius:7,padding:'5px 12px',fontSize:13 }}>
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

  React.useEffect(()=>{
    if(cfg.ibc_global) setIbc(cfg.ibc_global);
    if(cfg.porcentajes) setPcts({...cfg.porcentajes});
    if(cfg.plantilla_whatsapp !== undefined) setPlantilla(cfg.plantilla_whatsapp || PLANTILLA_DEFAULT);
  },[cfg]);

  const guardar = useMutation({
    mutationFn:()=>api.put('/config',{ ibc_global:+ibc, porcentajes:pcts, plantilla_whatsapp:plantilla }),
    onSuccess:()=>{ toast.success('Configuración actualizada'); qc.invalidateQueries({queryKey:['config']}); },
  });

  const ibcN = +ibc || 0;
  const ceil100 = v => Math.ceil(v/100)*100;

  return (
    <div>
      <PageHeader title="🧮 Calculadora de aportes" subtitle="Configura IBC global y porcentajes" />
      <div style={{ background:'#fff',borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <label style={{ ...lbl,fontSize:13 }}>IBC Global (Salario mínimo / base de cotización)</label>
        <input type="number" style={{ ...inp,width:240 }} value={ibc} onChange={e=>setIbc(e.target.value)} />
      </div>
      <div style={{ background:'#fff',borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
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
      <div style={{ background:'#fff',borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
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
      <Btn onClick={()=>guardar.mutate()} disabled={guardar.isPending}>
        {guardar.isPending?'Guardando...':'💾 Guardar configuración'}
      </Btn>
    </div>
  );
}

// ─── SHARED STYLES ────────────────────────────────────────────────────────────
const tdc = { padding:'10px 12px', fontSize:13, color:'#1E293B', verticalAlign:'middle' };
const sel = { padding:'8px 12px', border:'1px solid #E2E8F0', borderRadius:7, fontSize:13, outline:'none', background:'#fff', color:'#1E293B' };
const sel_s = { padding:'8px 12px', border:'1px solid #E2E8F0', borderRadius:7, fontSize:13, outline:'none', background:'#fff', color:'#1E293B' };
const lbl = { display:'block', fontSize:12, color:'#64748B', fontWeight:500, marginBottom:4 };
const inp = { width:'100%', padding:'9px 12px', border:'1px solid #E2E8F0', borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:'#1E293B' };

// Re-exports
export default Cobro;
