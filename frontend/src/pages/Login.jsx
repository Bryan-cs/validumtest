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
      login(data.access_token, { username: data.username, nombre: data.nombre, rol: data.rol, cliente_ref: data.cliente_ref }, data.refresh_token);
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
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; }

        .lr { min-height: 100vh; display: flex; font-family: 'DM Sans', sans-serif; }

        /* ── LEFT BRAND PANEL ── */
        .lr-brand {
          width: 44%;
          background: #071E3D;
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
            linear-gradient(rgba(232,155,42,.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(232,155,42,.05) 1px, transparent 1px);
          background-size: 44px 44px;
        }
        .lr-brand::after {
          content: '';
          position: absolute;
          right: -100px; top: -100px;
          width: 380px; height: 380px;
          border: 1.5px solid rgba(232,155,42,.15);
          border-radius: 50%;
        }
        .lr-circle2 {
          position: absolute;
          right: -40px; top: -40px;
          width: 220px; height: 220px;
          border: 1px solid rgba(232,155,42,.08);
          border-radius: 50%;
        }
        .lr-circle3 {
          position: absolute;
          left: -60px; bottom: 80px;
          width: 180px; height: 180px;
          border: 1px solid rgba(232,155,42,.07);
          border-radius: 50%;
        }
        .lr-top { position: relative; z-index: 1; }
        .lr-badge {
          display: inline-flex; align-items: center; gap: 7px;
          border: 1px solid rgba(232,155,42,.3);
          border-radius: 3px;
          padding: 5px 13px;
          margin-bottom: 44px;
          font-size: 10.5px; letter-spacing: 2.8px;
          text-transform: uppercase;
          color: #E89B2A; font-weight: 600;
        }
        .lr-badge-dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: #E89B2A;
          animation: lr-blink 2s ease-in-out infinite;
        }
        @keyframes lr-blink {
          0%, 100% { opacity: 1; } 50% { opacity: .3; }
        }
        .lr-wordmark {
          font-family: 'Playfair Display', serif;
          font-size: 78px; font-weight: 900;
          line-height: .88; color: #fff;
          margin: 0; letter-spacing: -3px;
        }
        .lr-wordmark em {
          color: #E89B2A; font-style: normal; display: block;
        }
        .lr-tagline {
          margin: 22px 0 0;
          font-size: 13px; color: rgba(255,255,255,.38);
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
          font-size: 12.5px; color: rgba(255,255,255,.42); font-weight: 300;
        }
        .lr-features li::before {
          content: '';
          width: 20px; height: 1px;
          background: linear-gradient(90deg, #E89B2A, transparent);
          flex-shrink: 0;
        }

        /* ── RIGHT FORM PANEL ── */
        .lr-form-panel {
          flex: 1;
          background: #F5F7FB;
          display: flex; align-items: center; justify-content: center;
          padding: 48px 56px;
          position: relative;
        }
        .lr-form-panel::before {
          content: '';
          position: absolute; inset: 0;
          background-image: radial-gradient(circle, rgba(13,59,110,.055) 1px, transparent 1px);
          background-size: 26px 26px;
        }
        .lr-card {
          width: 100%; max-width: 390px;
          position: relative; z-index: 1;
        }
        .lr-eyebrow {
          font-size: 12px; letter-spacing: 2.8px;
          text-transform: uppercase;
          color: #E89B2A; font-weight: 600; margin-bottom: 8px;
        }
        .lr-heading {
          font-family: 'Playfair Display', serif;
          font-size: 38px; font-weight: 700;
          color: #071E3D; margin: 0 0 6px; line-height: 1.1;
        }
        .lr-sub {
          font-size: 15px; color: #94A3B8;
          margin: 0 0 38px; font-weight: 300;
        }
        .lr-field { margin-bottom: 22px; }
        .lr-label {
          display: block;
          font-size: 12.5px; font-weight: 600;
          color: #475569; margin-bottom: 7px;
          letter-spacing: .8px; text-transform: uppercase;
        }
        .lr-input-wrap { position: relative; }
        .lr-input {
          width: 100%;
          padding: 13px 16px;
          border: 1.5px solid #DDE3EF;
          border-radius: 10px;
          font-size: 16px;
          font-family: 'DM Sans', sans-serif;
          color: #0F172A; background: #fff;
          outline: none;
          transition: border-color .18s, box-shadow .18s;
        }
        .lr-input:focus {
          border-color: #0D3B6E;
          box-shadow: 0 0 0 4px rgba(13,59,110,.09);
        }
        .lr-input::placeholder { color: #C1CBDB; }
        .lr-eye {
          position: absolute; right: 14px; top: 50%;
          transform: translateY(-50%);
          background: none; border: none; cursor: pointer;
          color: #94A3B8; padding: 4px;
          display: flex; align-items: center;
          font-size: 15px; line-height: 1;
          transition: color .15s;
        }
        .lr-eye:hover { color: #475569; }
        .lr-btn {
          width: 100%; padding: 14px;
          margin-top: 6px;
          background: linear-gradient(90deg, #E89B2A 50%, #0D3B6E 50%);
          background-size: 200% 100%;
          background-position: right center;
          color: #fff;
          border: 1.5px solid transparent;
          border-radius: 10px;
          font-size: 16px; font-weight: 600;
          font-family: 'DM Sans', sans-serif;
          cursor: pointer; letter-spacing: .3px;
          position: relative; overflow: hidden;
          transition: background-position 0.4s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s;
        }
        .lr-btn::after {
          width: 0; left: 50%;
          height: 100%;
          position: absolute;
          top: 0;
          border-top: 1.5px solid transparent;
          border-bottom: 1.5px solid transparent;
          transform: translate(-50%, 0);
          transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
          content: "";
        }
        .lr-btn:hover:not(:disabled) {
          background-position: left center;
          color: #071E3D;
        }
        .lr-btn:hover:not(:disabled)::after {
          width: 100%;
          border-color: #E89B2A;
          transition-delay: 0.15s;
        }
        .lr-btn:active:not(:disabled) {
          background-position: right center;
          color: #fff;
          transition: all 0.1s;
        }
        .lr-btn:active:not(:disabled)::after {
          border-color: transparent;
          width: 0;
          transition: all 0.1s;
        }
        .lr-btn:disabled { opacity: .6; cursor: not-allowed; }
        .lr-divider {
          display: flex; align-items: center; gap: 12px;
          margin: 28px 0 0;
        }
        .lr-divider span {
          flex: 1; height: 1px; background: #E8EDF5;
        }
        .lr-divider p {
          font-size: 11px; color: #C1CBDB;
          letter-spacing: .5px; margin: 0;
        }
        /* ── SOCIAL ── */
        .lr-social { margin-top: 24px; text-align: center; }
        .lr-social-label {
          font-size: 12px; letter-spacing: 2px;
          text-transform: uppercase;
          color: #1877F2; font-weight: 600; margin: 0 0 12px;
        }
        .lr-social-row { display: flex; justify-content: center; gap: 10px; }

        .fb-trapdoor {
          position: relative;
          width: 108px; height: 44px;
          overflow: hidden;
          background: #fff;
          border-radius: 10px;
          box-shadow: inset -6px 0 12px -8px rgba(0,0,0,.35), inset 6px 0 12px -8px rgba(0,0,0,.35);
          transition: background 400ms ease-in-out;
          text-decoration: none;
          display: inline-flex; align-items: center; justify-content: center;
          cursor: pointer;
        }
        .fb-trapdoor:hover .fb-door {
          box-shadow: 0 0 10px -2px rgba(0,0,0,.3);
          transform: scale(1.06);
        }
        .fb-trapdoor:hover .fb-door-top    { top: -50%; }
        .fb-trapdoor:hover .fb-door-bottom { top: 100%; }

        .fb-door {
          position: absolute; left: 0;
          width: 100%; height: 50%;
          background: #0D3B6E;
          overflow: hidden;
          z-index: 2;
          transition: top 400ms ease-in-out, box-shadow 200ms ease-in-out, transform 300ms ease-in-out;
          transition-timing-function: ease-in-out;
        }
        .fb-door-top    { top: 0; }
        .fb-door-bottom { top: 50%; }

        /* logo Facebook split entre las dos mitades de la puerta.
           El ícono mide 22px de alto, centrado en los 44px totales:
           offset = (44 - 22) / 2 = 11px
           Top door:    image.top = 11px  → visible 11–22px (top half)
           Bottom door: image.top = -11px → visible 0–11px  (bottom half) */
        .fb-f-img {
          position: absolute;
          height: 22px;
          width: auto;
          display: block;
          left: 50%;
          transform: translateX(-50%);
          top: 11px;
          pointer-events: none;
        }
        .fb-door-bottom .fb-f-img { top: -11px; }

        /* nombre revelado cuando las puertas abren */
        .fb-icon {
          position: relative; z-index: 1;
          color: #1877F2; font-size: 13px;
          font-weight: 700;
          font-family: 'DM Sans', sans-serif;
          letter-spacing: .3px;
          text-align: center;
          line-height: 1;
        }

        .lr-copyright {
          margin-top: 18px; text-align: center;
          font-size: 13.5px; color: #1877F2; letter-spacing: .3px;
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
            <div className="lr-badge">
              <span className="lr-badge-dot" />
              Sistema activo
            </div>
            <h1 className="lr-wordmark">
              BBC
              <em>File</em>
            </h1>
            <p className="lr-tagline">
              Plataforma integral de gestión de personal y seguridades sociales.
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

            <p className="lr-copyright">Copyright © 2026 — "BBC File" Todos los derechos reservados</p>
          </div>
        </div>
      </div>
    </>
  );
}
