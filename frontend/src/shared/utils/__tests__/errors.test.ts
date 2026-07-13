import { describe, expect, it } from 'vitest';

import { errorMessage } from '../errors';

describe('errorMessage', () => {
  it('returns the message from Error instances', () => {
    expect(errorMessage(new Error('request failed'))).toBe('request failed');
  });

  it('normalizes non-Error values to strings', () => {
    expect(errorMessage('request failed')).toBe('request failed');
    expect(errorMessage(404)).toBe('404');
    expect(errorMessage(null)).toBe('null');
  });
});
