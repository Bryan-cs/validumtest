import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useReactTable, getCoreRowModel, getSortedRowModel, flexRender } from '@tanstack/react-table';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, PageHeader, ConfirmModal, ErrorMsg } from '../components/UI';

const UP = v => (v || '').toUpperCase();

const tdc = { padding:'10px 12px', fontSize:13, color:C.text, verticalAlign:'middle' };
const lbl = { display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 };
const inp = { width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface };

export default function Usuarios() {
  const qc = useQueryClient();
  const [modal,setModal]=useState(false);
  const [form,setForm]=useState({rol:'empleado'});
  const [err,setErr]=useState('');
  const sf=(k,v)=>setForm(f=>({...f,[k]:v}));
  const [pwModal,setPwModal]=useState(null);
  const [pwForm,setPwForm]=useState({});
  const [pwErr,setPwErr]=useState('');
  const [showPw,setShowPw]=useState(false);
  const [confirmState, setConfirmState] = useState({ open: false, title: '', message: '', onConfirm: null });

  const { data: users=[], isError: isErrorUsers, refetch: refetchUsers } = useQuery({ queryKey:['usuarios'], queryFn:()=>api.get('/usuarios').then(r=>r.data), staleTime: 300_000 });
  const { data: clientes=[] } = useQuery({ queryKey:['clientes-lista'], queryFn:()=>api.get('/clientes').then(r=>r.data), staleTime: 300_000 });

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
            <Btn size="sm" variant="secondary" onClick={() => { setPwModal({ id: u.id, nombre: u.nombre }); setPwForm({}); setPwErr(''); setShowPw(false); }}>Contraseña</Btn>
            {u.username !== 'admin' && <Btn size="sm" variant="danger" onClick={() => setConfirmState({ open:true, title:'Eliminar usuario', message:`¿Eliminar al usuario "${u.nombre}"? Esta acción no se puede deshacer.`, onConfirm:()=>{ eliminar.mutate(u.id); setConfirmState(s=>({...s,open:false})); } })}>Eliminar</Btn>}
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
      {isErrorUsers && <ErrorMsg message="Error al cargar usuarios" onRetry={refetchUsers} />}
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead>
            {userTable.getHeaderGroups().map(hg => (
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
                <div style={{ position:'relative' }}>
                  <input type={showPw?'text':'password'} style={{ ...inp, paddingRight:40 }} value={pwForm[k]||''} onChange={e=>setPwForm(f=>({...f,[k]:e.target.value}))} />
                  <button type="button" onClick={()=>setShowPw(v=>!v)}
                    style={{ position:'absolute', right:10, top:'50%', transform:'translateY(-50%)', background:'none', border:'none', cursor:'pointer', fontSize:16, color:C.text2, padding:0, lineHeight:1 }}>
                    {showPw ? '🙈' : '👁️'}
                  </button>
                </div>
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
