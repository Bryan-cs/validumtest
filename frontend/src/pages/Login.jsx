import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading,  setLoading]  = useState(false);
  const [showPass, setShowPass] = useState(false);
  const { login }  = useAuthStore();
  const navigate   = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) { toast.error('Completa usuario y contraseña'); return; }
    setLoading(true);
    try {
      const { data } = await api.post('/auth/login', { username, password });
      login(data.access_token, { username: data.username, nombre: data.nombre, rol: data.rol, cliente_ref: data.cliente_ref });
      navigate(data.rol === 'cliente' ? '/portal' : '/');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

        *, *::before, *::after { box-sizing: border-box; }

        .lr { min-height: 100vh; display: flex; font-family: 'DM Sans', sans-serif; }

        /* ── LEFT BRAND PANEL ── */
        .lr-brand {
          width: 44%;
          background: #111827;
          position: relative;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 52px 56px;
          overflow: hidden;
        }
        .lr-brand::before {
          content: '';
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px);
          background-size: 44px 44px;
        }
        .lr-brand::after {
          content: '';
          position: absolute;
          right: -100px; top: -100px;
          width: 380px; height: 380px;
          border: 1.5px solid rgba(255,255,255,.06);
          border-radius: 50%;
        }
        .lr-circle2 {
          position: absolute;
          right: -40px; top: -40px;
          width: 220px; height: 220px;
          border: 1px solid rgba(255,255,255,.04);
          border-radius: 50%;
        }
        .lr-circle3 {
          position: absolute;
          left: -60px; bottom: 80px;
          width: 180px; height: 180px;
          border: 1px solid rgba(255,255,255,.04);
          border-radius: 50%;
        }
        .lr-top { position: relative; z-index: 1; }

        /* logo mark igual que sidebar */
        .lr-logomark {
          display: inline-flex; align-items: center; justify-content: center;
          width: 44px; height: 44px; border-radius: 10px;
          background: linear-gradient(135deg, #374151 0%, #1F2937 100%);
          margin-bottom: 40px;
          font-family: 'Syne', sans-serif;
          font-size: 15px; font-weight: 800;
          color: #F9FAFB; letter-spacing: -0.5px;
          box-shadow: 0 1px 3px rgba(0,0,0,.4);
        }

        .lr-badge {
          display: inline-flex; align-items: center; gap: 7px;
          border: 1px solid rgba(255,255,255,.12);
          border-radius: 3px;
          padding: 5px 13px;
          margin-bottom: 28px;
          font-size: 10.5px; letter-spacing: 2.8px;
          text-transform: uppercase;
          color: rgba(255,255,255,.5); font-weight: 600;
        }
        .lr-badge-dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: #4ADE80;
          animation: lr-blink 2s ease-in-out infinite;
        }
        @keyframes lr-blink {
          0%, 100% { opacity: 1; } 50% { opacity: .3; }
        }
        .lr-wordmark {
          font-family: 'Syne', sans-serif;
          font-size: 68px; font-weight: 800;
          line-height: .9; color: #F9FAFB;
          margin: 0; letter-spacing: -3px;
        }
        .lr-wordmark em {
          color: #9CA3AF; font-style: normal; display: block;
          font-size: 52px; font-weight: 700;
        }
        .lr-tagline {
          margin: 24px 0 0;
          font-size: 13px; color: rgba(255,255,255,.3);
          line-height: 1.75; max-width: 240px;
          font-weight: 300; letter-spacing: .2px;
        }
        .lr-bottom { position: relative; z-index: 1; }
        .lr-features {
          list-style: none; margin: 0; padding: 0;
          display: flex; flex-direction: column; gap: 13px;
        }
        .lr-features li {
          display: flex; align-items: center; gap: 12px;
          font-size: 12.5px; color: rgba(255,255,255,.32); font-weight: 300;
        }
        .lr-features li::before {
          content: '';
          width: 20px; height: 1px;
          background: linear-gradient(90deg, rgba(255,255,255,.25), transparent);
          flex-shrink: 0;
        }

        /* ── RIGHT FORM PANEL ── */
        .lr-form-panel {
          flex: 1;
          background: var(--c-bg, #F0F2FF);
          display: flex; align-items: center; justify-content: center;
          padding: 48px 56px;
          position: relative;
        }
        .lr-form-panel::before {
          content: '';
          position: absolute; inset: 0;
          background-image: radial-gradient(circle, rgba(0,0,0,.04) 1px, transparent 1px);
          background-size: 26px 26px;
        }
        .lr-card {
          width: 100%; max-width: 390px;
          position: relative; z-index: 1;
        }
        .lr-eyebrow {
          font-size: 11px; letter-spacing: 2.8px;
          text-transform: uppercase;
          color: var(--c-primary, #4F46E5); font-weight: 700; margin-bottom: 8px;
        }
        .lr-heading {
          font-family: 'Syne', sans-serif;
          font-size: 34px; font-weight: 800;
          color: var(--c-text, #1E293B); margin: 0 0 6px; line-height: 1.1;
          letter-spacing: -1px;
        }
        .lr-sub {
          font-size: 14px; color: var(--c-text2, #64748B);
          margin: 0 0 36px; font-weight: 400;
        }
        .lr-field { margin-bottom: 20px; }
        .lr-label {
          display: block;
          font-size: 11px; font-weight: 700;
          color: var(--c-text2, #64748B); margin-bottom: 7px;
          letter-spacing: 1px; text-transform: uppercase;
        }
        .lr-input-wrap { position: relative; }
        .lr-input {
          width: 100%;
          padding: 12px 16px;
          border: 1.5px solid var(--c-border, #E2E8F0);
          border-radius: 10px;
          font-size: 15px;
          font-family: 'DM Sans', sans-serif;
          color: var(--c-text, #1E293B);
          background: var(--c-surface, #FFFFFF);
          outline: none;
          transition: border-color .18s, box-shadow .18s;
        }
        .lr-input:focus {
          border-color: var(--c-primary, #4F46E5);
          box-shadow: 0 0 0 3px color-mix(in srgb, var(--c-primary, #4F46E5) 12%, transparent);
        }
        .lr-input::placeholder { color: var(--c-border, #E2E8F0); }
        .lr-eye {
          position: absolute; right: 13px; top: 50%;
          transform: translateY(-50%);
          background: none; border: none; cursor: pointer;
          color: var(--c-text2, #64748B); padding: 4px;
          display: flex; align-items: center;
          font-size: 15px; line-height: 1;
          transition: color .15s;
        }
        .lr-eye:hover { color: var(--c-text, #1E293B); }
        .lr-btn {
          width: 100%; padding: 13px;
          margin-top: 6px;
          background: var(--c-primary, #4F46E5);
          color: #fff;
          border: none;
          border-radius: 10px;
          font-size: 15px; font-weight: 600;
          font-family: 'DM Sans', sans-serif;
          cursor: pointer; letter-spacing: .2px;
          transition: opacity .15s, transform .1s;
        }
        .lr-btn:hover:not(:disabled) { opacity: .88; }
        .lr-btn:active:not(:disabled) { transform: scale(.99); }
        .lr-btn:disabled { opacity: .5; cursor: not-allowed; }

        /* ── SOCIAL ── */
        .lr-social { margin-top: 32px; }
        .lr-social-label {
          font-size: 11px; letter-spacing: 2px;
          text-transform: uppercase;
          color: #1877F2; font-weight: 700; margin: 0 0 12px;
          text-align: center;
        }
        .lr-social-row { display: flex; justify-content: center; gap: 10px; }

        .fb-trapdoor {
          position: relative;
          width: 108px; height: 44px;
          overflow: hidden;
          background: var(--c-surface, #fff);
          border-radius: 10px;
          border: 1.5px solid var(--c-border, #E2E8F0);
          transition: border-color .2s;
          text-decoration: none;
          display: inline-flex; align-items: center; justify-content: center;
          cursor: pointer;
        }
        .fb-trapdoor:hover { border-color: #1877F2; }
        .fb-trapdoor:hover .fb-door {
          box-shadow: 0 0 10px -2px rgba(0,0,0,.3);
          transform: scale(1.06);
        }
        .fb-trapdoor:hover .fb-door-top    { top: -50%; }
        .fb-trapdoor:hover .fb-door-bottom { top: 100%; }

        .fb-door {
          position: absolute; left: 0;
          width: 100%; height: 50%;
          background: #111827;
          overflow: hidden;
          z-index: 2;
          transition: top 400ms ease-in-out, box-shadow 200ms ease-in-out, transform 300ms ease-in-out;
        }
        .fb-door-top    { top: 0; }
        .fb-door-bottom { top: 50%; }

        .fb-f-img {
          position: absolute;
          height: 22px; width: auto; display: block;
          left: 50%; transform: translateX(-50%);
          top: 11px; pointer-events: none;
        }
        .fb-door-bottom .fb-f-img { top: -11px; }

        .fb-icon {
          position: relative; z-index: 1;
          color: #1877F2; font-size: 12px; font-weight: 700;
          font-family: 'DM Sans', sans-serif;
          letter-spacing: .2px; text-align: center; line-height: 1;
        }

        .lr-divider {
          height: 1px; background: var(--c-border, #E2E8F0);
          margin: 28px 0;
        }

        .lr-copyright {
          text-align: center;
          font-size: 12px; color: var(--c-text2, #64748B); letter-spacing: .2px;
        }

        @media (max-width: 820px) {
          .lr-brand { display: none; }
          .lr-form-panel { padding: 40px 28px; }
        }
      `}</style>

      <div className="lr">
        {/* ── Brand panel ── */}
        <div className="lr-brand">
          <div className="lr-circle2" />
          <div className="lr-circle3" />

          <div className="lr-top">
            <div className="lr-logomark">BB</div>
            <div className="lr-badge">
              <span className="lr-badge-dot" />
              Sistema activo
            </div>
            <h1 className="lr-wordmark">
              BBC
              <em>File</em>
            </h1>
            <p className="lr-tagline">
              Plataforma integral de gestión de personal y seguridad social.
            </p>
          </div>

          <div className="lr-bottom">
            <ul className="lr-features">
              <li>Gestión de afiliados y novedades</li>
              <li>Control de retiros y planillas</li>
              <li>Portal cliente integrado</li>
              <li>Reportes y facturación</li>
            </ul>
          </div>
        </div>

        {/* ── Form panel ── */}
        <div className="lr-form-panel">
          <div className="lr-card">
            <p className="lr-eyebrow">Bienvenido</p>
            <h2 className="lr-heading">Inicio de sesión</h2>
            <p className="lr-sub">Ingresa tus credenciales para continuar</p>

            <form onSubmit={handleSubmit}>
              <div className="lr-field">
                <label className="lr-label">Usuario</label>
                <div className="lr-input-wrap">
                  <input
                    className="lr-input"
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    placeholder="tu_usuario"
                    autoFocus
                  />
                </div>
              </div>

              <div className="lr-field">
                <label className="lr-label">Contraseña</label>
                <div className="lr-input-wrap">
                  <input
                    className="lr-input"
                    type={showPass ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    style={{ paddingRight: 46 }}
                  />
                  <button type="button" className="lr-eye" onClick={() => setShowPass(v => !v)}>
                    {showPass ? '🙈' : '👁'}
                  </button>
                </div>
              </div>

              <button type="submit" disabled={loading} className="lr-btn">
                {loading ? 'Verificando…' : 'Ingresar al sistema'}
              </button>
            </form>

            <div className="lr-divider" />

            <div className="lr-social">
              <p className="lr-social-label">Síguenos en Facebook</p>
              <div className="lr-social-row">
                <a href="https://www.facebook.com/TechPlanetEsal" target="_blank" rel="noreferrer" className="fb-trapdoor">
                  <div className="fb-door fb-door-top"><img src="/facebook-f.svg" className="fb-f-img" alt="" /></div>
                  <div className="fb-door fb-door-bottom"><img src="/facebook-f.svg" className="fb-f-img" alt="" /></div>
                  <span className="fb-icon">Techplanet</span>
                </a>
                <a href="https://www.facebook.com/profile.php?id=61584899039203" target="_blank" rel="noreferrer" className="fb-trapdoor">
                  <div className="fb-door fb-door-top"><img src="/facebook-f.svg" className="fb-f-img" alt="" /></div>
                  <div className="fb-door fb-door-bottom"><img src="/facebook-f.svg" className="fb-f-img" alt="" /></div>
                  <span className="fb-icon">Protsecoop</span>
                </a>
                <a href="https://www.facebook.com/profile.php?id=61586640354662" target="_blank" rel="noreferrer" className="fb-trapdoor">
                  <div className="fb-door fb-door-top"><img src="/facebook-f.svg" className="fb-f-img" alt="" /></div>
                  <div className="fb-door fb-door-bottom"><img src="/facebook-f.svg" className="fb-f-img" alt="" /></div>
                  <span className="fb-icon">Carsecoop</span>
                </a>
              </div>
            </div>

            <div className="lr-divider" />
            <p className="lr-copyright">Copyright © 2026 — "BBC File" Todos los derechos reservados</p>
          </div>
        </div>
      </div>
    </>
  );
}
