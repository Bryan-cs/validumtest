import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 30000,
});

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let _redirigiendo = false;

// Resetear flag cuando se navega a /login exitosamente
export function resetRedirectFlag() { _redirigiendo = false; }

api.interceptors.response.use(
  res => res,
  async err => {
    const originalRequest = err.config;

    if (err.response?.status === 401 && !_redirigiendo && !originalRequest._retry) {
      // Intentar refresh token antes de redirigir
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken && !originalRequest.url?.includes('/auth/login')) {
        originalRequest._retry = true;
        try {
          const resp = await axios.post(
            `${api.defaults.baseURL}/auth/refresh`,
            { refresh_token: refreshToken }
          );
          const newToken = resp.data.access_token;
          localStorage.setItem('token', newToken);
          // Actualizar Zustand store si está disponible
          try {
            const mod = await import('../hooks/useAuth');
            mod.default.getState().setToken(newToken);
          } catch { /* ignorar si no se puede importar */ }
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        } catch {
          // Refresh falló — redirigir a login
        }
      }

      _redirigiendo = true;
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;
