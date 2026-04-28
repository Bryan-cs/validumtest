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
if (!_tokenValido(_tokenGuardado)) {
  // Access token expirado o ausente — limpiar; el interceptor intentará refresh via cookie
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

const useAuthStore = create((set) => ({
  token: localStorage.getItem('token') || null,
  user:  _loadUser(),

  login: (token, user) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    resetRedirectFlag();
    set({ token, user });
  },

  setToken: (token) => {
    localStorage.setItem('token', token);
    set({ token });
  },

  logout: async () => {
    // Llama al servidor para invalidar el refresh token (cookie httpOnly) y borrarlo
    try {
      const { default: api } = await import('../utils/api');
      await api.post('/auth/logout');
    } catch { /* si falla el servidor, igual limpiar localmente */ }
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ token: null, user: null });
  },
}));

export default useAuthStore;
