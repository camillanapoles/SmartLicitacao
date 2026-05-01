'use client';

import Link from 'next/link';
import { useAnalytics } from '@/hooks/useAnalytics';

interface TrackingLinkProps {
  href: string;
  eventName: string;
  eventProps?: Record<string, unknown>;
  children: React.ReactNode;
  className?: string;
}

export default function TrackingLink({ href, eventName, eventProps, children, className }: TrackingLinkProps) {
  const { trackEvent } = useAnalytics();

  return (
    <Link
      href={href}
      className={className}
      onClick={() => trackEvent(eventName, eventProps ?? {})}
    >
      {children}
    </Link>
  );
}
