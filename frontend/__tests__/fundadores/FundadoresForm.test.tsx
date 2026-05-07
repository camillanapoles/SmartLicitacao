/**
 * Issue #786: FundadoresForm tests
 *
 * Covers email validation, submit payload, checkout redirect, and
 * availability-gate behavior.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import FundadoresForm from '../../app/fundadores/components/FundadoresForm';

function fillValidEmail() {
  fireEvent.change(screen.getByLabelText(/Seu email/i), {
    target: { value: 'maria@empresa.com' },
  });
}

describe('FundadoresForm', () => {
  const originalLocation = window.location;
  const hrefSetter = jest.fn();

  beforeEach(() => {
    jest.restoreAllMocks();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        assign: jest.fn(),
        set href(v: string) {
          hrefSetter(v);
        },
        get href() {
          return 'http://testhost/fundadores';
        },
      },
    });
    hrefSetter.mockClear();
    (global.fetch as unknown as jest.Mock) = jest.fn();
  });

  afterAll(() => {
    Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
  });

  it('renders email field and CTA button', () => {
    render(<FundadoresForm />);
    expect(screen.getByLabelText(/Seu email/i)).toBeInTheDocument();
    expect(screen.getByTestId('fundadores-form-submit')).toBeInTheDocument();
  });

  it('shows "Garantir acesso" in the CTA text by default', () => {
    render(<FundadoresForm />);
    expect(screen.getByTestId('fundadores-form-submit').textContent).toMatch(/Garantir acesso/i);
  });

  it('surfaces validation error for invalid email', async () => {
    render(<FundadoresForm />);
    fireEvent.change(screen.getByLabelText(/Seu email/i), { target: { value: 'nao-um-email' } });
    fireEvent.submit(screen.getByTestId('fundadores-form-submit').closest('form')!);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/email válido/i);
  });

  it('posts email to /api/founding/checkout and redirects on success', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ checkout_url: 'https://checkout.stripe.com/xyz', lead_id: 'lead-2' }),
    });

    render(<FundadoresForm />);
    fillValidEmail();
    fireEvent.submit(screen.getByTestId('fundadores-form-submit').closest('form')!);

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const [url, opts] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('/api/founding/checkout');
    const body = JSON.parse((opts as { body: string }).body);
    expect(body.email).toBe('maria@empresa.com');
    // Simplified form — no cnpj, nome, motivo in payload
    expect(body.cnpj).toBeUndefined();
    expect(body.nome).toBeUndefined();

    await waitFor(() =>
      expect(hrefSetter).toHaveBeenCalledWith('https://checkout.stripe.com/xyz')
    );
  });

  it('surfaces backend error message on non-2xx', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Este email já possui conta SmartLic.' }),
    });

    render(<FundadoresForm />);
    fillValidEmail();
    fireEvent.submit(screen.getByTestId('fundadores-form-submit').closest('form')!);

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/já possui conta/i);
    expect(hrefSetter).not.toHaveBeenCalled();
  });

  it('surfaces generic network error when fetch rejects', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('net down'));

    render(<FundadoresForm />);
    fillValidEmail();
    fireEvent.submit(screen.getByTestId('fundadores-form-submit').closest('form')!);

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/falha de rede/i);
  });

  it('uses custom price prop in button text', () => {
    render(<FundadoresForm price="R$1.200" />);
    expect(screen.getByTestId('fundadores-form-submit').textContent).toMatch(/R\$1\.200/);
  });

  describe('availability gate', () => {
    const FULL_SNAPSHOT = {
      available: false,
      seats_total: 50,
      seats_remaining: 0,
      seats_taken: 50,
      deadline_at: null,
      paused: false,
      reason: 'founding_cap_reached',
      coupon_code: 'FOUNDING_LIFETIME',
      discount_pct: 0,
    };

    it('disables submit and shows cap message when availability says full', () => {
      render(<FundadoresForm availability={FULL_SNAPSHOT} />);
      const btn = screen.getByTestId('fundadores-form-submit') as HTMLButtonElement;
      expect(btn).toBeDisabled();
      expect(btn.textContent).toMatch(/programa fechado/i);
      expect(screen.getByTestId('fundadores-form-unavailable').textContent).toMatch(/vagas fundadores/i);
    });

    it('keeps button enabled when availability.available=true', () => {
      const open = { ...FULL_SNAPSHOT, available: true, seats_remaining: 25, reason: 'available' };
      render(<FundadoresForm availability={open} />);
      const btn = screen.getByTestId('fundadores-form-submit') as HTMLButtonElement;
      expect(btn).not.toBeDisabled();
      expect(btn.textContent).toMatch(/Garantir acesso/i);
    });
  });
});
