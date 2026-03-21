import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import useAuthStore from '../hooks/useAuth';
import api from '../utils/api';

const C_PRIMARY = '#0D3B6E';
const C_ACCENT  = '#E89B2A';

const navItems = (rol) => [
  { to: '/',            label: '🏠 Dashboard',           section: 'PRINCIPAL' },
  { to: '/afiliados',   label: '👥 Afiliados',            section: 'GESTIÓN' },
  { to: '/retiros',     label: '↪️ Retiros',               section: null },
  { to: '/tareas',      label: '✅ Tareas',                section: null },
  { to: '/facturacion', label: '🧾 Facturación',           section: 'FINANCIERO' },
  { to: '/cobro',       label: '💰 Módulo de cobro',       section: null },
  ...(rol === 'admin' ? [
    { to: '/empleados',   label: '👔 Empleados',           section: 'ADMINISTRACIÓN' },
    { to: '/usuarios',    label: '⚙️ Usuarios',             section: null },
    { to: '/listas',      label: '📋 Listas y opciones',   section: null },
    { to: '/calculadora', label: '🧮 Calculadora aportes', section: null },
  ] : []),
];

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [showNotifs, setShowNotifs] = useState(false);

  const { data: notifs = [] } = useQuery({
    queryKey: ['notificaciones'],
    queryFn: () => api.get('/tareas/notificaciones').then(r => r.data),
    refetchInterval: 30_000,
  });
  const noLeidas = notifs.filter(n => !n.leida).length;

  const abrirNotifs = () => {
    setShowNotifs(v => !v);
    if (noLeidas > 0) {
      api.put('/tareas/notificaciones/leer').then(() =>
        qc.invalidateQueries({ queryKey: ['notificaciones'] })
      );
    }
  };

  const handleLogout = () => { logout(); navigate('/login'); };
  const items = navItems(user?.rol);

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Sidebar */}
      <aside style={{
        width: collapsed ? 56 : 220, minWidth: collapsed ? 56 : 220,
        background: C_PRIMARY, display: 'flex', flexDirection: 'column',
        transition: 'width 0.2s', overflow: 'hidden',
      }}>
        {/* Logo */}
        <div style={{ padding: '18px 16px 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: '#fff', whiteSpace: 'nowrap' }}>
            BBC <span style={{ color: C_ACCENT }}>File</span>
          </span>
          <button onClick={() => setCollapsed(!collapsed)}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'rgba(255,255,255,.5)', cursor: 'pointer', fontSize: 16 }}>
            {collapsed ? '→' : '←'}
          </button>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, overflowY: 'auto', paddingBottom: 12 }}>
          {items.map((item) => (
            <React.Fragment key={item.to}>
              {item.section && !collapsed && (
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,.4)', padding: '14px 16px 4px', fontWeight: 600, letterSpacing: '0.1em' }}>
                  {item.section}
                </div>
              )}
              <NavLink to={item.to} end={item.to === '/'}
                style={({ isActive }) => ({
                  display: 'block', padding: '9px 14px', margin: '1px 7px',
                  borderRadius: 7, textDecoration: 'none', fontSize: 13,
                  color: isActive ? '#fff' : 'rgba(255,255,255,.72)',
                  background: isActive ? C_ACCENT : 'transparent',
                  fontWeight: isActive ? 600 : 400,
                  whiteSpace: 'nowrap', overflow: 'hidden',
                })}>
                {item.label}
              </NavLink>
            </React.Fragment>
          ))}
        </nav>

        {/* Notificaciones */}
        <div style={{ position: 'relative', padding: '6px 14px', borderTop: '1px solid rgba(255,255,255,.1)' }}>
          <button onClick={abrirNotifs} style={{
            background: 'none', border: 'none', color: 'rgba(255,255,255,.8)',
            cursor: 'pointer', fontSize: 20, position: 'relative', padding: '4px 6px',
          }}>
            🔔
            {noLeidas > 0 && (
              <span style={{
                position: 'absolute', top: 0, right: 0,
                background: '#E53E3E', color: 'white', borderRadius: '50%',
                width: 17, height: 17, fontSize: 10, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {noLeidas > 9 ? '9+' : noLeidas}
              </span>
            )}
          </button>
          {!collapsed && <span style={{ color: 'rgba(255,255,255,.5)', fontSize: 12, verticalAlign: 'middle' }}>Notificaciones</span>}

          {showNotifs && (
            <div style={{
              position: 'absolute', bottom: 44, left: 8,
              width: 300, background: 'white', borderRadius: 10,
              boxShadow: '0 8px 30px rgba(0,0,0,.25)', zIndex: 300,
              maxHeight: 360, overflowY: 'auto',
            }}>
              <div style={{ padding: '10px 14px', fontWeight: 600, fontSize: 13, borderBottom: '1px solid #eee', color: '#1E293B' }}>
                Notificaciones
                <button onClick={() => setShowNotifs(false)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', color: '#888', fontSize: 16 }}>×</button>
              </div>
              {notifs.length === 0
                ? <p style={{ padding: 14, color: '#888', fontSize: 13, margin: 0 }}>Sin notificaciones</p>
                : notifs.map(n => (
                  <div key={n.id} style={{
                    padding: '10px 14px', borderBottom: '1px solid #f0f0f0',
                    fontSize: 12, background: n.leida ? 'white' : '#EBF8FF',
                  }}>
                    <div style={{ color: '#1E293B' }}>{n.mensaje}</div>
                    <div style={{ color: '#888', fontSize: 11, marginTop: 2 }}>
                      {new Date(n.creado).toLocaleString('es-CO')}
                    </div>
                  </div>
                ))
              }
            </div>
          )}
        </div>

        {/* User */}
        <div style={{ padding: '12px 14px', borderTop: '1px solid rgba(255,255,255,.1)' }}>
          {!collapsed && (
            <div style={{ color: 'rgba(255,255,255,.8)', fontSize: 12, marginBottom: 6 }}>
              <span style={{ fontWeight: 600 }}>{user?.nombre}</span>
              <span style={{ marginLeft: 6, background: 'rgba(255,255,255,.15)', borderRadius: 10, padding: '1px 8px', fontSize: 10 }}>
                {user?.rol?.toUpperCase()}
              </span>
            </div>
          )}
          <button onClick={handleLogout} style={{
            width: '100%', padding: '7px 10px', background: 'rgba(255,255,255,.1)',
            border: '1px solid rgba(255,255,255,.2)', borderRadius: 6,
            color: '#fff', fontSize: 12, cursor: 'pointer',
          }}>
            {collapsed ? '↩' : 'Cerrar sesión'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflowY: 'auto', background: '#F0F4F8', padding: 24 }}>
        <Outlet />
      </main>
    </div>
  );
}
