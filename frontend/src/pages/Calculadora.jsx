import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, Btn, PageHeader } from '../components/UI';

const MESES_ES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

const tdc = { padding:'10px 12px', fontSize:13, color:C.text, verticalAlign:'middle' };
const lbl = { display:'block', fontSize:12, color:C.text2, fontWeight:500, marginBottom:4 };
const inp = { width:'100%', padding:'9px 12px', border:`1px solid ${C.border}`, borderRadius:7, fontSize:13, outline:'none', boxSizing:'border-box', color:C.text, background:C.surface };

const PLANTILLA_DEFAULT =
`{{saludo}}!.
Señor@: {{nombre}}

 Estimado cliente;
Reciban un cordial saludo, por parte de CARSECOOP Y COOPERATIVA DE SERVICIOS GLOBALES TECHCOOP, identificado con Nit 901921756, por parte de Carsecoop le deseamos un excelente día.

Recordatorio de pago de su seguridad social del mes de {{mes}} {{anio}}, agradecemos su pago oportuno.

Fecha Emisión: {{fecha_emision}}
{{vencimiento}}
TOTAL: \${{total}}
{{servicios}}
*Medios de pago:*
-Nequi: 3170296773
-Daviplata: 3170296773
-Davivienda (Ahorros): 0550108900642357
-Banco de Bogotá (Ahorros): 462547688
-Llave Banco Bogotá: @BBJMF23103
-Bancolombia (Ahorros): 91270274485`;

export default function Calculadora() {
  const qc = useQueryClient();
  const { data: cfg={} } = useQuery({ queryKey:['config'], queryFn:()=>api.get('/config').then(r=>r.data), staleTime: 300_000 });
  const [ibc, setIbc] = useState('');
  const [pcts, setPcts] = useState({});
  const [plantilla, setPlantilla] = useState('');
  const [cargoAdicional, setCargoAdicional] = useState(2200);
  const [mesCobro, setMesCobro] = useState('');
  const [anioCobro, setAnioCobro] = useState('');

  useEffect(()=>{
    if(cfg.ibc_global) setIbc(cfg.ibc_global);
    if(cfg.porcentajes) setPcts({...cfg.porcentajes});
    if(cfg.plantilla_whatsapp !== undefined) setPlantilla(cfg.plantilla_whatsapp || PLANTILLA_DEFAULT);
    if(cfg.cargo_adicional !== undefined) setCargoAdicional(cfg.cargo_adicional ?? 2200);
    if(cfg.mes_inicio_cobro) setMesCobro(cfg.mes_inicio_cobro);
    if(cfg.anio_inicio_cobro) setAnioCobro(cfg.anio_inicio_cobro);
  },[cfg]);

  const guardar = useMutation({
    mutationFn:()=>api.put('/config',{ ibc_global:+ibc, porcentajes:pcts, plantilla_whatsapp:plantilla, cargo_adicional:+cargoAdicional, mes_inicio_cobro: mesCobro?+mesCobro:null, anio_inicio_cobro: anioCobro?+anioCobro:null }),
    onSuccess:(res)=>{ toast.success('Configuración actualizada'); qc.setQueryData(['config'], res.data); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error en la operación'),
  });

  const ibcN = +ibc || 0;
  const ceil100 = v => Math.ceil(v/100)*100;

  return (
    <div>
      <PageHeader title="🧮 Calculadora de aportes" subtitle="Configura IBC global y porcentajes" />
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <label style={{ ...lbl,fontSize:13 }}>IBC Global (Salario mínimo / base de cotización)</label>
        <input type="number" style={{ ...inp,width:240 }} value={ibc} onChange={e=>setIbc(e.target.value)} />
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <label style={{ ...lbl,fontSize:13 }}>Cargo adicional por impuestos (planilla)</label>
        <p style={{ margin:'0 0 10px',fontSize:12,color:C.text2 }}>Se suma al costo de planilla en cada factura. Editable individualmente por factura.</p>
        <input type="number" style={{ ...inp,width:240 }} value={cargoAdicional} onChange={e=>setCargoAdicional(e.target.value)} />
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <h3 style={{ margin:'0 0 16px',color:C.primary }}>Porcentajes de aporte</h3>
        <table style={{ width:'100%',borderCollapse:'collapse' }}>
          <thead><tr style={{ background:C.surface2 }}>
            {['Servicio','Porcentaje (%)','Valor 30 días','Valor 15 días'].map(h=>(
              <th key={h} style={{ padding:'9px 12px',textAlign:'left',fontSize:11,fontWeight:600,color:C.text2,borderBottom:`1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {Object.entries(pcts).map(([srv, pct])=>{
              const v30 = ceil100(ibcN * pct);
              const v15 = ceil100(ibcN * pct / 2);
              return (
                <tr key={srv} style={{ borderBottom:`1px solid ${C.border}` }}>
                  <td style={{ ...tdc,fontWeight:500 }}>{srv}</td>
                  <td style={tdc}>
                    <input type="number" step="0.001" style={{ ...inp,width:120 }}
                      value={(pct*100).toFixed(4)}
                      onChange={e=>setPcts(p=>({...p,[srv]:+e.target.value/100}))} />
                  </td>
                  <td style={{ ...tdc,textAlign:'right',color:C.red,fontWeight:600 }}>
                    $ {v30.toLocaleString('es-CO')}
                  </td>
                  <td style={{ ...tdc,textAlign:'right',color:C.amber,fontWeight:600 }}>
                    $ {v15.toLocaleString('es-CO')}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <h3 style={{ margin:'0 0 8px',color:C.primary }}>Plantilla mensaje WhatsApp</h3>
        <p style={{ margin:'0 0 12px',fontSize:12,color:C.text2 }}>
          Variables disponibles: <code>{'{{saludo}}'}</code> <code>{'{{nombre}}'}</code> <code>{'{{mes}}'}</code> <code>{'{{anio}}'}</code> <code>{'{{fecha_emision}}'}</code> <code>{'{{vencimiento}}'}</code> <code>{'{{total}}'}</code> <code>{'{{servicios}}'}</code>
        </p>
        <textarea
          rows={20}
          style={{ ...inp, fontFamily:'monospace', fontSize:12, resize:'vertical', whiteSpace:'pre' }}
          value={plantilla}
          onChange={e=>setPlantilla(e.target.value)}
        />
        <Btn size="sm" variant="secondary" style={{ marginTop:8 }} onClick={()=>setPlantilla(PLANTILLA_DEFAULT)}>
          Restaurar plantilla por defecto
        </Btn>
      </div>
      <div style={{ background:C.surface,borderRadius:10,border:`1px solid ${C.border}`,padding:24,marginBottom:20 }}>
        <h3 style={{ margin:'0 0 6px',color:C.primary }}>Fecha de inicio del módulo de cobro</h3>
        <p style={{ margin:'0 0 14px',fontSize:12,color:C.text2 }}>El módulo de cobro solo mostrará recordatorios a partir de este mes. Meses anteriores serán ignorados aunque el afiliado tenga deuda sin factura.</p>
        <div style={{ display:'flex',gap:10,alignItems:'center',flexWrap:'wrap' }}>
          <div>
            <label style={lbl}>Mes</label>
            <select style={{ ...inp,width:150 }} value={mesCobro} onChange={e=>setMesCobro(e.target.value)}>
              <option value="">Sin límite</option>
              {MESES_ES.map((m,i)=><option key={i+1} value={i+1}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año</label>
            <input type="number" style={{ ...inp,width:110 }} placeholder="ej: 2026" value={anioCobro} onChange={e=>setAnioCobro(e.target.value)} />
          </div>
        </div>
      </div>
      <Btn onClick={()=>guardar.mutate()} disabled={guardar.isPending}>
        {guardar.isPending?'Guardando...':'💾 Guardar configuración'}
      </Btn>
    </div>
  );
}
