/**
 * AdminPage Component Tests
 *
 * Tests user CRUD, plan assignment, authentication, authorization
 */

// Set backend URL before imports (required by component)
process.env.NEXT_PUBLIC_BACKEND_URL = 'http://test-backend:8000';

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { SWRConfig } from 'swr';
import AdminPage from '@/app/admin/page';

function renderWithSWR(ui: React.ReactElement) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {ui}
    </SWRConfig>
  );
}

// Mock useAuth hook
const mockUseAuth = jest.fn();

jest.mock('../../app/components/AuthProvider', () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock Next.js Link
jest.mock('next/link', () => {
  return function MockLink({ children, href }: { children: React.ReactNode; href: string }) {
    return <a href={href}>{children}</a>;
  };
});

// Mock child components with side effects (SWR, Mixpanel, etc.)
jest.mock('@/app/admin/components/LifecycleWidget', () => ({
  LifecycleWidget: () => <div data-testid="lifecycle-widget" />,
}));

jest.mock('@/app/admin/components/ABTestWidget', () => ({
  ABTestWidget: () => <div data-testid="ab-test-widget" />,
}));

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock window.confirm and window.alert
const mockConfirm = jest.fn();
const mockAlert = jest.fn();
window.confirm = mockConfirm;
window.alert = mockAlert;

// Default SWR-compatible mock responses for admin endpoints
const DEFAULT_RESPONSES: Record<string, unknown> = {
  '/api/admin/users': { users: [], total: 0 },
  '/api/status': { sources: {}, uptime_pct_30d: 99.5 },
  '/api/admin/reconciliation/history': { runs: [] },
  '/api/admin/support-sla': { avg_response_hours: 0, pending_count: 0, breached_count: 0 },
  '/api/admin/users/segments': { count_by_state: {}, total_users: 0, transitions_last_week: [], power_users: [] },
  '/api/admin/trial-metrics': { active_trials: 0, conversion_rate: 0 },
  '/api/admin/at-risk-trials': { users: [] },
};

function setupDefaultFetch(overrides: Record<string, unknown> = {}) {
  const responses = { ...DEFAULT_RESPONSES, ...overrides };
  mockFetch.mockImplementation((url: string, opts?: RequestInit) => {
    for (const [key, value] of Object.entries(responses)) {
      if (url.includes(key)) {
        if (value instanceof Error) {
          return Promise.resolve({ ok: false, status: 500 });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(value),
        });
      }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

function setupFetchWith403() {
  mockFetch.mockImplementation((url: string) => {
    if (url.includes('/api/admin/users')) {
      return Promise.resolve({ ok: false, status: 403 });
    }
    for (const [key, value] of Object.entries(DEFAULT_RESPONSES)) {
      if (url.includes(key)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(value) });
      }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

function setupFetchWithError() {
  mockFetch.mockImplementation((url: string) => {
    if (url.includes('/api/admin/users')) {
      return Promise.resolve({ ok: false, status: 500 });
    }
    for (const [key, value] of Object.entries(DEFAULT_RESPONSES)) {
      if (url.includes(key)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(value) });
      }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

describe('AdminPage Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockConfirm.mockReturnValue(true);
  });

  describe('Authentication states', () => {
    it('should show loading message during auth check', () => {
      mockUseAuth.mockReturnValue({
        session: null,
        loading: true,
      });

      renderWithSWR(<AdminPage />);

      expect(screen.getByText('Carregando...')).toBeInTheDocument();
    });

    it('should show login required when not authenticated', () => {
      mockUseAuth.mockReturnValue({
        session: null,
        loading: false,
      });

      renderWithSWR(<AdminPage />);

      expect(screen.getByRole('link', { name: /Login necessário/i })).toBeInTheDocument();
    });
  });

  describe('Authenticated state (admin)', () => {
    const mockSession = {
      access_token: 'admin-token-123',
    };

    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        session: mockSession,
        loading: false,
        isAdmin: true,
      });
    });

    it('should fetch users on mount', async () => {
      setupDefaultFetch();

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/admin/users'),
          expect.objectContaining({
            headers: { Authorization: 'Bearer admin-token-123' },
          })
        );
      });
    });

    it('should show page title', async () => {
      setupDefaultFetch();

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Admin - Usuários/i })).toBeInTheDocument();
      });
    });

    it('should show user count', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: [], total: 5 } });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText(/5 usuários/)).toBeInTheDocument();
      });
    });

    it('should use singular form for 1 user', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: [], total: 1 } });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText(/1 usuário$/)).toBeInTheDocument();
      });
    });

    it('should show back and new user buttons', async () => {
      setupDefaultFetch();

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('link', { name: /Voltar/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Novo usuário/i })).toBeInTheDocument();
      });
    });
  });

  describe('Non-admin access', () => {
    it('should show access restricted page for non-admin users', async () => {
      mockUseAuth.mockReturnValue({
        session: { access_token: 'regular-user-token' },
        loading: false,
        isAdmin: false,
      });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText(/Acesso Restrito/i)).toBeInTheDocument();
        expect(screen.getByText(/Esta página é exclusiva para administradores/i)).toBeInTheDocument();
      });
    });

    it('should show link to go back home', async () => {
      mockUseAuth.mockReturnValue({
        session: { access_token: 'regular-user-token' },
        loading: false,
        isAdmin: false,
      });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        const backLink = screen.getByRole('link', { name: /Voltar para início/i });
        expect(backLink).toBeInTheDocument();
        expect(backLink).toHaveAttribute('href', '/buscar');
      });
    });
  });

  describe('API 403 error handling', () => {
    it('should show error when API returns 403', async () => {
      mockUseAuth.mockReturnValue({
        session: { access_token: 'admin-token-123' },
        loading: false,
        isAdmin: true,
      });

      setupFetchWith403();

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText(/Acesso negado/i)).toBeInTheDocument();
      });
    });
  });

  describe('User list', () => {
    const mockSession = {
      access_token: 'admin-token-123',
    };

    const mockUsers = [
      {
        id: '1',
        email: 'user1@example.com',
        full_name: 'John Doe',
        company: 'Acme Inc',
        plan_type: 'monthly',
        created_at: '2024-01-15T10:00:00Z',
        user_subscriptions: [
          { id: 's1', plan_id: 'monthly', credits_remaining: null, expires_at: null, is_active: true },
        ],
      },
      {
        id: '2',
        email: 'user2@example.com',
        full_name: null,
        company: null,
        plan_type: 'free',
        created_at: '2024-01-20T10:00:00Z',
        user_subscriptions: [
          { id: 's2', plan_id: 'free', credits_remaining: 3, expires_at: null, is_active: true },
        ],
      },
    ];

    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        session: mockSession,
        loading: false,
        isAdmin: true,
      });
    });

    it('should display users in table', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 2 } });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('user1@example.com')).toBeInTheDocument();
        expect(screen.getByText('user2@example.com')).toBeInTheDocument();
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Acme Inc')).toBeInTheDocument();
      });
    });

    it('should show dash for missing name/company', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 2 } });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        const dashes = screen.getAllByText('-');
        expect(dashes.length).toBeGreaterThan(0);
      });
    });

    it('should show credits for pack plans', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 2 } });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });

    it('should show table headers', async () => {
      setupDefaultFetch();

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Email')).toBeInTheDocument();
        expect(screen.getByText('Nome')).toBeInTheDocument();
        expect(screen.getByText('Empresa')).toBeInTheDocument();
        expect(screen.getByText('Plano')).toBeInTheDocument();
        expect(screen.getByText('Créditos')).toBeInTheDocument();
        expect(screen.getByText('Criado')).toBeInTheDocument();
        expect(screen.getByText('Ações')).toBeInTheDocument();
      });
    });

    it('should show loading skeletons while fetching', async () => {
      mockFetch.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({
          ok: true,
          json: () => Promise.resolve({ users: [], total: 0 }),
        }), 100))
      );

      renderWithSWR(<AdminPage />);

      const skeletons = document.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Search functionality', () => {
    const mockSession = { access_token: 'admin-token-123' };

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ session: mockSession, loading: false, isAdmin: true });
    });

    it('should have search input', async () => {
      setupDefaultFetch();
      renderWithSWR(<AdminPage />);
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Buscar por email/i)).toBeInTheDocument();
      });
    });

    it('should trigger search on Enter key', async () => {
      setupDefaultFetch();
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Buscar por email/i)).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Buscar por email/i);
      await act(async () => {
        fireEvent.change(searchInput, { target: { value: 'test' } });
        fireEvent.keyDown(searchInput, { key: 'Enter' });
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('search=test'),
          expect.anything()
        );
      });
    });
  });

  describe('Create user form', () => {
    const mockSession = { access_token: 'admin-token-123' };

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ session: mockSession, loading: false, isAdmin: true });
    });

    it('should toggle create user form', async () => {
      setupDefaultFetch();
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Novo usuário/i })).toBeInTheDocument();
      });

      const newButton = screen.getByRole('button', { name: /Novo usuário/i });
      await act(async () => { fireEvent.click(newButton); });

      expect(screen.getByText('Criar usuário')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancelar/i })).toBeInTheDocument();
    });

    it('should show form fields', async () => {
      setupDefaultFetch();
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Novo usuário/i })).toBeInTheDocument();
      });

      const newButton = screen.getByRole('button', { name: /Novo usuário/i });
      await act(async () => { fireEvent.click(newButton); });

      expect(screen.getByText('Email *')).toBeInTheDocument();
      expect(screen.getByText('Senha *')).toBeInTheDocument();
      expect(screen.getAllByText('Nome').length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText('Empresa').length).toBeGreaterThanOrEqual(2);
      expect(screen.getAllByText('Plano').length).toBeGreaterThanOrEqual(2);
    });

    it('should submit create user form', async () => {
      setupDefaultFetch();
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Novo usuário/i })).toBeInTheDocument();
      });

      const newButton = screen.getByRole('button', { name: /Novo usuário/i });
      await act(async () => { fireEvent.click(newButton); });

      const emailInput = screen.getAllByRole('textbox')[0];
      const passwordInputs = document.querySelectorAll('input[type="password"]');
      await act(async () => {
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } });
        fireEvent.change(passwordInputs[0], { target: { value: 'password123' } });
      });

      const createButton = screen.getByRole('button', { name: /^Criar$/i });
      await act(async () => { fireEvent.click(createButton); });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/admin/users'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('new@example.com'),
          })
        );
      });
    });

    it('should show loading state during creation', async () => {
      setupDefaultFetch();
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Novo usuário/i })).toBeInTheDocument();
      });

      const newButton = screen.getByRole('button', { name: /Novo usuário/i });
      await act(async () => { fireEvent.click(newButton); });

      const emailInput = screen.getAllByRole('textbox')[0];
      const passwordInputs = document.querySelectorAll('input[type="password"]');
      await act(async () => {
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } });
        fireEvent.change(passwordInputs[0], { target: { value: 'password123' } });
      });

      // Override fetch to slow down the POST
      const origImpl = mockFetch.getMockImplementation();
      mockFetch.mockImplementation((url: string, opts?: RequestInit) => {
        if (opts?.method === 'POST' && url.includes('/admin/users')) {
          return new Promise((resolve) => setTimeout(() => resolve({
            ok: true, json: () => Promise.resolve({ id: 'new-user-123' }),
          }), 200));
        }
        return origImpl!(url, opts);
      });

      const createButton = screen.getByRole('button', { name: /^Criar$/i });
      await act(async () => { fireEvent.click(createButton); });

      expect(screen.getByRole('button', { name: /Criando.../i })).toBeInTheDocument();
    });
  });

  describe('Delete user', () => {
    const mockSession = { access_token: 'admin-token-123' };
    const mockUsers = [
      { id: '1', email: 'user@example.com', full_name: 'Test User', company: null, plan_type: 'free', created_at: '2024-01-15T10:00:00Z', user_subscriptions: [] },
    ];

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ session: mockSession, loading: false, isAdmin: true });
    });

    it('should show delete button for each user', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 1 } });
      renderWithSWR(<AdminPage />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Excluir/i })).toBeInTheDocument();
      });
    });

    it('should show confirmation before deleting', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 1 } });
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Excluir/i })).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button', { name: /Excluir/i });
      await act(async () => { fireEvent.click(deleteButton); });

      expect(mockConfirm).toHaveBeenCalledWith(expect.stringContaining('user@example.com'));
    });

    it('should call delete API when confirmed', async () => {
      mockConfirm.mockReturnValue(true);
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 1 } });
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Excluir/i })).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button', { name: /Excluir/i });
      await act(async () => { fireEvent.click(deleteButton); });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/admin/users/1'),
          expect.objectContaining({ method: 'DELETE' })
        );
      });
    });

    it('should not delete when cancelled', async () => {
      mockConfirm.mockReturnValue(false);
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 1 } });
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Excluir/i })).toBeInTheDocument();
      });

      const initialCallCount = mockFetch.mock.calls.length;
      const deleteButton = screen.getByRole('button', { name: /Excluir/i });
      await act(async () => { fireEvent.click(deleteButton); });

      // No additional fetch calls after cancel
      expect(mockFetch.mock.calls.length).toBe(initialCallCount);
    });
  });

  describe('Plan assignment', () => {
    const mockSession = { access_token: 'admin-token-123' };
    const mockUsers = [
      { id: '1', email: 'user@example.com', full_name: 'Test User', company: null, plan_type: 'free', created_at: '2024-01-15T10:00:00Z', user_subscriptions: [{ id: 's1', plan_id: 'free', credits_remaining: 3, expires_at: null, is_active: true }] },
    ];

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ session: mockSession, loading: false, isAdmin: true });
    });

    it('should show plan selector for each user', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 1 } });
      renderWithSWR(<AdminPage />);
      await waitFor(() => {
        const selects = screen.getAllByRole('combobox');
        expect(selects.length).toBeGreaterThan(0);
      });
    });

    it('should call assign plan API when plan changed', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: mockUsers, total: 1 } });
      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('user@example.com')).toBeInTheDocument();
      });

      const selects = screen.getAllByRole('combobox');
      const planSelect = selects.find(s => s.classList.contains('text-xs'));
      await act(async () => { fireEvent.change(planSelect!, { target: { value: 'maquina' } }); });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/admin/users/1/assign-plan?plan_id=maquina'),
          expect.objectContaining({ method: 'POST' })
        );
      });
    });
  });

  describe('Pagination', () => {
    const mockSession = { access_token: 'admin-token-123' };

    beforeEach(() => {
      mockUseAuth.mockReturnValue({ session: mockSession, loading: false, isAdmin: true });
    });

    it('should show pagination when multiple pages', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: [], total: 100 } });
      renderWithSWR(<AdminPage />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Anterior/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Próximo/i })).toBeInTheDocument();
      });
    });

    it('should not show pagination for single page', async () => {
      setupDefaultFetch({ '/api/admin/users': { users: [], total: 10 } });
      renderWithSWR(<AdminPage />);
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /Anterior/i })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Próximo/i })).not.toBeInTheDocument();
      });
    });
  });

  describe('Error handling', () => {
    const mockSession = { access_token: 'admin-token-123' };

    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        session: mockSession,
        loading: false,
        isAdmin: true,
      });
    });

    it('should show error message on fetch failure', async () => {
      setupFetchWithError();

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText(/Erro 500/i)).toBeInTheDocument();
      });
    });

    it('should show error on network failure', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/api/admin/users')) {
          return Promise.reject(new Error('Network error'));
        }
        for (const [key, value] of Object.entries(DEFAULT_RESPONSES)) {
          if (url.includes(key)) {
            return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(value) });
          }
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      });

      renderWithSWR(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });
});
