/**
 * RequireAdmin — envuelve rutas que solo admins pueden ver.
 * Uso: <RequireAdmin><Empleados /></RequireAdmin>
 */
import React from 'react';
import { Navigate } from 'react-router-dom';
import useAuthStore from '../hooks/useAuth';

export default function RequireAdmin({ children }) {
  const { user } = useAuthStore();
  if (!user) return <Navigate to="/login" replace />;
  if (user.rol !== 'admin') {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
        <h2 style={{ color: '#0D3B6E', marginBottom: 8 }}>Acceso restringido</h2>
        <p style={{ color: '#64748b' }}>Esta sección es solo para administradores.</p>
      </div>
    );
  }
  return children;
}
