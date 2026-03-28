import React, { useState, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';
import { StatCard, C, fmt, Btn, ConfirmModal } from '../components/UI';

const MESES = ['Todos','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear().toString();

export default function Dashboard() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const [anio, setAnio] = useState(anioActual);
  const [mes,  setMes]  = useState('Todos');
  const [descargando, setDescargando] = useState(false);
  const [importando, setImportando] = useState(false);
  const [confirmImport, setConfirmImport] = useState(null);
  const fileRef = useRef(null);

  const params = {};
  if (anio !== 'Todos') params.anio = anio;
  if (mes  !== 'Todos') params.mes  = mes;

  const { data: d, isLoading } = useQuery({
    queryKey: ['dashboard', anio, mes],
    queryFn: () => api.get('/dashboard', { params }).then(r => r.data),
    refetchInterval: 30_000,
  });

  const sel = { padding:'7px 12px', border:`1px solid ${C.border}`, borderRadius:7,
    fontSize:13, outline:'none', background:C.surface, color:C.text };

  const descargarExcel = async () => {
    setDescargando(true);
    try {
      const res = await api.get('/exportar-excel-completo', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      const disp = res.headers['content-disposition'] || '';
      const match = disp.match(/filename="?([^"]+)"?/);
      a.download = match ? match[1] : 'bbcfile_backup.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Excel descargado');
    } catch {
      toast.error('Error al descargar Excel');
    }
    setDescargando(false);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      toast.error('Solo archivos .xlsx');
      return;
    }
    setConfirmImport(file);
    e.target.value = '';
  };

  const ejecutarImport = async () => {
    if (!confirmImport) return;
    setImportando(true);
    setConfirmImport(null);
    try {
      const fd = new FormData();
      fd.append('file', confirmImport);
      const res = await api.post('/importar-excel-completo', fd);
      const data = res.data;
      const tablas = data.restaurado?.length || 0;
      const errores = data.errores?.length || 0;
      toast.success(`Importado: ${tablas} tablas${errores ? `, ${errores} errores` : ''}`);
      if (errores) data.errores.forEach(e => toast.error(e, { duration: 6000 }));
      qc.invalidateQueries();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al importar Excel');
    }
    setImportando(false);
  };

  const isAdmin = user?.rol === 'admin';

  return (
    <div>
      {/* Header + filtros */}
      <div style={{ display:'flex', alignItems:'center', marginBottom:20, gap:10, flexWrap:'wrap' }}>
        <div>
          <h1 style={{ margin:0, fontSize:22, fontWeight:700, color:C.primary }}>Dashboard</h1>
          <p style={{ margin:0, fontSize:13, color:C.text2 }}>Resumen general del sistema</p>
        </div>
        <div style={{ marginLeft:'auto', display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
          <span style={{ fontSize:12, color:C.text2 }}>Período:</span>
          <select style={sel} value={anio} onChange={e=>setAnio(e.target.value)}>
            {['Todos', anioActual, String(+anioActual-1)].map(a=><option key={a}>{a}</option>)}
          </select>
          <select style={sel} value={mes} onChange={e=>setMes(e.target.value)}>
            {MESES.map(m=><option key={m}>{m}</option>)}
          </select>
          <button onClick={()=>{setAnio('Todos');setMes('Todos');}}
            style={{ ...sel, cursor:'pointer', background:C.surface2 }}>↺ Todo</button>
        </div>
      </div>

      {/* Métricas afiliados */}
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
        <StatCard label="Activos"         value={d?.activos       ?? '—'} color={C.green} />
        <StatCard label="Retirados"       value={d?.retirados     ?? '—'} color={C.red} />
        <StatCard label="Suspendidos"     value={d?.suspendidos   ?? '—'} color={C.amber} />
        <StatCard label="Total afiliados" value={d?.total_afiliados?? '—'} color={C.primary} />
      </div>

      {/* Métricas financieras */}
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        <StatCard label="Facturas emitidas"  value={d?.facturas       ?? '—'} color={C.blue} />
        <StatCard label="Ingresos"           value={fmt(d?.ingresos)}         color={C.primary} />
        <StatCard label="Pendiente cobro"    value={fmt(d?.pendiente_cobro)}  color={C.amber} />
        <StatCard label={`Nóminas (×${d?.meses_factor??1} mes)`} value={fmt(d?.nominas)}      color={C.red} />
        <StatCard label={`Gastos fijos (×${d?.meses_factor??1} mes)`} value={fmt(d?.gastos_fijos)} color={C.red} />
        <StatCard label="Utilidad neta"      value={fmt(d?.utilidad_neta)}
          color={(d?.utilidad_neta ?? 0) >= 0 ? C.green : C.red} />
      </div>

      {/* Backup Excel — solo admin */}
      {isAdmin && (
        <div style={{
          background: C.surface, borderRadius: 12, border: `1px solid ${C.border}`,
          padding: 20, marginBottom: 20,
        }}>
          <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:12 }}>
            <span style={{ fontSize:16 }}>📦</span>
            <div>
              <div style={{ fontWeight:700, fontSize:14, color:C.text }}>Backup Excel del sistema</div>
              <div style={{ fontSize:12, color:C.text2 }}>Descarga todas las tablas en un Excel o restaura desde uno modificado</div>
            </div>
          </div>
          <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
            <Btn onClick={descargarExcel} disabled={descargando}>
              {descargando ? 'Descargando...' : '📥 Descargar Excel completo'}
            </Btn>
            <Btn variant="accent" onClick={() => fileRef.current?.click()} disabled={importando}>
              {importando ? 'Importando...' : '📤 Importar Excel como backup'}
            </Btn>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" style={{ display:'none' }}
              onChange={handleFileSelect} />
          </div>
        </div>
      )}

      <ConfirmModal
        open={!!confirmImport}
        title="Importar Excel como backup"
        message={`Se reemplazará TODA la base de datos con el contenido de "${confirmImport?.name}". Se creará un backup de seguridad automático antes de importar. Esta acción no se puede deshacer fácilmente.`}
        confirmLabel="Importar y reemplazar"
        variant="danger"
        onConfirm={ejecutarImport}
        onCancel={() => setConfirmImport(null)}
      />
    </div>
  );
}
