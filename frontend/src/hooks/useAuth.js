import { create } from 'zustand';
import { resetRedirectFlag } from '../utils/api';

function _loadUser() {
  try {
    const raw = localStorage.getItem('user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    localStorage.removeItem('user');
    return null;
  }
}

function _tokenValido(token) {
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

const _tokenGuardado = localStorage.getItem('token');
const _refreshGuardado = localStorage.getItem('refresh_token');
if (!_tokenValido(_tokenGuardado) && !_tokenValido(_refreshGuardado)) {
  // Solo limpiar todo si AMBOS tokens expiraron
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
} else if (!_tokenValido(_tokenGuardado)) {
  // Access token expirado pero refresh válido — limpiar solo el access token
  // El interceptor de api.js se encargará de renovarlo
  localStorage.removeItem('token');
}

const useAuthStore = create((set) => ({
  token:         localStorage.getItem('token') || null,
  refresh_token: localStorage.getItem('refresh_token') || null,
  user:          _loadUser(),

  login: (token, user, refresh_token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    if (refresh_token) {
      localStorage.setItem('refresh_token', refresh_token);
    }
    resetRedirectFlag();
    set({ token, user, refresh_token: refresh_token || null });
  },

  setToken: (token) => {
    localStorage.setItem('token', token);
    set({ token });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    set({ token: null, refresh_token: null, user: null });
  },
}));

export default useAuthStore;
