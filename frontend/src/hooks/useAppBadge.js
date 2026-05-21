import { useEffect } from 'react';

export default function useAppBadge(count) {
  useEffect(() => {
    if (!('setAppBadge' in navigator)) return;
    if (count > 0) {
      navigator.setAppBadge(count).catch(() => {});
    } else {
      navigator.clearAppBadge().catch(() => {});
    }
    return () => { navigator.clearAppBadge?.().catch(() => {}); };
  }, [count]);
}
