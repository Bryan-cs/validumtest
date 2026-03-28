/**
 * App.jsx con lazy loading — cada módulo carga solo cuando se navega a él.
 * Reduce el tiempo de carga inicial significativamente.
 * 
 * INSTRUCCIONES: Reemplaza tu App.jsx actual con este archivo.
 * Ajusta las rutas si las tuyas son diferentes.
 */
import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import useAuthStore from './hooks/useAuth';
import { C } from '../components/UI';

// ─── LAZY IMPORTS — cada página carga solo cuando se necesita ─────────────────
const Login       = lazy(() => import('./pages/Login'));
const Dashboard   = lazy(() => import('./pages/Dashboard'));
const Afiliados   = lazy(() => import('./pages/Afiliados'));
const Facturacion = lazy(() => import('./pages/Facturacion'));
const Cobro       = lazy(() => import('./pages/Cobro'));
const Retiros     = lazy(() => import('./pages/Retiros'));
const Empleados   = lazy(() => import('./pages/Empleados'));
const Listas      = lazy(() => import('./pages/Listas'));
const Usuarios    = lazy(() => import('./pages/Usuarios'));
const Calculadora = lazy(() => import('./pages/Calculadora'));
const Backups     = lazy(() => import('./pages/Backups'));

// ─── QUERY CLIENT — configurado para rendimiento óptimo ──────────────────────
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:        1000 * 60 * 2,   // datos frescos por 2 minutos
      cacheTime:        1000 * 60 * 10,  // caché por 10 minutos
      refetchOnWindowFocus: false,        // no recargar al volver a la ventana
      retry: 1,                           // solo 1 reintento en caso de error
    },
  },
});

// ─── LOADING FALLBACK ─────────────────────────────────────────────────────────
function PageLoader() {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center',
      height:'60vh', flexDirection:'column', gap:12 }}>
      <div style={{ width:36, height:36, border:'3px solid #E2E8F0',
        borderTop:'3px solid #0D3B6E', borderRadius:'50%',
        animation:'spin 0.8s linear infinite' }} />
      <span style={{ fontSize:13, color:'#94A3B8' }}>Cargando...</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ─── RUTA PROTEGIDA ───────────────────────────────────────────────────────────
function PrivateRoute({ children }) {
  const { token } = useAuthStore();
  return token ? children : <Navigate to="/login" replace />;
}

// ─── RUTA SOLO ADMIN ──────────────────────────────────────────────────────────
function AdminRoute({ children }) {
  const { token, user } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  if (user?.rol !== 'admin') return (
    <div style={{ padding:40, textAlign:'center' }}>
      <div style={{ fontSize:48, marginBottom:16 }}>🔒</div>
      <h2 style={{ color:'#0D3B6E' }}>Acceso restringido</h2>
      <p style={{ color:'#64748b' }}>Esta sección es solo para administradores.</p>
    </div>
  );
  return children;
}

// ─── LAYOUT PRINCIPAL ─────────────────────────────────────────────────────────
function Layout({ children }) {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const isAdmin  = user?.rol === 'admin';

  const navItems = [
    { to:'/',            icon:'📊', label:'Dashboard' },
    { to:'/afiliados',   icon:'👥', label:'Afiliados' },
    { to:'/facturacion', icon:'🧾', label:'Facturación' },
    { to:'/cobro',       icon:'💰', label:'Cobro' },
    { to:'/retiros',     icon:'📤', label:'Retiros' },
    { to:'/calculadora', icon:'🧮', label:'Calculadora' },
    ...(isAdmin ? [
      { to:'/empleados', icon:'👔', label:'Empleados' },
      { to:'/listas',    icon:'📋', label:'Listas' },
      { to:'/usuarios',  icon:'👤', label:'Usuarios' },
      { to:'/backups',   icon:'💾', label:'Backups' },
    ] : []),
  ];

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <div style={{ display:'flex', minHeight:'100vh', background:C.bg }}>
      {/* Sidebar */}
      <nav style={{ width:220, background:'#0D3B6E', display:'flex',
        flexDirection:'column', padding:'20px 0', flexShrink:0 }}>
        <div style={{ padding:'0 20px 20px', borderBottom:'1px solid rgba(255,255,255,.1)' }}>
          <div style={{ fontSize:20, fontWeight:700, color:'#fff' }}>
            BBC <span style={{ color:'#E89B2A' }}>File</span>
          </div>
          <div style={{ fontSize:11, color:'rgba(255,255,255,.5)', marginTop:2 }}>
            {user?.nombre}
            {isAdmin && <span style={{ marginLeft:6, background:'#E89B2A',
              color:'#fff', borderRadius:4, padding:'1px 6px', fontSize:10 }}>ADMIN</span>}
          </div>
        </div>
        <div style={{ flex:1, padding:'12px 0', overflowY:'auto' }}>
          {navItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.to==='/'} style={({ isActive }) => ({
              display:'flex', alignItems:'center', gap:10, padding:'10px 20px',
              textDecoration:'none', fontSize:13, fontWeight:500,
              color: isActive ? '#fff' : 'rgba(255,255,255,.65)',
              background: isActive ? 'rgba(255,255,255,.12)' : 'transparent',
              borderLeft: isActive ? '3px solid #E89B2A' : '3px solid transparent',
              transition:'all .15s',
            })}>
              <span>{item.icon}</span> {item.label}
            </NavLink>
          ))}
        </div>
        <div style={{ padding:'12px 16px', borderTop:'1px solid rgba(255,255,255,.1)' }}>
          <button onClick={handleLogout} style={{
            width:'100%', padding:'8px 12px', background:'rgba(255,255,255,.1)',
            border:'1px solid rgba(255,255,255,.2)', borderRadius:7,
            color:'rgba(255,255,255,.8)', fontSize:12, cursor:'pointer',
          }}>
            🚪 Cerrar sesión
          </button>
        </div>
      </nav>

      {/* Contenido principal */}
      <main style={{ flex:1, padding:24, overflowY:'auto', maxWidth:'100%' }}>
        <Suspense fallback={<PageLoader />}>
          {children}
        </Suspense>
      </main>
    </div>
  );
}

// ─── APP PRINCIPAL ────────────────────────────────────────────────────────────
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Toaster position="top-right"
          toastOptions={{ duration:3500, style:{ fontSize:13 } }} />
        <Routes>
          <Route path="/login" element={
            <Suspense fallback={<PageLoader />}><Login /></Suspense>
          } />
          <Route path="/*" element={
            <PrivateRoute>
              <Layout>
                <Routes>
                  <Route index             element={<Dashboard />} />
                  <Route path="afiliados"  element={<Afiliados />} />
                  <Route path="facturacion" element={<Facturacion />} />
                  <Route path="cobro"      element={<Cobro />} />
                  <Route path="retiros"    element={<Retiros />} />
                  <Route path="calculadora" element={<Calculadora />} />
                  <Route path="empleados"  element={<AdminRoute><Empleados /></AdminRoute>} />
                  <Route path="listas"     element={<AdminRoute><Listas /></AdminRoute>} />
                  <Route path="usuarios"   element={<AdminRoute><Usuarios /></AdminRoute>} />
                  <Route path="backups"    element={<AdminRoute><Backups /></AdminRoute>} />
                  <Route path="*"          element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </PrivateRoute>
          } />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
