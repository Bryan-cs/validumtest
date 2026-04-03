import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
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
          font-size: 10.5px; letter-spacing: 2.8px;
          text-transform: uppercase;
          color: #E89B2A; font-weight: 600; margin-bottom: 8px;
        }
        .lr-heading {
          font-family: 'Playfair Display', serif;
          font-size: 34px; font-weight: 700;
          color: #071E3D; margin: 0 0 6px; line-height: 1.1;
        }
        .lr-sub {
          font-size: 13px; color: #94A3B8;
          margin: 0 0 38px; font-weight: 300;
        }
        .lr-field { margin-bottom: 22px; }
        .lr-label {
          display: block;
          font-size: 11px; font-weight: 600;
          color: #475569; margin-bottom: 7px;
          letter-spacing: .8px; text-transform: uppercase;
        }
        .lr-input-wrap { position: relative; }
        .lr-input {
          width: 100%;
          padding: 13px 16px;
          border: 1.5px solid #DDE3EF;
          border-radius: 10px;
          font-size: 14.5px;
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
          background: #0D3B6E;
          color: #fff; border: none;
          border-radius: 10px;
          font-size: 14.5px; font-weight: 600;
          font-family: 'DM Sans', sans-serif;
          cursor: pointer; letter-spacing: .3px;
          position: relative; overflow: hidden;
          transition: background .2s, transform .15s, box-shadow .2s;
        }
        .lr-btn:hover:not(:disabled) {
          background: #0A2E57;
          transform: translateY(-1px);
          box-shadow: 0 8px 24px rgba(13,59,110,.28);
        }
        .lr-btn:active:not(:disabled) { transform: translateY(0); }
        .lr-btn:disabled { opacity: .6; cursor: not-allowed; transform: none; }
        .lr-btn-shine {
          position: absolute; inset: 0;
          background: linear-gradient(105deg, transparent 35%, rgba(255,255,255,.14) 50%, transparent 65%);
          animation: lr-shine 3s infinite;
        }
        @keyframes lr-shine {
          0%   { transform: translateX(-100%); }
          20%  { transform: translateX(160%); }
          100% { transform: translateX(160%); }
        }
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
        .lr-footer {
          margin-top: 28px; text-align: center;
          font-size: 11.5px; color: #C1CBDB; letter-spacing: .2px;
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
                {!loading && <span className="lr-btn-shine" />}
                {loading ? 'Verificando…' : 'Ingresar al sistema'}
              </button>
            </form>

            <div className="lr-divider">
              <span /><p>BBC File · Colombia</p><span />
            </div>

            <p className="lr-footer">Gestión de Personal — Seguridades Sociales</p>
          </div>
        </div>
      </div>
    </>
  );
}
