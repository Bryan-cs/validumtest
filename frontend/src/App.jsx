import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
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
const PlanillasSS         = lazy(() => import('./pages/PlanillasSS'));
const Finanzas            = lazy(() => import('./pages/Finanzas'));
const CredencialesPortales = lazy(() => import('./pages/CredencialesPortales'));
const Leads               = lazy(() => import('./pages/Leads'));

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
    mutations: {
      onError: (err) => {
        const raw = err?.response?.data?.detail;
        const msg = Array.isArray(raw)
          ? raw.map(e => e.msg).join('; ')
          : raw || err?.message || 'Error inesperado';
        import('sonner').then(m => m.toast.error(msg));
      },
    },
  },
});

function PrivateRoute({ children, adminOnly = false }) {
  const { token, user, _hasHydrated } = useAuthStore();
  if (!_hasHydrated) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', height:'100vh', color:'#888', fontSize:14 }}>
      Cargando...
    </div>
  );
  if (!token) return <Navigate to="/login" replace />;
  // Clientes solo pueden acceder al portal
  if (user?.rol === 'cliente') return <Navigate to="/portal" replace />;
  if (adminOnly && user?.rol !== 'admin') return <Navigate to="/" replace />;
  return children;
}

function ClienteOnlyRoute({ children }) {
  const { token, user, _hasHydrated } = useAuthStore();
  if (!_hasHydrated) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', height:'100vh', color:'#888', fontSize:14 }}>
      Cargando...
    </div>
  );
  if (!token) return <Navigate to="/login" replace />;
  if (user?.rol !== 'cliente' && user?.rol !== 'admin') return <Navigate to="/" replace />;
  return children;
}

function DefaultRedirect() {
  const { user } = useAuthStore();
  if (user?.rol === 'cliente') return <Navigate to="/portal" replace />;
  return <Dashboard />;
}

function Page({ children }) {
  return <ErrorBoundary>{children}</ErrorBoundary>;
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <OfflineBanner />
        <Toaster position="bottom-center" richColors closeButton />
        <ErrorBoundary>
        <Suspense fallback={<div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',color:'#888'}}>Cargando...</div>}>
        <Routes>
          <Route path="/login" element={<Login />} />

          {/* Portal de Cliente — layout propio */}
          <Route path="/portal" element={<ClienteOnlyRoute><Page><PortalCliente /></Page></ClienteOnlyRoute>} />

          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<Page><DefaultRedirect /></Page>} />
            <Route path="afiliados"   element={<Page><Afiliados /></Page>} />
            <Route path="retiros"     element={<Page><Retiros /></Page>} />
            <Route path="tareas"      element={<Page><Tareas /></Page>} />
            <Route path="facturacion" element={<Page><Facturacion /></Page>} />
            <Route path="cobro"       element={<Page><Cobro /></Page>} />
            <Route path="planillas-ss" element={<Page><PlanillasSS /></Page>} />

            {/* Admin only */}
            <Route path="finanzas"    element={<PrivateRoute adminOnly><Page><Finanzas /></Page></PrivateRoute>} />
            <Route path="empleados"   element={<PrivateRoute adminOnly><Page><Empleados /></Page></PrivateRoute>} />
            <Route path="usuarios"    element={<PrivateRoute adminOnly><Page><Usuarios /></Page></PrivateRoute>} />
            <Route path="listas"      element={<PrivateRoute adminOnly><Page><Listas /></Page></PrivateRoute>} />
            <Route path="calculadora" element={<PrivateRoute adminOnly><Page><Calculadora /></Page></PrivateRoute>} />
            <Route path="actividad"        element={<PrivateRoute adminOnly><Page><Actividad /></Page></PrivateRoute>} />
            <Route path="novedades-clientes" element={<PrivateRoute><Page><NovedadesClientes /></Page></PrivateRoute>} />
            <Route path="credenciales"       element={<PrivateRoute><Page><CredencialesPortales /></Page></PrivateRoute>} />
            <Route path="leads"              element={<PrivateRoute><Page><Leads /></Page></PrivateRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
