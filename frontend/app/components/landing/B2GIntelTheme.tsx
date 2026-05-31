'use client';

import { useEffect } from 'react';

/**
 * REPO-COMMS #1289: Aplica data-theme="b2g-intel" ao document element
 * enquanto a landing page está montada. Remove ao desmontar.
 */
export default function B2GIntelTheme({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const el = document.documentElement;
    const prev = el.getAttribute('data-theme');
    el.setAttribute('data-theme', 'b2g-intel');

    return () => {
      if (prev) {
        el.setAttribute('data-theme', prev);
      } else {
        el.removeAttribute('data-theme');
      }
    };
  }, []);

  return <>{children}</>;
}
