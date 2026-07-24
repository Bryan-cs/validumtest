import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { resetRedirectFlag } from '../utils/api';

const STORAGE_KEY = 'bbc-auth';

function _tokenValido(token) {
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

// Storage que decide local vs session según rememberMe persistido en el payload.
// Evita race: si rememberMe=false, futuros set() (rotación de access token) no
// reescriben localStorage. Si true, sessionStorage queda limpio.
const dualStorage = {
  getItem: (name) => {
    try {
      return localStorage.getItem(name) ?? sessionStorage.getItem(name);
    } catch { return null; }
  },
  setItem: (name, value) => {
    let remember = true;
    try {
      const parsed = JSON.parse(value);
      remember = parsed?.state?.rememberMe !== false;
    } catch { /* default remember=true */ }
    try {
      if (remember) {
        localStorage.setItem(name, value);
        sessionStorage.removeItem(name);
      } else {
        sessionStorage.setItem(name, value);
        localStorage.removeItem(name);
      }
    } catch { /* quota / disabled */ }
  },
  removeItem: (name) => {
    try { localStorage.removeItem(name); } catch {}
    try { sessionStorage.removeItem(name); } catch {}
  },
};

const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user:  null,
      rememberMe: true,
      _hasHydrated: false,
      // Multi-tenant: organización que el superadmin está viendo en "god mode".
      // Se envía como header X-Org-Id en cada petición (ver utils/api.js).
      orgActiva: null,   // { id, nombre } | null

      setHasHydrated: (v) => set({ _hasHydrated: v }),

      login: (token, user, rememberMe = true) => {
        resetRedirectFlag();
        // Set rememberMe primero para que el storage adapter elija el destino correcto.
        set({ rememberMe, token, user, orgActiva: null });
      },

      setToken: (token) => set({ token }),

      setOrgActiva: (org) => set({ orgActiva: org }),

      logout: async () => {
        try {
          const { default: api } = await import('../utils/api');
          await api.post('/auth/logout');
        } catch { /* si falla el servidor, igual limpiar localmente */ }
        set({ token: null, user: null, rememberMe: true, orgActiva: null });
        try { localStorage.removeItem(STORAGE_KEY); } catch {}
        try { sessionStorage.removeItem(STORAGE_KEY); } catch {}
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => dualStorage),
      partialize: (state) => ({ token: state.token, user: state.user, rememberMe: state.rememberMe, orgActiva: state.orgActiva }),
      onRehydrateStorage: () => (state) => {
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
