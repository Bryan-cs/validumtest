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

// Flag to prevent infinite refresh loops
let _isRefreshing = false;
let _failedQueue = [];

function processQueue(error, token = null) {
  _failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  _failedQueue = [];
}

api.interceptors.response.use(
  res => res,
  async err => {
    const originalRequest = err.config;

    if (err.response?.status === 401 && !originalRequest._retry) {
      const msg = err.response?.data?.detail || '';

      // If this is already a refresh attempt, bail out
      if (originalRequest.url && originalRequest.url.includes('/auth/refresh')) {
        // Refresh failed — logout
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(err);
      }

      const refreshToken = localStorage.getItem('refresh_token');

      if (refreshToken && (msg.includes('expirad') || msg.includes('inválid'))) {
        if (_isRefreshing) {
          // Queue this request until refresh completes
          return new Promise((resolve, reject) => {
            _failedQueue.push({ resolve, reject });
          }).then(token => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          }).catch(e => Promise.reject(e));
        }

        originalRequest._retry = true;
        _isRefreshing = true;

        try {
          const res = await axios.post(
            `${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/auth/refresh`,
            { refresh_token: refreshToken }
          );
          const newToken = res.data.access_token;
          localStorage.setItem('token', newToken);

          // Update Zustand store without import cycle
          try {
            const { default: useAuthStore } = await import('../hooks/useAuth');
            useAuthStore.getState().setToken(newToken);
          } catch (_) {}

          processQueue(null, newToken);
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        } catch (refreshErr) {
          processQueue(refreshErr, null);
          localStorage.removeItem('token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
          window.location.href = '/login';
          return Promise.reject(refreshErr);
        } finally {
          _isRefreshing = false;
        }
      }

      // Non-recoverable 401 — redirect to login
      if (msg.includes('expirad') || msg.includes('inválid')) {
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
    }

    return Promise.reject(err);
  }
);

export default api;
