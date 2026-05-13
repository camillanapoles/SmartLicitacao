/**
 * ProductWalkthrough Component Tests
 *
 * Tests:
 * - Modal visibility (open/close)
 * - Step navigation (next, back, skip, complete)
 * - Step indicator and progress
 * - "Não mostrar novamente" checkbox persistence
 * - ESC and overlay click to dismiss
 * - aria-live announcement for step changes
 * - Keyboard navigation (ArrowLeft / ArrowRight)
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ProductWalkthrough } from "../ProductWalkthrough";

// Mock createPortal to render in the same DOM tree (simpler tests)
jest.mock("react-dom", () => ({
  ...jest.requireActual("react-dom"),
  createPortal: (node: React.ReactNode) => node,
}));

// Mock focus-trap-react — it can cause issues in jsdom
jest.mock("focus-trap-react", () => {
  return function MockFocusTrap({ children }: { children: React.ReactNode }) {
    return <div data-testid="focus-trap">{children}</div>;
  };
});

describe("ProductWalkthrough", () => {
  const mockOnClose = jest.fn();
  const mockOnComplete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    // Clear localStorage before each test
    localStorage.clear();
  });

  describe("Visibility", () => {
    it("should not render when isOpen is false", () => {
      render(
        <ProductWalkthrough
          isOpen={false}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.queryByTestId("walkthrough-overlay")).not.toBeInTheDocument();
    });

    it("should render the modal when isOpen is true", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByTestId("walkthrough-overlay")).toBeInTheDocument();
    });

    it("should show the first step by default", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByText("Passo 1 de 5")).toBeInTheDocument();
      expect(screen.getByText("Busca Inteligente")).toBeInTheDocument();
    });

    it("should have role='dialog' for accessibility", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeInTheDocument();
    });
  });

  describe("Step Navigation", () => {
    it("should advance to the next step when clicking Próximo", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      fireEvent.click(screen.getByTestId("walkthrough-next"));

      expect(screen.getByText("Passo 2 de 5")).toBeInTheDocument();
      expect(screen.getByText("Resultados da Busca")).toBeInTheDocument();
    });

    it("should hide Voltar on the first step", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.queryByTestId("walkthrough-back")).not.toBeInTheDocument();
    });

    it("should show Voltar after advancing past step 1", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      fireEvent.click(screen.getByTestId("walkthrough-next"));

      expect(screen.getByTestId("walkthrough-back")).toBeInTheDocument();
    });

    it("should go back to the previous step when clicking Voltar", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      // Go to step 2
      fireEvent.click(screen.getByTestId("walkthrough-next"));
      expect(screen.getByText("Passo 2 de 5")).toBeInTheDocument();

      // Go back to step 1
      fireEvent.click(screen.getByTestId("walkthrough-back"));
      expect(screen.getByText("Passo 1 de 5")).toBeInTheDocument();
    });

    it('should show "Concluir" on the last step', () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      // Navigate to step 5
      for (let i = 0; i < 4; i++) {
        fireEvent.click(screen.getByTestId("walkthrough-next"));
      }

      expect(screen.getByTestId("walkthrough-finish")).toBeInTheDocument();
      expect(screen.getByText("Concluir")).toBeInTheDocument();
    });

    it("should call onComplete when finishing the last step", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      // Navigate to step 5 and click Concluir
      for (let i = 0; i < 4; i++) {
        fireEvent.click(screen.getByTestId("walkthrough-next"));
      }
      fireEvent.click(screen.getByTestId("walkthrough-finish"));

      expect(mockOnComplete).toHaveBeenCalledTimes(1);
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it("should call onClose when clicking Pular", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      fireEvent.click(screen.getByTestId("walkthrough-skip"));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe("Dismiss behaviors", () => {
    it("should close when pressing ESC", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      fireEvent.keyDown(window, { key: "Escape" });

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it("should close when clicking the overlay backdrop", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      fireEvent.click(screen.getByTestId("walkthrough-overlay"));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it("should not close when clicking inside the dialog", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      // Click the dialog element (not the overlay)
      const dialog = screen.getByRole("dialog");
      fireEvent.click(dialog);

      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  describe("localStorage persistence", () => {
    it('should save to localStorage when "Não mostrar novamente" is checked and user dismisses', () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      // Check the checkbox
      fireEvent.click(screen.getByTestId("walkthrough-dont-show"));

      // Dismiss by clicking Pular
      fireEvent.click(screen.getByTestId("walkthrough-skip"));

      expect(localStorage.getItem("smartlic_walkthrough_completed")).toBe("true");
    });

    it("should NOT save to localStorage when checkbox is unchecked on dismiss", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      // Dismiss without checking the box
      fireEvent.click(screen.getByTestId("walkthrough-skip"));

      expect(localStorage.getItem("smartlic_walkthrough_completed")).toBeNull();
    });
  });

  describe("aria-live announcements", () => {
    it("should have an aria-live region for step announcements", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      const liveRegion = document.querySelector('[aria-live="polite"][aria-atomic="true"]');
      expect(liveRegion).toBeInTheDocument();
    });
  });

  describe("Keyboard navigation", () => {
    it("should advance to next step with ArrowRight", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      fireEvent.keyDown(window, { key: "ArrowRight" });

      expect(screen.getByText("Passo 2 de 5")).toBeInTheDocument();
    });

    it("should go to previous step with ArrowLeft", () => {
      render(
        <ProductWalkthrough
          isOpen={true}
          onClose={mockOnClose}
          onComplete={mockOnComplete}
        />
      );

      // Advance to step 2 first
      fireEvent.keyDown(window, { key: "ArrowRight" });
      expect(screen.getByText("Passo 2 de 5")).toBeInTheDocument();

      // Go back
      fireEvent.keyDown(window, { key: "ArrowLeft" });
      expect(screen.getByText("Passo 1 de 5")).toBeInTheDocument();
    });
  });
});
