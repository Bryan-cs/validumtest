import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';
import { empresaStyle } from '../utils/colors';
import { StatCard, SkeletonCard, ErrorMsg, C } from '../components/UI';

function ClickableCard({ onClick, children }) {
  return (
    <div
      onClick={onClick}
      style={{ flex: 1, minWidth: 130, cursor: 'pointer', borderRadius: 12, transition: 'opacity .15s' }}
      onMouseEnter={e => e.currentTarget.style.opacity = '.8'}
      onMouseLeave={e => e.currentTarget.style.opacity = '1'}
    >
      {children}
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: d, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/dashboard').then(r => r.data),
    refetchInterval: 300_000,
  });

  const { data: recientes = [], isError: isErrorRecientes, refetch: refetchRecientes } = useQuery({
    queryKey: ['afiliados-recientes'],
    queryFn: () => api.get('/afiliados/recientes').then(r => r.data),
    refetchInterval: 30_000,
  });

  const irAAfiliados = (estado) => navigate('/afiliados', { state: { estadoFiltro: estado } });

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
          : isError
          ? <ErrorMsg message="Error al cargar métricas" onRetry={refetch} />
          : <>
            <div style={{ flex:1, minWidth:130 }}>
              <StatCard label="Activos"            value={d?.activos          ?? '—'} color={C.green}   icon="👥" />
            </div>
            <ClickableCard onClick={() => irAAfiliados('SUSPENDIDO')}>
              <StatCard label="Suspendidos"        value={d?.suspendidos      ?? '—'} color={C.amber}   icon="⏸️" />
            </ClickableCard>
            <ClickableCard onClick={() => irAAfiliados('DOBLE AFILIACION')}>
              <StatCard label="Doble afiliación"   value={d?.doble_afiliacion ?? '—'} color={C.blue}    icon="🔄" />
            </ClickableCard>
            <ClickableCard onClick={() => irAAfiliados('NO SE ENCUENTRA AFILIADO')}>
              <StatCard label="No se encuentra"    value={d?.no_encontrado    ?? '—'} color={C.red}     icon="🔍" />
            </ClickableCard>
            <ClickableCard onClick={() => irAAfiliados('EN ESPERA DE ACTIVACION')}>
              <StatCard label="En espera activac." value={d?.en_espera        ?? '—'} color={C.amber}   icon="⏳" />
            </ClickableCard>
            <div style={{ flex:1, minWidth:130 }}>
              <StatCard label="Total afiliados"    value={d?.total_afiliados  ?? '—'} color={C.primary} icon="📊" />
            </div>
          </>
        }
      </div>

      {/* Últimos afiliados */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 20px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: C.text2, letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: 14 }}>
          👥 Últimos afiliados
        </div>
        {isErrorRecientes ? (
          <ErrorMsg message="Error al cargar afiliados recientes" onRetry={refetchRecientes} />
        ) : recientes.length === 0 ? (
          <p style={{ color: C.text2, fontSize: 13, margin: 0 }}>Sin datos</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {recientes.map((a, idx) => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '10px 0', borderBottom: idx < recientes.length - 1 ? `1px solid ${C.border}` : 'none' }}>
                <div style={{
                  width: 34, height: 34, borderRadius: '50%',
                  background: C.surface2, border: `1px solid ${C.border}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: C.primary, flexShrink: 0, marginTop: 2,
                }}>
                  {a.nombre?.charAt(0)?.toUpperCase() ?? '?'}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {a.nombre}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: C.text }}>{a.doc}</span>
                    {a.empresa && (() => { const s = empresaStyle(a.empresa); return (
                      <span style={{ fontSize: 10, fontWeight: 700, borderRadius: 5, padding: '1px 7px', background: s.background, color: s.color }}>{a.empresa}</span>
                    ); })()}
                    {a.fecha_afiliacion && <span style={{ fontSize: 11, color: C.blue }}>📅 {a.fecha_afiliacion}</span>}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {a.eps && (
                      <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: C.greenBg, color: C.green, fontWeight: 600 }}>
                        EPS: {a.eps}
                      </span>
                    )}
                    {a.ccf && (
                      <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: C.amberBg, color: C.amber, fontWeight: 600 }}>
                        CCF: {a.ccf}
                      </span>
                    )}
                    {a.servicios?.map(s => (
                      <span key={s} style={{
                        fontSize: 10, padding: '2px 6px', borderRadius: 4,
                        background: C.blueBg, color: C.blue,
                        fontWeight: 600, letterSpacing: '.02em',
                      }}>{s}</span>
                    ))}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: C.text2, flexShrink: 0, marginTop: 2 }}>
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
