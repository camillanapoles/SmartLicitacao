/**
 * SEO-PROG-008: Tests for getBackendUrl chain fallback helper.
 */
import { getBackendUrl } from '../../lib/backend-url';

describe('getBackendUrl (SEO-PROG-008)', () => {
  const originalBackendUrl = process.env.BACKEND_URL;
  const originalPublicBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

  afterEach(() => {
    if (originalBackendUrl === undefined) {
      delete process.env.BACKEND_URL;
    } else {
      process.env.BACKEND_URL = originalBackendUrl;
    }
    if (originalPublicBackendUrl === undefined) {
      delete process.env.NEXT_PUBLIC_BACKEND_URL;
    } else {
      process.env.NEXT_PUBLIC_BACKEND_URL = originalPublicBackendUrl;
    }
  });

  it('returns BACKEND_URL when set', () => {
    process.env.BACKEND_URL = 'https://api.smartlic.tech';
    process.env.NEXT_PUBLIC_BACKEND_URL = 'https://public.example.com';
    expect(getBackendUrl()).toBe('https://api.smartlic.tech');
  });

  it('falls back to NEXT_PUBLIC_BACKEND_URL when BACKEND_URL undefined', () => {
    delete process.env.BACKEND_URL;
    process.env.NEXT_PUBLIC_BACKEND_URL = 'https://public.example.com';
    expect(getBackendUrl()).toBe('https://public.example.com');
  });

  it('falls back to NEXT_PUBLIC_BACKEND_URL when BACKEND_URL empty', () => {
    process.env.BACKEND_URL = '';
    process.env.NEXT_PUBLIC_BACKEND_URL = 'https://public.example.com';
    expect(getBackendUrl()).toBe('https://public.example.com');
  });

  it('falls back to http://localhost:8000 when both undefined', () => {
    delete process.env.BACKEND_URL;
    delete process.env.NEXT_PUBLIC_BACKEND_URL;
    expect(getBackendUrl()).toBe('http://localhost:8000');
  });

  it('falls back to http://localhost:8000 when both empty', () => {
    process.env.BACKEND_URL = '';
    process.env.NEXT_PUBLIC_BACKEND_URL = '';
    expect(getBackendUrl()).toBe('http://localhost:8000');
  });
});
