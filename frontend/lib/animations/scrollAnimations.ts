'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * REPO-COMMS #1289 / WCAG 2.1: Detecta preferência de reduced motion do usuário.
 *
 * Usa window.matchMedia('(prefers-reduced-motion: reduce)') + listener para
 * detectar mudanças em tempo real. Retorna `true` quando o usuário prefere
 * animações reduzidas ou desabilitadas.
 *
 * @returns true se o usuário prefere reduced motion
 */
export function usePrefersReducedMotion(): boolean {
  const [prefersReduced, setPrefersReduced] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReduced(mediaQuery.matches);

    const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  return prefersReduced;
}

/**
 * STORY-174: useScrollAnimation hook
 *
 * Triggers animation when element enters viewport using Intersection Observer.
 *
 * Features:
 * - Fires once per element (disconnects after trigger)
 * - Configurable threshold (visibility percentage)
 * - Returns ref and isVisible state
 * - Optimized for performance (no layout thrashing)
 *
 * @param threshold - Percentage of element that must be visible (0-1)
 * @returns { ref, isVisible } - Ref to attach to element and visibility state
 *
 * @example
 * const { ref, isVisible } = useScrollAnimation(0.1);
 *
 * <motion.div
 *   ref={ref}
 *   initial="hidden"
 *   animate={isVisible ? 'visible' : 'hidden'}
 *   variants={fadeInUp}
 * >
 *   Content
 * </motion.div>
 */
export function useScrollAnimation(threshold = 0.1) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect(); // Trigger once, then disconnect
        }
      },
      { threshold }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [threshold]);

  return { ref, isVisible };
}

/**
 * useStaggeredScrollAnimation - For lists/grids with staggered entrance
 *
 * @param itemCount - Number of items in the list
 * @param threshold - Visibility threshold (0-1)
 * @param staggerDelay - Delay between each item (ms)
 * @returns { ref, visibleItems } - Ref and array of visible item indices
 *
 * @example
 * const { ref, visibleItems } = useStaggeredScrollAnimation(4, 0.1, 100);
 *
 * <div ref={ref}>
 *   {items.map((item, i) => (
 *     <motion.div
 *       key={i}
 *       initial="hidden"
 *       animate={visibleItems.includes(i) ? 'visible' : 'hidden'}
 *       variants={fadeInUp}
 *       transition={{ delay: i * 0.1 }}
 *     >
 *       {item}
 *     </motion.div>
 *   ))}
 * </div>
 */
export function useStaggeredScrollAnimation(
  itemCount: number,
  threshold = 0.1,
  staggerDelay = 100
) {
  const ref = useRef<HTMLDivElement>(null);
  const [visibleItems, setVisibleItems] = useState<number[]>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          // Trigger items sequentially with delay
          for (let i = 0; i < itemCount; i++) {
            setTimeout(() => {
              setVisibleItems((prev) => [...prev, i]);
            }, i * staggerDelay);
          }
          observer.disconnect();
        }
      },
      { threshold }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [itemCount, threshold, staggerDelay]);

  return { ref, visibleItems };
}

/**
 * useScrollProgress - Track scroll progress through viewport
 *
 * @returns progress - Scroll progress (0-1)
 *
 * @example
 * const progress = useScrollProgress();
 *
 * <motion.div
 *   style={{ scaleX: progress }}
 *   className="fixed top-0 left-0 h-1 bg-brand-blue"
 * />
 */
export function useScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const scrollProgress = scrollTop / docHeight;
      setProgress(scrollProgress);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return progress;
}

/**
 * REPO-COMMS #1289: Combina useScrollAnimation + usePrefersReducedMotion
 * para uso nos componentes da landing page B2G.
 *
 * Centraliza a lógica de: scroll trigger + acessibilidade (WCAG 2.1
 * prefers-reduced-motion). Elimina duplicação em 6+ componentes.
 *
 * @param threshold - Porcentagem visível para trigger (0-1, default 0.15)
 * @returns { ref, isVisible, shouldAnimate }
 */
export function useLandingAnimation(threshold = 0.15) {
  const { ref, isVisible } = useScrollAnimation(threshold);
  const prefersReducedMotion = usePrefersReducedMotion();

  return {
    ref,
    isVisible,
    /** true quando scroll trigger disparou E usuário NÃO prefere reduced motion */
    shouldAnimate: isVisible && !prefersReducedMotion,
  };
}
