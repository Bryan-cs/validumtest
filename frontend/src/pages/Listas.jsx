import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, PageHeader, ConfirmModal, ErrorMsg } from '../components/UI';

const sel_s = { padding:'8px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', background:C.surface, color:C.text };

export default function Listas() {
  const qc = useQueryClient();
  const { data: listas={}, isError: isErrorListas, refetch: refetchListas } = useQuery({ queryKey:['listas'], queryFn:()=>api.get('/listas').then(r=>r.data), staleTime: 300_000 });
  const [sel, setSel] = useState('empresas');
  const [newItem, setNewItem] = useState('');
  const [confirmState, setConfirmState] = useState({ open: false, title: '', message: '', onConfirm: null });

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
  const removeItem = (item) => {
    setConfirmState({
      open: true,
      title: 'Eliminar elemento',
      message: `¿Eliminar "${item}" de la lista?`,
      onConfirm: () => { update.mutate(items.filter(i => i !== item)); setConfirmState(s => ({ ...s, open: false })); },
    });
  };

  const listas_nombres = Object.keys(listas);
  return (
    <div>
      <PageHeader title="📋 Listas y opciones" subtitle="Gestiona los valores disponibles en formularios" />
      {isErrorListas && <ErrorMsg message="Error al cargar listas" onRetry={refetchListas} />}
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
