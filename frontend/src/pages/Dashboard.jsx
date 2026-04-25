import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { StatCard, SkeletonCard, C } from '../components/UI';

export default function Dashboard() {
  const { data: d, isLoading } = useQuery({
    queryKey: ['dashboard', '', ''],
    queryFn: () => api.get('/dashboard').then(r => r.data),
    refetchInterval: 120_000,
  });

  const { data: recientes = [] } = useQuery({
    queryKey: ['afiliados-recientes'],
    queryFn: () => api.get('/afiliados/recientes').then(r => r.data),
    refetchInterval: 30_000,
  });

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', marginBottom:24, paddingBottom:20, borderBottom:`1px solid ${C.border}`, position:'relative' }}>
        <div style={{ position:'absolute', bottom:-1, left:0, width:48, height:2, background:`linear-gradient(90deg, ${C.primary}, ${C.accent})`, borderRadius:2 }} />
        <div>
          <div style={{ fontSize:11, color:C.text2, marginBottom:4, fontFamily:"'IBM Plex Mono', monospace" }}>Panel / Dashboard</div>
          <h1 style={{ margin:0, fontFamily:"'Syne', sans-serif", fontSize:24, fontWeight:800, color:C.text, letterSpacing:'-.4px' }}>Resumen general</h1>
          <p style={{ margin:0, fontSize:13, color:C.text2, fontWeight:300 }}>Estado operativo del sistema</p>
        </div>
      </div>

      {/* Métricas afiliados */}
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap' }}>
        {isLoading
          ? [1,2,3,4,5,6].map(i => <div key={i} style={{ flex:1, minWidth:120 }}><SkeletonCard height={88} /></div>)
          : <>
            <StatCard label="Activos"            value={d?.activos          ?? '—'} color={C.green}   icon="👥" />
            <StatCard label="Suspendidos"        value={d?.suspendidos      ?? '—'} color={C.amber}   icon="⏸️" />
            <StatCard label="Doble afiliación"   value={d?.doble_afiliacion ?? '—'} color={C.blue}    icon="🔄" />
            <StatCard label="No se encuentra"    value={d?.no_encontrado    ?? '—'} color={C.red}     icon="🔍" />
            <StatCard label="En espera activac." value={d?.en_espera        ?? '—'} color={C.amber}   icon="⏳" />
            <StatCard label="Total afiliados"    value={d?.total_afiliados  ?? '—'} color={C.primary} icon="📊" />
          </>
        }
      </div>

      {/* Últimos afiliados */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 20px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: C.text2, letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: 14 }}>
          👥 Últimos afiliados
        </div>
        {recientes.length === 0 ? (
          <p style={{ color: C.text2, fontSize: 13, margin: 0 }}>Sin datos</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {recientes.map(a => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 34, height: 34, borderRadius: '50%',
                  background: C.surface2, border: `1px solid ${C.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: C.primary, flexShrink: 0,
                }}>
                  {a.nombre?.charAt(0)?.toUpperCase() ?? '?'}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {a.nombre}
                  </div>
                  <div style={{ fontSize: 11, color: C.text2 }}>
                    {a.doc}{a.empresa ? ` · ${a.empresa}` : ''}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: C.text2, flexShrink: 0 }}>
                  {a.creado ? new Date(a.creado).toLocaleDateString('es-CO', { day:'2-digit', month:'short' }) : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
