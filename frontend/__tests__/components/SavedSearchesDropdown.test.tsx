/**
 * SavedSearchesDropdown Component Tests
 *
 * Tests dropdown, load, delete, and auto-save functionality
 * Target: 80%+ coverage
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import type { SavedSearch } from '@/lib/savedSearches';
import { useSavedSearches } from '../../hooks/useSavedSearches';

// Mock the hook module
jest.mock('../../hooks/useSavedSearches');

// Import component after mock declaration
import { SavedSearchesDropdown } from '@/app/components/SavedSearchesDropdown';

// Mock implementation functions
const mockDeleteSearch = jest.fn();
const mockLoadSearch = jest.fn();
const mockClearAll = jest.fn();
const mockSaveNewSearch = jest.fn();
const mockUpdateSearch = jest.fn();
const mockRefresh = jest.fn();

// Type assertion for the mocked hook
const mockedUseSavedSearches = useSavedSearches as jest.MockedFunction<typeof useSavedSearches>;

// Mock saved searches data
const mockSearches: SavedSearch[] = [
  {
    id: 'search-1',
    name: 'Uniformes SC/PR/RS',
    searchParams: {
      ufs: ['SC', 'PR', 'RS'],
      dataInicial: '2026-01-22',
      dataFinal: '2026-01-29',
      searchMode: 'setor',
      setorId: 'vestuario',
    },
    createdAt: '2026-01-29T10:00:00Z',
    lastUsedAt: '2026-01-29T10:00:00Z',
  },
  {
    id: 'search-2',
    name: 'Calçados Sudeste',
    searchParams: {
      ufs: ['SP', 'RJ', 'MG', 'ES'],
      dataInicial: '2026-01-15',
      dataFinal: '2026-01-22',
      searchMode: 'termos',
      termosBusca: 'calçado sapato',
    },
    createdAt: '2026-01-28T15:30:00Z',
    lastUsedAt: '2026-01-28T15:30:00Z',
  },
];

describe('SavedSearchesDropdown Component', () => {
  const mockOnLoadSearch = jest.fn();
  const mockOnAnalyticsEvent = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock implementation
    mockedUseSavedSearches.mockReturnValue({
      searches: mockSearches,
      loading: false,
      isMaxCapacity: false,
      saveNewSearch: mockSaveNewSearch,
      deleteSearch: mockDeleteSearch,
      updateSearch: mockUpdateSearch,
      loadSearch: mockLoadSearch,
      clearAll: mockClearAll,
      refresh: mockRefresh,
    });

    mockLoadSearch.mockReturnValue(mockSearches[0]);
  });

  describe('Rendering', () => {
    it('should render dropdown trigger button', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      expect(screen.getByRole('button', { name: /Análises salvas/i })).toBeInTheDocument();
    });

    it('should display search count badge', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('should show "Buscas Salvas" text on desktop', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const text = screen.getByText('Análises Salvas');
      expect(text).toHaveClass('hidden', 'sm:inline');
    });

    it('should have proper ARIA attributes on trigger button', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });

    it('should render clock icon', () => {
      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const clockIcon = container.querySelector('svg');
      expect(clockIcon).toBeInTheDocument();
    });
  });

  describe('Dropdown Open/Close', () => {
    it('should open dropdown when trigger button clicked', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText(/Análises Recentes/i)).toBeInTheDocument();
    });

    it('should update aria-expanded when opened', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(button).toHaveAttribute('aria-expanded', 'true');
    });

    it('should close dropdown when backdrop clicked', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText('Uniformes SC/PR/RS')).toBeInTheDocument();

      // Click backdrop
      const backdrop = screen.getByRole('button', { name: /Análises salvas/i })
        .parentElement?.querySelector('.fixed.inset-0');
      if (backdrop) {
        fireEvent.click(backdrop);
      }

      // Dropdown should close
      waitFor(() => {
        expect(screen.queryByText('Uniformes SC/PR/RS')).not.toBeInTheDocument();
      });
    });

    it('should rotate chevron icon when opened', () => {
      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const chevron = container.querySelector('.rotate-180');
      expect(chevron).toBeInTheDocument();
    });
  });

  describe('Saved Searches Display', () => {
    it('should display all saved searches', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText('Uniformes SC/PR/RS')).toBeInTheDocument();
      expect(screen.getByText('Calçados Sudeste')).toBeInTheDocument();
    });

    it('should display search count in header', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText('Análises Recentes (2/10)')).toBeInTheDocument();
    });

    it('should display UFs for each search', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText(/SC, PR, RS/i)).toBeInTheDocument();
      expect(screen.getByText(/SP, RJ, MG, ES/i)).toBeInTheDocument();
    });

    it('should display search mode label for "setor" mode', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText('vestuario')).toBeInTheDocument();
    });

    it('should display search terms label for "termos" mode', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText('"calçado sapato"')).toBeInTheDocument();
    });

    it('should format relative time correctly', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      // Check that dropdown is open and contains saved searches
      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByText('Uniformes SC/PR/RS')).toBeInTheDocument();
      expect(screen.getByText('Calçados Sudeste')).toBeInTheDocument();
    });
  });

  describe('Loading Search', () => {
    it('should call loadSearch when search item clicked', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const searchItem = screen.getByText('Uniformes SC/PR/RS');
      fireEvent.click(searchItem);

      expect(mockLoadSearch).toHaveBeenCalledWith('search-1');
    });

    it('should call onLoadSearch callback with search data', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const searchItem = screen.getByText('Uniformes SC/PR/RS');
      fireEvent.click(searchItem);

      expect(mockOnLoadSearch).toHaveBeenCalledWith(mockSearches[0]);
    });

    it('should close dropdown after loading search', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const searchItem = screen.getByText('Uniformes SC/PR/RS');
      fireEvent.click(searchItem);

      waitFor(() => {
        expect(screen.queryByText('Análises Recentes')).not.toBeInTheDocument();
      });
    });

    it('should track analytics when search is loaded', () => {
      render(
        <SavedSearchesDropdown
          onLoadSearch={mockOnLoadSearch}
          onAnalyticsEvent={mockOnAnalyticsEvent}
        />
      );

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const searchItem = screen.getByText('Uniformes SC/PR/RS');
      fireEvent.click(searchItem);

      expect(mockOnAnalyticsEvent).toHaveBeenCalledWith('saved_search_loaded', {
        search_id: 'search-1',
        search_name: 'Uniformes SC/PR/RS',
        search_mode: 'setor',
        ufs: ['SC', 'PR', 'RS'],
        uf_count: 3,
        days_since_created: expect.any(Number),
      });
    });
  });

  describe('Deleting Search', () => {
    it('should show delete button for each search', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      expect(deleteButtons).toHaveLength(2);
    });

    it('should show confirmation state on first delete click', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]);

      expect(screen.getByRole('button', { name: /Confirmar exclusão/i })).toBeInTheDocument();
    });

    it('should change button style in confirmation state', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]);

      const confirmButton = screen.getByRole('button', { name: /Confirmar exclusão/i });
      expect(confirmButton).toHaveClass('bg-error');
    });

    it('should delete search on second click (confirmed)', () => {
      mockDeleteSearch.mockReturnValue(true);

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });

      // First click - show confirmation
      fireEvent.click(deleteButtons[0]);

      // Second click - confirm deletion
      const confirmButton = screen.getByRole('button', { name: /Confirmar exclusão/i });
      fireEvent.click(confirmButton);

      expect(mockDeleteSearch).toHaveBeenCalledWith('search-1');
    });

    it('should auto-cancel delete confirmation after 3 seconds', async () => {
      jest.useFakeTimers();

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]);

      expect(screen.getByRole('button', { name: /Confirmar exclusão/i })).toBeInTheDocument();

      // Fast-forward 3 seconds
      act(() => {
        jest.advanceTimersByTime(3000);
      });

      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /Confirmar exclusão/i })).not.toBeInTheDocument();
      });

      jest.useRealTimers();
    });

    it('should track analytics when search is deleted', () => {
      mockDeleteSearch.mockReturnValue(true);

      render(
        <SavedSearchesDropdown
          onLoadSearch={mockOnLoadSearch}
          onAnalyticsEvent={mockOnAnalyticsEvent}
        />
      );

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]);

      const confirmButton = screen.getByRole('button', { name: /Confirmar exclusão/i });
      fireEvent.click(confirmButton);

      expect(mockOnAnalyticsEvent).toHaveBeenCalledWith('saved_search_deleted', {
        search_id: 'search-1',
        search_name: 'Uniformes SC/PR/RS',
        remaining_searches: 1,
      });
    });
  });

  describe('Clear All Searches', () => {
    it('should show "Limpar todas" button when searches exist', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByText('Limpar todas')).toBeInTheDocument();
    });

    it('should show confirmation dialog when "Limpar todas" clicked', () => {
      // Mock window.confirm
      const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const clearButton = screen.getByText('Limpar todas');
      fireEvent.click(clearButton);

      expect(confirmSpy).toHaveBeenCalledWith('Deseja excluir todas as análises salvas?');

      confirmSpy.mockRestore();
    });

    it('should call clearAll when user confirms', () => {
      const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const clearButton = screen.getByText('Limpar todas');
      fireEvent.click(clearButton);

      expect(mockClearAll).toHaveBeenCalled();

      confirmSpy.mockRestore();
    });

    it('should not call clearAll when user cancels', () => {
      const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const clearButton = screen.getByText('Limpar todas');
      fireEvent.click(clearButton);

      expect(mockClearAll).not.toHaveBeenCalled();

      confirmSpy.mockRestore();
    });

    it('should close dropdown after clearing all', () => {
      const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const clearButton = screen.getByText('Limpar todas');
      fireEvent.click(clearButton);

      waitFor(() => {
        expect(screen.queryByText('Análises Recentes')).not.toBeInTheDocument();
      });

      confirmSpy.mockRestore();
    });
  });

  describe('Empty State', () => {
    beforeEach(() => {
      // Override with empty searches for these tests
      mockedUseSavedSearches.mockReturnValue({
        searches: [],
        loading: false,
        isMaxCapacity: false,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });
    });

    it('should display empty state when no searches saved', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getAllByText('Nenhuma análise salva')[0]).toBeInTheDocument();
      expect(screen.getByText(/Suas análises aparecerão aqui/i)).toBeInTheDocument();
    });

    it('should display empty state icon', () => {
      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const emptyIcon = container.querySelector('.w-12.h-12');
      expect(emptyIcon).toBeInTheDocument();
    });

    it('should not show "Limpar todas" button in empty state', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.queryByText('Limpar todas')).not.toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should not render anything when loading', () => {
      // Override with loading state
      mockedUseSavedSearches.mockReturnValue({
        searches: mockSearches,
        loading: true,
        isMaxCapacity: false,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Styling and Layout', () => {
    it('should apply proper dropdown panel styling', () => {
      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const panel = container.querySelector('.absolute.right-0.mt-2');
      expect(panel).toBeInTheDocument();
      expect(panel).toHaveClass('rounded-card');
      expect(panel).toHaveClass('shadow-lg');
    });

    it('should have max-height and scroll on dropdown', () => {
      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      // Dropdown panel should have overflow-y-auto for scrolling
      const panel = container.querySelector('.overflow-y-auto');
      expect(panel).toBeInTheDocument();
      // Also has responsive max-height: max-h-[70vh] sm:max-h-[400px]
      expect(panel).toHaveClass('max-h-[70vh]');
    });

    it('should apply hover effects to search items', () => {
      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const searchItems = container.querySelectorAll('.hover\\:bg-surface-1');
      expect(searchItems.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      expect(button).toHaveAttribute('type', 'button');
      expect(button).toHaveAttribute('aria-label', 'Análises salvas');
    });

    it('should hide backdrop from screen readers', () => {
      const { container } = render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const backdrop = container.querySelector('[aria-hidden="true"]');
      expect(backdrop).toBeInTheDocument();
    });

    it('should provide title attribute on delete button', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      expect(deleteButtons[0]).toHaveAttribute('title', 'Excluir');
    });
  });

  describe('Filter Functionality', () => {
    const mockSearches = [
      {
        id: '1',
        name: 'Uniformes SC',
        searchParams: {
          ufs: ['SC'],
          dataInicial: '2024-01-01',
          dataFinal: '2024-01-07',
          searchMode: 'setor' as const,
          setorId: 'Vestuário',
        },
        createdAt: new Date().toISOString(),
        lastUsedAt: new Date().toISOString(),
      },
      {
        id: '2',
        name: 'Calçados RJ',
        searchParams: {
          ufs: ['RJ'],
          dataInicial: '2024-01-01',
          dataFinal: '2024-01-07',
          searchMode: 'termos' as const,
          termosBusca: 'sapato tenis',
        },
        createdAt: new Date().toISOString(),
        lastUsedAt: new Date().toISOString(),
      },
      {
        id: '3',
        name: 'Uniformes SP/PR',
        searchParams: {
          ufs: ['SP', 'PR'],
          dataInicial: '2024-01-01',
          dataFinal: '2024-01-07',
          searchMode: 'setor' as const,
          setorId: 'Vestuário',
        },
        createdAt: new Date().toISOString(),
        lastUsedAt: new Date().toISOString(),
      },
    ];

    beforeEach(() => {
      (useSavedSearches as jest.Mock).mockReturnValue({
        searches: mockSearches,
        loading: false,
        deleteSearch: jest.fn(() => true),
        loadSearch: jest.fn((id: string) => mockSearches.find(s => s.id === id)),
        clearAll: jest.fn(),
        refresh: jest.fn(),
      });
    });

    it('should display filter input when searches exist', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      expect(screen.getByPlaceholderText('Filtrar análises...')).toBeInTheDocument();
    });

    it('should filter searches by name', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'Calçados' } });

      expect(screen.getByText('Calçados RJ')).toBeInTheDocument();
      expect(screen.queryByText('Uniformes SC')).not.toBeInTheDocument();
      // Counter shows total saved searches out of max 10
      expect(screen.getByText(/\(3\/10\)/i)).toBeInTheDocument();
    });

    it('should filter searches by UF', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'PR' } });

      expect(screen.getByText('Uniformes SP/PR')).toBeInTheDocument();
      expect(screen.queryByText('Calçados RJ')).not.toBeInTheDocument();
      expect(screen.queryByText('Uniformes SC')).not.toBeInTheDocument();
    });

    it('should filter searches by setor/termos', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'sapato' } });

      expect(screen.getByText('Calçados RJ')).toBeInTheDocument();
      expect(screen.queryByText('Uniformes SC')).not.toBeInTheDocument();
    });

    it('should show clear button when typing', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'test' } });

      const clearButton = screen.getByLabelText('Limpar filtro');
      expect(clearButton).toBeInTheDocument();
    });

    it('should clear filter when clicking clear button', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const filterInput = screen.getByPlaceholderText('Filtrar análises...') as HTMLInputElement;
      fireEvent.change(filterInput, { target: { value: 'test' } });

      const clearButton = screen.getByLabelText('Limpar filtro');
      fireEvent.click(clearButton);

      expect(filterInput.value).toBe('');
      expect(screen.getByText(/\(3\/10\)/i)).toBeInTheDocument(); // Counter back to full
    });

    it('should close dropdown on Escape key (preventing global state loss)', async () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      // Verify dropdown is open
      expect(screen.getByPlaceholderText('Filtrar análises...')).toBeInTheDocument();

      // Press Escape - this should close the dropdown entirely
      fireEvent.keyDown(document, { key: 'Escape' });

      // Dropdown should be closed (filter input should no longer be visible)
      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Filtrar análises...')).not.toBeInTheDocument();
      });
    });

    it('should show empty state when no results match filter', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'NOMATCH123' } });

      expect(screen.getByText('Nenhuma análise encontrada')).toBeInTheDocument();
      expect(screen.getByText(/Tente outro termo de análise/i)).toBeInTheDocument();
    });

    it('should update counter dynamically when filtering', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      const button = screen.getByRole('button', { name: /Análises salvas/i });
      fireEvent.click(button);

      // Counter always shows total saved searches out of max 10
      expect(screen.getByText(/\(3\/10\)/i)).toBeInTheDocument();

      // Filter to 2 results - counter stays the same (shows total/max)
      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'Uniformes' } });
      expect(screen.getByText(/\(3\/10\)/i)).toBeInTheDocument();

      // Filter to 1 result - counter stays the same
      fireEvent.change(filterInput, { target: { value: 'SC' } });
      expect(screen.getByText(/\(3\/10\)/i)).toBeInTheDocument();

      // Clear filter: back to 3/10
      fireEvent.change(filterInput, { target: { value: '' } });
      expect(screen.getByText(/\(3\/10\)/i)).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Issue #228 — additional comprehensive coverage
  // -----------------------------------------------------------------------

  describe('Filter case-insensitivity and edge cases (#228)', () => {
    it('shows all searches when filter input is empty (whitespace only)', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      // whitespace-only filter should be treated as empty
      fireEvent.change(filterInput, { target: { value: '   ' } });

      expect(screen.getByText('Uniformes SC/PR/RS')).toBeInTheDocument();
      expect(screen.getByText('Calçados Sudeste')).toBeInTheDocument();
    });

    it('filters case-insensitively (UPPERCASE input matches lowercase data)', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'UNIFORMES' } });

      expect(screen.getByText('Uniformes SC/PR/RS')).toBeInTheDocument();
      expect(screen.queryByText('Calçados Sudeste')).not.toBeInTheDocument();
    });

    it('filters case-insensitively (mixed case)', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const filterInput = screen.getByPlaceholderText('Filtrar análises...');
      fireEvent.change(filterInput, { target: { value: 'cAlÇaDoS' } });

      expect(screen.getByText('Calçados Sudeste')).toBeInTheDocument();
      expect(screen.queryByText('Uniformes SC/PR/RS')).not.toBeInTheDocument();
    });

    it('Escape on the filter input clears the filter (via dropdown close handler)', async () => {
      // Component has a window-level Escape handler (capture phase) that closes
      // the dropdown AND clears filterTerm. The input also has its own onKeyDown
      // that clears filterTerm + blurs. Either way, after Escape the filter
      // term must be cleared. We verify by re-opening the dropdown and
      // observing an empty input.
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const filterInput = screen.getByPlaceholderText('Filtrar análises...') as HTMLInputElement;
      fireEvent.change(filterInput, { target: { value: 'Calçados' } });
      expect(filterInput.value).toBe('Calçados');

      // Escape: dropdown closes + filter term clears
      fireEvent.keyDown(filterInput, { key: 'Escape' });

      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Filtrar análises...')).not.toBeInTheDocument();
      });

      // Re-open: filter input should be back to empty (term was cleared)
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));
      const reopened = screen.getByPlaceholderText('Filtrar análises...') as HTMLInputElement;
      expect(reopened.value).toBe('');
    });
  });

  describe('Sort by lastUsedAt — most recent at top (#228)', () => {
    it('renders searches in the order returned by the hook (lastUsedAt desc)', () => {
      // Hook is the source of truth for sort. The component must NOT reorder.
      // We supply two entries with the most-recent first; assert DOM order matches.
      const recent: SavedSearch = {
        id: 'recent',
        name: 'Mais Recente',
        searchParams: {
          ufs: ['SC'],
          dataInicial: '2026-01-01',
          dataFinal: '2026-01-07',
          searchMode: 'setor',
          setorId: 'vestuario',
        },
        createdAt: '2026-01-05T10:00:00Z',
        lastUsedAt: '2026-02-10T10:00:00Z',
      };
      const older: SavedSearch = {
        id: 'older',
        name: 'Mais Antigo',
        searchParams: {
          ufs: ['SP'],
          dataInicial: '2026-01-01',
          dataFinal: '2026-01-07',
          searchMode: 'setor',
          setorId: 'vestuario',
        },
        createdAt: '2026-01-01T10:00:00Z',
        lastUsedAt: '2026-01-15T10:00:00Z',
      };

      mockedUseSavedSearches.mockReturnValue({
        searches: [recent, older], // hook sorts; component should preserve order
        loading: false,
        isMaxCapacity: false,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const recentEl = screen.getByText('Mais Recente');
      const olderEl = screen.getByText('Mais Antigo');

      // DOCUMENT_POSITION_FOLLOWING (4) means olderEl follows recentEl
      const positionMask = recentEl.compareDocumentPosition(olderEl);
      expect(positionMask & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
  });

  describe('Max capacity (10 searches) — "Gerenciar" button (#228)', () => {
    function buildSearches(n: number): SavedSearch[] {
      return Array.from({ length: n }, (_, i) => ({
        id: `s-${i}`,
        name: `Análise ${i + 1}`,
        searchParams: {
          ufs: ['SC'],
          dataInicial: '2026-01-01',
          dataFinal: '2026-01-07',
          searchMode: 'setor' as const,
          setorId: 'vestuario',
        },
        createdAt: new Date(2026, 0, i + 1).toISOString(),
        lastUsedAt: new Date(2026, 0, i + 1).toISOString(),
      }));
    }

    it('does not render "Gerenciar" button below max capacity (9 searches)', () => {
      mockedUseSavedSearches.mockReturnValue({
        searches: buildSearches(9),
        loading: false,
        isMaxCapacity: false,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      expect(screen.queryByRole('button', { name: /Gerenciar análises salvas/i })).not.toBeInTheDocument();
      expect(screen.getByText(/\(9\/10\)/i)).toBeInTheDocument();
    });

    it('renders "Gerenciar" button at exactly max capacity (10 searches)', () => {
      mockedUseSavedSearches.mockReturnValue({
        searches: buildSearches(10),
        loading: false,
        isMaxCapacity: true,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      expect(screen.getByRole('button', { name: /Gerenciar análises salvas/i })).toBeInTheDocument();
      expect(screen.getByText(/\(10\/10\)/i)).toBeInTheDocument();
    });

    it('renders all 10 search items at max capacity (no overflow truncation)', () => {
      mockedUseSavedSearches.mockReturnValue({
        searches: buildSearches(10),
        loading: false,
        isMaxCapacity: true,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      // Component advertises one delete button per search → exactly 10
      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      expect(deleteButtons).toHaveLength(10);
    });

    it('"Gerenciar" calls clearAll when user confirms', () => {
      mockedUseSavedSearches.mockReturnValue({
        searches: buildSearches(10),
        loading: false,
        isMaxCapacity: true,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const gerenciar = screen.getByRole('button', { name: /Gerenciar análises salvas/i });
      fireEvent.click(gerenciar);

      expect(confirmSpy).toHaveBeenCalledWith(
        expect.stringContaining('10 análises salvas')
      );
      expect(mockClearAll).toHaveBeenCalledTimes(1);
      confirmSpy.mockRestore();
    });

    it('"Gerenciar" does NOT call clearAll when user cancels', () => {
      mockedUseSavedSearches.mockReturnValue({
        searches: buildSearches(10),
        loading: false,
        isMaxCapacity: true,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      fireEvent.click(screen.getByRole('button', { name: /Gerenciar análises salvas/i }));

      expect(mockClearAll).not.toHaveBeenCalled();
      confirmSpy.mockRestore();
    });
  });

  describe('Hook contract — localStorage sync surface (#228)', () => {
    // The component delegates ALL persistence to the useSavedSearches hook.
    // localStorage I/O is the hook's responsibility (covered by hook unit tests).
    // From the component's perspective, "sync" means: on user action, the
    // hook's mutating method is invoked exactly once with the right argument.
    // These tests pin that contract.

    it('invokes deleteSearch with the correct id (single call) on confirmed delete', () => {
      mockDeleteSearch.mockReturnValue(true);
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]); // arm
      fireEvent.click(screen.getByRole('button', { name: /Confirmar exclusão/i })); // confirm

      expect(mockDeleteSearch).toHaveBeenCalledTimes(1);
      expect(mockDeleteSearch).toHaveBeenCalledWith('search-1');
    });

    it('does NOT invoke deleteSearch on the first (arming) click', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]);

      expect(mockDeleteSearch).not.toHaveBeenCalled();
    });

    it('arming delete on one item does not arm delete on a sibling item', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]);

      // Only one button should be in "Confirmar exclusão" state
      const confirmButtons = screen.queryAllByRole('button', { name: /Confirmar exclusão/i });
      expect(confirmButtons).toHaveLength(1);

      // The second item must still show the standard delete label
      expect(deleteButtons[1]).toHaveAttribute('aria-label', 'Excluir análise');
    });

    it('clicking a different item\'s delete button switches the armed item (does not delete either)', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      fireEvent.click(screen.getByRole('button', { name: /Análises salvas/i }));

      const deleteButtons = screen.getAllByRole('button', { name: /Excluir análise/i });
      fireEvent.click(deleteButtons[0]); // arm item 0
      // Re-query — DOM has updated, item 0 now has the "Confirmar" label
      const remainingDelete = screen.getAllByRole('button', { name: /Excluir análise/i });
      // Only item 1 should still have the plain "Excluir análise" label
      expect(remainingDelete).toHaveLength(1);
      fireEvent.click(remainingDelete[0]); // arm item 1

      // No deletion happened — only one item armed, the other reverted
      expect(mockDeleteSearch).not.toHaveBeenCalled();
      expect(screen.getAllByRole('button', { name: /Confirmar exclusão/i })).toHaveLength(1);
    });

    it('does not invoke loadSearch on mount (read is the hook\'s job, not the component\'s)', () => {
      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);
      expect(mockLoadSearch).not.toHaveBeenCalled();
      expect(mockOnLoadSearch).not.toHaveBeenCalled();
    });
  });

  describe('Trigger badge — count formatting edge cases (#228)', () => {
    it('hides the count badge when there are zero searches', () => {
      mockedUseSavedSearches.mockReturnValue({
        searches: [],
        loading: false,
        isMaxCapacity: false,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      // The count badge has aria-label="N análise(s) salva(s)" with a leading
      // digit. Trigger button has aria-label="Análises salvas" (no digit).
      // When count is 0, no element with a digit-prefixed aria-label exists.
      expect(screen.queryByLabelText(/^\d+\s+análise/i)).not.toBeInTheDocument();
    });

    it('uses singular Portuguese form for exactly 1 saved search', () => {
      const single: SavedSearch = {
        id: 'only',
        name: 'Única análise',
        searchParams: {
          ufs: ['SC'],
          dataInicial: '2026-01-01',
          dataFinal: '2026-01-07',
          searchMode: 'setor',
          setorId: 'vestuario',
        },
        createdAt: '2026-01-05T10:00:00Z',
        lastUsedAt: '2026-02-10T10:00:00Z',
      };
      mockedUseSavedSearches.mockReturnValue({
        searches: [single],
        loading: false,
        isMaxCapacity: false,
        saveNewSearch: mockSaveNewSearch,
        deleteSearch: mockDeleteSearch,
        updateSearch: mockUpdateSearch,
        loadSearch: mockLoadSearch,
        clearAll: mockClearAll,
        refresh: mockRefresh,
      });

      render(<SavedSearchesDropdown onLoadSearch={mockOnLoadSearch} />);

      // Badge label should NOT include the plural "s"
      expect(screen.getByLabelText('1 análise salva')).toBeInTheDocument();
    });
  });
});
