import { create } from 'zustand';

const useAuthStore = create((set) => ({
  token:         localStorage.getItem('token') || null,
  refresh_token: localStorage.getItem('refresh_token') || null,
  user:          JSON.parse(localStorage.getItem('user') || 'null'),

  login: (token, user, refresh_token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    if (refresh_token) {
      localStorage.setItem('refresh_token', refresh_token);
    }
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
