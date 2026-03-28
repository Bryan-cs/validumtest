import React, { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import { C, Btn, PageHeader } from '../components/UI';

export default function Backups() {
  const qc = useQueryClient();
  const [creando, setCreando] = useState(false);
  const [restaurando, setRestaurando] = useState(false);
  const fileRef = useRef(null);

  const { data, isLoading } = useQuery({
    queryKey: ['backups'],
    queryFn: () => api.get('/backups').then(r => r.data),
    refetchInterval: 60000,
  });

  const backups = data?.backups || [];

  const crearBackup = useMutation({
    mutationFn: () => api.post('/backups/crear'),
    onMutate: () => setCreando(true),
    onSuccess: () => {
      toast.success('Backup creado exitosamente');
      qc.invalidateQueries({ queryKey: ['backups'] });
      setCreando(false);
    },
    onError: (e) => {
      toast.error(e.response?.data?.detail || 'Error creando backup');
      setCreando(false);
    },
  });

  const descargar = async (nombre) => {
    try {
      const res = await api.get(`/backups/${nombre}/descargar`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = nombre;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('Error descargando backup');
    }
  };

  const restaurar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith('.json')) {
      toast.error('Solo se aceptan archivos .json');
      return;
    }
    const confirmar = window.confirm(
      'ADVERTENCIA: Esto reemplazará TODOS los datos actuales con los del backup.\n\n' +
      'Se creará un backup de seguridad antes de restaurar.\n\n' +
      '¿Estás seguro de continuar?'
    );
    if (!confirmar) {
      e.target.value = '';
      return;
    }
    setRestaurando(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/backups/restaurar', fd);
      const data = res.data;
      const tablas = data.restaurado?.length || 0;
      const errores = data.errores?.length || 0;
      toast.success(`Backup restaurado: ${tablas} tablas${errores ? `, ${errores} errores` : ''}`);
      qc.invalidateQueries({ queryKey: ['backups'] });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error restaurando backup');
    } finally {
      setRestaurando(false);
      e.target.value = '';
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <PageHeader title="Backups" subtitle="Respaldos automáticos de la base de datos en Cloudflare R2"
        action={
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="accent" onClick={() => crearBackup.mutate()} disabled={creando}>
              {creando ? 'Creando...' : '+ Crear backup'}
            </Btn>
            <Btn variant="secondary" onClick={() => fileRef.current?.click()} disabled={restaurando}>
              {restaurando ? 'Restaurando...' : 'Restaurar backup'}
            </Btn>
            <input ref={fileRef} type="file" accept=".json" onChange={restaurar} style={{ display: 'none' }} />
          </div>
        }
      />

      <div style={{
        background: C.surface2, borderRadius: 10, padding: 16, marginBottom: 20,
        border: `1px solid ${C.border}`, fontSize: 13, color: C.text2, lineHeight: 1.6,
      }}>
        <strong style={{ color: C.text }}>Horario automático (hora Colombia):</strong><br/>
        2:00 AM — Cierre del día &nbsp;&bull;&nbsp;
        12:00 PM — Mediodía &nbsp;&bull;&nbsp;
        9:00 PM — Cierre jornada<br/>
        <span style={{ fontSize: 12 }}>Los backups se eliminan automáticamente después de 30 días.</span>
      </div>

      {isLoading ? (
        <p style={{ color: C.text2, textAlign: 'center', padding: 40 }}>Cargando backups...</p>
      ) : backups.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: 60, color: C.text2,
          background: C.surface, borderRadius: 10, border: `1px solid ${C.border}`,
        }}>
          <p style={{ fontSize: 15, marginBottom: 8 }}>No hay backups todavía</p>
          <p style={{ fontSize: 13 }}>Los backups automáticos comenzarán en el próximo horario programado, o puedes crear uno manual ahora.</p>
        </div>
      ) : (
        <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
            <thead>
              <tr style={{ background: C.surface2 }}>
                <th style={th}>Archivo</th>
                <th style={th}>Fecha</th>
                <th style={th}>Tamaño</th>
                <th style={{ ...th, textAlign: 'center' }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {backups.map((b, i) => {
                const fecha = new Date(b.fecha);
                const fechaStr = fecha.toLocaleDateString('es-CO', {
                  year: 'numeric', month: 'short', day: 'numeric',
                  hour: '2-digit', minute: '2-digit',
                });
                return (
                  <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={td}>
                      <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{b.archivo}</span>
                    </td>
                    <td style={td}>{fechaStr}</td>
                    <td style={td}>{b.tamano_mb} MB</td>
                    <td style={{ ...td, textAlign: 'center' }}>
                      <Btn size="sm" variant="primary" onClick={() => descargar(b.archivo)}>
                        Descargar
                      </Btn>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ fontSize: 12, color: C.text2, marginTop: 16, textAlign: 'center' }}>
        Total: {backups.length} backup{backups.length !== 1 ? 's' : ''} almacenado{backups.length !== 1 ? 's' : ''}
      </p>
    </div>
  );
}

const th = { padding: '10px 12px', fontSize: 12, fontWeight: 600, color: C.text2, textAlign: 'left' };
const td = { padding: '10px 12px', fontSize: 13, color: C.text, verticalAlign: 'middle' };
