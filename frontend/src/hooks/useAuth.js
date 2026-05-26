import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { resetRedirectFlag } from '../utils/api';

function _tokenValido(token) {
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user:  null,
      _hasHydrated: false,

      setHasHydrated: (v) => set({ _hasHydrated: v }),

      login: (token, user, rememberMe = true) => {
        resetRedirectFlag();
        set({ token, user });
        if (!rememberMe) {
          // Session-only: remove persisted data so browser restart clears the session
          try { localStorage.removeItem('bbc-auth'); } catch (_) {}
        }
      },

      setToken: (token) => set({ token }),

      logout: async () => {
        try {
          const { default: api } = await import('../utils/api');
          await api.post('/auth/logout');
        } catch { /* si falla el servidor, igual limpiar localmente */ }
        set({ token: null, user: null });
      },
    }),
    {
      name: 'bbc-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ token: state.token, user: state.user }),
      onRehydrateStorage: () => (state) => {
        // Si el token guardado expiró, limpiar al rehidratar
        if (state && !_tokenValido(state.token)) {
          state.token = null;
          state.user  = null;
        }
        state?.setHasHydrated(true);
      },
    }
  )
);

export default useAuthStore;
