import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import useAuthStore from './hooks/useAuth';

import Login       from './pages/Login';
import Layout      from './components/Layout';
import Dashboard   from './pages/Dashboard';
import Afiliados   from './pages/Afiliados';
import Retiros     from './pages/Retiros';
import Facturacion from './pages/Facturacion';
import Cobro       from './pages/Cobro';
import Empleados   from './pages/Empleados';
import Usuarios    from './pages/Usuarios';
import Listas      from './pages/Listas';
import Calculadora from './pages/Calculadora';
import Tareas      from './pages/Tareas';
import Actividad   from './pages/Actividad';

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

function PrivateRoute({ children, adminOnly = false }) {
  const { token, user } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  if (adminOnly && user?.rol !== 'admin') return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Toaster position="bottom-center" toastOptions={{ duration: 3000 }} />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="afiliados"   element={<Afiliados />} />
            <Route path="retiros"     element={<Retiros />} />
            <Route path="tareas"      element={<Tareas />} />
            <Route path="facturacion" element={<Facturacion />} />
            <Route path="cobro"       element={<Cobro />} />
            {/* Admin only */}
            <Route path="empleados"   element={<PrivateRoute adminOnly><Empleados /></PrivateRoute>} />
            <Route path="usuarios"    element={<PrivateRoute adminOnly><Usuarios /></PrivateRoute>} />
            <Route path="listas"      element={<PrivateRoute adminOnly><Listas /></PrivateRoute>} />
            <Route path="calculadora" element={<PrivateRoute adminOnly><Calculadora /></PrivateRoute>} />
            <Route path="actividad"   element={<PrivateRoute adminOnly><Actividad /></PrivateRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
