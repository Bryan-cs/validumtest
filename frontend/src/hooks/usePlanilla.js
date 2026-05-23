import { useQuery } from '@tanstack/react-query';
import api from '../utils/api';

/** Cálculo de planilla SS desde el backend (fuente única de verdad). */
export default function usePlanilla(afiliado, dias) {
  const id = afiliado?.id;
  const d = Math.min(30, Math.max(0, Number(dias) || 0));
  return useQuery({
    queryKey: ['calc-planilla', id, d],
    queryFn: async () => {
      const r = await api.get('/facturas/calc-planilla', {
        params: { afiliado_id: id, dias: d },
      });
      return r.data?.detalle ?? [];
    },
    enabled: !!id,
    staleTime: 0,
    placeholderData: [],
  });
}
