import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

// ── Palette: Navy & Gold ──────────────────────────────────────────────────────
const P = {
  overlay:  'rgba(11,27,43,0.55)',
  overlayE: 'rgba(11,27,43,0.92)',
  ink:      '#0B1B2B',
  accent:   '#E6CFA3',
  accentD:  '#B6884B',
  cream:    '#FBFAF6',
  muted:    '#34495C',
  statusG:  '#5EE2A0',
};

const PHOTO = 'https://images.unsplash.com/photo-1582213782179-e0d53f98f2ca?w=1800&q=85&auto=format&fit=crop';

// ── Live news ticker ──────────────────────────────────────────────────────────
function useNews() {
  const [items, setItems]   = useState([]);
  const [status, setStatus] = useState('loading');

  const load = useCallback(() => {
    api.get('/news/ticker')
      .then(r => {
        setItems(r.data);
        setStatus(r.data.length ? 'ok' : 'empty');
      })
      .catch(() => setStatus('empty'));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 600_000); return () => clearInterval(t); }, [load]);
  return { items, status };
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Login() {
  const [username,    setUsername]    = useState('');
  const [password,    setPassword]    = useState('');
  const [loading,     setLoading]     = useState(false);
  const [showPass,    setShowPass]    = useState(false);
  const [rememberMe,  setRememberMe]  = useState(true);
  const { login }  = useAuthStore();
  const navigate   = useNavigate();
  const formRef    = useRef(null);
  const stageRef   = useRef(null);
  const photoRef   = useRef(null);
  const mouseRef   = useRef({ x: 0, y: 0 });
  const rafRef     = useRef(null);
  const [isMobile, setIsMobile] = useState(false);
  const { items: news, status: newsStatus } = useNews();

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 820);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // RAF-driven parallax — zero React re-renders on mousemove
  const applyParallax = useCallback(() => {
    const { x, y } = mouseRef.current;
    if (photoRef.current) {
      photoRef.current.style.transform = `translate3d(${x * -18}px, ${y * -12}px, 0) scale(1.04)`;
    }
    if (formRef.current) {
      formRef.current.style.transform =
        `perspective(1600px) rotateX(${y * -3}deg) rotateY(${x * 4}deg) translateZ(20px)`;
    }
  }, []);

  const onMouseMove = useCallback((e) => {
    if (isMobile) return;
    const r = stageRef.current?.getBoundingClientRect();
    if (!r) return;
    mouseRef.current = {
      x: ((e.clientX - r.left) / r.width  - 0.5) * 2,
      y: ((e.clientY - r.top)  / r.height - 0.5) * 2,
    };
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      applyParallax();
      rafRef.current = null;
    });
  }, [isMobile, applyParallax]);

  const onMouseLeave = useCallback(() => {
    mouseRef.current = { x: 0, y: 0 };
    applyParallax();
  }, [applyParallax]);

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); }, []);

  const shake = () => {
    if (!formRef.current) return;
    formRef.current.style.animation = 'none';
    void formRef.current.offsetWidth;
    formRef.current.style.animation = 'edShake 0.4s';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) { toast.error('Completa usuario y contraseña'); shake(); return; }
    setLoading(true);
    try {
      const { data } = await api.post('/auth/login', { username, password, remember_me: rememberMe });
      login(data.access_token, { username: data.username, nombre: data.nombre, rol: data.rol, cliente_ref: data.cliente_ref }, rememberMe);
      navigate(data.rol === 'cliente' ? '/portal' : '/');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al iniciar sesión');
      shake();
    } finally {
      setLoading(false);
    }
  };

  const tickerLoop = news.length ? [...news, ...news] : [];

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400;1,6..72,500&family=Manrope:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

        *, *::before, *::after { box-sizing: border-box; }

        @keyframes edShake {
          10%,90%      { transform: translateX(-1px); }
          20%,80%      { transform: translateX(2px); }
          30%,50%,70%  { transform: translateX(-4px); }
          40%,60%      { transform: translateX(4px); }
        }
        @keyframes edSpin     { from { transform: rotate(0deg); }  to { transform: rotate(360deg); } }
        @keyframes edFadeUp   { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
        @keyframes edFadeIn   { from { opacity:0; } to { opacity:1; } }
        @keyframes edPulse    { 0%,100% { opacity:1; } 50% { opacity:0.35; } }
        @keyframes edShine    { from { transform: translateX(-120%) skewX(-20deg); } to { transform: translateX(220%) skewX(-20deg); } }
@keyframes edTicker   { from { transform: translateX(0); } to { transform: translateX(-50%); } }

        .ed-input {
          width: 100%; padding: 13px 15px;
          background: rgba(255,255,255,0.92); color: #0B1B2B;
          border: 1px solid rgba(11,27,43,0.22); border-radius: 10px;
          font-size: 14px; font-family: 'Manrope', sans-serif;
          outline: none; transition: border-color .2s, box-shadow .2s;
        }
        .ed-input:focus { border-color: #0B1B2B; box-shadow: 0 0 0 3px rgba(11,27,43,0.10); }
        .ed-input::placeholder { color: #8BA0B0; }
        .ed-input:disabled { background: rgba(11,27,43,0.06); opacity: 0.7; }

        /* Facebook buttons — editorial Navy/Gold palette */
        .ed-trap {
          position: relative;
          width: 112px; height: 44px;
          overflow: hidden; border-radius: 8px;
          border: 1.5px solid rgba(11,27,43,0.22);
          background: rgba(11,27,43,0.04);
          display: inline-flex; align-items: center; justify-content: center;
          cursor: pointer; text-decoration: none;
          transition: border-color .22s, box-shadow .22s;
        }
        .ed-trap::before {
          content: '';
          position: absolute; inset: 0;
          background: #0B1B2B;
          transform: translateY(102%);
          transition: transform .3s cubic-bezier(0.22,1,0.36,1);
        }
        .ed-trap:hover {
          border-color: #0B1B2B;
          box-shadow: 0 6px 18px rgba(11,27,43,0.20);
        }
        .ed-trap:hover::before { transform: translateY(0); }
        .ed-trap:hover .ed-trap-lbl { color: #E6CFA3; }

        .ed-trap-lbl {
          position: relative; z-index: 1;
          color: #34495C; font-size: 10.5px; font-weight: 700;
          font-family: 'Manrope', sans-serif;
          letter-spacing: 0.1em; text-transform: uppercase;
          transition: color .22s;
        }

        @media (max-width: 819px) {
          .ed-trap { flex: 1; width: auto; }
        }
      `}</style>

      <div
        ref={stageRef}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        style={{
          width: '100vw', height: '100vh', position: 'relative',
          overflow: isMobile ? 'auto' : 'hidden',
          background: P.ink, perspective: '1600px',
          fontFamily: "'Manrope', system-ui, sans-serif", color: P.cream,
        }}
      >
        {/* Background photo */}
        <img ref={photoRef} src={PHOTO} alt="" style={{
          position: isMobile ? 'fixed' : 'absolute',
          inset: '-4%', width: '108%', height: '108%',
          objectFit: 'cover',
          filter: 'saturate(0.9) brightness(0.52)',
          transform: 'translate3d(0,0,0) scale(1.04)',
          transition: 'transform 0.5s cubic-bezier(0.22,1,0.36,1)',
          willChange: 'transform',
        }} />



        {/* Color wash gradients */}
        <div style={{
          position: isMobile ? 'fixed' : 'absolute', inset: 0, zIndex: 1,
          background: isMobile
            ? `linear-gradient(180deg, ${P.overlay} 0%, ${P.overlayE} 100%)`
            : `linear-gradient(90deg, ${P.overlay} 0%, rgba(0,0,0,0.05) 35%, ${P.overlay} 75%, ${P.overlayE} 100%)`,
        }} />
        <div style={{
          position: isMobile ? 'fixed' : 'absolute', inset: 0, zIndex: 1,
          background: `radial-gradient(ellipse at 25% 60%, transparent 0%, ${P.overlay} 75%)`,
        }} />

        {/* Brand bar */}
        <div style={{
          position: 'relative', zIndex: 2,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: isMobile ? '14px 16px' : '28px 56px', flexWrap: 'wrap', gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: isMobile ? 36 : 44, height: isMobile ? 41 : 50, flexShrink: 0, filter: `drop-shadow(0 4px 10px ${P.ink}55)` }}>
              <svg viewBox="0 0 40 46" width={isMobile ? 36 : 44} height={isMobile ? 41 : 50} style={{ display: 'block' }}>
                <path d="M20 2 L36 7 V22 C36 31 29.5 39 20 44 C10.5 39 4 31 4 22 V7 Z"
                  fill="none" stroke="#3DD68C" strokeWidth="2" strokeLinejoin="round" />
                <path d="M13.5 22 L18 27 L27 17"
                  fill="none" stroke="#3DD68C" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div style={{ lineHeight: 1.1 }}>
              <div style={{ fontFamily: "'Newsreader', serif", fontSize: isMobile ? 20 : 24, fontWeight: 600, color: P.cream, letterSpacing: '-0.018em' }}>
                BBC File
              </div>
              {!isMobile && (
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, letterSpacing: '0.22em', marginTop: 4, color: P.accent }}>
                  SOFTWARE DE GESTIÓN · CO
                </div>
              )}
            </div>
          </div>

          {!isMobile ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <a href="https://landing-page-bbc-file.vercel.app" target="_blank" rel="noopener noreferrer"
                onMouseEnter={e => { e.currentTarget.style.background = `${P.accent}22`; e.currentTarget.style.transform = 'translateY(-1px)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = `${P.accent}10`; e.currentTarget.style.transform = 'none'; }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '7px 14px', border: `1px solid ${P.accent}55`, borderRadius: 999,
                  fontSize: 10.5, letterSpacing: '0.16em',
                  fontFamily: "'JetBrains Mono', monospace",
                  color: P.accent, textDecoration: 'none',
                  background: `${P.accent}10`, transition: 'all 0.2s',
                }}
              >
                CONOCE EL SISTEMA <span aria-hidden="true">→</span>
              </a>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '7px 14px', border: `1px solid ${P.cream}22`,
                borderRadius: 999, fontSize: 10.5, letterSpacing: '0.18em', color: P.cream,
              }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: P.statusG, boxShadow: `0 0 10px ${P.statusG}` }} />
                SISTEMA OPERATIVO
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: P.statusG, boxShadow: `0 0 8px ${P.statusG}` }} />
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, letterSpacing: '0.18em', color: P.statusG }}>EN LÍNEA</span>
            </div>
          )}
        </div>

        {/* Main content grid */}
        <div style={{
          position: 'relative', zIndex: 2,
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : '1fr 460px',
          gap: isMobile ? 28 : 56,
          padding: isMobile ? '16px 16px 80px' : '0 56px',
          height: isMobile ? 'auto' : 'calc(100% - 154px)',
          minHeight: isMobile ? 'calc(100vh - 60px)' : 'auto',
          alignItems: 'center',
        }}>

          {/* Editorial hero — desktop only */}
          {!isMobile && <LoginHero isMobile={isMobile} />}

          {/* Glass login card */}
          <form
            ref={formRef}
            onSubmit={handleSubmit}
            style={{
              background: 'rgba(251,250,246,0.97)',
              borderRadius: 18,
              padding: isMobile ? '26px 22px 22px' : '34px 32px 26px',
              boxShadow: '0 30px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.15) inset',
              border: '1px solid rgba(0,0,0,0.12)',
              animation: 'edFadeUp 0.8s 0.25s both',
              color: P.ink, width: '100%', boxSizing: 'border-box',
              transformStyle: 'preserve-3d',
              transition: 'transform 0.35s cubic-bezier(0.22,1,0.36,1)',
              willChange: 'transform',
            }}
          >
            {isMobile && (
              <div style={{ fontFamily: "'Newsreader', serif", fontSize: 22, lineHeight: 1.15, color: P.ink, letterSpacing: '-0.02em', marginBottom: 16 }}>
                Gestiona la seguridad social,{' '}
                <em style={{ color: P.accentD }}>simplificada.</em>
              </div>
            )}
            <div style={{ fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.22em', color: P.accentD, marginBottom: 10, fontSize: isMobile ? 9 : 11 }}>
              BIENVENIDO DE VUELTA
            </div>
            <div style={{ fontFamily: "'Newsreader', serif", fontSize: isMobile ? 30 : 38, lineHeight: 1.02, color: P.ink, letterSpacing: '-0.02em', marginBottom: 6 }}>
              Inicia sesión
            </div>
            <div style={{ fontSize: 13, color: P.muted, marginBottom: isMobile ? 16 : 22 }}>
              Ingresa con tus credenciales corporativas.
            </div>

            {/* Usuario */}
            <div style={{ marginBottom: 14 }}>
              <label style={{
                display: 'block', marginBottom: 7,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10, letterSpacing: '0.16em', color: '#000',
              }}>USUARIO</label>
              <input
                className="ed-input"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="usuario"
                autoFocus
                disabled={loading}
              />
            </div>

            {/* Contraseña */}
            <div style={{ marginBottom: 14 }}>
              <label style={{
                display: 'block', marginBottom: 7,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10, letterSpacing: '0.16em', color: '#000',
              }}>CONTRASEÑA</label>
              <div style={{ position: 'relative' }}>
                <input
                  className="ed-input"
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••••"
                  disabled={loading}
                  style={{ paddingRight: 44 }}
                />
                <button type="button" onClick={() => setShowPass(v => !v)}
                  aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  style={{
                    position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                    width: 28, height: 28, border: 'none', background: 'transparent',
                    color: showPass ? P.ink : P.muted, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 1, padding: 0, transition: 'color .15s',
                  }}
                >
                  {showPass ? (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                      <line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Recordar sesión */}
            <label style={{
              display: 'flex', alignItems: 'center', gap: 9,
              marginBottom: 16, cursor: 'pointer', userSelect: 'none',
            }}>
              <div
                onClick={() => setRememberMe(v => !v)}
                style={{
                  width: 18, height: 18, borderRadius: 5, flexShrink: 0,
                  border: `1.5px solid ${rememberMe ? P.ink : 'rgba(11,27,43,0.30)'}`,
                  background: rememberMe ? P.ink : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all .15s', cursor: 'pointer',
                }}
              >
                {rememberMe && (
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                    <path d="M2 6l3 3 5-5" stroke="#FBFAF6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </div>
              <span style={{ fontSize: 12.5, color: P.muted, fontFamily: "'Manrope', sans-serif" }}
                onClick={() => setRememberMe(v => !v)}>
                Recordar sesión
              </span>
            </label>

            <SubmitBtn loading={loading} P={P} />

            {/* Social — 3 Facebook trapdoor buttons */}
            <div style={{
              marginTop: 20, paddingTop: 16,
              borderTop: `1px solid ${P.ink}14`,
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="#1877F2">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
                <span style={{
                  fontFamily: "'Manrope', sans-serif",
                  fontSize: 12, fontWeight: 700, letterSpacing: '0.06em',
                  color: '#1877F2',
                }}>
                  SÍGUENOS EN FACEBOOK
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, width: '100%', justifyContent: 'center' }}>
                <a href="https://www.facebook.com/TechPlanetEsal" target="_blank" rel="noreferrer" className="ed-trap">
                  <span className="ed-trap-lbl">Techplanet</span>
                </a>
                <a href="https://www.facebook.com/profile.php?id=61584899039203" target="_blank" rel="noreferrer" className="ed-trap">
                  <span className="ed-trap-lbl">Protsecoop</span>
                </a>
                <a href="https://www.facebook.com/profile.php?id=61586640354662" target="_blank" rel="noreferrer" className="ed-trap">
                  <span className="ed-trap-lbl">Carsecoop</span>
                </a>
              </div>
            </div>

            <div style={{
              marginTop: 14, paddingTop: 10,
              borderTop: `1px solid ${P.ink}14`,
              textAlign: 'center', fontSize: 11, color: P.muted,
              fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.06em',
            }}>
              © 2026 BBC File · Todos los derechos reservados
            </div>
          </form>
        </div>

        {/* News ticker */}
        <div style={{
          position: isMobile ? 'fixed' : 'absolute', left: 0, right: 0, bottom: 0, zIndex: 3,
          height: 48, display: 'flex', alignItems: 'center',
          background: 'rgba(11,27,43,0.88)',
          borderTop: `1px solid ${P.cream}1c`,
          animation: 'edFadeIn 0.6s 0.6s both',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '0 22px', borderRight: `1px solid ${P.cream}1c`,
            height: '100%', flexShrink: 0,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: newsStatus === 'ok' ? P.statusG : P.accent,
              boxShadow: `0 0 10px ${newsStatus === 'ok' ? P.statusG : P.accent}`,
              animation: newsStatus === 'loading' ? 'edPulse 1.2s infinite' : 'none',
            }} />
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.22em', color: P.cream, fontWeight: 700 }}>
              EN VIVO · DEL SECTOR
            </span>
          </div>

          <div style={{
            flex: 1, overflow: 'hidden', position: 'relative',
            maskImage: 'linear-gradient(90deg, transparent, black 4%, black 96%, transparent)',
            WebkitMaskImage: 'linear-gradient(90deg, transparent, black 4%, black 96%, transparent)',
          }}>
            {newsStatus === 'loading' ? (
              <div style={{ padding: '0 20px', fontFamily: "'Newsreader', serif", fontStyle: 'italic', color: `${P.cream}88`, fontSize: 13 }}>
                Cargando noticias del sector…
              </div>
            ) : tickerLoop.length > 0 ? (
              <div style={{ display: 'inline-flex', whiteSpace: 'nowrap', alignItems: 'center', animation: 'edTicker 150s linear infinite' }}>
                {tickerLoop.map((it, i) => (
                  <button key={i}
                    onClick={() => { try { window.open(it.link, '_blank', 'noopener,noreferrer'); } catch(_){} }}
                    style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 14, padding: '0 26px' }}
                  >
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.18em', color: P.accent, fontWeight: 700 }}>
                      {it.source.toUpperCase()}
                    </span>
                    <span style={{ width: 3, height: 3, background: `${P.cream}55`, borderRadius: '50%' }} />
                    <span style={{ fontFamily: "'Newsreader', serif", fontSize: 14, color: P.cream, letterSpacing: '-0.005em' }}>
                      {it.title.replace(/ - [^-]+$/, '').slice(0, 110)}
                    </span>
                    <span style={{ color: `${P.cream}44`, fontSize: 12 }}>·</span>
                  </button>
                ))}
              </div>
            ) : (
              <div style={{ padding: '0 20px', fontFamily: "'Newsreader', serif", fontStyle: 'italic', color: `${P.cream}88`, fontSize: 13 }}>
                Sin noticias disponibles en este momento.
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

const LoginHero = React.memo(function LoginHero({ isMobile }) {
  return (
    <div style={{ maxWidth: 620, animation: 'edFadeUp 0.8s 0.1s both' }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        letterSpacing: '0.22em', color: P.cream,
        marginBottom: isMobile ? 14 : 22, fontSize: isMobile ? 13 : 14,
      }}>BBC FILE</div>
      <div style={{
        fontFamily: "'Newsreader', 'Iowan Old Style', Georgia, serif",
        fontSize: isMobile ? 44 : 72, lineHeight: 0.98,
        letterSpacing: '-0.03em', fontWeight: 400,
        marginBottom: isMobile ? 18 : 26,
      }}>
        Gestiona la seguridad social,<br />
        <span style={{ fontStyle: 'italic', color: P.accent }}>simplificada.</span>
      </div>
      <div style={{ lineHeight: 1.62, color: P.cream, maxWidth: 480, fontSize: isMobile ? 15 : 18 }}>
        Afiliaciones, novedades, planillas y reportes en una sola plataforma para tu empresa y tu equipo.
      </div>
      <ul style={{
        listStyle: 'none', padding: 0, margin: isMobile ? '20px 0 0' : '30px 0 0',
        display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr',
        gap: isMobile ? '10px' : '12px 28px', maxWidth: 520,
      }}>
        {['Gestión de afiliados y novedades', 'Control de retiros y planillas', 'Portal cliente integrado', 'Reportes y facturación'].map((feat, i) => (
          <li key={i} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            color: P.cream, fontSize: 14.5, lineHeight: 1.35,
            animation: `edFadeUp 0.5s ${0.35 + i * 0.1}s both`,
          }}>
            <span style={{
              width: 22, height: 22, borderRadius: '50%',
              background: `${P.accent}28`, color: P.accent,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, border: `1px solid ${P.accent}55`,
            }}>
              <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
                <path d="M3 8.5L6.5 12L13 4.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            {feat}
          </li>
        ))}
      </ul>
    </div>
  );
});

function SubmitBtn({ loading, P }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="submit"
      disabled={loading}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        width: '100%', marginTop: 10, padding: '15px',
        background: P.ink, color: P.cream,
        border: 'none', borderRadius: 10,
        fontSize: 14.5, fontFamily: "'Manrope', sans-serif",
        fontWeight: 600, letterSpacing: '0.01em',
        cursor: loading ? 'not-allowed' : 'pointer',
        opacity: loading ? 0.8 : 1,
        boxShadow: hover && !loading ? `0 14px 30px ${P.ink}66` : `0 4px 12px ${P.ink}22`,
        transform: hover && !loading ? 'translateY(-2px)' : 'none',
        transition: 'all 0.22s',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        position: 'relative', overflow: 'hidden',
      }}
    >
      {hover && !loading && (
        <span aria-hidden="true" style={{
          position: 'absolute', top: 0, left: 0, width: '40%', height: '100%',
          background: `linear-gradient(90deg, transparent, ${P.accent}55, transparent)`,
          animation: 'edShine 0.9s ease-out', pointerEvents: 'none',
        }} />
      )}
      {loading && <Spinner P={P} />}
      <span style={{ position: 'relative' }}>
        {loading ? 'Verificando…' : 'Ingresar al sistema'}
      </span>
      {!loading && <span style={{ marginLeft: 6, opacity: 0.7, position: 'relative' }}>→</span>}
    </button>
  );
}

function Spinner({ P }) {
  return (
    <span style={{
      display: 'inline-block', width: 14, height: 14, borderRadius: '50%',
      border: `2px solid ${P.cream}55`, borderTopColor: P.cream,
      animation: 'edSpin 0.7s linear infinite',
    }} />
  );
}
