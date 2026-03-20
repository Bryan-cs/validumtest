import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import useAuthStore from '../hooks/useAuth';

const C_PRIMARY = '#0D3B6E';
const C_ACCENT  = '#E89B2A';

const navItems = (rol) => [
  { to: '/',            label: '🏠 Dashboard',           section: 'PRINCIPAL' },
  { to: '/afiliados',   label: '👥 Afiliados',            section: 'GESTIÓN' },
  { to: '/retiros',     label: '↪️ Retiros',               section: null },
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
  const [collapsed, setCollapsed] = useState(false);

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
          {items.map((item, idx) => (
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
