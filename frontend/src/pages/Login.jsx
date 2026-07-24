import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

/* ─────────────────────────────────────────────────────────────────────────────
   Login Validum — foto de fondo, gradientes animados, orbes flotantes,
   acento índigo→cian, entradas escalonadas. Coherente con la consola.
   ──────────────────────────────────────────────────────────────────────────── */
const PHOTO = 'https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1400&q=75&auto=format&fit=crop';

const ESTILOS = `
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

.lg-root {
  --card:  #FFFFFF;
  --ink:   #1B1E24;
  --muted: #8A9099;
  --line:  #E9EBEF;
  --dark:  #14161C;
  --a1:    #6366F1;   /* índigo */
  --a2:    #06B6D4;   /* cian   */
  --green: #10B981;
  --red:   #F05252;
  min-height: 100vh; display: flex;
  background: #EEF0F5; color: var(--ink);
  font-family: 'Figtree', sans-serif; -webkit-font-smoothing: antialiased;
}
@keyframes lgUp    { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }
@keyframes lgIn    { from { opacity: 0; transform: translateX(-18px); } to { opacity: 1; transform: none; } }
@keyframes lgShake { 0%,100% { transform: translateX(0); } 20%,60% { transform: translateX(-8px); } 40%,80% { transform: translateX(8px); } }
@keyframes lgFloat { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(24px,-30px) scale(1.12); } }
@keyframes lgFloat2{ 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-30px,26px) scale(1.18); } }
@keyframes lgShine { 0% { transform: translateX(-120%) skewX(-18deg); } 100% { transform: translateX(220%) skewX(-18deg); } }
@keyframes lgPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(99,102,241,.45); } 50% { box-shadow: 0 0 0 10px rgba(99,102,241,0); } }
@keyframes lgGrad  { 0% { background-position: 0% 50%; } 100% { background-position: 200% 50%; } }

/* ── Panel de marca ── */
.lg-brandpane {
  width: 46%; min-width: 400px; position: relative; overflow: hidden;
  display: flex; flex-direction: column; justify-content: space-between;
  padding: 46px 50px; color: #fff;
  background:
    linear-gradient(155deg, rgba(20,22,28,.72), rgba(30,27,75,.82) 55%, rgba(8,47,73,.9)),
    url('${PHOTO}') center/cover no-repeat, var(--dark);
}
/* Malla de gradiente animada por encima de la foto */
.lg-brandpane::before {
  content: ''; position: absolute; inset: 0; pointer-events: none; opacity: .5;
  background: linear-gradient(110deg, transparent, rgba(99,102,241,.35), rgba(6,182,212,.28), transparent);
  background-size: 200% 100%; animation: lgGrad 9s linear infinite;
  mix-blend-mode: screen;
}
.lg-orb { position: absolute; border-radius: 999px; filter: blur(46px); pointer-events: none; opacity: .55; }
.lg-orb--1 { width: 300px; height: 300px; top: -60px; right: -40px; background: radial-gradient(circle, #6366F1, transparent 70%); animation: lgFloat 11s ease-in-out infinite; }
.lg-orb--2 { width: 260px; height: 260px; bottom: -50px; left: -30px; background: radial-gradient(circle, #06B6D4, transparent 70%); animation: lgFloat2 13s ease-in-out infinite; }

.lg-brand { display: flex; align-items: center; gap: 13px; position: relative; z-index: 2; animation: lgIn .5s ease both; }
.lg-logo {
  width: 46px; height: 46px; border-radius: 13px; display: grid; place-items: center;
  font-weight: 900; font-size: 21px; color: #fff;
  background: linear-gradient(135deg, var(--a1), var(--a2));
  box-shadow: 0 8px 26px -6px rgba(99,102,241,.6);
}
.lg-brand-name { font-size: 19px; font-weight: 800; letter-spacing: -.3px; }
.lg-brand-sub  { font-size: 11px; color: rgba(255,255,255,.6); font-weight: 500; margin-top: 1px; letter-spacing: .3px; }

.lg-hero { position: relative; z-index: 2; }
.lg-hero h1 {
  font-size: clamp(30px, 3.2vw, 44px); font-weight: 900; letter-spacing: -1px; line-height: 1.08;
  margin: 0 0 16px; animation: lgUp .6s .1s ease both;
}
.lg-hero h1 em {
  font-style: normal;
  background: linear-gradient(100deg, #A5B4FC, #67E8F9); -webkit-background-clip: text;
  background-clip: text; color: transparent;
}
.lg-hero p  { color: rgba(255,255,255,.72); font-size: 14.5px; line-height: 1.65; max-width: 40ch; margin: 0 0 28px; animation: lgUp .6s .2s ease both; }
.lg-feats { display: flex; flex-direction: column; gap: 13px; }
.lg-feat { display: flex; align-items: center; gap: 12px; font-size: 13.5px; font-weight: 600; color: rgba(255,255,255,.9); animation: lgIn .5s ease both; }
.lg-feat-ico {
  width: 28px; height: 28px; border-radius: 9px; flex: none; color: #fff;
  background: linear-gradient(135deg, rgba(99,102,241,.9), rgba(6,182,212,.9));
  display: grid; place-items: center; box-shadow: 0 4px 12px -4px rgba(6,182,212,.6);
}
.lg-foot { position: relative; z-index: 2; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: rgba(255,255,255,.42); letter-spacing: .6px; animation: lgUp .6s .4s ease both; }

/* ── Formulario ── */
.lg-formpane { flex: 1; display: flex; align-items: center; justify-content: center; padding: 28px; position: relative; }
.lg-formpane::before {
  content: ''; position: absolute; width: 340px; height: 340px; border-radius: 999px;
  background: radial-gradient(circle, rgba(99,102,241,.10), transparent 70%); top: 8%; right: 4%;
  animation: lgFloat 14s ease-in-out infinite; pointer-events: none;
}
.lg-card {
  position: relative; background: var(--card); border-radius: 22px; width: 404px; max-width: 100%;
  padding: 38px; overflow: hidden;
  box-shadow: 0 1px 3px rgba(16,24,40,.06), 0 24px 60px -18px rgba(30,27,75,.25);
  animation: lgUp .55s .1s ease both;
}
.lg-card::before {   /* barra superior de acento */
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
  background: linear-gradient(90deg, var(--a1), var(--a2));
}
.lg-card-logo {
  width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; color: #fff;
  font-weight: 900; font-size: 22px; margin-bottom: 20px;
  background: linear-gradient(135deg, var(--a1), var(--a2)); box-shadow: 0 8px 24px -8px rgba(99,102,241,.55);
}
.lg-title { font-size: 24px; font-weight: 800; letter-spacing: -.5px; margin: 0 0 5px; }
.lg-sub   { font-size: 13px; color: var(--muted); margin: 0 0 26px; }
.lg-label { display: block; font-size: 12px; font-weight: 700; margin-bottom: 7px; }
.lg-field { margin-bottom: 16px; animation: lgUp .5s ease both; }
.lg-field:nth-of-type(1) { animation-delay: .18s; }
.lg-field:nth-of-type(2) { animation-delay: .26s; }
.lg-input {
  width: 100%; box-sizing: border-box; padding: 12px 14px; font-family: inherit; font-size: 14px;
  background: #F7F8FB; color: var(--ink); border: 1.5px solid var(--line); border-radius: 12px;
  outline: none; transition: border-color .2s, box-shadow .2s, background .2s;
}
.lg-input::placeholder { color: #B4B9C2; }
.lg-input:focus { border-color: var(--a1); background: #fff; box-shadow: 0 0 0 4px rgba(99,102,241,.12); }
.lg-passwrap { position: relative; }
.lg-eye {
  position: absolute; right: 7px; top: 50%; transform: translateY(-50%);
  background: none; border: none; cursor: pointer; color: var(--muted);
  width: 34px; height: 34px; border-radius: 9px; display: grid; place-items: center; transition: all .2s;
}
.lg-eye:hover { background: #EEF0F6; color: var(--a1); }
.lg-remember { display: flex; align-items: center; gap: 9px; margin: 6px 0 22px; cursor: pointer; user-select: none; font-size: 13px; font-weight: 600; color: var(--muted); animation: lgUp .5s .32s ease both; }
.lg-check {
  width: 19px; height: 19px; border-radius: 6px; border: 1.5px solid var(--line);
  display: grid; place-items: center; transition: all .2s; background: #fff; flex: none; color: #fff;
}
.lg-check[data-on="true"] { background: linear-gradient(135deg, var(--a1), var(--a2)); border-color: transparent; }
.lg-btn {
  position: relative; overflow: hidden; width: 100%; padding: 13px; font-family: inherit; font-size: 14.5px; font-weight: 700;
  color: #fff; border: none; border-radius: 12px; cursor: pointer;
  background: linear-gradient(120deg, var(--a1), var(--a2)); background-size: 180% 100%;
  transition: background-position .4s, transform .15s, box-shadow .25s;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  animation: lgUp .5s .38s ease both;
}
.lg-btn:hover { background-position: 100% 50%; box-shadow: 0 12px 26px -10px rgba(99,102,241,.6); }
.lg-btn:active { transform: translateY(1px); }
.lg-btn:disabled { opacity: .7; cursor: wait; }
.lg-btn::after {   /* barrido de brillo */
  content: ''; position: absolute; top: 0; left: 0; width: 40%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.4), transparent);
}
.lg-btn:hover::after { animation: lgShine .8s ease; }

@media (max-width: 880px) {
  .lg-brandpane { display: none; }
  .lg-formpane::before { display: none; }
}
@media (min-width: 881px) { .lg-card-logo { display: none; } }
`;

const IcoCheck = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);
const IcoEye = ({ off }) => off ? (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
    <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" />
  </svg>
) : (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
  </svg>
);

export default function Login() {
  const [username,   setUsername]   = useState('');
  const [password,   setPassword]   = useState('');
  const [loading,    setLoading]    = useState(false);
  const [showPass,   setShowPass]   = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const { login } = useAuthStore();
  const navigate  = useNavigate();
  const cardRef   = useRef(null);

  // Precargar la foto (evita parpadeo al entrar)
  useEffect(() => { const i = new Image(); i.src = PHOTO; }, []);

  const shake = () => {
    if (!cardRef.current) return;
    cardRef.current.style.animation = 'none';
    void cardRef.current.offsetWidth;
    cardRef.current.style.animation = 'lgShake .4s';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) { toast.error('Completa usuario y contraseña'); shake(); return; }
    setLoading(true);
    try {
      const { data } = await api.post('/auth/login', { username, password, remember_me: rememberMe });
      login(data.access_token, { username: data.username, nombre: data.nombre, rol: data.rol, organizacion_id: data.organizacion_id, cliente_ref: data.cliente_ref, ver_detalle: data.ver_detalle }, rememberMe);
      navigate(data.rol === 'superadmin' ? '/organizaciones' : data.rol === 'cliente' ? '/portal' : '/');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al iniciar sesión');
      shake();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="lg-root">
      <style>{ESTILOS}</style>

      {/* Panel de marca */}
      <div className="lg-brandpane">
        <div className="lg-orb lg-orb--1" />
        <div className="lg-orb lg-orb--2" />

        <div className="lg-brand">
          <div className="lg-logo">V</div>
          <div>
            <div className="lg-brand-name">Validum</div>
            <div className="lg-brand-sub">Seguridad social · Colombia</div>
          </div>
        </div>

        <div className="lg-hero">
          <h1>Todas tus <em>organizaciones</em>,<br />un solo mando.</h1>
          <p>
            Afiliaciones, novedades, planillas y facturación — cada organización con sus
            datos, en una sola plataforma potente y ordenada.
          </p>
          <div className="lg-feats">
            {['Datos 100% aislados por organización',
              'Gestión de afiliados y novedades',
              'Facturación y reportes por organización',
              'Portal del cliente integrado'].map((f, i) => (
              <div key={f} className="lg-feat" style={{ animationDelay: `${0.3 + i * 0.1}s` }}>
                <span className="lg-feat-ico"><IcoCheck /></span>{f}
              </div>
            ))}
          </div>
        </div>

        <div className="lg-foot">© {new Date().getFullYear()} VALIDUM · TODOS LOS DERECHOS RESERVADOS</div>
      </div>

      {/* Formulario */}
      <div className="lg-formpane">
        <form ref={cardRef} className="lg-card" onSubmit={handleSubmit}>
          <div className="lg-card-logo">V</div>
          <h2 className="lg-title">Inicia sesión</h2>
          <p className="lg-sub">Ingresa con tus credenciales corporativas.</p>

          <div className="lg-field">
            <label className="lg-label">Usuario</label>
            <input className="lg-input" autoFocus autoComplete="username"
                   value={username} onChange={e => setUsername(e.target.value)} placeholder="tu usuario" />
          </div>

          <div className="lg-field">
            <label className="lg-label">Contraseña</label>
            <div className="lg-passwrap">
              <input className="lg-input" type={showPass ? 'text' : 'password'} autoComplete="current-password"
                     style={{ paddingRight: 44 }}
                     value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
              <button type="button" className="lg-eye" onClick={() => setShowPass(v => !v)}
                      aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}>
                <IcoEye off={showPass} />
              </button>
            </div>
          </div>

          <div className="lg-remember" onClick={() => setRememberMe(v => !v)}>
            <span className="lg-check" data-on={rememberMe}>{rememberMe && <IcoCheck />}</span>
            Recordar sesión
          </div>

          <button type="submit" className="lg-btn" disabled={loading}>
            {loading ? 'Ingresando…' : 'Ingresar al sistema'}
            {!loading && <span aria-hidden>→</span>}
          </button>
        </form>
      </div>
    </div>
  );
}
