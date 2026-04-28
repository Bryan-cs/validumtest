import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
  withCredentials: true,
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

    const esLoginRequest = originalRequest.url?.includes('/auth/login') || originalRequest.url?.includes('/auth/refresh');

    if (err.response?.status === 401 && !esLoginRequest && !_redirigiendo && !originalRequest._retry) {
      // Intentar refresh — el refresh_token se envía automáticamente como cookie httpOnly
      originalRequest._retry = true;
      try {
        const resp = await axios.post(
          `${api.defaults.baseURL}/auth/refresh`,
          {},
          { withCredentials: true }
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

      _redirigiendo = true;
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

/**
 * Genera un UUID v4 para usar como upload_id.
 * Permite que el backend detecte reintentos y evite duplicados.
 */
export function genUploadId() {
  return crypto.randomUUID();
}

/**
 * Construye un FormData con upload_id incluido.
 * @param {File} file
 * @param {Object} extras - campos adicionales (afiliado_doc, contexto, contexto_id, etc.)
 * @param {string} uploadId - UUID generado antes de la petición
 */
export function buildUploadForm(file, extras = {}, uploadId = genUploadId()) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('upload_id', uploadId);
  for (const [k, v] of Object.entries(extras)) {
    if (v !== undefined && v !== null) fd.append(k, String(v));
  }
  return { fd, uploadId };
}

export default api;
