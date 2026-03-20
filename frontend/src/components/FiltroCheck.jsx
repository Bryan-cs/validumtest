import React, { useState, useRef, useEffect } from 'react';
import { C } from './UI';

export default function FiltroCheck({ label, options = [], selected = [], onChange, icon = '🔽' }) {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState('');
    const ref = useRef(null);

    useEffect(() => {
        const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const filtered = options.filter(o => o.toLowerCase().includes(search.toLowerCase()));
    const allSelected = selected.length === 0;
    const count = selected.length;
    const toggle = (val) => { if (selected.includes(val)) onChange(selected.filter(v => v !== val)); else onChange([...selected, val]); };
    const toggleAll = () => onChange([]);

    return (
        <div ref={ref} style={{ position: 'relative', userSelect: 'none' }}>
            <button onClick={() => setOpen(!open)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', border: `2px solid ${count > 0 ? C.primary : C.border}`, borderRadius: 8, background: count > 0 ? C.blueBg : '#fff', color: count > 0 ? C.primary : C.text, cursor: 'pointer', fontSize: 13, fontWeight: count > 0 ? 700 : 400, whiteSpace: 'nowrap', transition: 'all .15s', boxShadow: open ? `0 0 0 3px ${C.primary}22` : 'none' }}>
                <span style={{ fontSize: 12 }}>{icon}</span>
                <span>{label}</span>
                {count > 0 && <span style={{ background: C.primary, color: '#fff', borderRadius: 10, padding: '1px 7px', fontSize: 11, fontWeight: 700 }}>{count}</span>}
                <span style={{ fontSize: 10, color: C.text2, marginLeft: 2 }}>{open ? '▲' : '▼'}</span>
            </button>
            {open && (
                <div style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 500, background: '#fff', border: `1px solid ${C.border}`, borderRadius: 10, boxShadow: '0 8px 30px rgba(0,0,0,.15)', minWidth: 220, maxWidth: 280, overflow: 'hidden' }}>
                    {options.length > 6 && (
                        <div style={{ padding: '8px 10px', borderBottom: `1px solid ${C.border}` }}>
                            <input autoFocus placeholder="Buscar..." value={search} onChange={e => setSearch(e.target.value)}
                                style={{ width: '100%', padding: '6px 10px', border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12, outline: 'none', boxSizing: 'border-box' }} />
                        </div>
                    )}
                    <div onClick={toggleAll} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', cursor: 'pointer', background: allSelected ? C.blueBg : '#fff', borderBottom: `1px solid ${C.border}` }}>
                        <div style={{ width: 16, height: 16, borderRadius: 4, border: `2px solid ${allSelected ? C.primary : C.border}`, background: allSelected ? C.primary : '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            {allSelected && <span style={{ color: '#fff', fontSize: 10, fontWeight: 700 }}>✓</span>}
                        </div>
                        <span style={{ fontSize: 13, fontWeight: 600, color: allSelected ? C.primary : C.text }}>Todos</span>
                    </div>
                    <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                        {filtered.length === 0 && <div style={{ padding: '10px 12px', fontSize: 12, color: C.text2 }}>Sin resultados</div>}
                        {filtered.map(opt => {
                            const isChecked = selected.includes(opt);
                            return (
                                <div key={opt} onClick={() => toggle(opt)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', cursor: 'pointer', background: isChecked ? C.blueBg : '#fff', borderBottom: `1px solid ${C.border}`, transition: 'background .1s' }}>
                                    <div style={{ width: 16, height: 16, borderRadius: 4, border: `2px solid ${isChecked ? C.primary : C.border}`, background: isChecked ? C.primary : '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                        {isChecked && <span style={{ color: '#fff', fontSize: 10, fontWeight: 700 }}>✓</span>}
                                    </div>
                                    <span style={{ fontSize: 13, color: isChecked ? C.primary : C.text, fontWeight: isChecked ? 600 : 400 }}>{opt}</span>
                                </div>
                            );
                        })}
                    </div>
                    {count > 0 && (
                        <div style={{ padding: '8px 12px', borderTop: `1px solid ${C.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: 11, color: C.text2 }}>{count} seleccionado{count > 1 ? 's' : ''}</span>
                            <button onClick={toggleAll} style={{ fontSize: 11, color: C.red, background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Limpiar</button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export function BarraFiltros({ filtros = [], valores = {}, onChange, onLimpiar }) {
    const totalActivos = Object.values(valores).flat().length;
    return (
        <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 10, padding: '12px 16px', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: C.text2, whiteSpace: 'nowrap' }}>🔍 Filtrar por:</span>
                {filtros.map(f => (
                    <FiltroCheck key={f.key} label={f.label} icon={f.icon} options={f.options}
                        selected={valores[f.key] || []} onChange={vals => onChange(f.key, vals)} />
                ))}
                {totalActivos > 0 && (
                    <button onClick={onLimpiar} style={{ marginLeft: 'auto', background: 'none', border: `1px solid ${C.border}`, borderRadius: 7, padding: '7px 14px', fontSize: 12, color: C.text2, cursor: 'pointer' }}>
                        ✕ Limpiar todo
                    </button>
                )}
            </div>
            {totalActivos > 0 && (
                <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                    {filtros.map(f => (valores[f.key] || []).map(v => (
                        <span key={f.key + v} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: C.blueBg, color: C.blue, border: `1px solid ${C.blue}`, borderRadius: 20, padding: '3px 10px', fontSize: 11, fontWeight: 600 }}>
                            <span style={{ opacity: .7 }}>{f.label}:</span> {v}
                            <button onClick={() => onChange(f.key, (valores[f.key] || []).filter(x => x !== v))}
                                style={{ background: 'none', border: 'none', color: C.blue, cursor: 'pointer', fontSize: 13, padding: 0, lineHeight: 1 }}>×</button>
                        </span>
                    )))}
                </div>
            )}
        </div>
    );
}