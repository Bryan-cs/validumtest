import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import useAuthStore from './hooks/useAuth';

import { ErrorBoundary, OfflineBanner } from './components/UI';
import Login          from './pages/Login';
import Layout         from './components/Layout';

// Lazy loading — cada página se descarga solo cuando se necesita
const Dashboard      = lazy(() => import('./pages/Dashboard'));
const Afiliados      = lazy(() => import('./pages/Afiliados'));
const Retiros        = lazy(() => import('./pages/Retiros'));
const Facturacion    = lazy(() => import('./pages/Facturacion'));
const Cobro          = lazy(() => import('./pages/Cobro'));
const Empleados      = lazy(() => import('./pages/Empleados'));
const Usuarios       = lazy(() => import('./pages/Usuarios'));
const Listas         = lazy(() => import('./pages/Listas'));
const Calculadora    = lazy(() => import('./pages/Calculadora'));
const Tareas         = lazy(() => import('./pages/Tareas'));
const Actividad      = lazy(() => import('./pages/Actividad'));
const PortalCliente       = lazy(() => import('./pages/PortalCliente'));
const NovedadesClientes   = lazy(() => import('./pages/NovedadesClientes'));
const Backups             = lazy(() => import('./pages/Backups'));
const PlanillasSS         = lazy(() => import('./pages/PlanillasSS'));

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 60_000, refetchOnWindowFocus: 'always' },
    mutations: {
      onError: (err) => {
        const msg = err?.response?.data?.detail || err?.message || 'Error inesperado';
        import('react-hot-toast').then(m => m.default.error(msg));
      },
    },
  },
});

function PrivateRoute({ children, adminOnly = false }) {
  const { token, user } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  // Clientes solo pueden acceder al portal
  if (user?.rol === 'cliente') return <Navigate to="/portal" replace />;
  if (adminOnly && user?.rol !== 'admin') return <Navigate to="/" replace />;
  return children;
}

function ClienteOnlyRoute({ children }) {
  const { token, user } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  if (user?.rol !== 'cliente' && user?.rol !== 'admin') return <Navigate to="/" replace />;
  return children;
}

function DefaultRedirect() {
  const { user } = useAuthStore();
  if (user?.rol === 'cliente') return <Navigate to="/portal" replace />;
  return <Dashboard />;
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <OfflineBanner />
        <Toaster position="bottom-center" toastOptions={{ duration: 3000 }} />
        <ErrorBoundary>
        <Suspense fallback={<div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',color:'#888'}}>Cargando...</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />

          {/* Portal de Cliente — layout propio */}
          <Route path="/portal" element={<ClienteOnlyRoute><PortalCliente /></ClienteOnlyRoute>} />

          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<DefaultRedirect />} />
            <Route path="afiliados"   element={<Afiliados />} />
            <Route path="retiros"     element={<Retiros />} />
            <Route path="tareas"      element={<Tareas />} />
            <Route path="facturacion" element={<Facturacion />} />
            <Route path="cobro"       element={<Cobro />} />
            <Route path="planillas-ss" element={<PlanillasSS />} />

            {/* Admin only */}
            <Route path="empleados"   element={<PrivateRoute adminOnly><Empleados /></PrivateRoute>} />
            <Route path="usuarios"    element={<PrivateRoute adminOnly><Usuarios /></PrivateRoute>} />
            <Route path="listas"      element={<PrivateRoute adminOnly><Listas /></PrivateRoute>} />
            <Route path="calculadora" element={<PrivateRoute adminOnly><Calculadora /></PrivateRoute>} />
            <Route path="actividad"        element={<PrivateRoute adminOnly><Actividad /></PrivateRoute>} />
            <Route path="novedades-clientes" element={<PrivateRoute adminOnly><NovedadesClientes /></PrivateRoute>} />
            <Route path="backups"            element={<PrivateRoute adminOnly><Backups /></PrivateRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
