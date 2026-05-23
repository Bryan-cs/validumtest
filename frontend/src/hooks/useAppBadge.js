import { useEffect, useRef } from 'react';

const SIZE = 96;
const BADGE = 28;

let _imgCache = null;

function loadBaseIcon() {
  if (_imgCache) return Promise.resolve(_imgCache);
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => { _imgCache = img; resolve(img); };
    img.onerror = () => resolve(null);
    img.src = '/favicon-96x96.png';
  });
}

async function buildFavicon(count) {
  const img = await loadBaseIcon();
  const c = document.createElement('canvas');
  c.width = SIZE; c.height = SIZE;
  const ctx = c.getContext('2d');

  if (img) {
    ctx.drawImage(img, 0, 0, SIZE, SIZE);
  } else {
    // Fallback "BB" si no carga la imagen
    const r = 16;
    ctx.beginPath();
    ctx.moveTo(r,0); ctx.lineTo(SIZE-r,0); ctx.quadraticCurveTo(SIZE,0,SIZE,r);
    ctx.lineTo(SIZE,SIZE-r); ctx.quadraticCurveTo(SIZE,SIZE,SIZE-r,SIZE);
    ctx.lineTo(r,SIZE); ctx.quadraticCurveTo(0,SIZE,0,SIZE-r);
    ctx.lineTo(0,r); ctx.quadraticCurveTo(0,0,r,0); ctx.closePath();
    ctx.fillStyle = '#111827'; ctx.fill();
    ctx.fillStyle = '#F9FAFB';
    ctx.font = 'bold 38px system-ui,sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('BB', SIZE/2, SIZE/2);
  }

  if (count > 0) {
    const bx = SIZE - BADGE / 2;
    const by = BADGE / 2;

    // Anillo de contraste
    ctx.beginPath();
    ctx.arc(bx, by, BADGE / 2 + 3, 0, 2 * Math.PI);
    ctx.fillStyle = '#ffffff';
    ctx.fill();

    // Círculo rojo
    ctx.beginPath();
    ctx.arc(bx, by, BADGE / 2, 0, 2 * Math.PI);
    ctx.fillStyle = '#EF4444';
    ctx.fill();

    // Número
    const label = count > 99 ? '99+' : String(count);
    ctx.fillStyle = '#FFFFFF';
    ctx.font = `bold ${label.length > 1 ? 13 : 16}px system-ui,sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, bx, by);
  }

  return c.toDataURL('image/png');
}

export default function useAppBadge(count) {
  const linkRef = useRef(null);

  useEffect(() => {
    if (!linkRef.current) {
      const el = document.createElement('link');
      el.rel = 'icon';
      el.type = 'image/png';
      el.setAttribute('sizes', '96x96');
      document.head.appendChild(el);
      linkRef.current = el;
    }

    buildFavicon(count).then(dataUrl => {
      if (linkRef.current) linkRef.current.href = dataUrl;
    });

    if ('setAppBadge' in navigator) {
      count > 0
        ? navigator.setAppBadge(count).catch(() => {})
        : navigator.clearAppBadge().catch(() => {});
    }
  }, [count]);

  useEffect(() => {
    return () => {
      navigator.clearAppBadge?.().catch(() => {});
      if (linkRef.current) {
        buildFavicon(0).then(dataUrl => {
          if (linkRef.current) linkRef.current.href = dataUrl;
        });
      }
    };
  }, []);
}
