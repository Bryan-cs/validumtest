import { useRegisterSW } from 'virtual:pwa-register/react';

export default function PWAUpdateBanner() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered(r) {
      // Verificar actualizaciones cada 60 minutos
      if (r) setInterval(() => r.update(), 60 * 60 * 1000);
    },
  });

  if (!needRefresh) return null;

  return (
    <div style={{
      position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
      background: '#1E40AF', color: '#fff',
      borderRadius: 12, padding: '12px 20px',
      display: 'flex', alignItems: 'center', gap: 14,
      boxShadow: '0 8px 32px rgba(0,0,0,.35)',
      zIndex: 9999, fontSize: 13, fontWeight: 500,
      whiteSpace: 'nowrap',
    }}>
      <span>🔄 Nueva versión disponible</span>
      <button
        onClick={() => updateServiceWorker(true)}
        style={{
          background: '#fff', color: '#1E40AF',
          border: 'none', borderRadius: 7,
          padding: '5px 14px', fontSize: 12,
          fontWeight: 700, cursor: 'pointer',
        }}
      >
        Actualizar
      </button>
      <button
        onClick={() => updateServiceWorker(false)}
        style={{
          background: 'transparent', color: 'rgba(255,255,255,.7)',
          border: 'none', fontSize: 18, cursor: 'pointer',
          lineHeight: 1, padding: '0 2px',
        }}
      >
        ×
      </button>
    </div>
  );
}
