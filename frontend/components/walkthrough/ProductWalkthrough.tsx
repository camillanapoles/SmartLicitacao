"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import FocusTrap from "focus-trap-react";
import { X, ChevronLeft, ChevronRight } from "lucide-react";

import { WalkthroughStep } from "./WalkthroughStep";
import { WALKTHROUGH_STEPS } from "./mock-data";

const STORAGE_KEY = "smartlic_walkthrough_completed";

export interface ProductWalkthroughProps {
  /** Whether the walkthrough modal is visible. */
  isOpen: boolean;
  /** Called when the user dismisses the walkthrough (Pular, ESC, overlay click, etc.). */
  onClose: () => void;
  /** Called when the user completes all 5 steps. */
  onComplete?: () => void;
}

/**
 * ProductWalkthrough is a modal-based guided tour with 5 mock steps.
 *
 * Features:
 * - Step indicator ("Passo N de 5")
 * - Navigation: Voltar (hidden on step 1), Próximo, Pular, Concluir
 * - "Não mostrar novamente" checkbox (persisted to localStorage)
 * - Close via ESC or overlay click
 * - role="dialog", aria-live="polite", keyboard navigation, focus trap
 *
 * @param isOpen - Controls visibility
 * @param onClose - Callback when dismissed
 * @param onComplete - Callback when user completes all steps
 */
export function ProductWalkthrough({
  isOpen,
  onClose,
  onComplete,
}: ProductWalkthroughProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [dontShowAgain, setDontShowAgain] = useState(false);
  const [mounted, setMounted] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const stepAnnounceRef = useRef<HTMLDivElement>(null);

  const totalSteps = WALKTHROUGH_STEPS.length;
  const currentStep = WALKTHROUGH_STEPS[stepIndex];
  const isFirstStep = stepIndex === 0;
  const isLastStep = stepIndex === totalSteps - 1;

  useEffect(() => {
    setMounted(true);
  }, []);

  // Reset state when the walkthrough opens
  useEffect(() => {
    if (isOpen) {
      setStepIndex(0);
      setDontShowAgain(false);
    }
  }, [isOpen]);

  // Announce step changes to screen readers
  useEffect(() => {
    if (isOpen && stepAnnounceRef.current && currentStep) {
      stepAnnounceRef.current.textContent = `Passo ${stepIndex + 1} de ${totalSteps}: ${currentStep.title}`;
    }
  }, [isOpen, stepIndex, currentStep, totalSteps]);

  // ESC key handler
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleDismiss();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, dontShowAgain]);

  // Keyboard navigation (ArrowLeft / ArrowRight)
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        handleNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        handleBack();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, stepIndex]);

  // Body scroll lock
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [isOpen]);

  const persistDismiss = useCallback(() => {
    if (dontShowAgain && typeof window !== "undefined") {
      try {
        window.localStorage.setItem(STORAGE_KEY, "true");
      } catch {
        /* noop — quota / private mode */
      }
    }
  }, [dontShowAgain]);

  const handleDismiss = useCallback(() => {
    persistDismiss();
    onClose();
  }, [persistDismiss, onClose]);

  const handleComplete = useCallback(() => {
    persistDismiss();
    onComplete?.();
    onClose();
  }, [persistDismiss, onComplete, onClose]);

  const handleNext = useCallback(() => {
    if (isLastStep) {
      handleComplete();
    } else {
      setStepIndex((prev) => prev + 1);
    }
  }, [isLastStep, handleComplete]);

  const handleBack = useCallback(() => {
    if (!isFirstStep) {
      setStepIndex((prev) => prev - 1);
    }
  }, [isFirstStep]);

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === overlayRef.current) {
        handleDismiss();
      }
    },
    [handleDismiss]
  );

  // Do not render on the server
  if (!mounted || !isOpen || !currentStep) return null;

  const titleId = "walkthrough-title";
  const liveId = "walkthrough-live-region";

  return createPortal(
    <FocusTrap
      focusTrapOptions={{
        escapeDeactivates: false,
        clickOutsideDeactivates: false,
        allowOutsideClick: true,
        returnFocusOnDeactivate: true,
        fallbackFocus: `#${titleId}`,
        tabbableOptions: { displayCheck: "none" },
      }}
    >
      <div
        ref={overlayRef}
        onClick={handleOverlayClick}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto"
        data-testid="walkthrough-overlay"
      >
        <div
          id={titleId}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-live="polite"
          tabIndex={-1}
          className="relative w-full max-w-lg rounded-lg bg-white dark:bg-gray-900 shadow-xl"
        >
          {/* Screen reader live region for step announcements */}
          <div
            ref={stepAnnounceRef}
            id={liveId}
            aria-live="polite"
            aria-atomic="true"
            className="sr-only"
          />

          {/* Close button */}
          <button
            type="button"
            onClick={handleDismiss}
            aria-label="Fechar demonstração"
            className="absolute right-3 top-3 rounded-md p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>

          {/* Progress indicator */}
          <div className="px-6 pt-6 pb-2">
            <div className="flex items-center gap-2 mb-3">
              {Array.from({ length: totalSteps }).map((_, i) => (
                <div
                  key={i}
                  className={`h-1.5 flex-1 rounded-full transition-colors ${
                    i <= stepIndex
                      ? "bg-[var(--brand-blue)]"
                      : "bg-[var(--surface-1)]"
                  }`}
                />
              ))}
            </div>
            <span className="text-xs font-medium text-[var(--ink-secondary)]">
              Passo {stepIndex + 1} de {totalSteps}
            </span>
          </div>

          {/* Step content */}
          <div className="px-6 py-4 max-h-[55vh] overflow-y-auto">
            <WalkthroughStep title={currentStep.title}>
              {currentStep.renderContent()}
            </WalkthroughStep>
          </div>

          {/* Divider */}
          <hr className="mx-6 border-[var(--border)]" />

          {/* Navigation */}
          <div className="px-6 py-4 space-y-3">
            <div className="flex items-center justify-between">
              {/* Voltar — hidden on first step */}
              <div className="w-24">
                {!isFirstStep && (
                  <button
                    type="button"
                    onClick={handleBack}
                    className="inline-flex items-center gap-1 text-sm font-medium text-[var(--ink-secondary)] hover:text-[var(--ink)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2 rounded-md px-2 py-1"
                    data-testid="walkthrough-back"
                  >
                    <ChevronLeft className="w-4 h-4" aria-hidden="true" />
                    Voltar
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDismiss}
                  className="text-sm font-medium text-[var(--ink-secondary)] hover:text-[var(--ink)] transition-colors px-3 py-1.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
                  data-testid="walkthrough-skip"
                >
                  Pular
                </button>
                <button
                  type="button"
                  onClick={handleNext}
                  autoFocus
                  className="inline-flex items-center gap-1 rounded-button bg-[var(--brand-navy)] text-white px-4 py-2 text-sm font-medium hover:bg-[var(--brand-blue-hover)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
                  data-testid={isLastStep ? "walkthrough-finish" : "walkthrough-next"}
                >
                  {isLastStep ? "Concluir" : "Próximo"}
                  {!isLastStep && <ChevronRight className="w-4 h-4" aria-hidden="true" />}
                </button>
              </div>
            </div>

            {/* "Não mostrar novamente" checkbox */}
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={dontShowAgain}
                onChange={(e) => setDontShowAgain(e.target.checked)}
                className="w-4 h-4 rounded border-[var(--border)] text-[var(--brand-blue)] focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
                data-testid="walkthrough-dont-show"
              />
              <span className="text-xs text-[var(--ink-secondary)] group-hover:text-[var(--ink)] transition-colors">
                Não mostrar novamente
              </span>
            </label>
          </div>
        </div>
      </div>
    </FocusTrap>,
    document.body
  );
}
