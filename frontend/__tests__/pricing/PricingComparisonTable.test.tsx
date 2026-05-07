/**
 * Tests for PricingComparisonTable component (#789)
 *
 * Covers:
 * - Column collapse when available=false
 * - Fail-open on API error (renders without Founders column)
 * - Deadline formatting
 * - CTA links present
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import PricingComparisonTable from '../../components/pricing/PricingComparisonTable';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetchSuccess(data: object) {
  global.fetch = jest.fn().mockResolvedValueOnce({
    ok: true,
    json: async () => data,
  });
}

function mockFetchError() {
  global.fetch = jest.fn().mockRejectedValueOnce(new Error('network error'));
}

function mockFetchNotOk() {
  global.fetch = jest.fn().mockResolvedValueOnce({
    ok: false,
    json: async () => ({}),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PricingComparisonTable', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Founders column visibility', () => {
    it('shows Founders column by default (before fetch resolves)', () => {
      // Mock fetch that never resolves so we see the initial state
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable />);

      expect(screen.getByText('Plano Fundadores')).toBeInTheDocument();
    });

    it('shows Founders column when available=true', async () => {
      mockFetchSuccess({
        available: true,
        seats_remaining: 5,
        deadline_at: '2026-06-30T23:59:59Z',
      });

      render(<PricingComparisonTable />);

      await waitFor(() => {
        expect(screen.getByText('Plano Fundadores')).toBeInTheDocument();
      });
    });

    it('collapses Founders column when available=false', async () => {
      mockFetchSuccess({
        available: false,
        seats_remaining: 0,
        deadline_at: null,
      });

      render(<PricingComparisonTable />);

      await waitFor(() => {
        expect(screen.queryByText('Plano Fundadores')).not.toBeInTheDocument();
      });
    });

    it('collapses Founders column when seats_remaining=0 even if available=true', async () => {
      mockFetchSuccess({
        available: true,
        seats_remaining: 0,
        deadline_at: '2026-06-30T23:59:59Z',
      });

      render(<PricingComparisonTable />);

      await waitFor(() => {
        expect(screen.queryByText('Plano Fundadores')).not.toBeInTheDocument();
      });
    });

    it('respects showFounders=false prop override (no fetch needed)', () => {
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable showFounders={false} />);

      expect(screen.queryByText('Plano Fundadores')).not.toBeInTheDocument();
    });
  });

  describe('Fail-open on API errors', () => {
    it('keeps showing table when fetch throws a network error', async () => {
      mockFetchError();

      await act(async () => {
        render(<PricingComparisonTable />);
      });

      // Table still renders — fail-open means Founders stays visible (initial=true)
      expect(screen.getByText('Plano Fundadores')).toBeInTheDocument();
      expect(screen.getAllByText('SmartLic Pro')[0]).toBeInTheDocument();
    });

    it('keeps showing table when API returns non-ok response', async () => {
      mockFetchNotOk();

      await act(async () => {
        render(<PricingComparisonTable />);
      });

      // Non-ok treated as null — fail-open keeps initial state (Founders visible)
      expect(screen.getByText('Plano Fundadores')).toBeInTheDocument();
    });

    it('renders all Pro columns regardless of fetch outcome', async () => {
      mockFetchError();

      await act(async () => {
        render(<PricingComparisonTable />);
      });

      // Both monthly and annual columns are always present
      expect(screen.getByText('Mensal')).toBeInTheDocument();
      expect(screen.getByText('Anual')).toBeInTheDocument();
    });
  });

  describe('Deadline formatting', () => {
    it('formats ISO deadline to pt-BR dd/mm/yyyy', async () => {
      mockFetchSuccess({
        available: true,
        seats_remaining: 3,
        deadline_at: '2026-06-30T23:59:59Z',
      });

      render(<PricingComparisonTable />);

      await waitFor(() => {
        // Date is formatted as pt-BR: 30/06/2026
        expect(screen.getByText(/30\/06\/2026/)).toBeInTheDocument();
      });
    });

    it('falls back to "30/06" when deadline_at is null', () => {
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable foundersDeadline={null} />);

      expect(screen.getByText(/encerra 30\/06/)).toBeInTheDocument();
    });

    it('uses provided foundersDeadline prop as initial deadline', () => {
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable foundersDeadline="2026-05-31T23:59:59Z" />);

      expect(screen.getByText(/31\/05\/2026/)).toBeInTheDocument();
    });
  });

  describe('CTA links', () => {
    it('Founders CTA link points to /fundadores', () => {
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable />);

      const foundersLink = screen.getByRole('link', {
        name: /Garantir vitalício por R\$997/,
      });
      expect(foundersLink).toHaveAttribute('href', '/fundadores');
    });

    it('Pro Mensal CTA link points to /planos?billing=monthly', () => {
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable />);

      const links = screen.getAllByRole('link', { name: /Assinar agora/ });
      const monthlyLink = links.find(
        (l) => l.getAttribute('href') === '/planos?billing=monthly',
      );
      expect(monthlyLink).toBeDefined();
    });

    it('Pro Anual CTA link points to /planos?billing=annual', () => {
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable />);

      const links = screen.getAllByRole('link', { name: /Assinar agora/ });
      const annualLink = links.find(
        (l) => l.getAttribute('href') === '/planos?billing=annual',
      );
      expect(annualLink).toBeDefined();
    });

    it('Founders CTA is absent when column is collapsed', async () => {
      mockFetchSuccess({
        available: false,
        seats_remaining: 0,
        deadline_at: null,
      });

      render(<PricingComparisonTable />);

      await waitFor(() => {
        expect(
          screen.queryByRole('link', { name: /Garantir vitalício/ }),
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('Pricing values', () => {
    it('shows R$997 one-time for Founders (v2 lifetime model)', () => {
      global.fetch = jest.fn().mockReturnValueOnce(new Promise(() => {}));

      render(<PricingComparisonTable />);

      expect(screen.getByText(/R\$997 ÚNICO/)).toBeInTheDocument();
    });

    it('shows seats remaining when provided by API', async () => {
      mockFetchSuccess({
        available: true,
        seats_remaining: 7,
        deadline_at: null,
      });

      render(<PricingComparisonTable />);

      await waitFor(() => {
        expect(screen.getByText(/7 vagas restantes/)).toBeInTheDocument();
      });
    });

    it('uses singular "vaga restante" for 1 seat', async () => {
      mockFetchSuccess({
        available: true,
        seats_remaining: 1,
        deadline_at: null,
      });

      render(<PricingComparisonTable />);

      await waitFor(() => {
        expect(screen.getByText(/1 vaga restante/)).toBeInTheDocument();
      });
    });
  });
});
