import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading,  setLoading]  = useState(false);
  const { login }  = useAuthStore();
  const navigate   = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) { toast.error('Completa usuario y contraseña'); return; }
    setLoading(true);
    try {
      const { data } = await api.post('/auth/login', { username, password });
      login(data.access_token, { username: data.username, nombre: data.nombre, rol: data.rol });
      navigate('/');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center',
      background:'linear-gradient(135deg,#0D3B6E 0%,#185FA5 100%)' }}>
      <div style={{ background:'#fff', borderRadius:16, padding:'40px 36px', width:360,
        boxShadow:'0 20px 60px rgba(0,0,0,.25)' }}>
        <h1 style={{ margin:'0 0 4px', fontSize:28, fontWeight:700, color:'#0D3B6E', textAlign:'center' }}>
          BBC <span style={{ color:'#E89B2A' }}>File</span>
        </h1>
        <p style={{ margin:'0 0 28px', textAlign:'center', color:'#64748b', fontSize:13 }}>
          Gestión de Personal — Seguridades Sociales
        </p>
        <form onSubmit={handleSubmit}>
          <label style={lbl}>Usuario</label>
          <input style={inp} value={username} onChange={e=>setUsername(e.target.value)}
            placeholder="tu_usuario" autoFocus />
          <label style={lbl}>Contraseña</label>
          <input style={inp} type="password" value={password} onChange={e=>setPassword(e.target.value)}
            placeholder="••••••••" />
          <button type="submit" disabled={loading} style={{
            width:'100%', padding:'12px', marginTop:8, background:'#0D3B6E',
            color:'#fff', border:'none', borderRadius:8, fontSize:15,
            fontWeight:600, cursor: loading?'not-allowed':'pointer',
            opacity: loading ? 0.7 : 1,
          }}>
            {loading ? 'Ingresando...' : 'Ingresar al sistema'}
          </button>
        </form>
      </div>
    </div>
  );
}
const lbl = { display:'block', fontSize:12, color:'#475569', fontWeight:500, marginBottom:4, marginTop:14 };
const inp = { width:'100%', padding:'10px 12px', border:'1px solid #CBD5E1', borderRadius:7,
  fontSize:14, outline:'none', boxSizing:'border-box', color:'#1e293b' };
