import { describe, expect, it } from 'vitest';
import { tokenDeSesion } from './sesion';

describe('tokenDeSesion', () => {
  it('devuelve el access token guardado', () => {
    const raw = JSON.stringify({ state: { token: 'abc' } });
    expect(tokenDeSesion(raw)).toBe('abc');
  });

  it('devuelve vacío si el JSON está roto o no hay token', () => {
    expect(tokenDeSesion('')).toBe('');
    expect(tokenDeSesion('{')).toBe('');
    expect(tokenDeSesion(JSON.stringify({ state: {} }))).toBe('');
  });
});
